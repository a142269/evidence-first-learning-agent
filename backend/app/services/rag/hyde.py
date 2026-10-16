"""HyDE — Hypothetical Document Embeddings for RAG

论文: Gao et al. 2022, "Precise Zero-Shot Dense Retrieval without Relevance Labels"
       (arxiv: 2212.10496)

核心思路:
    用户的 query 通常比较简短/抽象（"如何理解 CNN"），向量检索时
    跟知识库里详细描述的句子相似度低。HyDE 让 LLM 先"假设性地回答"
    query → 用回答的 embedding 去检索 → 比直接用 query 检索更精准，
    因为假设回答的语言风格、术语密度跟知识库正文更接近。

实现:
    1. 不动 RAGService，独立包装一层 HydeRetriever
    2. 给定 query → call_llm(query) 得到 hypothetical answer
    3. 用 hypothetical answer 作为新 query 调 RAGService.retrieve
    4. 返回结果 dict 里加 ``hyde_used=True`` 字段，便于 trace

设计取舍:
    * LLM 失败 / offline 时：自动降级走原 query，不抛
    * cache 通过 CachedLLMClient 接入（同 prompt 不再重复生成假设答案）
    * 与 RRF 组合：通常做法是「原 query 检索 ∪ HyDE 检索 → RRF 融合」
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ================================================================
# Prompt 模板
# ================================================================
HYDE_PROMPT_ZH = """你是教学领域专家。请针对下面的学生提问，先**写一段假设性的标准答案**，
用于检索增强（不会直接展示给学生）。

要求:
1. 用 80-150 字的连贯段落
2. 包含与题目相关的核心术语和公式
3. 不要写"以下是答案"等元话
4. 不要使用 markdown / 列表 / 代码块

学生提问: {query}

假设性答案:"""


# ================================================================
# 数据模型
# ================================================================
@dataclass
class HydeResult:
    """HyDE 检索的完整 trace，便于后续 RRF / 可解释。"""
    query: str
    hypothetical_answer: str  # LLM 生成的假设答案
    chunks: List[Dict[str, Any]]  # 用假设答案检索得到的 chunk 列表
    used_fallback: bool = False  # True 表示 LLM 失败回退到 query
    extra: Dict[str, Any] = field(default_factory=dict)


# ================================================================
# HydeRetriever
# ================================================================
class HydeRetriever:
    """HyDE 适配器。

    用法::

        hyde = HydeRetriever(
            rag=get_rag_service(),
            llm_call=lambda prompt: cached_llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.3
            ),
        )
        result = hyde.retrieve("什么是反向传播？", top_k=5)
        for chunk in result.chunks:
            print(chunk["content"][:80])
    """

    def __init__(
        self,
        rag: Any,  # RAGService
        llm_call: Callable[[str], str],
        *,
        prompt_template: str = HYDE_PROMPT_ZH,
    ) -> None:
        self._rag = rag
        self._llm = llm_call
        self._template = prompt_template

    def _generate_hypothetical(self, query: str) -> str:
        """让 LLM 生成假设答案；失败返回空串。"""
        prompt = self._template.format(query=query)
        try:
            answer = self._llm(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[hyde] LLM 调用失败，回退原 query: %s", exc)
            return ""
        return (answer or "").strip()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        course_filter: Optional[str] = None,
    ) -> HydeResult:
        """返回 HydeResult。当 LLM 不可用时降级到原 query 检索（保证可用性）。"""
        if not query or not query.strip():
            return HydeResult(query=query, hypothetical_answer="", chunks=[])

        hypothetical = self._generate_hypothetical(query)

        if hypothetical:
            # 真正的 HyDE：用假设答案去检索
            chunks = self._rag.retrieve(
                hypothetical, top_k=top_k, course_filter=course_filter
            )
            for c in chunks:
                c.setdefault("retriever", "hyde")
            return HydeResult(
                query=query,
                hypothetical_answer=hypothetical,
                chunks=chunks,
                used_fallback=False,
            )

        # 降级：LLM 不可用 → 走原 query
        chunks = self._rag.retrieve(query, top_k=top_k, course_filter=course_filter)
        for c in chunks:
            c.setdefault("retriever", "hyde_fallback")
        return HydeResult(
            query=query,
            hypothetical_answer="",
            chunks=chunks,
            used_fallback=True,
        )
