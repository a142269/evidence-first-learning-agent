"""
Critic Agent — 4 维内容审查器（Phase 1 重构版 v3）

设计:
- Strategy Pattern: 每个审查维度是独立的 CriticDimension 子类
- 4 维: factual(事实支撑度) / pedagogy(教学有效性) / bloom(认知层级) / citation(引用充分性)
- Phase 1: 纯规则引擎，毫秒级响应（Phase 2 加 LLM 深度审查通道）

核心改进 (v3):
- FactualDimension 现在真正检查内容与 RAG 知识库的事实吻合度
- 辩论日志通过 DebateRepository 持久化到 SQLite
- 各维度阈值可通过类属性覆盖

学术依据:
- Bloom Taxonomy: Anderson & Krathwohl 2001
- Multi-Agent Debate: Du et al. NeurIPS 2023
- CIDDP 5维评估: EduPlanner IEEE TLT 2025
"""
from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse

logger = logging.getLogger(__name__)

# ================================================================
# 数据模型
# ================================================================
@dataclass
class CriticIssue:
    """审查发现的具体问题"""
    severity: str                         # "blocker" | "major" | "minor" | "info"
    description: str
    location: str = ""
    suggestion: Optional[str] = None


@dataclass
class CriticVerdict:
    """单个维度的审查结论"""
    dimension: str
    passed: bool
    score: float
    issues: List[CriticIssue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)  # 评分依据（可解释性）

    def to_summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.dimension}: "
            f"score={self.score:.0%} "
            f"issues={len(self.issues)} "
            f"tips={len(self.suggestions)}"
        )


# ================================================================
# 抽象维度基类
# ================================================================
class CriticDimension(ABC):
    """审查维度抽象基类 — strategy pattern"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def evaluate(self, content: str, context: dict) -> CriticVerdict:
        ...

    @property
    def pass_threshold(self) -> float:
        return 0.6

    def _empty_verdict(self, reason: str = "内容为空") -> CriticVerdict:
        return CriticVerdict(
            dimension=self.name,
            passed=False,
            score=0.0,
            issues=[CriticIssue(severity="blocker", description=reason)],
            suggestions=["请提供有效的学习内容"],
        )


# ================================================================
# 维度 1: Factual — 事实支撑度
# ================================================================
class FactualDimension(CriticDimension):
    """检查内容是否有知识库支撑 + 结构完整性

    两层检查:
    1. 结构层 (always on): 长度/词汇多样性/重复率/标题/段落
    2. 事实层 (有 RAG 时): 内容术语与 RAG 知识库的覆盖度
       - 抽取内容核心术语 → 计算与 RAG 文档的 Jaccard 重叠度
       - 重叠度 < 阈值 → 可能含有无来源的声明 → 警告

    Phase 2 计划: 接入 LLM 做 claim-level 逐条验证 (Chain-of-Verification)
    """

    name: str = "factual"
    MIN_CONTENT_LENGTH: int = 80
    MIN_UNIQUE_WORDS: int = 8
    MAX_REPEAT_RATIO: float = 0.6
    MIN_RAG_OVERLAP: float = 0.15            # 至少 15% 术语在 RAG 中出现过

    def evaluate(self, content: str, context: dict) -> CriticVerdict:
        if not content or not content.strip():
            return self._empty_verdict()

        stripped = content.strip()
        issues: List[CriticIssue] = []
        suggestions: List[str] = []
        evidence: Dict[str, Any] = {}

        # ================================================================
        # 层 1: 结构完整性
        # ================================================================
        meaningful = re.sub(r'[\s`#*\-\[\]()>]+', '', stripped)

        if len(meaningful) < self.MIN_CONTENT_LENGTH:
            issues.append(CriticIssue(
                severity="major",
                description=f"有效内容过短({len(meaningful)}字符, 最少{self.MIN_CONTENT_LENGTH})",
                suggestion="请补充更多实质性内容",
            ))

        words = re.findall(r'\w+', stripped.lower())
        unique_words = set(w for w in words if len(w) > 1)
        if len(unique_words) < self.MIN_UNIQUE_WORDS:
            # 长内容却词汇量极低 → 疑似 spam / 重复填充 (如 "ABC "*200)
            # 视为 blocker 直接否决; 短内容词汇少是正常的, 维持 major
            is_spam = len(meaningful) >= self.MIN_CONTENT_LENGTH
            issues.append(CriticIssue(
                severity="blocker" if is_spam else "major",
                description=f"词汇量不足({len(unique_words)}个不重复词, 最少{self.MIN_UNIQUE_WORDS})",
                suggestion="请使用更多专业术语和多样化的表达",
            ))

        if len(meaningful) > 20:
            char_counts: Dict[str, int] = {}
            for c in meaningful:
                char_counts[c] = char_counts.get(c, 0) + 1
            most_common_ratio = max(char_counts.values()) / len(meaningful)
            if most_common_ratio > self.MAX_REPEAT_RATIO:
                issues.append(CriticIssue(
                    severity="blocker",
                    description=f"字符重复率过高({most_common_ratio:.0%}), 疑似垃圾文本",
                    suggestion="请撰写有意义的教学内容",
                ))

        has_heading = bool(re.search(r'^#{1,6}\s', stripped, re.MULTILINE))
        has_paragraph = bool(re.search(r'\n\n', stripped))

        evidence["has_heading"] = has_heading
        evidence["has_paragraph"] = has_paragraph
        evidence["char_count"] = len(meaningful)
        evidence["unique_words"] = len(unique_words)

        # ================================================================
        # 层 2: RAG 事实支撑度（真正的事实检查）
        # ================================================================
        rag_texts: List[dict] = context.get("rag_results", [])
        if rag_texts:
            # 抽取内容的中文+英文术语
            content_terms = set(
                t.lower() for t in
                re.findall(r'[一-鿿]{2,}|[A-Za-z]{3,}', stripped)
            )
            # 聚合 RAG 文档术语
            rag_terms: set[str] = set()
            total_rag_chars = 0
            for r in rag_texts:
                rc = r.get("content", "")
                total_rag_chars += len(rc)
                rag_terms.update(
                    t.lower() for t in
                    re.findall(r'[一-鿿]{2,}|[A-Za-z]{3,}', rc)
                )

            if content_terms and rag_terms:
                overlap = content_terms & rag_terms
                overlap_ratio = len(overlap) / len(content_terms)
                evidence["rag_overlap_ratio"] = round(overlap_ratio, 2)
                evidence["content_terms_count"] = len(content_terms)
                evidence["rag_terms_count"] = len(rag_terms)
                evidence["overlap_terms"] = sorted(overlap)[:10]

                if overlap_ratio < self.MIN_RAG_OVERLAP:
                    issues.append(CriticIssue(
                        severity="major",
                        description=(
                            f"内容与知识库的事实重叠度低 "
                            f"({len(overlap)}/{len(content_terms)} = {overlap_ratio:.0%}"
                            f", 阈值 {self.MIN_RAG_OVERLAP:.0%})"
                        ),
                        suggestion=(
                            "生成内容可能含有知识库未覆盖的声明，"
                            "请参考 RAG 检索结果并标注信息来源"
                        ),
                    ))
                    suggestions.append("请基于 RAG 检索结果核实关键事实")
            else:
                evidence["rag_overlap_ratio"] = 0.0
        else:
            # 无 RAG 结果时不扣分（不是内容的问题）
            evidence["rag_overlap_ratio"] = None
            evidence["note"] = "无 RAG 上下文可用，跳过了事实支撑检查"

        # ================================================================
        # 综合评分
        # ================================================================
        score_deductions = 0.0
        if not has_heading:
            score_deductions += 0.1
        if not has_paragraph:
            score_deductions += 0.1

        score = max(0.0, 1.0 - score_deductions - len(issues) * 0.05)
        passed = score >= self.pass_threshold and not any(
            i.severity == "blocker" for i in issues
        )

        return CriticVerdict(
            dimension=self.name,
            passed=passed,
            score=round(score, 2),
            issues=issues,
            suggestions=suggestions,
            evidence=evidence,
        )


# ================================================================
# 维度 2: Pedagogy — 教学有效性
# ================================================================
class PedagogyDimension(CriticDimension):
    """检查教学有效性: 例子/类比/步骤拆解/巩固练习

    规则依据: 教育心理学中的"示例学习"(Sweller 1988) +
    "结构化教学"(Rosenshine 2012)
    """

    name: str = "pedagogy"
    EXAMPLE_PATTERNS: List[str] = ["例如", "比如", "举个例子", "example", "e.g.", "实例", "具体来说"]
    ANALOGY_PATTERNS: List[str] = ["就像", "好比", "类比", "类似", "可以理解为", "相当于"]
    STEP_PATTERNS: List[str] = ["首先", "然后", "接着", "最后", "第一步", "第二步", "step"]
    PRACTICE_PATTERNS: List[str] = ["练习", "巩固", "回顾", "习题", "测试", "practice", "动手"]

    def evaluate(self, content: str, context: dict) -> CriticVerdict:
        if not content or not content.strip():
            return self._empty_verdict()

        stripped = content.strip()
        issues: List[CriticIssue] = []
        suggestions: List[str] = []
        evidence: Dict[str, Any] = {}

        has_examples = any(p in stripped for p in self.EXAMPLE_PATTERNS)
        has_analogy = any(p in stripped for p in self.ANALOGY_PATTERNS)
        has_steps = any(p in stripped for p in self.STEP_PATTERNS)
        has_practice = any(p in stripped for p in self.PRACTICE_PATTERNS)

        evidence = {
            "has_examples": has_examples,
            "has_analogy": has_analogy,
            "has_steps": has_steps,
            "has_practice": has_practice,
        }

        score = 1.0

        if not has_examples:
            score -= 0.25
            suggestions.append("建议添加 2-3 个具体例子帮助理解")
            issues.append(CriticIssue(
                severity="major",
                description="缺少具体例子, 教学效果打折扣",
                suggestion="在每个核心概念后加一个生活化/技术化的实例",
            ))

        if not has_analogy:
            score -= 0.15
            suggestions.append("建议使用类比降低理解门槛")

        if not has_steps:
            score -= 0.1
            issues.append(CriticIssue(
                severity="minor",
                description="缺少步骤拆解, 建议用'首先→然后→最后'结构",
            ))

        if not has_practice:
            score -= 0.1
            suggestions.append("末尾添加练习题或巩固建议")

        score = round(max(0.0, score), 2)
        passed = score >= self.pass_threshold

        return CriticVerdict(
            dimension=self.name,
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            evidence=evidence,
        )


# ================================================================
# 维度 3: Bloom — 认知层级匹配
# ================================================================
class BloomDimension(CriticDimension):
    """检查内容是否达到目标 Bloom 认知层级 (Anderson & Krathwohl 2001)

    方案: 关键词匹配做启发式快速分级。
    局限: 无法真正理解语义（"使用 Python 实现 CNN" 和 "我使用过 Python"
    都会被归类为 apply）。Phase 2 加 LLM 做语义层级判别。
    """

    name: str = "bloom"
    LEVEL_KEYWORDS: Dict[str, List[str]] = {
        "remember":  ["定义", "列出", "描述", "define", "list", "describe", "是什么"],
        "understand": ["解释", "总结", "分类", "explain", "summarize", "理解为", "为什么"],
        "apply":     ["使用", "实现", "应用", "练习", "代码", "apply", "implement", "编写", "训练"],
        "analyze":   ["分析", "比较", "对比", "区别", "analyze", "compare", "为什么更好"],
        "evaluate":  ["评估", "判断", "优缺点", "evaluate", "pros and cons", "选择理由"],
        "create":    ["设计", "构建", "创新", "综合", "design", "create", "build", "项目"],
    }
    LEVEL_ORDER: List[str] = ["remember", "understand", "apply", "analyze", "evaluate", "create"]

    def evaluate(self, content: str, context: dict) -> CriticVerdict:
        if not content or not content.strip():
            return self._empty_verdict()

        target_bloom: str = context.get("target_bloom", "understand")
        stripped = content.strip()
        issues: List[CriticIssue] = []
        suggestions: List[str] = []

        # 检测最高命中层级
        level_hits: Dict[str, int] = {}
        for level, keywords in self.LEVEL_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in stripped)
            level_hits[level] = hits

        detected_level = "remember"
        for level in reversed(self.LEVEL_ORDER):
            if level_hits.get(level, 0) > 0:
                detected_level = level
                break

        target_idx = (
            self.LEVEL_ORDER.index(target_bloom)
            if target_bloom in self.LEVEL_ORDER
            else 1
        )
        detected_idx = self.LEVEL_ORDER.index(detected_level)

        evidence = {
            "target_bloom": target_bloom,
            "detected_level": detected_level,
            "level_hits": level_hits,
            "method": "keyword-heuristic (Phase 1)",
        }

        if detected_idx < target_idx:
            score = 0.3 + 0.1 * detected_idx
            issues.append(CriticIssue(
                severity="major",
                description=(
                    f"目标 Bloom 层级为 '{target_bloom}', "
                    f"但内容仅达到 '{detected_level}' 层级"
                ),
                suggestion=(
                    f"请添加 {target_bloom} 层级的元素"
                    f"(如: {', '.join(self.LEVEL_KEYWORDS[target_bloom][:4])})"
                ),
            ))
            suggestions.append(f"升级内容到 {target_bloom} 层级")
        elif detected_idx == target_idx:
            score = 0.9
        else:
            score = 1.0

        score = round(score, 2)
        passed = score >= self.pass_threshold

        return CriticVerdict(
            dimension=self.name,
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            evidence=evidence,
        )


# ================================================================
# 维度 4: Citation — 引用充分性
# ================================================================
class CitationDimension(CriticDimension):
    """检查引用/来源标注的充分性"""

    name: str = "citation"
    INLINE_PATTERNS: List[str] = [
        r'et al\.', r'\[\d+\]', r'参考文献', r'reference',
        r'论文', r'paper', r'提出', r'作者',
    ]

    def evaluate(self, content: str, context: dict) -> CriticVerdict:
        if not content or not content.strip():
            return self._empty_verdict()

        stripped = content.strip()
        issues: List[CriticIssue] = []
        suggestions: List[str] = []

        has_inline = any(
            re.search(p, stripped, re.IGNORECASE) for p in self.INLINE_PATTERNS
        )

        rag_texts = context.get("rag_results", [])
        rag_used = False
        if rag_texts:
            for rag in rag_texts:
                rag_content = rag.get("content", "")[:50]
                if rag_content and rag_content[:20] in stripped:
                    rag_used = True
                    break

        evidence = {
            "has_inline_citation": has_inline,
            "rag_sources_available": len(rag_texts) > 0,
            "rag_content_used": rag_used,
        }

        score = 1.0
        if not has_inline:
            score -= 0.3
            suggestions.append("建议在关键概念后标注来源(如作者+年份)")

        if rag_texts and not rag_used:
            score -= 0.15
            issues.append(CriticIssue(
                severity="minor",
                description="RAG 检索到相关资料但内容中未体现引用",
                suggestion="请参考 RAG 检索到的材料并标注来源",
            ))

        score = round(max(0.0, score), 2)
        passed = score >= self.pass_threshold

        return CriticVerdict(
            dimension=self.name,
            passed=passed,
            score=score,
            issues=issues,
            suggestions=suggestions,
            evidence=evidence,
        )


# ================================================================
# CriticAgent
# ================================================================
class CriticAgent(BaseAgent):
    """多维度内容审查 Agent

    职责: 对生成的教育内容进行 4 维审查，输出每个维度的 CriticVerdict
    用法:
    - Orchestrator 调用 execute() 作为独立审查步骤
    - DebateModerator 的 orchestrate_debate() 内嵌调用

    设计决策:
    - Phase 1: 纯规则引擎，毫秒级 (<5ms) 响应
    - Phase 2: 加 LLM 深度审查通道（rule+LLM 融合）
    - 可插拔: 通过构造函数注入自定义维度
    """

    DEFAULT_DIMENSIONS: List[type] = [
        FactualDimension,
        PedagogyDimension,
        BloomDimension,
        CitationDimension,
    ]

    def __init__(
        self,
        llm_client=None,
        dimensions: Optional[List[CriticDimension]] = None,
    ):
        super().__init__(llm_client=llm_client)
        self._dimensions = (
            [cls() for cls in self.DEFAULT_DIMENSIONS]
            if dimensions is None
            else dimensions
        )

    @property
    def name(self) -> str:
        return "critic"

    @property
    def description(self) -> str:
        return (
            "4 维内容审查器: "
            "事实支撑度 / 教学有效性 / Bloom层级匹配 / 引用充分性"
        )

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名严格的学术内容审查员。\n\n"
            "你的任务是对教育内容进行多维度质量审查:\n"
            "1. 事实准确性 — 概念是否正确, 有无错误陈述\n"
            "2. 教学有效性 — 是否有例子/类比/步骤拆解\n"
            "3. Bloom 层级 — 是否达到目标认知层级\n"
            "4. 引用充分性 — 是否有来源标注和参考\n\n"
            "每个维度独立打分, 最终给出综合结论。"
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行 4 维审查"""
        content = (
            context.extra.get("content_to_review")
            or context.user_input
        )

        if not content or not content.strip():
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error="审查内容为空",
                metadata={
                    "overall_passed": False,
                    "overall_score": 0.0,
                    "verdicts": [],
                },
            )

        eval_context: Dict[str, Any] = {
            "target_bloom": context.extra.get(
                "target_bloom",
                context.extra.get("bloom_target", "understand"),
            ),
            "rag_results": context.rag_results or [],
            "profile": context.profile,
            "course_name": context.course_name,
        }

        # 各维度独立评估
        verdicts: List[CriticVerdict] = []
        for dim in self._dimensions:
            try:
                verdict = dim.evaluate(content, eval_context)
                verdicts.append(verdict)
            except Exception as exc:
                logger.exception(f"[Critic] 维度 {dim.name} 评估异常: {exc}")
                verdicts.append(CriticVerdict(
                    dimension=dim.name,
                    passed=False,
                    score=0.0,
                    issues=[CriticIssue(
                        severity="blocker",
                        description=f"评估异常: {exc}",
                    )],
                    suggestions=["请联系开发者排查"],
                ))

        overall_passed = all(v.passed for v in verdicts)
        overall_score = sum(v.score for v in verdicts) / max(len(verdicts), 1)
        overall_score = round(overall_score, 2)

        # 生成报告
        summary_lines = ["## 内容审查报告\n"]
        for v in verdicts:
            summary_lines.append(f"- {v.to_summary()}")
        summary_lines.append(f"\n**综合评分**: {overall_score:.0%}")
        status = "通过" if overall_passed else "需修改"
        summary_lines.append(f"**审查结论**: {status}")

        if not overall_passed:
            all_issues = [i for v in verdicts for i in v.issues]
            blockers = [i for i in all_issues if i.severity == "blocker"]
            majors = [i for i in all_issues if i.severity == "major"]
            if blockers:
                summary_lines.append(f"\n**阻塞({len(blockers)}):**")
                for i in blockers[:3]:
                    summary_lines.append(f"  - {i.description}")
            if majors:
                summary_lines.append(f"\n**主要({len(majors)}):**")
                for i in majors[:5]:
                    summary_lines.append(f"  - {i.description}")

        return AgentResponse(
            agent_name=self.name,
            success=True,
            content="\n".join(summary_lines),
            content_type="markdown",
            metadata={
                "verdicts": verdicts,
                "overall_passed": overall_passed,
                "overall_score": overall_score,
                "dimension_count": len(verdicts),
            },
        )


# ================================================================
# 日志持久化（通过 Repository 层）
# ================================================================
def record_debate_log(
    session_id: str,
    round_num: int,
    expert_name: str,
    draft: str,
    critic_review: Dict[str, Any],
    revised: str = "",
    verdict: str = "",
) -> Dict[str, Any]:
    """记录一轮辩论（向后兼容的便捷函数）"""
    try:
        from backend.app.repositories.debate_repository import insert_debate_log

        return insert_debate_log({
            "session_id": session_id,
            "round_num": round_num,
            "expert_name": expert_name,
            "draft_preview": draft[:1000],
            "critic_score": critic_review.get("score", 0),
            "critic_passed": critic_review.get("passed", False),
            "critic_issues": critic_review.get("issues", []),
            "verdict": verdict,
        })
    except Exception as exc:
        logger.warning(f"[Critic] 辩论日志持久化失败: {exc}")
        return {
            "session_id": session_id,
            "round": round_num,
            "expert": expert_name,
            "timestamp": time.time(),
            "persisted": False,
            "error": str(exc),
        }


def get_debate_logs(session_id: str = "") -> List[Dict[str, Any]]:
    """获取辩论日志（向后兼容）"""
    try:
        from backend.app.repositories.debate_repository import get_debate_repository

        repo = get_debate_repository()
        if session_id:
            return repo.get_by_session(session_id)
        return repo.get_recent(limit=50)
    except Exception as exc:
        logger.warning(f"[Critic] 获取辩论日志失败: {exc}")
        return []
