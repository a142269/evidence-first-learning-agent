"""
7 阶段 Stage 包

按职责拆为 3 个模块:
- inputs.py:        Stage 1-3 (校验 / RAG / 实时学情)
- orchestration.py: Stage 4-5 (智能体编排 / 辩论+反思)
- outputs.py:       Stage 6-7 (聚合 / 持久化)
- _shared.py:       共享单例

build_default_pipeline() 构造完整 7 阶段流水线。
"""
from __future__ import annotations

from backend.app.api.v1.chat_pipeline.pipeline import ConversationPipeline
from backend.app.api.v1.chat_pipeline.stages.inputs import (
    InputValidationStage,
    RAGRetrievalStage,
    RealtimeStateStage,
)
from backend.app.api.v1.chat_pipeline.stages.orchestration import (
    DebateReflectionStage,
    OrchestrationStage,
)
from backend.app.api.v1.chat_pipeline.stages.outputs import (
    AggregationStage,
    PersistStage,
)

__all__ = [
    "InputValidationStage",
    "RAGRetrievalStage",
    "RealtimeStateStage",
    "OrchestrationStage",
    "DebateReflectionStage",
    "AggregationStage",
    "PersistStage",
    "build_default_pipeline",
]


def build_default_pipeline() -> ConversationPipeline:
    """构造默认 7 阶段对话流水线"""
    return ConversationPipeline([
        InputValidationStage(),
        RAGRetrievalStage(),
        RealtimeStateStage(),
        OrchestrationStage(),
        DebateReflectionStage(),
        AggregationStage(),
        PersistStage(),
    ])
