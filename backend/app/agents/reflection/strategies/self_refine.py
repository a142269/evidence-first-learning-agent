"""
SelfRefineStrategy - Madaan et al. (2023) Self-Refine

算法:
    while not converged and rounds < max_iterations:
        1. evaluate: score + weaknesses
        2. reflect: 把 weaknesses 总结为修订建议 (verbal)
        3. revise: 把建议应用到 content (规则或 LLM)
        4. verify: 重新评分
        if delta < min_improvement: break

特点:
- 单 agent 自我对话, 无外部 critic
- 适合内容生成类任务 (doc / 解释)
"""
from __future__ import annotations

import time
from typing import Any, List, Optional

from backend.app.agents.reflection.strategies.base import (
    ReflectionConfig,
    ReflexionStrategy,
)
from backend.app.agents.reflection.trace import (
    ReflectionStep,
    ReflectionTrace,
    ReflectionVerdict,
    WeaknessItem,
)


class SelfRefineStrategy(ReflexionStrategy):
    """Self-Refine 单 agent 多轮自我修正"""

    name = "self_refine"

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

        current = content
        prev_overall = -1.0

        for i in range(config.max_iterations):
            step_start = time.perf_counter()
            # 1) evaluate
            pre_score, weaknesses = self.rubric.evaluate(
                current, bloom=config.bloom_target,
                rag_results=rag_results,
            )
            # 2) reflect (verbal)
            reasoning = self._verbalize(weaknesses, pre_score.overall)
            # 3) revise
            revised = await self._revise(
                current, weaknesses, config, llm_client,
            )
            # 4) verify
            post_score, _ = self.rubric.evaluate(
                revised, bloom=config.bloom_target,
                rag_results=rag_results,
            )

            step = ReflectionStep(
                step_index=i + 1,
                pre_score=pre_score,
                weaknesses=weaknesses,
                reasoning=reasoning,
                revised_content=revised,
                revision_diff_summary=self._diff_summary(current, revised),
                post_score=post_score,
                improved=post_score.overall > pre_score.overall,
                duration_ms=(time.perf_counter() - step_start) * 1000,
            )
            trace.add_step(step)

            current = revised
            # 终止判断
            if post_score.overall >= config.pass_threshold:
                trace.final_content = current
                trace.verdict = ReflectionVerdict.PASS
                return trace

            if prev_overall >= 0 and abs(
                post_score.overall - prev_overall
            ) < config.min_improvement:
                break
            prev_overall = post_score.overall

        # 反思耗尽 → 判定是否需重写
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
    # 内部
    # ----------------------------------------------------------------
    def _verbalize(
        self, weaknesses: List[WeaknessItem], overall: float,
    ) -> str:
        if not weaknesses:
            return f"当前评分 {overall:.0%}, 无需进一步修订。"
        lines = [f"当前评分 {overall:.0%}, 发现 {len(weaknesses)} 处弱点:"]
        for w in weaknesses[:5]:
            lines.append(f"  - [{w.severity}/{w.dimension}] {w.description}")
        return "\n".join(lines)

    async def _revise(
        self, content: str, weaknesses: List[WeaknessItem],
        config: ReflectionConfig, llm_client: Any,
    ) -> str:
        if config.use_llm_revise and llm_client is not None:
            return await self._revise_with_llm(content, weaknesses, llm_client)
        return self._revise_with_rules(content, weaknesses)

    def _revise_with_rules(
        self, content: str, weaknesses: List[WeaknessItem],
    ) -> str:
        """规则修订 — 在末尾追加建议补充段落

        策略: 不破坏原内容, 仅在文末加 "🔧 改进建议" 段落
        """
        if not weaknesses:
            return content
        tips: List[str] = []
        for w in weaknesses[:5]:
            if w.suggestion:
                tips.append(f"- {w.suggestion}")
        if not tips:
            return content
        suffix = "\n\n---\n\n## 🔧 改进建议 (Self-Refine)\n\n" + "\n".join(tips)
        return content + suffix

    async def _revise_with_llm(
        self, content: str, weaknesses: List[WeaknessItem], llm_client: Any,
    ) -> str:
        """LLM 修订 — 把弱点交给 LLM 重写"""
        tips = "\n".join(
            f"- [{w.severity}] {w.description}: {w.suggestion}"
            for w in weaknesses[:8]
        )
        prompt = (
            "请根据以下评审意见, 修订原文。保留原意但消除被指出的问题。\n\n"
            f"## 评审意见\n{tips}\n\n"
            f"## 原文\n{content}\n\n"
            "请直接输出修订后的全文, 不要解释。"
        )
        try:
            if hasattr(llm_client, "achat"):
                return await llm_client.achat([
                    {"role": "user", "content": prompt},
                ])
            return llm_client.chat([
                {"role": "user", "content": prompt},
            ])
        except Exception:
            return self._revise_with_rules(content, weaknesses)

    def _diff_summary(self, old: str, new: str) -> str:
        if old == new:
            return "no_change"
        return (
            f"+{max(0, len(new) - len(old))} chars / "
            f"-{max(0, len(old) - len(new))} chars"
        )
