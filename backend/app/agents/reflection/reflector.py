"""
Reflector - 反思流程统一入口

设计:
- 把 strategy 选择 / config 构造 / trace 收集 包成单一调用
- 供 BaseAgent.reflect() 使用, 不直接暴露 strategy 给 agent 子类

用法:
    reflector = get_reflector()
    trace = await reflector.run(
        content="...", agent_name="course_expert",
        bloom_target="apply", rag_results=[...],
    )
    # 调用方根据 trace.verdict 决定后续动作
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.app.agents.reflection.strategies import (
    ReflectionConfig,
    get_strategy,
)
from backend.app.agents.reflection.trace import ReflectionTrace


logger = logging.getLogger(__name__)


class Reflector:
    """反思统一调度器

    单例模式; 每次调用按需选 strategy。
    """

    DEFAULT_STRATEGY = "bloom_aware"

    def __init__(self, default_strategy: str = DEFAULT_STRATEGY):
        self.default_strategy = default_strategy

    async def run(
        self,
        content: str,
        *,
        agent_name: str = "",
        prompt_version: str = "",
        bloom_target: str = "understand",
        strategy: Optional[str] = None,
        max_iterations: int = 1,
        pass_threshold: float = 0.7,
        use_llm_revise: bool = False,
        rag_results: Optional[list] = None,
        llm_client: Any = None,
        extra: Optional[dict] = None,
    ) -> ReflectionTrace:
        """执行一次反思

        Args:
            content:        待反思的内容
            agent_name:     调用 agent 名 (写入 Trace)
            prompt_version: 该 agent 当前 prompt 版本 (写入 Trace)
            bloom_target:   目标 Bloom 层级
            strategy:       策略名 (None = 用默认 bloom_aware)
            max_iterations: 最大反思轮数
            pass_threshold: 通过分数
            use_llm_revise: 是否调 LLM 重写
            rag_results:    RAG 上下文 (用于 factual 评分)
            llm_client:     LLM 客户端 (use_llm_revise=True 时必须)

        Returns:
            ReflectionTrace
        """
        strat_name = strategy or self.default_strategy
        strat = get_strategy(strat_name)

        cfg = ReflectionConfig(
            max_iterations=max_iterations,
            pass_threshold=pass_threshold,
            bloom_target=bloom_target,
            use_llm_revise=use_llm_revise,
        )

        try:
            trace = await strat.reflect(
                content=content,
                config=cfg,
                llm_client=llm_client,
                agent_name=agent_name,
                prompt_version=prompt_version,
                rag_results=rag_results,
                extra=extra,
            )
            return trace
        except Exception as exc:
            logger.exception(
                f"[Reflector] strategy={strat_name} failed: {exc}"
            )
            # 失败时给出空 Trace - 调用方应判定 needs_rewrite=False
            return ReflectionTrace(
                agent_name=agent_name,
                strategy=strat_name,
                prompt_version=prompt_version,
                original_content=content,
                final_content=content,
                bloom_target=bloom_target,
            )


# ================================================================
# 单例
# ================================================================
_reflector: Optional[Reflector] = None


def get_reflector() -> Reflector:
    global _reflector
    if _reflector is None:
        _reflector = Reflector()
    return _reflector


def reset_reflector(default_strategy: str = "bloom_aware") -> None:
    global _reflector
    _reflector = Reflector(default_strategy=default_strategy)
