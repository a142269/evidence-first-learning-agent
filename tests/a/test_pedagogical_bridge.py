"""pedagogical_bridge 单测：B → A 桥接层

确保 B 的 pedagogical_context dict 能稳定转成 A 的 TutoringContext + EvidencePool。
覆盖：
    A. tutoring_context_from_b 字段映射
    B. evidence_pool_from_b 5 source type 拆分
    C. bridge_full_context 一站式 + B 不可用时空兜底
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.claim_ledger import EvidencePool
from backend.app.services.pedagogical_bridge import (
    bridge_full_context,
    evidence_pool_from_b,
    tutoring_context_from_b,
)
from backend.app.services.pedagogical_safety import TutoringContext


# ================================================================
# A. tutoring_context_from_b
# ================================================================
class TestTutoringContextFromB:
    def test_full_mistake_kt_mapping(self) -> None:
        b_ctx = {
            "mistake": {
                "has_mistakes": True,
                "top_misconception": "公式",
                "error_categories": [{"category": "公式", "count": 3}],
                "top_misconception_bloom": "Apply",
            },
            "kt": {
                "masteries": {"kp:cnn": 0.62, "kp:rnn": 0.51},
                "trends": {"kp:cnn": "rising"},
            },
        }
        tc = tutoring_context_from_b(
            b_ctx,
            student_question="什么是 CNN?",
            student_answer="错答",
            correct_answer="正答",
        )
        assert isinstance(tc, TutoringContext)
        assert tc.bloom_level == "apply"
        assert tc.attribution_category == "公式"
        assert set(tc.kp_ids) == {"kp:cnn", "kp:rnn"}
        assert tc.student_question == "什么是 CNN?"
        assert tc.student_answer == "错答"
        assert tc.correct_answer == "正答"

    def test_missing_fields_fallback(self) -> None:
        tc = tutoring_context_from_b({})
        assert isinstance(tc, TutoringContext)
        assert tc.bloom_level is None
        assert tc.attribution_category is None
        assert tc.kp_ids == []

    def test_error_categories_as_string_list(self) -> None:
        b_ctx = {
            "mistake": {"error_categories": ["公式", "计算"]},
        }
        tc = tutoring_context_from_b(b_ctx)
        assert tc.attribution_category == "公式"

    def test_top_misconception_fallback_when_no_categories(self) -> None:
        b_ctx = {"mistake": {"top_misconception": "审题"}}
        tc = tutoring_context_from_b(b_ctx)
        assert tc.attribution_category == "审题"


# ================================================================
# B. evidence_pool_from_b
# ================================================================
class TestEvidencePoolFromB:
    def test_rag_chunks_split_by_knowledge_base_path(self) -> None:
        b_ctx = {
            "evidence": {
                "rag_chunks": [
                    {"source": "knowledge_base/ai/04_cnn.md", "content": "教材 CNN 章节"},
                    {"source": "chunk_external_42", "content": "外部 chunk"},
                ],
            },
        }
        pool = evidence_pool_from_b(b_ctx)
        assert len(pool.textbook) == 1
        assert pool.textbook[0]["ref"].endswith(".md")
        assert len(pool.rag_chunk) == 1
        assert pool.rag_chunk[0]["ref"] == "chunk_external_42"

    def test_kg_neighbors_and_center(self) -> None:
        b_ctx = {
            "evidence": {
                "kg_neighbors": [
                    {"kp_id": "kp:rnn", "relation_type": "related_to"},
                    {"kp_id": "kp:lstm", "relation_type": "prereq"},
                ],
                "kg_center": {"id": "kp:cnn", "name": "CNN", "description": "卷积"},
            },
        }
        pool = evidence_pool_from_b(b_ctx)
        # center + 2 neighbors → 3 条 kg
        assert len(pool.kg) == 3
        refs = {item["ref"] for item in pool.kg}
        assert "kp:cnn" in refs
        assert "kp:rnn" in refs
        assert "kp:lstm" in refs

    def test_mistake_and_history(self) -> None:
        b_ctx = {
            "evidence": {
                "related_mistakes": [
                    {"id": "m-12", "error_type": "公式", "question": "求 x"},
                ],
                "learning_history": [
                    {"id": "h-1", "summary": "学过 CNN"},
                ],
            },
        }
        pool = evidence_pool_from_b(b_ctx)
        assert len(pool.mistake) == 1
        assert pool.mistake[0]["ref"] == "mistake_id:m-12"
        assert "公式" in pool.mistake[0]["content"]
        assert len(pool.history) == 1
        assert pool.history[0]["ref"] == "path:h-1"

    def test_empty_b_ctx_returns_empty_pool(self) -> None:
        pool = evidence_pool_from_b({})
        assert isinstance(pool, EvidencePool)
        assert pool.textbook == []
        assert pool.kg == []
        assert pool.rag_chunk == []
        assert pool.mistake == []
        assert pool.history == []

    def test_non_dict_items_skipped(self) -> None:
        b_ctx = {
            "evidence": {
                "rag_chunks": ["not a dict", {"source": "ok.md", "content": "ok"}],
                "kg_neighbors": [None, {"kp_id": "kp:x"}],
            },
        }
        pool = evidence_pool_from_b(b_ctx)
        # 应只命中合法的 dict 项
        assert len(pool.textbook) + len(pool.rag_chunk) == 1
        assert len(pool.kg) == 1


# ================================================================
# C. bridge_full_context — 一站式
# ================================================================
class TestBridgeFullContext:
    def test_bridge_returns_3_keys(self) -> None:
        # 不打 patch，让 B 调用真实模块（B 模块异常会被 try/except 兜底返回空）
        result = bridge_full_context(
            user_id="demo-student-1",
            query="CNN 卷积",
            kp_id="",
            student_question="什么是 CNN?",
        )
        assert "tutoring_context" in result
        assert "evidence_pool" in result
        assert "b_raw" in result
        assert isinstance(result["tutoring_context"], TutoringContext)
        assert isinstance(result["evidence_pool"], EvidencePool)

    def test_bridge_falls_back_when_b_unavailable(self) -> None:
        """B 模块异常时返回空 context + 空 pool（不抛）。"""
        with patch(
            "backend.app.services.pedagogical_context.get_full_pedagogical_context",
            side_effect=RuntimeError("B unavailable"),
        ):
            result = bridge_full_context(
                user_id="demo-student-1",
                query="x",
                student_question="x",
            )
            tc = result["tutoring_context"]
            pool = result["evidence_pool"]
            assert tc.bloom_level is None
            assert pool.textbook == []
            assert result["b_raw"] == {}

    def test_bridge_uses_query_as_student_question_fallback(self) -> None:
        with patch(
            "backend.app.services.pedagogical_context.get_full_pedagogical_context",
            return_value={},
        ):
            result = bridge_full_context(
                user_id="u",
                query="询问内容",
            )
            assert result["tutoring_context"].student_question == "询问内容"


# ================================================================
# D. 端到端：A 服务能消费桥接结果
# ================================================================
class TestEndToEndIntegration:
    def test_safety_evaluator_consumes_bridged_context(self) -> None:
        from backend.app.services.pedagogical_safety import get_pedagogical_safety_evaluator

        b_ctx = {
            "mistake": {"top_misconception_bloom": "Apply", "top_misconception": "公式"},
            "kt": {"masteries": {"kp:cnn": 0.6}},
        }
        tc = tutoring_context_from_b(b_ctx)
        ev = get_pedagogical_safety_evaluator()
        # 响应里没有问号，确保 uptake_prompt 走 Bloom apply 模板池而非复用响应问句
        result = ev.evaluate("我们一起想想 CNN 的计算过程。第一步先看输入维度。", tc)
        # bloom=apply 模板都含 "X" 或 "例子"
        assert ("X" in result.student_uptake_prompt
                or "例子" in result.student_uptake_prompt), result.student_uptake_prompt

    def test_claim_ledger_consumes_bridged_pool(self) -> None:
        from backend.app.services.claim_ledger import get_claim_ledger

        b_ctx = {
            "evidence": {
                "rag_chunks": [
                    {"source": "knowledge_base/ai/04_cnn.md",
                     "content": "CNN 是卷积神经网络的简称, 处理图像数据。"}
                ],
            },
        }
        pool = evidence_pool_from_b(b_ctx)
        ledger = get_claim_ledger()
        r = ledger.build("CNN 是卷积神经网络的简称。", pool=pool)
        # 应该命中 textbook
        assert r.total_claims >= 1
        c = r.claims[0]
        types = {s.source_type for s in c.sources}
        assert "textbook" in types
