"""KnowledgeGuardAgent — 知识入库审核官（防幻觉体系的"源头防线"）。

赛题依据：A3 非功能性需求 3 ——"系统需具备完善的『防幻觉』与内容安全过滤机制，
确保生成的学术内容无事实性错误、无敏感违规信息"。

本系统的防幻觉是**双 Agent 协同防线**（多智能体架构的一部分）：

    ┌────────────────────────────────────────────────────────┐
    │ 入库时  KnowledgeGuardAgent（本文件）                     │
    │   教师上传文档 → 内容安全扫描 + 注入攻击检测 + 质量审查     │
    │   → 不合规文档拒绝入库，从数据源头阻断幻觉与违规内容        │
    ├────────────────────────────────────────────────────────┤
    │ 生成时  COVVerifierAgent（cov_verifier.py，已有）         │
    │   LLM 输出 → 声称抽取 → 逐条对照 RAG 知识库验证 → 重写标注 │
    └────────────────────────────────────────────────────────┘

设计原则（与 SafeDeclineAgent 一致）：
* 规则判定不调 LLM —— 安全扫描/质量审查是机械规则，必须离线可用、毫秒级返回
* LLM 深度审查是 best-effort 增强 —— 凭据未配置或调用失败时静默降级，
  不阻塞教师上传流程
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from backend.app.agents.base import AgentContext, AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内容安全规则
# ---------------------------------------------------------------------------
# 硬拒绝敏感词（与 safe_decline_agent 的词表同源，入库侧从严）
_HARD_KEYWORDS = [
    "邪教", "法轮", "颠覆国家", "颠覆政权", "分裂国家",
    "色情", "裸聊", "约炮", "嫖娼",
    "自残", "自杀教程", "怎么自杀",
    "毒品", "冰毒", "海洛因", "制毒",
    "枪支买卖", "炸药配方", "爆炸物制作",
]

# 提示词注入模式 —— 上传文档会进入 RAG 上下文喂给 LLM，
# 必须拦截"藏在课件里的越权指令"（indirect prompt injection）
_INJECTION_PATTERNS = [
    r"忽略(之前|上面|以上|前面)的?(所有)?(指令|提示|设定|规则)",
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
    r"you\s+are\s+now\s+(dan|jailbroken|unrestricted)",
    r"(system|assistant)\s*prompt\s*[:：]",
    r"<\s*/?\s*system\s*>",
    r"扮演.{0,12}(不受限制|没有限制|无限制)的",
    r"disregard\s+(your|the)\s+(rules|guidelines|instructions)",
]

# 质量规则 —— 与 knowledge/course_loader.py 的 QUALITY_RULES 对齐
_MIN_CONTENT_CHARS = 80
_ACADEMIC_HINTS = ["定义", "概念", "原理", "公式", "代码", "示例", "例", "章", "##", "```"]


class KnowledgeGuardAgent(BaseAgent):
    """知识入库审核官 — 教师上传文档的安全/质量守门 Agent。

    verdict 判决：
        passed   — 安全扫描与质量审查全部通过，可直接入库
        warning  — 可入库，但存在质量瑕疵（内容偏短/缺乏学术结构），报告给教师
        rejected — 命中敏感违规内容或注入攻击模式，拒绝入库
    """

    name = "knowledge_guard"
    description = (
        "知识入库审核官 — 对教师上传的知识库文档执行内容安全扫描、"
        "提示词注入检测与学术质量审查，从数据源头阻断幻觉与违规内容"
    )
    prompt_version = "v1"

    @property
    def system_prompt(self) -> str:
        return (
            "你是高校课程知识库的内容审核专家。请审查一份即将进入教学知识库的文档，"
            "只关注两点：1) 是否含有事实性错误（概念定义错误、年份/数字错误、张冠李戴）；"
            "2) 是否含有不适合出现在高校教学材料中的内容。"
            "用简体中文输出不超过5条审查意见，每条一行，格式：[类别] 意见。"
            "如果没有问题，只输出：无明显问题。"
        )

    # ------------------------------------------------------------------
    # 核心：文档审核（同步纯规则，供 ingest 流水线直接调用）
    # ------------------------------------------------------------------
    def audit_document(
        self,
        text: str,
        filename: str = "",
        course: str = "",
    ) -> Dict[str, Any]:
        """规则审核（不调 LLM）。返回结构化审核报告。"""
        content = str(text or "")
        issues: List[Dict[str, str]] = []

        safety_hits = self._scan_safety(content)
        for hit in safety_hits:
            issues.append({"level": "error", "category": "content_safety", "detail": hit})

        injection_hits = self._scan_injection(content)
        for hit in injection_hits:
            issues.append({"level": "error", "category": "prompt_injection", "detail": hit})

        quality_issues = self._check_quality(content)
        issues.extend(quality_issues)

        if safety_hits or injection_hits:
            verdict = "rejected"
        elif any(i["level"] == "warning" for i in issues):
            verdict = "warning"
        else:
            verdict = "passed"

        report = {
            "agent": self.name,
            "verdict": verdict,
            "filename": filename,
            "course": course,
            "issues": issues,
            "stats": {
                "chars": len(content),
                "lines": content.count("\n") + 1 if content else 0,
                "headings": len(re.findall(r"^#{1,4}\s", content, flags=re.M)),
                "code_blocks": content.count("```") // 2,
            },
        }
        logger.info(
            "[knowledge-guard] %s course=%s verdict=%s issues=%d",
            filename, course, verdict, len(issues),
        )
        return report

    async def audit_with_llm(
        self,
        text: str,
        filename: str = "",
        course: str = "",
        max_chars: int = 6000,
    ) -> Dict[str, Any]:
        """规则审核 + LLM 深度审查（best-effort，失败静默降级为纯规则）。"""
        report = self.audit_document(text, filename=filename, course=course)
        if report["verdict"] == "rejected":
            return report  # 已拒绝，不浪费 LLM 调用

        try:
            excerpt = str(text or "")[:max_chars]
            review = await self._acall_llm(
                f"文档名：{filename}\n所属课程：{course}\n\n文档内容（节选）：\n{excerpt}",
                temperature=0.2,
            )
            review = str(review or "").strip()
            if review and "无明显问题" not in review:
                for line in review.splitlines():
                    line = line.strip("· -").strip()
                    if line:
                        report["issues"].append(
                            {"level": "warning", "category": "llm_review", "detail": line[:200]}
                        )
                if report["verdict"] == "passed":
                    report["verdict"] = "warning"
            report["llm_review"] = "done"
        except Exception as exc:  # noqa: BLE001 — LLM 不可用时降级为纯规则审核
            logger.info("[knowledge-guard] LLM 深度审查跳过: %s", exc)
            report["llm_review"] = "skipped"
        return report

    # ------------------------------------------------------------------
    # BaseAgent 接口 — 供 Orchestrator / 单 Agent 对话调用
    # ------------------------------------------------------------------
    async def execute(self, context: AgentContext) -> AgentResponse:
        report = await self.audit_with_llm(
            context.user_input,
            filename=str(context.extra.get("filename", "")),
            course=context.course_name,
        )
        verdict_label = {"passed": "✅ 通过", "warning": "⚠️ 通过（有提醒）", "rejected": "❌ 拒绝入库"}
        lines = [f"**审核判决：{verdict_label.get(report['verdict'], report['verdict'])}**", ""]
        if report["issues"]:
            lines.append("| 级别 | 类别 | 说明 |")
            lines.append("| --- | --- | --- |")
            for issue in report["issues"][:10]:
                lines.append(
                    f"| {issue['level']} | {issue['category']} | {issue['detail']} |"
                )
        else:
            lines.append("未发现安全或质量问题。")
        return self._success("\n".join(lines), content_type="markdown", metadata=report)

    # ------------------------------------------------------------------
    # 规则实现
    # ------------------------------------------------------------------
    def _scan_safety(self, content: str) -> List[str]:
        hits = []
        for keyword in _HARD_KEYWORDS:
            if keyword in content:
                hits.append(f"命中敏感词「{keyword}」")
        return hits

    def _scan_injection(self, content: str) -> List[str]:
        hits = []
        for pattern in _INJECTION_PATTERNS:
            match = re.search(pattern, content, flags=re.I)
            if match:
                hits.append(f"疑似提示词注入片段「{match.group(0)[:40]}」")
        return hits

    def _check_quality(self, content: str) -> List[Dict[str, str]]:
        issues: List[Dict[str, str]] = []
        stripped = content.strip()
        if len(stripped) < _MIN_CONTENT_CHARS:
            issues.append({
                "level": "warning",
                "category": "quality",
                "detail": f"内容过短（{len(stripped)} 字符 < {_MIN_CONTENT_CHARS}），检索价值有限",
            })
        elif not any(hint in content for hint in _ACADEMIC_HINTS):
            issues.append({
                "level": "warning",
                "category": "quality",
                "detail": "未检测到学术结构要素（标题/定义/公式/代码示例），建议补充章节结构",
            })
        return issues


_guard: KnowledgeGuardAgent | None = None


def get_knowledge_guard() -> KnowledgeGuardAgent:
    global _guard
    if _guard is None:
        _guard = KnowledgeGuardAgent()
    return _guard
