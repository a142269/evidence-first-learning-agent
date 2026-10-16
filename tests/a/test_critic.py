"""
测试: Critic Agent — 4 维内容审查器 (v3 真实检查版)

覆盖:
- CriticVerdict / CriticIssue 数据模型 + evidence 字段
- FactualDimension: 结构完整性 + RAG 事实支撑度
- PedagogyDimension: 例子/类比/步骤/练习
- BloomDimension: 6 层认知层级匹配（关键词启发式 + Phase2 标注）
- CitationDimension: 内联引用/RAG 溯源
- CriticAgent.execute() 完整流程
- Strategy pattern 可插拔性
- 边界: 空/短/垃圾/无RAG/RAG不匹配
"""
from __future__ import annotations

import pytest


# ================================================================
# 模型测试
# ================================================================
class TestCriticVerdict:
    def test_passed_verdict(self):
        from backend.app.agents.critic_agent import CriticVerdict
        v = CriticVerdict(dimension="factual", passed=True, score=0.95)
        assert v.passed is True
        assert v.dimension == "factual"
        assert v.evidence == {}

    def test_verdict_with_evidence(self):
        from backend.app.agents.critic_agent import CriticVerdict
        v = CriticVerdict(
            dimension="factual", passed=True, score=0.85,
            evidence={"rag_overlap_ratio": 0.42, "content_terms_count": 15},
        )
        assert v.evidence["rag_overlap_ratio"] == 0.42

    def test_to_summary_includes_dimension(self):
        from backend.app.agents.critic_agent import CriticVerdict, CriticIssue
        v = CriticVerdict(
            dimension="pedagogy", passed=False, score=0.4,
            issues=[CriticIssue(severity="major", description="无例子")],
        )
        s = v.to_summary()
        assert "pedagogy" in s
        assert "FAIL" in s


class TestCriticIssue:
    def test_minimal(self):
        from backend.app.agents.critic_agent import CriticIssue
        i = CriticIssue(severity="minor", description="措辞可优化")
        assert i.suggestion is None

    def test_full(self):
        from backend.app.agents.critic_agent import CriticIssue
        i = CriticIssue(
            severity="major", description="事实错误",
            location="第2段", suggestion="应使用ReLU而非sigmoid",
        )
        assert "ReLU" in i.suggestion


# ================================================================
# FactualDimension — 结构 + RAG 事实支撑
# ================================================================
class TestFactualDimension:
    def test_empty_fails(self):
        from backend.app.agents.critic_agent import FactualDimension
        v = FactualDimension().evaluate("", {})
        assert v.passed is False

    def test_balanced_content_passes(self):
        from backend.app.agents.critic_agent import FactualDimension
        content = (
            "# 卷积神经网络\n\n"
            "卷积神经网络是一种深度学习架构。\n\n"
            "## 核心组成\n"
            "1. **卷积层**：提取局部特征\n"
            "2. **池化层**：下采样降维\n\n"
            "## 应用\nCNN在图像分类等任务上取得了显著成果。"
        )
        v = FactualDimension().evaluate(content, {})
        assert v.passed is True

    def test_junk_content_blocked(self):
        from backend.app.agents.critic_agent import FactualDimension
        v = FactualDimension().evaluate("ABC " * 200, {})
        assert v.passed is False

    def test_rag_overlap_high_passes(self):
        """RAG 中有匹配术语 → 事实支撑度高"""
        from backend.app.agents.critic_agent import FactualDimension
        content = (
            "# 卷积神经网络\n\n"
            "卷积神经网络通过卷积核提取特征，池化层降维。"
            "全连接层用于分类输出。ReLU激活函数增加非线性。"
        )
        context = {
            "rag_results": [
                {"content": "卷积神经网络是一种前馈神经网络，包含卷积层、池化层和全连接层。"
                 "卷积核用于提取局部特征，ReLU是非线性激活函数。"},
            ]
        }
        v = FactualDimension().evaluate(content, context)
        assert v.passed is True
        assert v.evidence.get("rag_overlap_ratio", 0) >= 0.15

    def test_rag_overlap_low_warns(self):
        """内容术语与 RAG 不重叠 → 警告"""
        from backend.app.agents.critic_agent import FactualDimension
        content = (
            "# 量子计算入门\n\n"
            "量子比特利用叠加态和纠缠态进行计算，"
            "量子门操作实现幺正变换。Grover算法加速搜索。"
        )
        context = {
            "rag_results": [
                {"content": "卷积神经网络是深度学习的基础模型。"},
            ]
        }
        v = FactualDimension().evaluate(content, context)
        # 量子术语与 CNN RAG 结果完全不重叠 → 应报警
        assert v.evidence.get("rag_overlap_ratio", 1.0) < 0.15
        # 至少有一个 RAG 相关的 issue 或建议
        has_rag_concern = any(
            "重叠" in i.description or "RAG" in str(i.suggestion or "")
            for i in v.issues
        ) or any("RAG" in s for s in v.suggestions)
        assert has_rag_concern, f"Expected RAG concern but got: issues={v.issues}, suggestions={v.suggestions}"

    def test_no_rag_no_penalty(self):
        """无 RAG 结果时不应扣事实分"""
        from backend.app.agents.critic_agent import FactualDimension
        content = "# 测试\n\n这是测试内容，内容足够长了。这里还要更多字。"
        v = FactualDimension().evaluate(content, {})
        # 不因缺少 RAG 而失败
        evidence = v.evidence
        assert evidence.get("rag_overlap_ratio") is None or evidence.get("note")


# ================================================================
# PedagogyDimension
# ================================================================
class TestPedagogyDimension:
    def test_has_examples_passes(self):
        from backend.app.agents.critic_agent import PedagogyDimension
        content = (
            "# Softmax\n\n"
            "Softmax 将 logits 转为概率。\n\n"
            "## 例子\n比如分类猫狗鸟，[2.0,1.0,0.1] → softmax → [0.66,0.24,0.10]。"
        )
        v = PedagogyDimension().evaluate(content, {})
        assert v.passed is True

    def test_no_examples_warns(self):
        from backend.app.agents.critic_agent import PedagogyDimension
        content = "Softmax 定义为 $\\sigma(z_i) = e^{z_i}/\\sum e^{z_j}$"
        v = PedagogyDimension().evaluate(content, {})
        assert v.passed is False or len(v.suggestions) > 0

    def test_has_analogy_scores_higher(self):
        from backend.app.agents.critic_agent import PedagogyDimension
        with_analogy = PedagogyDimension().evaluate(
            "过拟合就像死记硬背答案，遇到新题就不会做。", {},
        )
        without = PedagogyDimension().evaluate("过拟合是模型在训练集上表现好但泛化差。", {})
        assert with_analogy.score >= without.score


# ================================================================
# BloomDimension
# ================================================================
class TestBloomDimension:
    def test_definition_is_remember(self):
        from backend.app.agents.critic_agent import BloomDimension
        v = BloomDimension().evaluate(
            "ReLU定义为 f(x)=max(0,x)", {"target_bloom": "apply"},
        )
        assert v.passed is False

    def test_exercise_is_apply(self):
        from backend.app.agents.critic_agent import BloomDimension
        content = (
            "ReLU 定义为 f(x)=max(0,x)\n\n"
            "## 练习\n使用 PyTorch 实现 ReLU 并在 MNIST 上训练。"
        )
        v = BloomDimension().evaluate(content, {"target_bloom": "apply"})
        assert v.passed is True

    def test_evidence_notes_method(self):
        from backend.app.agents.critic_agent import BloomDimension
        v = BloomDimension().evaluate("定义CNN", {})
        assert "keyword-heuristic" in v.evidence.get("method", "")


# ================================================================
# CitationDimension
# ================================================================
class TestCitationDimension:
    def test_has_reference_passes(self):
        from backend.app.agents.critic_agent import CitationDimension
        content = "Dropout 由 Srivastava et al. (2014) 提出，参考文献[1]。"
        v = CitationDimension().evaluate(content, {"rag_results": [{"content": "Dropout..."}]})
        assert v.passed is True

    def test_no_reference_warns(self):
        from backend.app.agents.critic_agent import CitationDimension
        v = CitationDimension().evaluate("Dropout随机丢弃神经元。", {})
        if not v.passed:
            assert any("引用" in s or "来源" in s for s in v.suggestions)


# ================================================================
# CriticAgent 集成
# ================================================================
class TestCriticAgent:
    @pytest.fixture
    def agent(self, mock_llm_client):
        from backend.app.agents.critic_agent import CriticAgent
        return CriticAgent(llm_client=mock_llm_client)

    @pytest.fixture
    def context(self):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(
            user_input=(
                "# CNN 详解\n\n"
                "卷积神经网络由 Yann LeCun 提出。\n\n"
                "## 例子\n人脸识别中，底层提取边缘，高层提取器官。\n\n"
                "## 练习\n用 PyTorch 实现 LeNet-5。"
            ),
            extra={"target_bloom": "apply"},
            rag_results=[
                {"content": "CNN由Yann LeCun提出，包含卷积层池化层全连接层。"},
            ],
        )
        return ctx

    @pytest.mark.asyncio
    async def test_execute_success(self, agent, context):
        resp = await agent.execute(context)
        assert resp.success is True
        assert resp.agent_name == "critic"

    @pytest.mark.asyncio
    async def test_all_four_dimensions(self, agent, context):
        resp = await agent.execute(context)
        verdicts = resp.metadata.get("verdicts", [])
        dims = {v.dimension for v in verdicts}
        assert dims == {"factual", "pedagogy", "bloom", "citation"}

    @pytest.mark.asyncio
    async def test_empty_content(self, agent):
        from backend.app.agents.base import AgentContext
        resp = await agent.execute(AgentContext(user_input=""))
        assert resp.success is False

    @pytest.mark.asyncio
    async def test_custom_dimensions(self, mock_llm_client):
        from backend.app.agents.critic_agent import (
            CriticAgent, FactualDimension, PedagogyDimension, BloomDimension,
        )
        from backend.app.agents.base import AgentContext
        agent = CriticAgent(
            llm_client=mock_llm_client,
            dimensions=[FactualDimension(), PedagogyDimension(), BloomDimension()],
        )
        ctx = AgentContext(user_input="# 测试\n足够长的测试内容。这里还有更多字来填充。")
        resp = await agent.execute(ctx)
        assert resp.metadata.get("dimension_count") == 3

    @pytest.mark.asyncio
    async def test_overall_score_range(self, agent, context):
        resp = await agent.execute(context)
        score = resp.metadata.get("overall_score", -1)
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_content_to_review_fallback(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(
            user_input="不是审查内容",
            extra={
                "content_to_review": (
                    "# 实际审查内容\n\n这应该是被审查的内容。"
                    "这是更多内容来确保长度足够通过基本检查。"
                ),
            },
        )
        resp = await agent.execute(ctx)
        assert resp.success is True


# ================================================================
# 可插拔性
# ================================================================
class TestPluggability:
    def test_custom_dimension(self):
        from backend.app.agents.critic_agent import (
            CriticDimension, CriticVerdict, CriticIssue,
        )

        class LengthCheck(CriticDimension):
            name = "length"

            def evaluate(self, content, context):
                if len(content) < 100:
                    return CriticVerdict(
                        dimension="length", passed=False, score=0.0,
                        issues=[CriticIssue(severity="major", description="过短")],
                        suggestions=["扩展"],
                    )
                return CriticVerdict(dimension="length", passed=True, score=1.0)

        assert LengthCheck().evaluate("hi", {}).passed is False
        assert LengthCheck().evaluate("x" * 200, {}).passed is True
