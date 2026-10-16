"""
ReflexionStrategy - 反思策略抽象基类

策略模式让 BaseAgent.reflect() 支持插拔不同 reflection 算法:
- SelfRefineStrategy:    Madaan 2023 - 多轮自我修正
- ReflexionStrategy:     Shinn 2023 - verbal RL 记忆累积
- BloomAwareStrategy:    我们的原创 - 按 Bloom 层级针对性反思
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from backend.app.agents.reflection.rubric import ReflectionRubric
from backend.app.agents.reflection.trace import ReflectionTrace


@dataclass
class ReflectionConfig:
    """反思策略的运行参数"""
    max_iterations: int = 1                 # 最大反思轮数
    pass_threshold: float = 0.7             # 通过分数
    min_improvement: float = 0.02           # 单轮最小改进, 低于此终止
    bloom_target: str = "understand"
    use_llm_revise: bool = False            # 是否调 LLM 重写 (默认规则修订)
    enable_rag: bool = True


class ReflexionStrategy(ABC):
    """反思策略抽象基类"""

    name: str = "abstract"

    def __init__(self, rubric: Optional[ReflectionRubric] = None):
        self.rubric = rubric or ReflectionRubric()

    @abstractmethod
    async def reflect(
        self,
        content: str,
        config: ReflectionConfig,
        *,
        llm_client: Any = None,
        agent_name: str = "",
        prompt_version: str = "",
        rag_results: Optional[list] = None,
        extra: Optional[dict] = None,
    ) -> ReflectionTrace:
        """执行反思, 返回 Trace"""
