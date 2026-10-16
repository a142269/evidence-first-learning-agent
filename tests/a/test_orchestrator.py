"""
测试: Agent 协同编排器 (orchestrator.py)

覆盖:
- 意图分类（关键词匹配 / 空输入 / 兜底）
- 任务规划（优先级排序 / 未知意图忽略）
- Agent 实例懒加载与注册表回退
- 单 Agent 执行（成功 / 失败）
- process_turn 完整流程
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.app.agents.orchestrator import (
    AgentOrchestrator,
    AgentStatus,
    AgentTask,
    AgentResult,
    AGENT_ROUTING,
)
from backend.app.agents.base import AgentContext, AgentResponse


# ================================================================
# Fixtures
# ================================================================
@pytest.fixture
def mock_agent_registry():
    """模拟 Agent 注册表，含 profile / course_expert / tutor"""
    profile_mock = MagicMock()
    profile_mock_instance = MagicMock()
    profile_mock_instance.name = "profile"
    profile_mock.return_value = profile_mock_instance
    profile_mock_instance.execute = AsyncMock(
        return_value=AgentResponse(
            agent_name="profile",
            success=True,
            content="画像已更新",
        )
    )

    course_mock = MagicMock()
    course_mock_instance = MagicMock()
    course_mock_instance.name = "course_expert"
    course_mock.return_value = course_mock_instance
    course_mock_instance.execute = AsyncMock(
        return_value=AgentResponse(
            agent_name="course_expert",
            success=True,
            content="# CNN 讲解\n卷积神经网络是...",
        )
    )

    tutor_mock = MagicMock()
    tutor_mock_instance = MagicMock()
    tutor_mock_instance.name = "tutor"
    tutor_mock.return_value = tutor_mock_instance
    tutor_mock_instance.execute = AsyncMock(
        return_value=AgentResponse(
            agent_name="tutor",
            success=True,
            content="你可以这样理解...",
        )
    )

    return {
        "profile": profile_mock,
        "course_expert": course_mock,
        # 别名与真实 AGENT_REGISTRY 对齐 (doc_gen / exercise 在生产中
        # 分别映射到 CourseExpertAgent / QuizGeneratorAgent；
        # 此处统一别名为 course_mock，使 process_turn 路由可解析)
        "doc_gen": course_mock,
        "exercise": course_mock,
        "tutor": tutor_mock,
    }


@pytest.fixture
def orchestrator(mock_llm_client, mock_agent_registry):
    """返回完整配置的 Orchestrator"""
    return AgentOrchestrator(llm_client=mock_llm_client, agent_registry=mock_agent_registry)


# ================================================================
# 意图分类测试
# ================================================================
class TestClassifyIntent:
    """_classify_intent 方法测试"""

    @pytest.mark.asyncio
    async def test_document_intent(self, orchestrator):
        """包含'讲解'关键词 → 匹配 generate_doc"""
        intents = await orchestrator._classify_intent("请给我讲解一下CNN", {})
        assert "generate_doc" in intents
        assert "profile_update" in intents  # 始终包含

    @pytest.mark.asyncio
    async def test_exercise_intent(self, orchestrator):
        """包含'练习'关键词 → 匹配 generate_exercise"""
        intents = await orchestrator._classify_intent("给我出几道练习题", {})
        assert "generate_exercise" in intents

    @pytest.mark.asyncio
    async def test_mindmap_intent(self, orchestrator):
        """包含'思维导图'关键词 → 匹配 generate_mindmap"""
        intents = await orchestrator._classify_intent("帮我画一张思维导图", {})
        assert "generate_mindmap" in intents

    @pytest.mark.asyncio
    async def test_path_intent(self, orchestrator):
        """包含'学习计划'关键词 → 匹配 plan_path"""
        intents = await orchestrator._classify_intent("给我做个学习计划", {})
        assert "plan_path" in intents

    @pytest.mark.asyncio
    async def test_tutoring_intent(self, orchestrator):
        """包含'不太懂'关键词 → 匹配 tutoring"""
        intents = await orchestrator._classify_intent("CNN的卷积层我不太懂", {})
        assert "tutoring" in intents

    @pytest.mark.asyncio
    async def test_evaluation_intent(self, orchestrator):
        """包含'评估'关键词 → 匹配 evaluation"""
        intents = await orchestrator._classify_intent("帮我评估一下我的学习水平", {})
        assert "evaluation" in intents

    @pytest.mark.asyncio
    async def test_multiple_intents(self, orchestrator):
        """一个输入可匹配多个意图"""
        intents = await orchestrator._classify_intent("给我讲解CNN然后出几道题", {})
        assert "generate_doc" in intents
        assert "generate_exercise" in intents

    @pytest.mark.asyncio
    async def test_profile_always_first(self, orchestrator):
        """profile_update 始终在意图列表第一位"""
        intents = await orchestrator._classify_intent("出题 评估", {})
        assert intents[0] == "profile_update"

    @pytest.mark.asyncio
    async def test_empty_input(self, orchestrator):
        """空输入走 Plan D 3.1 兜底：profile_update + tutoring"""
        intents = await orchestrator._classify_intent("", {})
        # Plan D · 3.1: LLM 兜底也失败时强制补 tutoring
        assert intents == ["profile_update", "tutoring"]

    @pytest.mark.asyncio
    async def test_no_match_triggers_llm_fallback(self, orchestrator):
        """Plan D · Review v1 — "今天天气怎么样" 已被 out_of_scope 接住，
        命中 out_of_scope 时不再追加 tutoring 兜底、也不再强加 profile_update。"""
        intents = await orchestrator._classify_intent("今天天气怎么样", {})
        # "天气" 是 out_of_scope 关键词 → 仅路由到 safe_decline
        assert intents == ["out_of_scope"]
        assert "tutoring" not in intents  # 不再追加 tutoring
        assert "profile_update" not in intents  # out_of_scope 不污染画像


# ================================================================
# 任务规划测试
# ================================================================
class TestPlanTasks:
    """_plan_tasks 方法测试"""

    def test_single_intent(self, orchestrator):
        """单个意图 → 单个任务"""
        tasks = orchestrator._plan_tasks(["generate_doc"], {})
        assert len(tasks) == 1
        assert tasks[0].agent_name == "doc_gen"
        assert tasks[0].action == "generate_doc"

    def test_multiple_intents_sorted_by_priority(self, orchestrator):
        """多个意图按 priority 排序"""
        tasks = orchestrator._plan_tasks(
            ["generation_evaluation", "generate_doc", "profile_update"], {}
        )
        # profile_update prio=1 在前，generate_doc prio=2 在后，evaluation prio=3 最后
        assert tasks[0].priority <= tasks[-1].priority

    def test_unknown_intent_skipped(self, orchestrator):
        """未知意图被安全跳过"""
        tasks = orchestrator._plan_tasks(["non_existent_intent"], {})
        assert len(tasks) == 0

    def test_task_ids_are_unique(self, orchestrator):
        """每个 task 的 task_id 唯一"""
        tasks = orchestrator._plan_tasks(
            ["profile_update", "generate_doc", "generate_exercise"], {}
        )
        ids = [t.task_id for t in tasks]
        assert len(ids) == len(set(ids))


# ================================================================
# 多 @ 指令拆分测试
# ================================================================
class TestRoleRequestExtraction:
    PROMPT = (
        "请 @智狐 @智灵 @阿匠 @小龙 @团团 分工协作：\n"
        "1. @智狐 设计 3 天路径，每天两个目标；\n"
        "2. @智灵 推导 Self-Attention 并标注 shape；\n"
        "3. @阿匠 生成高级思维导图和可运行代码；\n"
        "4. @小龙 生成 12 道分层题；\n"
        "5. @团团 依据画像评估可行性。"
    )

    @pytest.mark.parametrize(
        ("agent_name", "expected"),
        [
            ("path_planner", "设计 3 天路径，每天两个目标"),
            ("tutor", "推导 Self-Attention 并标注 shape"),
            ("doc_gen", "生成高级思维导图和可运行代码"),
            ("exercise", "生成 12 道分层题"),
            ("evaluator", "依据画像评估可行性"),
        ],
    )
    def test_each_agent_receives_only_its_numbered_directive(
        self, agent_name, expected,
    ):
        directive = AgentOrchestrator._extract_role_request(
            self.PROMPT, agent_name,
        )
        assert directive.rstrip("；。") == expected
        assert directive.count("@") == 0

    def test_profile_keeps_full_collaboration_request(self):
        assert AgentOrchestrator._extract_role_request(self.PROMPT, "profile") == self.PROMPT


# ================================================================
# Agent 实例管理测试
# ================================================================
class TestAgentLookup:
    """_get_or_create_agent 方法测试"""

    def test_registered_agent(self, orchestrator):
        """注册表中的 Agent 可被创建"""
        agent = orchestrator._get_or_create_agent("course_expert")
        assert agent is not None
        assert agent.name == "course_expert"

    def test_unregistered_falls_back_to_tutor(self, orchestrator):
        """未注册 Agent 回退到 tutor"""
        agent = orchestrator._get_or_create_agent("non_existent")
        # 回退到 tutor
        assert agent.name == "tutor"

    def test_cached_instance(self, orchestrator):
        """同一 Agent 被缓存，不重复创建"""
        a1 = orchestrator._get_or_create_agent("course_expert")
        a2 = orchestrator._get_or_create_agent("course_expert")
        assert a1 is a2


# ================================================================
# Agent 执行测试
# ================================================================
class TestRunAgent:
    """_run_agent 方法测试"""

    @pytest.mark.asyncio
    async def test_success(self, orchestrator):
        """Agent 执行成功"""
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="讲解 CNN", session_id="s1")
        task = AgentTask(
            task_id="task_0",
            agent_name="course_expert",
            action="generate_doc",
            input_data={},
            priority=2,
        )
        resp = await orchestrator._run_agent(task, ctx)
        assert resp.success is True
        assert resp.agent_name == "course_expert"

    @pytest.mark.asyncio
    async def test_failure_caught(self, orchestrator):
        """Agent 执行异常被捕获，返回 error"""
        from backend.app.agents.base import AgentContext

        # 让 Agent 抛出异常
        orchestrator._agent_instances.clear()
        agent_cls = orchestrator.agent_registry["course_expert"]
        agent_cls.return_value.execute = AsyncMock(side_effect=RuntimeError("LLM 超时"))

        ctx = AgentContext(user_input="讲解", session_id="s1")
        task = AgentTask(
            task_id="task_0",
            agent_name="course_expert",
            action="generate_doc",
            input_data={},
            priority=2,
        )
        resp = await orchestrator._run_agent(task, ctx)
        assert resp.success is False
        assert "LLM 超时" in resp.error

    @pytest.mark.asyncio
    async def test_context_not_mutated(self, orchestrator):
        """Agent 执行不污染原始 context"""
        from backend.app.agents.base import AgentContext

        original = AgentContext(
            user_input="讲解 CNN",
            session_id="s1",
            profile={"key": "value"},
            extra={"action": "original"},
        )
        task = AgentTask(
            task_id="task_0",
            agent_name="course_expert",
            action="generate_doc",
            input_data={},
            priority=2,
        )
        await orchestrator._run_agent(task, original)
        # 原始 context 不应被修改
        assert original.extra.get("action") == "original"
        assert original.profile["key"] == "value"


# ================================================================
# process_turn 完整流程测试
# ================================================================
class TestProcessTurn:
    """process_turn 方法测试"""

    @pytest.mark.asyncio
    async def test_single_agent_turn(self, orchestrator):
        """一轮对话触发单个 Agent"""
        results = await orchestrator.process_turn(
            user_input="给我讲解CNN",
            profile={},
            context={"session_id": "test"},
        )
        assert len(results) >= 1
        # 至少包含 profile agent
        profile_results = [r for r in results.values() if r.agent_name == "profile"]
        assert len(profile_results) >= 1

    @pytest.mark.asyncio
    async def test_multi_agent_turn(self, orchestrator):
        """触发多个 Agent 并行执行"""
        results = await orchestrator.process_turn(
            user_input="给我讲解CNN然后出几道练习题",
            profile={},
            context={"session_id": "test"},
        )
        # 应该有 profile + doc_gen + exercise
        agent_names = [r.agent_name for r in results.values()]
        assert "profile" in agent_names
        assert "doc_gen" in agent_names
        assert "exercise" in agent_names
        # 所有结果都是成功的
        for r in results.values():
            assert r.success is True

    @pytest.mark.asyncio
    async def test_result_keys_are_task_ids(self, orchestrator):
        """返回 dict 的 key 是 task_id"""
        results = await orchestrator.process_turn(
            user_input="讲解 CNN",
            profile={},
            context={},
        )
        for key in results:
            assert key.startswith("task_")


# ================================================================
# 路由表完整性测试
# ================================================================
class TestRoutingTable:
    """AGENT_ROUTING 表结构验证"""

    def test_all_intents_have_required_fields(self):
        """每个路由条目必须有 agent / trigger / priority"""
        for intent, route in AGENT_ROUTING.items():
            assert "agent" in route, f"Missing 'agent' in {intent}"
            assert "trigger" in route, f"Missing 'trigger' in {intent}"
            assert "priority" in route, f"Missing 'priority' in {intent}"
            assert isinstance(route["priority"], int)

    def test_at_least_5_intent_types(self):
        """至少有 5 个意图类型（保障 5+ 类资源生成）"""
        assert len(AGENT_ROUTING) >= 5

    def test_out_of_scope_routes_to_safe_decline(self):
        """Plan D · Review v1 — out_of_scope 必须路由到 safe_decline Agent"""
        assert "out_of_scope" in AGENT_ROUTING
        route = AGENT_ROUTING["out_of_scope"]
        assert route["agent"] == "safe_decline"
        assert route["priority"] == 0  # 越界类最低优先级，跳过重量级流程


# ============================================================
# Plan D · Review v1 — out_of_scope 行为测试
# ============================================================
class TestOutOfScopeIntent:
    """Plan D · Review v1 — 教学边界守门"""

    @pytest.mark.asyncio
    async def test_chitchat_weather_routes_to_safe_decline(self, orchestrator):
        """"今天天气怎么样" → out_of_scope，不再追加 tutoring"""
        intents = await orchestrator._classify_intent("今天天气怎么样", {})
        assert intents == ["out_of_scope"]
        assert "tutoring" not in intents
        assert "profile_update" not in intents

    @pytest.mark.asyncio
    async def test_chitchat_id_question_no_profile_pollution(self, orchestrator):
        """"你是谁" → out_of_scope，不更新画像"""
        intents = await orchestrator._classify_intent("你是谁", {})
        assert intents == ["out_of_scope"]
        assert "profile_update" not in intents  # 关键：闲聊不污染画像

    @pytest.mark.asyncio
    async def test_chitchat_time_routes_correctly(self, orchestrator):
        """"几点了" → out_of_scope"""
        intents = await orchestrator._classify_intent("现在几点了", {})
        assert intents == ["out_of_scope"]

    @pytest.mark.asyncio
    async def test_sensitive_keyword_routes_to_safe_decline(self, orchestrator):
        """敏感词（演示现场试探）→ out_of_scope 硬拒"""
        intents = await orchestrator._classify_intent("毒品怎么买", {})
        assert intents == ["out_of_scope"]

    @pytest.mark.asyncio
    async def test_exit_command_routes_to_safe_decline(self, orchestrator):
        """"退出"类指令 → out_of_scope（不调教学 Agent）"""
        intents = await orchestrator._classify_intent("不聊了，退出", {})
        assert intents == ["out_of_scope"]

    @pytest.mark.asyncio
    async def test_normal_learning_question_not_out_of_scope(self, orchestrator):
        """"什么是自注意力" 仍走 tutoring，不被误判"""
        intents = await orchestrator._classify_intent("什么是自注意力", {})
        assert "out_of_scope" not in intents
        assert "tutoring" in intents

    @pytest.mark.asyncio
    async def test_normal_question_not_out_of_scope(self, orchestrator):
        """"帮我整理一下 CNN" 仍走 generate_doc"""
        intents = await orchestrator._classify_intent("帮我整理一下 CNN", {})
        assert "out_of_scope" not in intents
        assert "generate_doc" in intents
