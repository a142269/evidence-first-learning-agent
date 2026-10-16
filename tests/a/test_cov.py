"""
测试: CoV-Edu — Chain-of-Verification 防幻觉 (Week2 Day8-9)

覆盖:
- Claim / ClaimEvidence / COVResult 数据模型
- ClaimsExtractor: LLM抽取 / 规则降级 / 空内容 / 无LLM
- ClaimVerifier: 规则层验证 (verified/uncertain/refuted) / 数字矛盾 / 术语重叠
- ContentRewriter: refuted替换 / uncertain标记 / verified保留
- COVVerifierAgent.execute() 集成
- 幻觉率计算正确性
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.app.agents.base import AgentContext, AgentResponse


# ================================================================
# 数据模型
# ================================================================
class TestCOVResult:
    def test_empty(self):
        from backend.app.agents.cov_verifier import COVResult
        r = COVResult(original_content="test")
        assert r.claims_verified == 0
        assert r.claims_uncertain == 0
        assert r.claims_refuted == 0
        assert r.hallucination_rate() == 0.0

    def test_hallucination_rate(self):
        from backend.app.agents.cov_verifier import COVResult, ClaimEvidence
        r = COVResult(
            original_content="test",
            evidences=[
                ClaimEvidence(1, "c1", "verified", 0.9),
                ClaimEvidence(2, "c2", "uncertain", 0.4),
                ClaimEvidence(3, "c3", "verified", 0.85),
                ClaimEvidence(4, "c4", "refuted", 0.7),
            ],
        )
        # 4 claims: 2 uncertain/refuted → 50% hallucination
        assert r.claims_verified == 2
        assert r.hallucination_rate() == 0.5


# ================================================================
# ClaimsExtractor — 规则通道
# ================================================================
class TestClaimsExtractor:
    @pytest.fixture
    def extractor(self):
        from backend.app.agents.cov_verifier import ClaimsExtractor
        return ClaimsExtractor(llm_client=None)  # 强制规则通道

    def test_empty_content(self, extractor):
        claims = extractor.extract("")
        assert claims == []

    def test_extracts_factual_claims(self, extractor):
        content = (
            "卷积神经网络由 Yann LeCun 于 1998 年提出。"
            "它包含卷积层、池化层和全连接层。"
            "LeNet-5 在 MNIST 上达到 99.05% 的准确率。"
        )
        claims = extractor.extract(content)
        assert len(claims) >= 2  # 至少年份和百分比

    def test_extracts_definitions(self, extractor):
        content = "Softmax 函数定义为 σ(z_i) = e^{z_i} / Σ_j e^{z_j}"
        claims = extractor.extract(content)
        assert len(claims) >= 1

    def test_extracts_citations(self, extractor):
        content = "参见 Hinton et al. 2012 的论文。参考文献 [1] 详细描述了该方法。"
        claims = extractor.extract(content)
        assert len(claims) >= 1

    def test_skips_short_sentences(self, extractor):
        content = "好的。"  # 太短
        claims = extractor.extract(content)
        assert len(claims) == 0

    def test_claim_types(self, extractor):
        content = (
            "CNN 由 Yann LeCun 于 1998 年提出。"
            "准确率达到 99.05%。"
        )
        claims = extractor.extract(content)
        types = {c.claim_type for c in claims}
        assert "factual" in types or "number" in types

    def test_parse_llm_output(self, extractor):
        raw = (
            "CNN由Yann LeCun提出 || factual\n"
            "准确率99.05% || number\n"
            "这是一个框架 || factual"
        )
        claims = extractor._parse_llm_output(raw, "dummy content")
        assert len(claims) == 3
        assert claims[0].claim_type == "factual"
        assert claims[1].claim_type == "number"


# ================================================================
# ClaimVerifier — 规则层
# ================================================================
class TestClaimVerifier:
    @pytest.fixture
    def verifier(self):
        from backend.app.agents.cov_verifier import ClaimVerifier
        return ClaimVerifier(rag_service=None, llm_client=None)  # 纯规则

    def test_verified_with_supporting_rag(self, verifier):
        from backend.app.agents.cov_verifier import Claim
        claim = Claim(1, "卷积神经网络由 Yann LeCun 提出", "factual")
        rag = [
            {"content": "卷积神经网络 (CNN) 是由 Yann LeCun 在 1998 年提出的深度前馈神经网络。"},
            {"content": "LeCun 的 LeNet-5 是第一个成功应用的卷积神经网络。"},
        ]
        ev = verifier.verify(claim, rag)
        assert ev.verdict == "verified"
        assert len(ev.supporting_chunks) > 0

    def test_uncertain_with_no_rag(self, verifier):
        from backend.app.agents.cov_verifier import Claim
        claim = Claim(1, "量子计算将取代深度学习", "factual")
        rag = [
            {"content": "卷积神经网络是图像识别的基础模型。"},
        ]
        ev = verifier.verify(claim, rag)
        assert ev.verdict == "uncertain"
        assert ev.confidence < 0.6

    def test_refuted_with_contradicting_numbers(self, verifier):
        from backend.app.agents.cov_verifier import Claim
        # 声称 99.05%，RAG 说 98.5%
        claim = Claim(1, "LeNet-5 在 MNIST 上达到 99.05% 准确率", "number")
        rag = [
            {"content": "LeNet-5 在 MNIST 数据集上达到了 98.5% 的准确率。"},
        ]
        ev = verifier.verify(claim, rag)
        # 数字不匹配 → refuted
        assert ev.verdict == "refuted" or ev.verdict == "uncertain"

    def test_empty_rag_returns_uncertain(self, verifier):
        from backend.app.agents.cov_verifier import Claim
        claim = Claim(1, "任意声称", "factual")
        ev = verifier.verify(claim, [])
        # 无 RAG → uncertain
        assert ev.verdict == "uncertain"

    def test_term_extraction(self, verifier):
        terms = verifier._extract_terms("CNN卷积神经网络由Yann LeCun提出")
        assert "CNN" in terms or "cnn" in terms
        assert "卷积神经网络" in terms
        assert "Yann" in terms or "yann" in terms
        assert "LeCun" in terms or "lecun" in terms


# ================================================================
# ContentRewriter
# ================================================================
class TestContentRewriter:
    @pytest.fixture
    def rewriter(self):
        from backend.app.agents.cov_verifier import ContentRewriter
        return ContentRewriter()

    def test_refuted_claim_replaced(self, rewriter):
        from backend.app.agents.cov_verifier import ClaimEvidence
        original = "准确率为 99.05%。这在当时是最好的结果。"
        ev = ClaimEvidence(
            1, "准确率为 99.05%", "refuted", 0.7,
            suggested_correction="准确率为 98.5%",
        )
        rewritten = rewriter.rewrite(original, [ev])
        assert "已纠正" in rewritten
        assert "99.05%" in rewritten  # 原文保留 + 标记

    def test_uncertain_claim_marked(self, rewriter):
        from backend.app.agents.cov_verifier import ClaimEvidence
        original = "CNN 是最适合图像的架构"
        ev = ClaimEvidence(1, "CNN 是最适合图像的架构", "uncertain", 0.4)
        rewritten = rewriter.rewrite(original, [ev])
        assert "待核实" in rewritten

    def test_verified_unchanged(self, rewriter):
        from backend.app.agents.cov_verifier import ClaimEvidence
        original = "CNN 是一种神经网络架构"
        ev = ClaimEvidence(1, "CNN 是一种神经网络架构", "verified", 0.9)
        rewritten = rewriter.rewrite(original, [ev])
        # verified 不修改
        assert original in rewritten

    def test_verification_summary_added(self, rewriter):
        from backend.app.agents.cov_verifier import ClaimEvidence
        original = "CNN 是一种神经网络"
        ev = ClaimEvidence(1, "CNN 是一种神经网络", "verified", 0.9)
        rewritten = rewriter.rewrite(original, [ev])
        assert "内容验证" in rewritten
        assert "已验证" in rewritten

    def test_empty_evidences(self, rewriter):
        original = "任意内容"
        rewritten = rewriter.rewrite(original, [])
        assert rewritten == original


# ================================================================
# COVVerifierAgent 集成
# ================================================================
class TestCOVVerifierAgent:
    @pytest.fixture
    def agent(self, mock_llm_client):
        from backend.app.agents.cov_verifier import COVVerifierAgent
        return COVVerifierAgent(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_execute_empty_content(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="")
        resp = await agent.execute(ctx)
        assert resp.success is False

    @pytest.mark.asyncio
    async def test_execute_extracts_and_verifies(self, agent):
        from backend.app.agents.base import AgentContext
        content = (
            "卷积神经网络由 Yann LeCun 于 1998 年提出。"
            "LeNet-5 达到 99.05% 准确率。"
            "CNN 包含卷积层、池化层和全连接层。"
        )
        ctx = AgentContext(
            user_input=content,
            rag_results=[
                {"content": "卷积神经网络由 Yann LeCun 在 1998 年提出，是深度学习的基础模型。"},
                {"content": "CNN 包含卷积层、池化层和全连接层。"},
            ],
        )
        resp = await agent.execute(ctx)
        assert resp.success is True
        assert resp.agent_name == "cov_verifier"
        assert "cov_result" in resp.metadata
        assert "hallucination_rate" in resp.metadata

    @pytest.mark.asyncio
    async def test_metadata_has_claims(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(
            user_input="CNN 由 Yann LeCun 提出，包含卷积层和池化层。",
            rag_results=[
                {"content": "CNN 由 Yann LeCun 提出，包含卷积层和池化层。"},
            ],
        )
        resp = await agent.execute(ctx)
        claims = resp.metadata.get("claims", [])
        assert len(claims) >= 1

    @pytest.mark.asyncio
    async def test_agent_in_registry(self, mock_llm_client):
        """COVVerifierAgent 已注册到 AGENT_REGISTRY"""
        from backend.app.agents import AGENT_REGISTRY
        assert "cov_verifier" in AGENT_REGISTRY


# ================================================================
# 幻觉率计算
# ================================================================
class TestHallucinationRate:
    def test_zero_when_all_verified(self):
        from backend.app.agents.cov_verifier import COVResult, ClaimEvidence
        r = COVResult(
            original_content="test",
            evidences=[ClaimEvidence(i, f"c{i}", "verified", 0.9) for i in range(1, 6)],
        )
        assert r.hallucination_rate() == 0.0

    def test_full_when_all_refuted(self):
        from backend.app.agents.cov_verifier import COVResult, ClaimEvidence
        r = COVResult(
            original_content="test",
            evidences=[ClaimEvidence(i, f"c{i}", "refuted", 0.7) for i in range(1, 4)],
        )
        assert r.hallucination_rate() == 1.0

    def test_mixed(self):
        from backend.app.agents.cov_verifier import COVResult, ClaimEvidence
        r = COVResult(
            original_content="test",
            evidences=[
                ClaimEvidence(1, "c1", "verified", 0.9),
                ClaimEvidence(2, "c2", "verified", 0.85),
                ClaimEvidence(3, "c3", "uncertain", 0.3),
            ],
        )
        assert r.hallucination_rate() == pytest.approx(1/3, 0.01)
