"""
Reflection 子包 - Agent 反思框架 (P1-7)

公开 API:
    Reflector / get_reflector()   流程入口
    ReflectionTrace               结构化反思轨迹
    ReflectionRubric              5 维 + Bloom-aware 评分
    3 个 Strategy:
        - SelfRefineStrategy       Madaan 2023
        - ShinnReflexionStrategy   Shinn 2023 (verbal RL)
        - BloomAwareStrategy       A3 原创创新点
"""
from __future__ import annotations

from backend.app.agents.reflection.reflector import (
    Reflector,
    get_reflector,
    reset_reflector,
)
from backend.app.agents.reflection.rubric import (
    BLOOM_FAILURE_MODES,
    ReflectionRubric,
)
from backend.app.agents.reflection.strategies import (
    BLOOM_REVISION_HINTS,
    STRATEGY_REGISTRY,
    BloomAwareStrategy,
    ReflectionConfig,
    ReflexionStrategy,
    SelfRefineStrategy,
    ShinnReflexionStrategy,
    get_strategy,
)
from backend.app.agents.reflection.trace import (
    ReflectionScore,
    ReflectionStep,
    ReflectionTrace,
    ReflectionVerdict,
    WeaknessItem,
)


__all__ = [
    # reflector
    "Reflector",
    "get_reflector",
    "reset_reflector",
    # trace
    "ReflectionScore",
    "ReflectionStep",
    "ReflectionTrace",
    "ReflectionVerdict",
    "WeaknessItem",
    # rubric
    "ReflectionRubric",
    "BLOOM_FAILURE_MODES",
    # strategies
    "ReflectionConfig",
    "ReflexionStrategy",
    "SelfRefineStrategy",
    "ShinnReflexionStrategy",
    "BloomAwareStrategy",
    "STRATEGY_REGISTRY",
    "BLOOM_REVISION_HINTS",
    "get_strategy",
]
