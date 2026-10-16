"""FIX-01~04 / 06 / 12 回归测试（docs/TripleU代码问题与修复建议.md，2026-07-17 修复）。

覆盖：
* FIX-01 聊天生成的学习路径写入 LearningPathRepository（重启可读）
* FIX-02 聊天评估写入 AssessmentRepository
* FIX-03 AgentContext.user_id 统一身份解析（session ≠ user 不串数据）
* FIX-04 RAG 命中携带 kp_id（RealDINA/BKT 回写契约）
* FIX-06 ConfigurableAgent 读取主 RAG 的 content 字段
* FIX-12 SafeDeclineAgent.reflect 与基类异步签名兼容
"""
from __future__ import annotations

import uuid

import pytest

from backend.app.agents.base import AgentContext, AgentResponse
from backend.app.core.database import SessionLocal, init_db
from backend.app.core.models import AssessmentRecord, LearningPathRecord


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture()
def temp_user():
    user_id = f"pytest-fix-{uuid.uuid4().hex[:8]}"
    yield user_id
    with SessionLocal() as db:
        db.query(AssessmentRecord).filter(AssessmentRecord.user_id == user_id).delete()
        db.query(LearningPathRecord).filter(LearningPathRecord.user_id == user_id).delete()
        db.commit()


# ----------------------------------------------------------------------
# FIX-03
# ----------------------------------------------------------------------
def test_agent_context_user_id_prefers_extra():
    ctx = AgentContext(session_id="sess_x", extra={"user_id": "demo-student-1"})
    assert ctx.user_id == "demo-student-1"


def test_agent_context_user_id_falls_back_to_session():
    assert AgentContext(session_id="sess_x").user_id == "sess_x"
    assert AgentContext().user_id == "default"


# ----------------------------------------------------------------------
# FIX-01
# ----------------------------------------------------------------------
def test_chat_learning_path_persisted_to_repository(temp_user):
    from backend.app.api.v1 import learning_path as lp_api
    from backend.app.api.v1.chat_pipeline.stages.outputs import PersistStage

    response = AgentResponse(
        agent_name="path_planner",
        success=True,
        metadata={"path_data": {"stages": [{"name": "阶段1", "kp_ids": ["AI_001"]}]}},
    )
    PersistStage._save_learning_path(temp_user, response, {"title": "chat 生成路径"})

    assert lp_api._repository is not None, "repository 必须可用"
    items = lp_api._repository.list(user_id=temp_user)
    assert items, "聊天生成的路径必须能从 Repository 读到"
    assert items[0]["title"] == "chat 生成路径"


# ----------------------------------------------------------------------
# FIX-02
# ----------------------------------------------------------------------
def test_chat_assessment_persisted_to_repository(temp_user):
    from backend.app.api.v1.chat_pipeline.stages.outputs import PersistStage
    from backend.app.repositories.assessment_repo import AssessmentRepository

    response = AgentResponse(
        agent_name="evaluator",
        success=True,
        metadata={
            "evaluation_data": {"overall_score": 0.8, "topic": "闭环验证"},
            "evaluation_id": f"eval-{uuid.uuid4().hex[:8]}",
        },
    )
    PersistStage._record_assessment(temp_user, response)

    records = AssessmentRepository().list(temp_user)
    assert records, "评估必须写入 AssessmentRepository"
    assert records[-1]["type"] == "evaluation"
    assert records[-1]["score"] == pytest.approx(80.0)


# ----------------------------------------------------------------------
# FIX-04
# ----------------------------------------------------------------------
def test_rag_hits_carry_kp_id_for_chapter_sources():
    from backend.app.services.rag_service import get_rag_service

    hits = get_rag_service().retrieve(
        "什么是 Transformer 注意力机制", top_k=5,
        course_filter="artificial_intelligence",
    )
    assert hits, "RAG 必须有命中"
    for hit in hits:
        assert "kp_id" in hit and "metadata" in hit, "字段契约必须包含 kp_id/metadata"
    chapter_hits = [h for h in hits if "/chapters/" in h["source"]]
    assert any(h["kp_id"] for h in chapter_hits), "章节命中必须解析出图谱 kp_id"


# ----------------------------------------------------------------------
# FIX-06
# ----------------------------------------------------------------------
def test_configurable_agent_reads_rag_content_field():
    import inspect

    from backend.app.agents import configurable_agent as module

    source = inspect.getsource(module.ConfigurableAgent.execute)
    assert 'item.get("content")' in source, "必须优先读取主 RAG 的 content 字段"


# ----------------------------------------------------------------------
# FIX-12
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_safe_decline_reflect_signature_compatible():
    from backend.app.agents.safe_decline_agent import SafeDeclineAgent

    agent = SafeDeclineAgent.__new__(SafeDeclineAgent)  # 跳过 LLM 初始化
    ctx = AgentContext(user_input="今天天气怎么样", session_id="s1")
    result = await agent.reflect("模板回复", ctx, max_iterations=2, pass_threshold=0.7)
    assert result["skipped"] is True
    assert result["needs_rewrite"] is False
