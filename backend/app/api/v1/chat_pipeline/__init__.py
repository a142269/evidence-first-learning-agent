"""Chat Pipeline 包 - 7 阶段对话流水线 (P1-1 重构)

将原 chat.py 213 行 spaghetti 一行式代码拆分为:
    - pipeline.py: 调度核心 (ConversationPipeline + Stage + Telemetry)
    - session.py:  会话存储 (替代模块级 _sessions dict)
    - stages.py:   7 个独立阶段实现
    - events.py:   SSE 事件协议 + Last-Event-ID 断线重连
"""
from __future__ import annotations

from backend.app.api.v1.chat_pipeline.pipeline import (
    ConversationPipeline,
    ConversationTelemetry,
    PipelineContext,
    PipelineResult,
    Stage,
    StageMetrics,
)
from backend.app.api.v1.chat_pipeline.session import SessionStore, get_session_store
from backend.app.api.v1.chat_pipeline.stages import (
    AggregationStage,
    DebateReflectionStage,
    InputValidationStage,
    OrchestrationStage,
    PersistStage,
    RAGRetrievalStage,
    RealtimeStateStage,
    build_default_pipeline,
)
from backend.app.api.v1.chat_pipeline.events import (
    EventBuffer,
    SSEEvent,
    clear_buffer,
    get_or_create_buffer,
    parse_last_event_id,
    sse_format,
    sse_heartbeat,
)

__all__ = [
    # pipeline 调度
    "ConversationPipeline",
    "ConversationTelemetry",
    "PipelineContext",
    "PipelineResult",
    "Stage",
    "StageMetrics",
    # session
    "SessionStore",
    "get_session_store",
    # stages
    "InputValidationStage",
    "RAGRetrievalStage",
    "RealtimeStateStage",
    "OrchestrationStage",
    "DebateReflectionStage",
    "AggregationStage",
    "PersistStage",
    "build_default_pipeline",
    # SSE
    "EventBuffer",
    "SSEEvent",
    "sse_format",
    "sse_heartbeat",
    "get_or_create_buffer",
    "clear_buffer",
    "parse_last_event_id",
]
