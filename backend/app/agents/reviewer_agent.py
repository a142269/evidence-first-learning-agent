"""
资源质检 Agent —— 对生成的资源进行质量审查
借鉴自: NPUYUN/LearnPath 的 Reviewer Agent 设计

职责：
1. 检查资源内容是否紧扣请求主题（防偏离）
2. 检查是否包含 LLM 复述提示词的脏数据
3. 检查事实性错误（基于知识库对照）
4. 标记低质量内容供重生成
"""
from __future__ import annotations

import re
import json
import logging
from typing import Optional

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse

logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    """质量审查员 —— 对 AI 生成的学习资源进行质检"""

    @property
    def name(self) -> str:
        return "reviewer"

    @property
    def description(self) -> str:
        return "对 AI 生成的资源进行质量审查，检测偏离主题、脏数据、事实性错误"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名严格的教育内容质量审查员。你的任务是对 AI 生成的学习资源进行质检。\n\n"
            "检查维度：\n"
            "1. **主题相关性**：内容是否紧扣用户请求的主题？有无明显偏离？\n"
            "2. **结构完整性**：是否有标题、正文、总结等基本结构？\n"
            "3. **学术准确性**：概念定义是否正确？有无明显事实性错误？\n"
            "4. **可读性**：语言是否流畅？难度是否适合目标学生？\n"
            "5. **原创性**：是否有明显的 AI 复读提示词、JSON 格式残留等脏数据？\n\n"
            "输出要求：\n"
            "- 先给出总体评价（优/良/中/差）\n"
            "- 逐项列出问题和建议\n"
            "- 在末尾用 ```review_result``` 包裹结构化审查结果\n\n"
            "审查 JSON 格式：\n"
            '```review_result\n'
            '{"quality": "good", "score": 85, "issues": [{"dimension": "学术准确性", "severity": "minor", '
            '"description": "梯度下降的学习率说明不够精确", "suggestion": "建议补充具体的学习率范围示例"}], '
            '"pass": true, "regenerate": false}\n'
            '```\n'
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """审查资源质量"""
        content_to_review = context.extra.get("resource_content", "")
        original_request = context.user_input or context.extra.get("original_request", "")

        if not content_to_review:
            return self._error("没有可审查的内容")

        # 快速规则检查（不调用 LLM）
        quick_issues = self._quick_check(content_to_review, original_request)

        review_prompt = f"""请审查以下 AI 生成的学习资源质量：

【原始请求】{original_request[:500]}

【生成内容】
{content_to_review[:3000]}

【快速规则已发现的问题】
{json.dumps(quick_issues, ensure_ascii=False, indent=2) if quick_issues else "无"}
"""

        result = await self._acall_llm(
            user_prompt=review_prompt,
            history=context.conversation_history,
            temperature=0.3,
        )

        review_data = self._extract_review_data(result)

        # 判断是否需要重生成
        needs_regenerate = (
            review_data.get("quality") == "poor"
            or review_data.get("score", 100) < 50
            or review_data.get("regenerate", False)
        )

        return self._success(
            content=result,
            content_type="review",
            metadata={
                "review_data": review_data,
                "needs_regenerate": needs_regenerate,
                "quick_issues": quick_issues,
            },
        )

    def _quick_check(self, content: str, request: str) -> list[dict]:
        """
        快速规则检查 —— 不调用 LLM，毫秒级完成

        检测项：
        1. 是否复述了生成指令/提示词
        2. 是否包含原始 JSON 数据
        3. 内容是否过短
        """
        issues = []

        # 检查1：是否复述了提示词（LLM 常见问题）
        prompt_leak_patterns = [
            r"你是一名.{0,30}请根据以下要求",
            r"系统提示.*System Prompt",
            r"你需要.*生成.*内容",
        ]
        for pattern in prompt_leak_patterns:
            if re.search(pattern, content):
                issues.append({
                    "dimension": "原创性",
                    "severity": "major",
                    "description": "内容中包含了 AI 生成指令/提示词的复述",
                    "suggestion": "移除提示词相关内容，只保留实际教学内容",
                })
                break

        # 检查2：是否包含 JSON 格式残留
        json_patterns = [
            r'```json\s*\n\s*\{',
            r'"resource_type":\s*"(?:document|quiz|mindmap)"',
            r'"content_type":\s*"',
        ]
        for pattern in json_patterns:
            if re.search(pattern, content) and len(content) < 200:
                issues.append({
                    "dimension": "原创性",
                    "severity": "major",
                    "description": "疑似返回了 JSON 格式数据而非教学内容",
                    "suggestion": "需要重新生成，确保返回 Markdown 格式的教学内容",
                })
                break

        # 检查3：内容过短
        if len(content.strip()) < 100:
            issues.append({
                "dimension": "完整性",
                "severity": "major",
                "description": f"生成内容过短（{len(content)}字符），可能不完整",
                "suggestion": "建议重新生成或检查 RAG 检索结果",
            })

        return issues

    def _extract_review_data(self, llm_output: str) -> dict:
        """从审查输出中提取结构化数据"""
        pattern = r"```review_result\s*\n(.*?)\n```"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 如果无法提取 JSON，从文本中推断质量
        if "优" in llm_output[:100] or "good" in llm_output[:100].lower():
            return {"quality": "good", "score": 80, "pass": True, "regenerate": False}
        if "差" in llm_output[:100] or "poor" in llm_output[:100].lower():
            return {"quality": "poor", "score": 30, "pass": False, "regenerate": True}
        return {"quality": "medium", "score": 60, "pass": True, "regenerate": False}


# ================================================================
# 资源质量评分工具（无需 LLM 调用的轻量检查）
# ================================================================
def quick_quality_score(content: str, content_type: str = "document") -> dict:
    """
    快速质量评分 —— 用于生成后的即时反馈

    Returns:
        {"score": 0-100, "issues": [...], "suggestions": [...]}
    """
    score = 100
    issues = []
    suggestions = []

    # 长度检查
    content_len = len(content.strip())
    if content_type in ("document", "reading"):
        if content_len < 300:
            score -= 40
            issues.append("内容过短，建议至少300字")
        elif content_len < 800:
            score -= 15
            issues.append("内容偏短，建议扩充")
    elif content_type == "quiz":
        if content_len < 100:
            score -= 30
            issues.append("题目内容过短")

    # 结构检查
    if content_type in ("document", "reading"):
        if not re.search(r"^#{1,3}\s", content, re.MULTILINE):
            score -= 10
            suggestions.append("建议添加标题结构（使用 # ## ###）")

    # Markdown 格式检查
    if content_type == "mindmap":
        if "```mermaid" not in content and "mindmap" not in content.lower():
            score -= 20
            issues.append("思维导图未包含 Mermaid 代码块")
    elif content_type == "quiz":
        has_answer = bool(re.search(r"(?:答案|解析|正确|错误)", content))
        if not has_answer:
            score -= 15
            issues.append("练习题缺少参考答案或解析")

    # 代码块检查（代码相关资源）
    if content_type in ("code", "document"):
        has_code = "```" in content
        if not has_code and any(kw in content for kw in ["代码", "编程", "实现", "code"]):
            suggestions.append("如果涉及编程内容，建议添加代码示例")

    return {
        "score": max(0, score),
        "issues": issues,
        "suggestions": suggestions,
    }
