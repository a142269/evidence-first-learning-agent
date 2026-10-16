"""
ReflexionStrategy (Shinn 2023) - Verbal RL

特点 (区别于 Self-Refine):
- 维护 "memory" - 上一轮的 verbal feedback 累积传给下一轮 prompt
- evaluator (Critic) 与 actor (Generator) 是分离的角色
- 适合需要外部反馈信号的任务 (e.g. 数学/编程)

工程实现:
- memory 用环形缓冲, 保留最近 3 轮 feedback
- 每轮的 reasoning 显式包含上轮 memory 引用
- 复用 SelfRefine 的修订路径 (规则 / LLM)
"""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Deque, List, Optional

from backend.app.agents.reflection.strategies.base import (
    ReflectionConfig,
    ReflexionStrategy,
)
from backend.app.agents.reflection.strategies.self_refine import (
    SelfRefineStrategy,
)
from backend.app.agents.reflection.trace import (
    ReflectionStep,
    ReflectionTrace,
    ReflectionVerdict,
    WeaknessItem,
)


class ShinnReflexionStrategy(ReflexionStrategy):
    """Shinn 2023 Verbal RL 风格反思 - memory-augmented Self-Refine"""

    name = "reflexion_shinn"

    def __init__(self, *args, memory_size: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory_size = memory_size
        self._refiner = SelfRefineStrategy(rubric=self.rubric)

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
        trace = ReflectionTrace(
            agent_name=agent_name, strategy=self.name,
            prompt_version=prompt_version,
            original_content=content, final_content=content,
            bloom_target=config.bloom_target,
        )

        memory: Deque[str] = deque(maxlen=self.memory_size)
        current = content
        prev_overall = -1.0

        for i in range(config.max_iterations):
            step_start = time.perf_counter()
            # 1) Evaluator (separate role)
            pre_score, weaknesses = self.rubric.evaluate(
                current, bloom=config.bloom_target,
                rag_results=rag_results,
            )

            # 2) Reflect — 把上轮 memory 引用进来
            reasoning = self._compose_reasoning(
                weaknesses, pre_score.overall, memory, round_no=i + 1,
            )

            # 3) Revise (Actor)
            revised = await self._refiner._revise(
                current, weaknesses, config, llm_client,
            )

            # 4) Verify
            post_score, _ = self.rubric.evaluate(
                revised, bloom=config.bloom_target,
                rag_results=rag_results,
            )

            # 把本轮反思加入 memory
            memory.append(
                f"R{i + 1}: 评分 {pre_score.overall:.0%} → "
                f"{post_score.overall:.0%}, 主因 {self._top_weakness(weaknesses)}"
            )

            step = ReflectionStep(
                step_index=i + 1,
                pre_score=pre_score,
                weaknesses=weaknesses,
                reasoning=reasoning,
                revised_content=revised,
                revision_diff_summary=self._refiner._diff_summary(
                    current, revised,
                ),
                post_score=post_score,
                improved=post_score.overall > pre_score.overall,
                duration_ms=(time.perf_counter() - step_start) * 1000,
            )
            trace.add_step(step)

            current = revised
            if post_score.overall >= config.pass_threshold:
                trace.final_content = current
                trace.verdict = ReflectionVerdict.PASS
                return trace
            if prev_overall >= 0 and abs(
                post_score.overall - prev_overall
            ) < config.min_improvement:
                break
            prev_overall = post_score.overall

        trace.final_content = current
        best = trace.best_score()
        if best < 0.4:
            trace.verdict = ReflectionVerdict.NEEDS_REGEN
        elif best < config.pass_threshold:
            trace.verdict = ReflectionVerdict.NEEDS_REVISION
        else:
            trace.verdict = ReflectionVerdict.PASS
        return trace

    # ----------------------------------------------------------------
    def _compose_reasoning(
        self, weaknesses: List[WeaknessItem], overall: float,
        memory: Deque[str], round_no: int,
    ) -> str:
        head = (
            f"## Reflexion R{round_no}\n"
            f"当前评分: {overall:.0%}\n"
            f"诊断弱点: {len(weaknesses)} 处\n"
        )
        if memory:
            head += "\n## 历史反思\n" + "\n".join(f"- {m}" for m in memory)
        return head

    def _top_weakness(self, weaknesses: List[WeaknessItem]) -> str:
        if not weaknesses:
            return "无"
        # 优先取 blocker > major > minor
        order = {"blocker": 0, "major": 1, "minor": 2}
        sorted_ws = sorted(
            weaknesses, key=lambda w: order.get(w.severity, 3),
        )
        return sorted_ws[0].description[:30]
