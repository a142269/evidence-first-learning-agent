"""
反思策略注册表
"""
from __future__ import annotations

from typing import Dict, Type

from backend.app.agents.reflection.strategies.base import (
    ReflectionConfig,
    ReflexionStrategy,
)
from backend.app.agents.reflection.strategies.bloom_aware import (
    BLOOM_REVISION_HINTS,
    BloomAwareStrategy,
)
from backend.app.agents.reflection.strategies.reflexion import (
    ShinnReflexionStrategy,
)
from backend.app.agents.reflection.strategies.self_refine import (
    SelfRefineStrategy,
)


STRATEGY_REGISTRY: Dict[str, Type[ReflexionStrategy]] = {
    "self_refine": SelfRefineStrategy,
    "reflexion_shinn": ShinnReflexionStrategy,
    "bloom_aware": BloomAwareStrategy,
}


def get_strategy(name: str = "bloom_aware") -> ReflexionStrategy:
    """获取反思策略实例 (默认 bloom_aware - 我们的原创)"""
    cls = STRATEGY_REGISTRY.get(name) or BloomAwareStrategy
    return cls()


__all__ = [
    "ReflectionConfig",
    "ReflexionStrategy",
    "SelfRefineStrategy",
    "ShinnReflexionStrategy",
    "BloomAwareStrategy",
    "BLOOM_REVISION_HINTS",
    "STRATEGY_REGISTRY",
    "get_strategy",
]
