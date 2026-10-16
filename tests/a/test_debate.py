"""
测试: Debate Moderator — Multi-Agent Debate 协调器 (v3 可注入版)

覆盖:
- should_debate() 路由判决
- DebateRound / DebateState 数据模型
- orchestrate_debate() 辩论流程（可注入 critic_agent）
- 收敛检测真正 break
- DebateModeratorAgent.execute() 真正运行辩论
- 边界: Expert 失败 / 空内容 / max_rounds 耗尽
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.app.agents.base import AgentContext, AgentResponse
from backend.app.agents.critic_agent import CriticVerdict, CriticIssue


# ================================================================
# should_debate
# ================================================================
class TestShouldDebate:
    def test_doc_eligible(self):
        from backend.app.agents.debate_moderator import should_debate
        assert should_debate("generate_doc") is True

    def test_exercise_eligible(self):
        from backend.app.agents.debate_moderator import should_debate
        assert should_debate("generate_exercise") is True

    def test_tutoring_eligible(self):
        from backend.app.agents.debate_moderator import should_debate
        assert should_debate("tutoring") is True

    def test_profile_not_eligible(self):
        from backend.app.agents.debate_moderator import should_debate
        assert should_debate("profile_update") is False

    def test_skip_context(self):
        from backend.app.agents.debate_moderator import should_debate
        assert should_debate("generate_doc", {"skip_debate": True}) is False


# ================================================================
# 模型测试
# ================================================================
class TestDebateRound:
    def test_basic(self):
        from backend.app.agents.debate_moderator import DebateRound
        resp = AgentResponse(agent_name="e", success=True, content="x")
        rd = DebateRound(round_num=1, expert_response=resp, critic_score=85, critic_passed=True)
        assert rd.round_num == 1
        assert rd.critic_passed is True


# ================================================================
# Mock 工厂
# ================================================================
def _make_mock_critic(first_pass: bool = False):
    """创建 mock Critic Agent: 根据内容长度决定 pass/fail"""
    agent = MagicMock()
    agent.name = "critic"

    async def execute(ctx):
        content = ctx.extra.get("content_to_review", "")
        passed = first_pass or len(content) > 100
        score = 0.9 if passed else 0.3
        return AgentResponse(
            agent_name="critic", success=True,
            content="PASS" if passed else "FAIL",
            metadata={
                "verdicts": [
                    CriticVerdict(
                        dimension="factual", passed=passed, score=score,
                        issues=[] if passed else [
                            CriticIssue(severity="major", description="内容过短"),
                        ],
                        suggestions=[] if passed else ["扩展内容"],
                    )
                ],
                "overall_passed": passed,
                "overall_score": score,
            },
        )

    agent.execute = AsyncMock(side_effect=execute)
    return agent


def _make_mock_expert(content_on_revision: bool = True):
    """创建 mock Expert: 第1轮短内容，修订轮长内容"""
    agent = MagicMock()
    agent.name = "course_expert"
    agent.llm = MagicMock()

    async def execute(ctx):
        is_rev = ctx.extra.get("is_revision", False) if hasattr(ctx, "extra") else False
        if is_rev and content_on_revision:
            return AgentResponse(
                agent_name="course_expert", success=True,
                content=(
                    "# CNN 详解\n\n## 定义\n"
                    "卷积神经网络(CNN)由 Yann LeCun 提出...\n\n"
                    "## 例子\n人脸识别中底层提取边缘...\n\n"
                    "## 练习\n用 PyTorch 实现 LeNet-5 并在 CIFAR-10 上训练。"
                ),
            )
        return AgentResponse(
            agent_name="course_expert", success=True,
            content="CNN 是一种神经网络。",
        )

    agent.execute = AsyncMock(side_effect=execute)
    return agent


# ================================================================
# orchestrate_debate 集成测试
# ================================================================
class TestOrchestrateDebate:
    @pytest.mark.asyncio
    async def test_fail_then_pass_two_rounds(self):
        """第1轮短内容不通过 → 第2轮修订通过"""
        from backend.app.agents.debate_moderator import orchestrate_debate

        expert = _make_mock_expert(content_on_revision=True)
        critic = _make_mock_critic(first_pass=False)

        ctx = AgentContext(
            user_input="讲解 CNN", session_id="test-001",
            extra={"target_bloom": "apply"},
        )
        result = await orchestrate_debate(
            expert_agent=expert, expert_context=ctx,
            critic_agent=critic, max_rounds=2, session_id="test-001",
        )
        assert result["debate_rounds"] == 2
        # mock critic 返回 overall_score=0.9 (critic 0-1 约定),
        # debate 内部按 0-100 整数刻度归一化 (与 PASS_THRESHOLD=75 一致),
        # 故 best_score=90
        assert result["best_score"] == 90
        assert "第 2 轮通过" in result["verdict"]

    @pytest.mark.asyncio
    async def test_pass_first_round(self):
        """内容质量高 → 第1轮通过"""
        from backend.app.agents.debate_moderator import orchestrate_debate

        expert = _make_mock_expert(content_on_revision=True)
        # expert 首次返回短内容("CNN是一种神经网络", <100字)
        # 需要让它首次就返回长内容
        good_expert = MagicMock()
        good_expert.name = "course_expert"
        good_expert.llm = MagicMock()
        good_expert.execute = AsyncMock(return_value=AgentResponse(
            agent_name="course_expert", success=True,
            content=(
                "# CNN 详解\n\n## 定义\n"
                "卷积神经网络(CNN)是由 Yann LeCun 在 1998 年提出的深度前馈神经网络。\n\n"
                "## 例子\n例如在手写数字识别中，LeNet-5 达到了 99% 的准确率。\n\n"
                "## 练习\n使用 PyTorch 实现一个简单的 CNN 并在 MNIST 上训练。"
            ),
        ))
        critic = _make_mock_critic(first_pass=True)

        ctx = AgentContext(user_input="讲解 CNN", session_id="test")
        result = await orchestrate_debate(
            expert_agent=good_expert, expert_context=ctx,
            critic_agent=critic, max_rounds=2, session_id="test",
        )
        assert result["debate_rounds"] == 1

    @pytest.mark.asyncio
    async def test_debate_starts_convergence_tracker_session(self):
        from backend.app.agents.debate_moderator import orchestrate_debate
        from backend.app.services.debate.convergence_tracker import (
            get_convergence_tracker,
            reset_tracker,
        )

        reset_tracker()
        sid = "tracker-session"
        expert = _make_mock_expert(content_on_revision=True)
        critic = _make_mock_critic(first_pass=True)
        ctx = AgentContext(user_input="讲解 CNN", session_id=sid)

        await orchestrate_debate(
            expert_agent=expert,
            expert_context=ctx,
            critic_agent=critic,
            max_rounds=2,
            session_id=sid,
        )

        analysis = get_convergence_tracker().analyze(sid)
        assert analysis.total_rounds == 1

    @pytest.mark.asyncio
    async def test_expert_failure_ends_debate(self):
        """Expert 抛出异常 → 辩论终止但不崩溃"""
        from backend.app.agents.debate_moderator import orchestrate_debate

        failing_expert = MagicMock()
        failing_expert.name = "failing"
        failing_expert.llm = MagicMock()
        failing_expert.execute = AsyncMock(
            return_value=AgentResponse(
                agent_name="failing", success=False, error="LLM超时",
            )
        )

        ctx = AgentContext(user_input="讲解 CNN", session_id="test")
        result = await orchestrate_debate(
            expert_agent=failing_expert, expert_context=ctx,
            critic_agent=_make_mock_critic(), max_rounds=2,
        )
        # 应优雅降级
        assert result is not None

    @pytest.mark.asyncio
    async def test_convergence_detection_breaks(self):
        """评分变化 < 5% → 收敛 break"""
        from backend.app.agents.debate_moderator import orchestrate_debate

        # Expert 每轮返回相同内容 → Critic 给相同分数 → 收敛
        expert = MagicMock()
        expert.name = "course_expert"
        expert.llm = MagicMock()
        expert.execute = AsyncMock(return_value=AgentResponse(
            agent_name="course_expert", success=True,
            content=(
                "# 内容\n\n这是足够长的内容。它还包含例子比如某个具体场景。"
                "还有练习题来巩固知识。内容长度足够通过所有检查。"
            ),
        ))

        # Critic 始终给相同不通过的分数 → 第2轮应该收敛
        critic = MagicMock()
        critic.name = "critic"

        call_count = [0]

        async def critic_execute(ctx):
            call_count[0] += 1
            return AgentResponse(
                agent_name="critic", success=True, content="FAIL",
                metadata={
                    "verdicts": [
                        CriticVerdict(
                            dimension="factual", passed=False, score=0.45,
                            issues=[CriticIssue(severity="major", description="问题A")],
                            suggestions=["修复"],
                        )
                    ],
                    "overall_passed": False,
                    "overall_score": 0.45,
                },
            )

        critic.execute = AsyncMock(side_effect=critic_execute)

        ctx = AgentContext(user_input="讲解", session_id="test")
        result = await orchestrate_debate(
            expert_agent=expert, expert_context=ctx,
            critic_agent=critic, max_rounds=5,
        )
        # 收敛检测应提前终止，不会跑满 5 轮
        assert result["debate_rounds"] < 5
        assert "收敛" in result.get("verdict", "")

    @pytest.mark.asyncio
    async def test_max_rounds_exhausted_takes_best(self):
        """max_rounds 耗尽 → 取最优版本"""
        from backend.app.agents.debate_moderator import orchestrate_debate

        expert = _make_mock_expert(content_on_revision=True)
        critic = _make_mock_critic(first_pass=False)

        ctx = AgentContext(user_input="讲解 CNN", session_id="test")
        result = await orchestrate_debate(
            expert_agent=expert, expert_context=ctx,
            critic_agent=critic, max_rounds=2, session_id="test",
        )
        assert result["debate_rounds"] >= 1
        assert result["best_score"] > 0


# ================================================================
# DebateModeratorAgent.execute() — 不再是 stub
# ================================================================
class TestDebateModeratorAgent:
    def test_name_and_description(self, mock_llm_client):
        from backend.app.agents.debate_moderator import DebateModeratorAgent
        agent = DebateModeratorAgent(llm_client=mock_llm_client)
        assert agent.name == "debate_moderator"
        assert "Expert" in agent.description

    @pytest.mark.asyncio
    async def test_execute_skip_debate(self, mock_llm_client):
        """context 中 skip_debate=True → 跳过辩论"""
        from backend.app.agents.debate_moderator import DebateModeratorAgent
        agent = DebateModeratorAgent(llm_client=mock_llm_client)
        ctx = AgentContext(
            user_input="讲解 CNN", session_id="test",
            extra={"skip_debate": True},
        )
        resp = await agent.execute(ctx)
        assert resp.success is True
        assert "跳过" in resp.content

    @pytest.mark.asyncio
    async def test_execute_no_expert_agent(self, mock_llm_client):
        """没有提供 expert_agent → 错误"""
        from backend.app.agents.debate_moderator import DebateModeratorAgent
        agent = DebateModeratorAgent(llm_client=mock_llm_client)
        ctx = AgentContext(
            user_input="讲解 CNN", session_id="test",
            extra={"expert_name": "non_existent"},
        )
        resp = await agent.execute(ctx)
        assert resp.success is False
        assert "未找到" in resp.error

    @pytest.mark.asyncio
    async def test_execute_runs_real_debate(self, mock_llm_client):
        """execute() 真正运行辩论流程"""
        from backend.app.agents.debate_moderator import DebateModeratorAgent

        agent = DebateModeratorAgent(llm_client=mock_llm_client, max_rounds=2)

        # 构造 expert mock
        expert = MagicMock()
        expert.name = "course_expert"
        expert.llm = mock_llm_client
        expert.execute = AsyncMock(return_value=AgentResponse(
            agent_name="course_expert", success=True,
            content=(
                "# CNN 详解\n\n"
                "卷积神经网络由 Yann LeCun 提出。核心思想是局部感受野和权值共享。\n\n"
                "## 例子\n"
                "例如在图像识别任务中，底层检测边缘，中层检测纹理，高层检测语义。\n\n"
                "## 练习\n"
                "使用 PyTorch 实现一个 LeNet-5 网络并在 MNIST 上训练。"
            ),
        ))

        ctx = AgentContext(
            user_input="讲解 CNN", session_id="test-debate",
            extra={
                "expert_agent": expert,
                "target_bloom": "apply",
            },
        )
        resp = await agent.execute(ctx)
        assert resp.success is True
        assert "debate_rounds" in resp.metadata
        assert resp.metadata["debate_applied"] is True
