"""
防幻觉 L3 一致性检查 —— 答辩创新点补充

L1: RAG 来源引用（rag_service.py）
L2: Reviewer 快速规则检查（reviewer_agent.py）
L3: 生成内容 vs RAG context 的 chunk overlap + 关键实体一致性（本模块）

策略：
  1. 从生成内容提取关键术语/实体
  2. 与 RAG 检索到的 context 做重叠度检查
  3. 不通过时返回标志，触发重写（接入 A 的 reflect 机制）
  4. 纯规则实现，0 LLM 开销
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 中英文术语提取
_TERM_PATTERN = re.compile(
    r"[A-Z][a-zA-Z]{2,}|[一-鿿]{2,8}|"
    r"`[^`]+`|"
    r"\*\*[^*]+\*\*",
)


class ConsistencyChecker:
    """L3 生成内容一致性检查"""

    def __init__(self, overlap_threshold: float = 0.4):
        self.overlap_threshold = overlap_threshold

    def check(
        self,
        generated_text: str,
        rag_contexts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """检查生成内容与 RAG context 的一致性。

        Args:
            generated_text: LLM 生成的文本
            rag_contexts: RAG 检索到的上下文列表 [{content, source, ...}, ...]

        Returns:
            {"passed": bool, "score": float, "missing_terms": [...], "suggestion": str}
        """
        if not rag_contexts or not generated_text.strip():
            return {"passed": True, "score": 1.0, "missing_terms": [], "suggestion": ""}

        # 提取生成内容的关键术语
        gen_terms = set(_TERM_PATTERN.findall(generated_text.lower()))
        if not gen_terms:
            return {"passed": True, "score": 1.0, "missing_terms": [], "suggestion": ""}

        # 提取 RAG context 的术语
        context_terms: set = set()
        for ctx in rag_contexts:
            text = ctx.get("content", "") or ""
            context_terms.update(_TERM_PATTERN.findall(text.lower()))

        if not context_terms:
            return {"passed": True, "score": 1.0, "missing_terms": [], "suggestion": ""}

        # 计算重叠率
        overlap = gen_terms & context_terms
        overlap_ratio = len(overlap) / max(len(gen_terms), 1)

        # 检查是否有"幻觉术语"（生成中出现但 context 中完全没有）
        missing = list(gen_terms - context_terms)[:10]

        passed = overlap_ratio >= self.overlap_threshold

        suggestion = ""
        if not passed:
            suggestion = (
                f"生成内容与知识库一致性较低（{overlap_ratio:.0%}），"
                f"以下术语未在知识库中找到：{', '.join(missing[:5])}"
            )

        return {
            "passed": passed,
            "score": round(overlap_ratio, 4),
            "missing_terms": missing,
            "suggestion": suggestion,
            "gen_term_count": len(gen_terms),
            "context_term_count": len(context_terms),
        }

    def should_rewrite(self, check_result: Dict[str, Any]) -> bool:
        """是否需要触发重写"""
        return not check_result.get("passed", True)


# 模块级单例
_checker: ConsistencyChecker | None = None


def get_consistency_checker() -> ConsistencyChecker:
    global _checker
    if _checker is None:
        _checker = ConsistencyChecker()
    return _checker
