"""
BloomAwareStrategy - A3 原创反思策略 (创新点)

核心思想:
反思不应是通用的, 而应按学习者当前的 Bloom 认知层级针对性诊断。

例子:
- 目标 Bloom=apply 的内容, 反思应重点检查 "是否有可执行步骤"
- 目标 Bloom=evaluate 的内容, 反思应重点检查 "是否陈述权衡 + 利弊"

学术依据:
- Anderson & Krathwohl (2001) Bloom 六层认知
- Krathwohl (2002) Revision of Bloom's Taxonomy
- Mayer (2014) Cognitive Theory of Multimedia Learning (CTML)

可投稿:
- AIED 2027 short paper (3 页)
- TLT (IEEE Transactions on Learning Technologies) workshop

实现:
- 复用 ReflectionRubric 的 Bloom-aware 失败模式诊断
- 修订时按 Bloom 层级生成定向 prompt
- 反思 verbal reasoning 中显式说明 "本次诊断针对 X 层"
"""
from __future__ import annotations

import time
from typing import Any, List, Optional

from backend.app.agents.reflection.rubric import (
    BLOOM_FAILURE_MODES,
    ReflectionRubric,
)
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


# ================================================================
# Bloom 层级 → 修订侧重点
# ================================================================
BLOOM_REVISION_HINTS = {
    "remember":   "确保事实陈述准确、术语规范, 添加权威来源标注。",
    "understand": "添加至少 1-2 个具体例子 + 1 个类比, 帮助初学者建立直觉。",
    "apply":      "把抽象描述拆为可复现步骤; 提供可直接运行的代码或操作示例。",
    "analyze":    "增加对比对象 (≥ 2 个); 显式说明部分 - 整体或因果关系。",
    "evaluate":   "陈述判断标准; 列举至少 2 个权衡维度; 给出利弊对照。",
    "create":     "鼓励新颖整合; 提供开放性引导问题, 让学生提出自己的方案。",
}


class BloomAwareStrategy(ReflexionStrategy):
    """Bloom-aware 反思策略 (原创)"""

    name = "bloom_aware"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        target = config.bloom_target or "understand"

        current = content
        prev_overall = -1.0

        for i in range(config.max_iterations):
            step_start = time.perf_counter()
            # 1) evaluate (含 Bloom-aware 失败模式)
            pre_score, weaknesses = self.rubric.evaluate(
                current, bloom=target, rag_results=rag_results,
            )

            # 2) reflect — 按 Bloom 层级针对性 reasoning
            reasoning = self._compose_bloom_reasoning(
                target, weaknesses, pre_score.overall,
            )

            # 3) revise — 注入 Bloom 修订提示
            revised = await self._bloom_aware_revise(
                current, target, weaknesses, config, llm_client,
            )

            # 4) verify
            post_score, _ = self.rubric.evaluate(
                revised, bloom=target, rag_results=rag_results,
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
    def _compose_bloom_reasoning(
        self, target: str, weaknesses: List[WeaknessItem], overall: float,
    ) -> str:
        bloom_specific = [
            w for w in weaknesses if w.dimension == "bloom"
        ]
        lines = [
            f"## Bloom-Aware Reflection",
            f"目标层级: **{target}**",
            f"当前评分: {overall:.0%}",
            f"针对 {target} 层级的失败模式诊断:",
        ]
        if bloom_specific:
            for w in bloom_specific[:3]:
                lines.append(f"  - {w.description}")
        else:
            lines.append("  - 该层级失败模式无明显证据 (已通过 keyword 检查)")
        lines.append(
            f"\n修订侧重: {BLOOM_REVISION_HINTS.get(target, '保持当前层级')}"
        )
        return "\n".join(lines)

    async def _bloom_aware_revise(
        self, content: str, target: str,
        weaknesses: List[WeaknessItem],
        config: ReflectionConfig, llm_client: Any,
    ) -> str:
        if config.use_llm_revise and llm_client is not None:
            return await self._llm_revise_with_bloom_hint(
                content, target, weaknesses, llm_client,
            )
        return self._rule_revise_with_bloom_hint(
            content, target, weaknesses,
        )

    def _rule_revise_with_bloom_hint(
        self, content: str, target: str, weaknesses: List[WeaknessItem],
    ) -> str:
        hint = BLOOM_REVISION_HINTS.get(target, "")
        suggestions = [w.suggestion for w in weaknesses if w.suggestion][:5]
        if not hint and not suggestions:
            return content
        suffix = (
            f"\n\n---\n\n## 🎯 Bloom-Aware 改进建议 ({target})\n\n"
            f"**侧重**: {hint}\n\n"
        )
        if suggestions:
            suffix += "**具体修订**:\n" + "\n".join(
                f"- {s}" for s in suggestions
            )
        return content + suffix

    async def _llm_revise_with_bloom_hint(
        self, content: str, target: str,
        weaknesses: List[WeaknessItem], llm_client: Any,
    ) -> str:
        hint = BLOOM_REVISION_HINTS.get(target, "")
        tips = "\n".join(
            f"- [{w.severity}] {w.description}"
            for w in weaknesses[:6]
        )
        prompt = (
            f"请把以下内容升级到 Bloom **{target}** 层级。\n\n"
            f"**修订侧重**: {hint}\n\n"
            f"**评审意见**:\n{tips}\n\n"
            f"**原文**:\n{content}\n\n"
            "直接输出修订后全文, 不要解释。"
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
            return self._rule_revise_with_bloom_hint(
                content, target, weaknesses,
            )
