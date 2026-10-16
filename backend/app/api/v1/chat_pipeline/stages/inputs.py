"""
输入侧 3 阶段 (1-3): 校验 / RAG / 实时学情
"""
from __future__ import annotations

import logging
import time
from typing import Any

from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext, Stage
from backend.app.api.v1.chat_pipeline.session import SessionStore
from backend.app.services.rag_service import get_rag_service
from backend.app.services.realtime_state_service import (
    build_personalization_prompt,
    get_analyzer,
)

logger = logging.getLogger(__name__)


def _persist_realtime_state(ctx: PipelineContext, state: Any) -> None:
    """Persist the latest per-session learning state for restart-safe demos."""
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import RealtimeStateRecord

        state_data = {
            "summary": state.summary(),
            "emotion": state.emotion,
            "implicit_emotion": state.implicit_emotion,
            "engagement": state.engagement,
            "confidence": state.confidence_level,
            "confusion": state.confusion_level,
            "curiosity": state.curiosity_level,
            "cognitive_load": state.cognitive_load_level,
            "fatigue": state.fatigue_level,
            "stuck_topics": list(state.stuck_topics),
            "curiosity_topics": list(state.curiosity_topics),
            "preferred_reply_style": state.preferred_reply_style,
            "next_best_action": state.next_best_action,
            "evidence": list(state.evidence),
        }
        with SessionLocal() as db:
            row = db.get(RealtimeStateRecord, ctx.session_id)
            if row is None:
                row = RealtimeStateRecord(session_id=ctx.session_id)
                db.add(row)
            row.user_id = str(ctx.session.get("user_id") or ctx.session_id)
            row.state_data = state_data
            row.updated_at = time.time()
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Pipeline] realtime state persistence skipped: %s", exc)


# ================================================================
# Stage 1: 输入校验 + 会话准备
# ================================================================
class InputValidationStage(Stage):
    """阶段 1: 校验 user_input + 准备 session

    失败条件: 空消息 / 超长消息
    Fatal: 输入校验失败直接终止整条流水线
    """

    name = "input_validation"
    timeout_seconds = 1.0
    fatal_on_fail = True

    MIN_LEN = 1
    MAX_LEN = 4000

    async def run(self, ctx: PipelineContext) -> None:
        msg = (ctx.user_input or "").strip()
        if len(msg) < self.MIN_LEN:
            ctx.abort_reason = "message_required"
            err = "message_required: empty input"
            raise ValueError(err)
        if len(msg) > self.MAX_LEN:
            ctx.abort_reason = "message_too_long"
            err = f"message_too_long: {len(msg)} > {self.MAX_LEN}"
            raise ValueError(err)

        ctx.user_input = msg
        ctx.validated = True
        ctx.role_view = ctx.session.get("role_view", "student")

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        logger.info(f"[Pipeline] InputValidation fail: {error}")
        return False


# ================================================================
# Stage 2: RAG 检索
# ================================================================
class RAGRetrievalStage(Stage):
    """阶段 2: RAG 检索 - 失败时退化为空列表"""

    name = "rag_retrieval"
    timeout_seconds = 6.0
    retry_count = 1
    fatal_on_fail = False

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    async def run(self, ctx: PipelineContext) -> None:
        rag_service = ctx.services.get("rag_service") or get_rag_service()
        results = rag_service.retrieve(
            ctx.user_input, top_k=self.top_k, course_filter=ctx.course,
        )
        ctx.rag_results = list(results) if results else []

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        ctx.rag_results = []
        return True


# ================================================================
# Stage 3: 实时学情分析
# ================================================================
class RealtimeStateStage(Stage):
    """阶段 3: 实时学情分析 + 个性化策略 prompt"""

    name = "realtime_state"
    timeout_seconds = 3.0
    fatal_on_fail = False

    async def run(self, ctx: PipelineContext) -> None:
        analyzer = ctx.services.get("realtime_analyzer") or get_analyzer()
        store: SessionStore = ctx.services["session_store"]
        prev_state = store.get_realtime_state(ctx.session_id)

        state = analyzer.analyze(
            user_message=ctx.user_input,
            history=ctx.session.get("history", []),
            previous_state=prev_state,
        )
        store.set_realtime_state(ctx.session_id, state)
        _persist_realtime_state(ctx, state)
        ctx.realtime_state = state
        ctx.strategy_prompt = build_personalization_prompt(
            state, ctx.session.get("profile", {}),
        )

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        ctx.realtime_state = None
        ctx.strategy_prompt = ""
        return True
