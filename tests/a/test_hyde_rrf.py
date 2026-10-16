"""HyDE + RRF Fusion 单元测试 (T2.1)

覆盖:
    HyDE
        1. LLM 成功生成假设答案 → 用假设答案检索
        2. LLM 失败 → 降级到原 query 检索（不抛）
        3. 空 query → 返回空
        4. chunks 字段自动打上 retriever='hyde'
    RRF
        5. 单路输入：rank 顺序保持 + score 等于 1/(k+rank)
        6. 多路输入：同 chunk 被多次命中 → score 累加
        7. 跨路去重：用 chunk_id 唯一标识
        8. top_n 截断
        9. fuse_with_metadata：自动给 chunks 打 retriever 标签
       10. 排序稳定性：相同 score 不应交换顺序
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from backend.app.services.rag.hyde import HydeResult, HydeRetriever
from backend.app.services.rag.rrf import (
    DEFAULT_RRF_K,
    fuse_with_metadata,
    reciprocal_rank_fusion,
)


# ================================================================
# HyDE
# ================================================================
class TestHyDE:
    @pytest.fixture
    def mock_rag(self) -> MagicMock:
        rag = MagicMock()
        rag.retrieve = MagicMock(
            return_value=[
                {"content": "CNN 是卷积神经网络...", "source": "ai/04_cnn.md", "chunk_id": "c1", "score": 0.9},
                {"content": "卷积层通过滤波器...", "source": "ai/04_cnn.md", "chunk_id": "c2", "score": 0.7},
            ]
        )
        return rag

    def test_llm_success_uses_hypothetical_for_retrieval(self, mock_rag: MagicMock) -> None:
        # LLM 返回假设答案，rag 应该用假设答案而不是原 query 去检索
        llm = MagicMock(return_value="卷积神经网络是深度学习中处理图像的核心架构...")
        hyde = HydeRetriever(rag=mock_rag, llm_call=llm)

        result = hyde.retrieve("CNN 是什么？", top_k=2)

        assert isinstance(result, HydeResult)
        assert result.hypothetical_answer.startswith("卷积神经网络")
        assert result.used_fallback is False
        # rag 必须被假设答案触发
        mock_rag.retrieve.assert_called_once()
        called_query = mock_rag.retrieve.call_args[0][0]
        assert "卷积" in called_query

    def test_llm_failure_falls_back_to_query(self, mock_rag: MagicMock) -> None:
        llm = MagicMock(side_effect=RuntimeError("LLM 不可用"))
        hyde = HydeRetriever(rag=mock_rag, llm_call=llm)

        result = hyde.retrieve("CNN 是什么？", top_k=2)

        assert result.used_fallback is True
        assert result.hypothetical_answer == ""
        # rag 用原 query 触发
        called_query = mock_rag.retrieve.call_args[0][0]
        assert called_query == "CNN 是什么？"
        # 每个 chunk 都打了 fallback 标签
        for c in result.chunks:
            assert c["retriever"] == "hyde_fallback"

    def test_empty_query_returns_empty(self, mock_rag: MagicMock) -> None:
        llm = MagicMock(return_value="should not be called")
        hyde = HydeRetriever(rag=mock_rag, llm_call=llm)

        result = hyde.retrieve("   ", top_k=5)

        assert result.chunks == []
        assert result.hypothetical_answer == ""
        llm.assert_not_called()
        mock_rag.retrieve.assert_not_called()

    def test_chunks_tagged_with_retriever(self, mock_rag: MagicMock) -> None:
        llm = MagicMock(return_value="假设答案")
        hyde = HydeRetriever(rag=mock_rag, llm_call=llm)

        result = hyde.retrieve("query", top_k=2)
        for c in result.chunks:
            assert c["retriever"] == "hyde"


# ================================================================
# RRF
# ================================================================
class TestRRF:
    def test_single_list_preserves_order_and_scores(self) -> None:
        chunks = [
            {"chunk_id": "c1", "content": "first"},
            {"chunk_id": "c2", "content": "second"},
            {"chunk_id": "c3", "content": "third"},
        ]
        fused = reciprocal_rank_fusion([chunks])

        assert [c["chunk_id"] for c in fused] == ["c1", "c2", "c3"]
        # score = 1/(k+rank)
        assert fused[0]["rrf_score"] == pytest.approx(1 / (DEFAULT_RRF_K + 1))
        assert fused[1]["rrf_score"] == pytest.approx(1 / (DEFAULT_RRF_K + 2))
        assert fused[2]["rrf_score"] == pytest.approx(1 / (DEFAULT_RRF_K + 3))

    def test_multi_list_accumulates_for_common_chunks(self) -> None:
        """同一 chunk 在两路里都命中 → score 应累加。"""
        list_a = [
            {"chunk_id": "c1", "content": "shared", "retriever": "plain"},
            {"chunk_id": "c2", "content": "only_a", "retriever": "plain"},
        ]
        list_b = [
            {"chunk_id": "c1", "content": "shared", "retriever": "hyde"},
            {"chunk_id": "c3", "content": "only_b", "retriever": "hyde"},
        ]
        fused = reciprocal_rank_fusion([list_a, list_b])

        # c1 应排第一（两路 rank 1 累加）
        assert fused[0]["chunk_id"] == "c1"
        assert fused[0]["rrf_score"] == pytest.approx(
            2.0 / (DEFAULT_RRF_K + 1)
        )
        # c1 应同时含两个 retriever
        assert set(fused[0]["rrf_sources"]) == {"plain", "hyde"}
        assert fused[0]["rrf_ranks"] == {"plain": 1, "hyde": 1}

    def test_dedup_by_chunk_id(self) -> None:
        """无 chunk_id 时按 source+content head 兜底去重。"""
        list_a = [
            {"source": "ai/01.md", "content": "abc" * 100},  # 无 chunk_id
        ]
        list_b = [
            {"source": "ai/01.md", "content": "abc" * 100},  # 无 chunk_id
        ]
        fused = reciprocal_rank_fusion([list_a, list_b])
        assert len(fused) == 1, "same source+content should dedup"
        assert fused[0]["rrf_score"] == pytest.approx(2.0 / (DEFAULT_RRF_K + 1))

    def test_top_n_truncation(self) -> None:
        chunks = [{"chunk_id": f"c{i}", "content": str(i)} for i in range(10)]
        fused = reciprocal_rank_fusion([chunks], top_n=3)
        assert len(fused) == 3
        assert [c["chunk_id"] for c in fused] == ["c0", "c1", "c2"]

    def test_empty_input(self) -> None:
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []

    def test_fuse_with_metadata_auto_tags(self) -> None:
        """fuse_with_metadata 应自动给 chunks 打 retriever 标签。"""
        plain = [{"chunk_id": "c1", "content": "a"}]
        hyde = [{"chunk_id": "c1", "content": "a"}]
        kg = [{"chunk_id": "c2", "content": "b"}]

        fused = fuse_with_metadata({"plain": plain, "hyde": hyde, "kg": kg})

        # c1 在 plain + hyde 命中两次
        c1 = next(c for c in fused if c["chunk_id"] == "c1")
        assert set(c1["rrf_sources"]) == {"plain", "hyde"}

        c2 = next(c for c in fused if c["chunk_id"] == "c2")
        assert c2["rrf_sources"] == ["kg"]

    def test_score_ordering(self) -> None:
        """两路命中的 chunk 必须排在单路命中的 chunk 前面。"""
        list_a = [
            {"chunk_id": "single_a_top", "content": "x"},
            {"chunk_id": "shared", "content": "y"},  # rank 2 in a
        ]
        list_b = [
            {"chunk_id": "shared", "content": "y"},  # rank 1 in b
            {"chunk_id": "single_b_top", "content": "z"},
        ]
        fused = reciprocal_rank_fusion([list_a, list_b])

        # shared 应排第一：1/(k+2) + 1/(k+1) > 1/(k+1) 单路
        assert fused[0]["chunk_id"] == "shared"


# ================================================================
# HyDE + RRF 集成
# ================================================================
class TestHydeRrfIntegration:
    def test_hyde_then_rrf_with_plain(self) -> None:
        """典型组合：原 query 检索 + HyDE 检索 → RRF 融合。"""
        # 每次返回独立的 list/dict，避免共享引用让 retriever 标签互相覆盖
        def _retrieve_factory(*_args, **_kwargs) -> List[Dict[str, Any]]:
            return [
                {"chunk_id": "shared", "content": "CNN 概念", "score": 0.9},
                {"chunk_id": "hyde_only", "content": "卷积细节", "score": 0.7},
            ]

        mock_rag = MagicMock()
        mock_rag.retrieve = MagicMock(side_effect=_retrieve_factory)

        # 原 query 直接走 RAG
        plain_chunks = mock_rag.retrieve("CNN 是什么")
        for c in plain_chunks:
            c["retriever"] = "plain"

        # HyDE 走 RAG（独立 chunks，不共享引用）
        llm = MagicMock(return_value="CNN 是卷积神经网络...")
        hyde = HydeRetriever(rag=mock_rag, llm_call=llm)
        hyde_result = hyde.retrieve("CNN 是什么", top_k=2)

        # RRF 融合
        fused = fuse_with_metadata(
            {"plain": plain_chunks, "hyde": hyde_result.chunks},
            top_n=5,
        )

        shared = next(c for c in fused if c["chunk_id"] == "shared")
        assert set(shared["rrf_sources"]) == {"plain", "hyde"}
