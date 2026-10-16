"""
测试: IntentClassifier — LLM 意图分类兜底 (P1-8)

覆盖:
- classify() 解析 LLM 输出: 纯数组 / markdown包裹 / 文本内嵌
- 无效意图过滤 / 去重
- 空输入 / LLM失败 / 超时 降级
- orchestrator._llm_classify_intent 不再返回空列表
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.intent_classifier import (
    IntentClassifier,
    INTENT_DESCRIPTIONS,
    CLASSIFY_PROMPT,
    get_intent_classifier,
    reset_classifier,
)


# ================================================================
# Fixtures
# ================================================================
@pytest.fixture(autouse=True)
def _reset():
    reset_classifier()


@pytest.fixture
def mock_llm():
    """Mock LLM client — achat 返回可控文本"""
    client = MagicMock()
    client.achat = AsyncMock(return_value='["generate_doc", "generate_exercise"]')
    return client


@pytest.fixture
def classifier(mock_llm):
    return IntentClassifier(mock_llm)


# ================================================================
# 解析测试（不依赖 LLM）
# ================================================================
class TestParse:
    def test_pure_json_array(self, classifier):
        result = classifier._parse('["generate_doc", "tutoring"]')
        assert result == ["generate_doc", "tutoring"]

    def test_markdown_code_block(self, classifier):
        result = classifier._parse(
            '```json\n["plan_path", "generate_doc"]\n```'
        )
        assert result == ["plan_path", "generate_doc"]

    def test_text_with_embedded_array(self, classifier):
        result = classifier._parse(
            'The user wants: ["generate_doc", "generate_exercise"] and more.'
        )
        assert result == ["generate_doc", "generate_exercise"]

    def test_empty_array(self, classifier):
        result = classifier._parse("[]")
        assert result == []

    def test_single_intent(self, classifier):
        result = classifier._parse('["tutoring"]')
        assert result == ["tutoring"]

    def test_invalid_json_returns_empty(self, classifier):
        result = classifier._parse("这不是 JSON")
        assert result == []

    def test_empty_string(self, classifier):
        result = classifier._parse("")
        assert result == []


# ================================================================
# 验证测试
# ================================================================
class TestValidate:
    def test_filters_unknown_intents(self, classifier):
        result = classifier._validate(["generate_doc", "buy_coffee", "tutoring"])
        assert result == ["generate_doc", "tutoring"]

    def test_deduplicates(self, classifier):
        result = classifier._validate(["generate_doc", "generate_doc", "tutoring"])
        assert result == ["generate_doc", "tutoring"]

    def test_all_known_intents(self, classifier):
        result = classifier._validate(list(INTENT_DESCRIPTIONS.keys()))
        assert len(result) == len(INTENT_DESCRIPTIONS)

    def test_case_insensitive(self, classifier):
        result = classifier._validate(["Generate_Doc", "TUTORING", "Plan_Path"])
        assert "generate_doc" in result


# ================================================================
# classify 集成测试
# ================================================================
class TestClassify:
    @pytest.mark.asyncio
    async def test_returns_parsed_intents(self, classifier):
        intents = await classifier.classify("给我讲解CNN然后出几道题")
        assert "generate_doc" in intents
        assert "generate_exercise" in intents

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, classifier):
        intents = await classifier.classify("")
        assert intents == []

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self, mock_llm):
        mock_llm.achat = AsyncMock(side_effect=RuntimeError("API down"))
        classifier = IntentClassifier(mock_llm)
        intents = await classifier.classify("讲解CNN")
        assert intents == []  # 静默降级

    @pytest.mark.asyncio
    async def test_llm_timeout_returns_empty(self, mock_llm):
        import asyncio

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(10)
            return "[]"

        mock_llm.achat = AsyncMock(side_effect=slow_response)
        classifier = IntentClassifier(mock_llm)
        intents = await classifier.classify("讲解CNN", timeout=0.1)
        assert intents == []  # 超时降级


# ================================================================
# Prompt 模板测试
# ================================================================
class TestPromptTemplate:
    def test_prompt_includes_user_input(self):
        prompt = CLASSIFY_PROMPT.format(user_input="讲解CNN")
        assert "讲解CNN" in prompt
        assert "generate_doc" in prompt
        assert "tutoring" in prompt

    def test_prompt_includes_all_intent_descriptions(self):
        prompt = CLASSIFY_PROMPT.format(user_input="test")
        for key in INTENT_DESCRIPTIONS:
            assert key in prompt


# ================================================================
# orchestrator 集成测试
# ================================================================
class TestOrchestratorIntegration:
    @pytest.mark.asyncio
    async def test_llm_classify_no_longer_empty_stub(self, mock_llm_client):
        """orchestrator._llm_classify_intent 不再返回空列表"""
        from backend.app.services.intent_classifier import reset_classifier
        reset_classifier()

        mock_llm_client.achat = AsyncMock(
            return_value='["generate_doc", "tutoring"]'
        )
        from backend.app.agents.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(llm_client=mock_llm_client)

        intents = await orch._llm_classify_intent("讲解CNN的原理")
        assert len(intents) > 0
        # should be valid intents
        valid = set(INTENT_DESCRIPTIONS.keys())
        for i in intents:
            assert i in valid

    @pytest.mark.asyncio
    async def test_llm_failure_in_orchestrator(self, mock_llm_client):
        """LLM 失败时 orchestrator 不崩溃"""
        from backend.app.services.intent_classifier import reset_classifier
        reset_classifier()

        mock_llm_client.achat = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )
        from backend.app.agents.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(llm_client=mock_llm_client)

        intents = await orch._llm_classify_intent("讲解CNN")
        assert intents == []  # 静默失败
