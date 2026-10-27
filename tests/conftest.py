"""
Pytest 全局 fixtures —— 供 tests/a/ 和 tests/b/ 共享
"""
from __future__ import annotations

import sys
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pytest
from unittest.mock import MagicMock, AsyncMock


def pytest_sessionstart(session) -> None:
    """Remove a stale ``--basetemp`` tree before pytest reuses it.

    Windows Explorer sends every deleted file to the Recycle Bin; a full-suite
    basetemp can contain thousands of tiny SQLite journals.  Remove the old
    tree directly here so repeated runs never accumulate recycle-bin entries.
    Only paths strictly inside this repository's ``output/`` and named like a
    pytest basetemp are touched.
    """
    raw = getattr(session.config.option, "basetemp", None)
    if not raw:
        return
    try:
        base = Path(str(raw)).expanduser().resolve()
        root = Path(__file__).resolve().parents[1].resolve()
        output = (root / "output").resolve()
        if base == output or output not in base.parents:
            return
        if not base.name.startswith(("base", "basetemp", "pytest-")):
            return
        if base.exists() and not base.is_symlink():
            shutil.rmtree(base)
    except OSError:
        # A failed pre-clean must not abort collection; pytest will create a
        # fresh numbered directory and the explicit cleanup script remains.
        pass


# ================================================================
# 路径修补：确保 backend 在 sys.path 中
# ================================================================
@pytest.fixture(autouse=True)
def _patch_sys_path():
    """自动将项目根目录加入 sys.path"""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


# ================================================================
# Mock LLMClient
# ================================================================
@pytest.fixture
def mock_llm_client():
    """返回一个 Mock LLMClient，所有方法返回可控占位文本"""
    client = MagicMock()
    client.chat.return_value = "[MOCK] LLM response"
    # 模拟 async achat
    client.achat = AsyncMock(return_value="[MOCK] Async LLM response")
    # 模拟 async generator chat_stream（直接赋值为 async generator 工厂）
    async def _stream_gen(*args, **kwargs):
        yield "[MOCK] "
        yield "stream "
        yield "response"

    client.chat_stream = _stream_gen
    return client


# ================================================================
# 标准 AgentContext fixture
# ================================================================
@pytest.fixture
def agent_context() -> Any:
    """返回一个标准的 AgentContext"""
    from backend.app.agents.base import AgentContext

    return AgentContext(
        user_input="请给我讲解一下卷积神经网络",
        session_id="test-session-001",
        profile={
            "knowledge_base": {"level": "入门"},
            "learning_preference": {"preferred_format": "视频+代码"},
            "cognitive_style": {"type": "视觉型"},
        },
        course_name="artificial_intelligence",
        conversation_history=[
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮你的？"},
        ],
        rag_results=[],
        extra={
            "strategy_prompt": "学生当前情绪积极，好奇心强，建议用启发式教学",
            "dina_snapshot": {"cnn": 0.45, "rnn": 0.72},
            "archetype": {"code": "high_achiever", "nickname": "笃行的探路人"},
            "rag_mode": "hybrid",
        },
    )


# ================================================================
# Mock LLMClient with real _mock_chat behavior
# ================================================================
@pytest.fixture
def real_mock_llm():
    """返回一个使用真实 _mock_chat 逻辑的 LLMClient（无 API Key 时）"""
    from backend.app.core.config import AppConfig
    from backend.app.core.llm_client import LLMClient

    config = AppConfig.from_env()
    config.llm.spark_app_id = ""  # 强制无 provider
    config.llm.openai_base_url = ""
    return LLMClient(config=config.llm)
