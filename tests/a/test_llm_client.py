"""
测试: LLM 客户端 (llm_client.py)

覆盖:
- Mock 模式下各 Agent 类型的回复特征
- Mock 模式 chat_stream 分块输出
- achat 异步聚合
- 不同 Agent system_prompt 触发不同 mock 分支
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.app.core.llm_client import LLMClient
from backend.app.core.config import AppConfig


# ================================================================
# Fixtures
# ================================================================
@pytest.fixture
def mock_llm():
    """返回 Mock 模式下的 LLMClient（强制无 provider）"""
    config = AppConfig.from_env()
    config.llm.spark_app_id = ""
    config.llm.openai_base_url = ""
    config.llm.openai_api_key = ""
    return LLMClient(config=config.llm)


def _msgs(sys_hint: str, user_text: str):
    """快捷构建 messages 列表"""
    return [
        {"role": "system", "content": f"你是一个{sys_hint}"},
        {"role": "user", "content": user_text},
    ]


# ================================================================
# Mock 模式：各 Agent 类型回复
# ================================================================
class TestMockChatByAgent:
    """_mock_chat 根据 system_prompt 中 Agent 身份返回不同文案"""

    def test_profile_agent(self, mock_llm):
        """画像 Agent → 返回 profile_update JSON"""
        text = mock_llm._mock_chat(_msgs("画像分析师", "我最近学习有点吃力"))
        assert "profile_update" in text
        assert "knowledge_base" in text
        assert "learning_preference" in text

    def test_quiz_generator(self, mock_llm):
        """出题专家 → 返回 quiz_json"""
        text = mock_llm._mock_chat(_msgs("出题专家", "针对CNN出题"))
        assert "quiz_json" in text
        assert "选择题" in text

    def test_mindmap_agent(self, mock_llm):
        """思维导图请求 → 返回 mermaid mindmap"""
        text = mock_llm._mock_chat(_msgs("多模态生成师", "画一张思维导图"))
        assert "mermaid" in text
        assert "mindmap" in text

    def test_path_planner(self, mock_llm):
        """路径规划师 → 返回 learning_path"""
        text = mock_llm._mock_chat(_msgs("路径规划师", "帮我规划学习路径"))
        assert "learning_path" in text
        assert "prerequisites" in text

    def test_evaluator(self, mock_llm):
        """评估师 → 返回 evaluation_result"""
        text = mock_llm._mock_chat(_msgs("评估", "评估我的水平"))
        assert "evaluation_result" in text
        assert "overall_score" in text

    def test_reviewer(self, mock_llm):
        """审查师 → 返回 review_result"""
        text = mock_llm._mock_chat(_msgs("质量审查员", "检查内容质量"))
        assert "review_result" in text

    def test_course_expert(self, mock_llm):
        """课程专家 → 返回讲解"""
        text = mock_llm._mock_chat(_msgs("课程专家 / 教授", "讲解 CNN"))
        assert "核心原理" in text or "## 一句话定义" in text

    def test_tutor(self, mock_llm):
        """导师 → 返回"一句话"开头"""
        text = mock_llm._mock_chat(_msgs("智能导师", "什么是CNN"))
        assert "## 详细展开" in text or "形象类比" in text

    def test_default_fallback(self, mock_llm):
        """无法识别 Agent 身份 → 返回默认演示提示"""
        text = mock_llm._mock_chat(
            [{"role": "user", "content": "你好"}]
        )
        assert "演示模式" in text or "Mock" in text


# ================================================================
# chat_stream Mock 模式
# ================================================================
class TestChatStream:
    """chat_stream 在 Mock 模式下的行为"""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, mock_llm):
        """stream 分块输出，不是一次性返回全部"""
        chunks = []
        async for chunk in mock_llm.chat_stream(_msgs("课程专家", "讲解CNN")):
            chunks.append(chunk)
        assert len(chunks) > 1  # 至少分了 2 块
        # 拼接后应包含原始内容
        full = "".join(chunks)
        assert len(full) > 50

    @pytest.mark.asyncio
    async def test_stream_non_empty(self, mock_llm):
        """stream 输出不为空"""
        chunks = []
        async for chunk in mock_llm.chat_stream(_msgs("出题专家", "出题")):
            chunks.append(chunk)
        assert len("".join(chunks)) > 0


# ================================================================
# achat 异步接口
# ================================================================
class TestAChat:
    """achat 聚合 stream 输出"""

    @pytest.mark.asyncio
    async def test_achat_aggregates(self, mock_llm):
        """achat 返回完整文本（聚合 stream）"""
        text = await mock_llm.achat(_msgs("课程专家", "讲解CNN"))
        assert len(text) > 20
        assert isinstance(text, str)


# ================================================================
# Mock 模式内容质量验证
# ================================================================
class TestMockContentQuality:
    """Mock 输出质量（确保演示可用）"""

    def test_all_agent_types_produce_non_junk(self, mock_llm):
        """所有 Mock Agent 输出都不是错误信息"""
        agents = [
            ("画像分析师", "我学习吃力"),
            ("出题专家", "出题"),
            ("多模态生成师", "画思维导图"),
            ("路径规划师", "规划路径"),
            ("评估", "评估水平"),
            ("质量审查员", "审查"),
            ("课程专家", "讲解CNN"),
            ("智能导师", "什么是CNN"),
        ]
        for sys_hint, user_text in agents:
            text = mock_llm._mock_chat(_msgs(sys_hint, user_text))
            assert "[ERROR]" not in text, f"Agent {sys_hint} 输出含错误标记"
            assert len(text) > 50, f"Agent {sys_hint} 输出过短: {len(text)} 字符"

    def test_all_outputs_are_utf8_safe(self, mock_llm):
        """所有 Mock 输出可安全编码为 UTF-8"""
        agents = [
            ("画像分析师", "我学习吃力"),
            ("出题专家", "出题"),
            ("课程专家", "讲解CNN"),
        ]
        for sys_hint, user_text in agents:
            text = mock_llm._mock_chat(_msgs(sys_hint, user_text))
            text.encode("utf-8")  # 不应抛异常
