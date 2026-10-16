"""
编排侧 2 阶段 (4-5): 多智能体编排 / 辩论 + 反思
"""
from __future__ import annotations

import logging
import os
from typing import Dict

from backend.app.agents.base import AgentContext, AgentResponse
from backend.app.agents.orchestrator import VALID_AGENT_KEYS
from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext, Stage
from backend.app.api.v1.chat_pipeline.stages._shared import (
    get_shared_orchestrator,
)

logger = logging.getLogger(__name__)


def _resolve_orchestration_timeout() -> float:
    """Allow long-thinking models without code changes per machine."""
    raw_timeout = os.getenv("CHAT_ORCHESTRATION_TIMEOUT", "").strip()
    if raw_timeout:
        try:
            return max(30.0, float(raw_timeout))
        except ValueError:
            logger.warning("Invalid CHAT_ORCHESTRATION_TIMEOUT=%s", raw_timeout)

    try:
        from backend.app.core.config import get_config
        llm_timeout = float(get_config().llm.timeout or 300)
    except Exception:
        llm_timeout = 300.0
    return max(360.0, llm_timeout + 120.0)


# ================================================================
# Stage 4: 多智能体编排
# ================================================================
class OrchestrationStage(Stage):
    """阶段 4: 多智能体编排 - Fatal (是核心生成)"""

    name = "orchestration"
    timeout_seconds = _resolve_orchestration_timeout()
    fatal_on_fail = True

    async def run(self, ctx: PipelineContext) -> None:
        orch = ctx.services.get("orchestrator") or get_shared_orchestrator()

        extra_ctx = {
            "strategy_prompt": ctx.strategy_prompt,
            "user_id": str(ctx.session.get("user_id") or ""),
            "realtime_state_summary": (
                ctx.realtime_state.summary() if ctx.realtime_state else ""
            ),
            "role_view": ctx.role_view,
        }
        # 教师端会把已压缩的学情快照放在会话里。这里显式透传给
        # 既有编排器，避免 Agent 只能根据教师的自然语言猜测数据现状。
        if ctx.session.get("teacher_context"):
            extra_ctx["teacher_context"] = ctx.session["teacher_context"]
        agent_results: Dict[str, AgentResponse] = await orch.process_turn(
            user_input=ctx.user_input,
            profile=ctx.session.get("profile", {}),
            context=extra_ctx,
            conversation_history=ctx.session.get("history", []),
            rag_results=ctx.rag_results,
            course_name=ctx.course,
            session_id=ctx.session_id,
            target_agent=ctx.target_agent,
        )
        ctx.agent_results = agent_results

        # 单 Agent 模式标记，供后续阶段判断
        if ctx.target_agent and ctx.target_agent in VALID_AGENT_KEYS:
            ctx.single_agent_mode = True

        for resp in agent_results.values():
            ctx.telemetry.record_agent(resp.agent_name)

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        ctx.agent_results = {}
        return False  # Fatal


# ================================================================
# Stage 5: 辩论 + 反思
# ================================================================
class DebateReflectionStage(Stage):
    """阶段 5: Multi-Agent Debate + Reflexion

    辩论触发: 响应成功 + Agent 在 DEBATE_TRIGGERING_AGENTS 中。
    反思触发: 响应成功 + content_type 不在 SKIP_REFLECTION_TYPES 中
              + 未走过辩论。
    """

    name = "debate_reflection"
    timeout_seconds = 45.0
    fatal_on_fail = False

    DEBATE_TRIGGERING_AGENTS = frozenset({
        "course_expert", "quiz_generator", "tutor_agent",
        "doc_gen", "exercise", "tutor",
    })

    SKIP_REFLECTION_TYPES = frozenset({
        "profile_update", "review", "evaluation", "learning_path",
    })

    async def run(self, ctx: PipelineContext) -> None:
        # 单 Agent 模式: 跳过辩论/反思
        if ctx.single_agent_mode:
            return
        await self._run_debate(ctx)
        await self._run_reflection(ctx)

    async def _run_debate(self, ctx: PipelineContext) -> None:
        """对核心生成 Agent 运行 Multi-Agent Debate"""
        from backend.app.agents.debate_moderator import orchestrate_debate

        orch = ctx.services.get("orchestrator") or get_shared_orchestrator()
        extra_ctx = self._build_extra_ctx(ctx)

        for resp in list(ctx.agent_results.values()):
            if not self._should_debate(resp):
                continue

            try:
                gen_agent = orch._get_or_create_agent(resp.agent_name)
                debate_ctx = AgentContext(
                    user_input=ctx.user_input,
                    session_id=ctx.session_id,
                    profile=ctx.session.get("profile", {}),
                    course_name=ctx.course,
                    conversation_history=ctx.session.get("history", []),
                    rag_results=ctx.rag_results,
                    extra=extra_ctx,
                )
                debate_result = await orchestrate_debate(
                    gen_agent, debate_ctx, session_id=ctx.session_id,
                )
                ctx.debate_log = debate_result
                resp.content = debate_result.get("final_content", resp.content)
                resp.metadata["debate"] = {
                    "rounds": debate_result.get("debate_rounds", 0),
                    "best_score": debate_result.get("best_score", 0),
                    "verdict": debate_result.get("verdict", ""),
                }
            except Exception as exc:
                logger.warning(
                    f"[Pipeline] Debate skip ({resp.agent_name}): {exc}"
                )

    def _should_debate(self, resp: AgentResponse) -> bool:
        if not resp.success:
            return False
        return resp.agent_name in self.DEBATE_TRIGGERING_AGENTS

    async def _run_reflection(self, ctx: PipelineContext) -> None:
        """对未走辩论的 Agent 运行 Reflexion"""
        orch = ctx.services.get("orchestrator") or get_shared_orchestrator()
        extra_ctx = self._build_extra_ctx(ctx)

        for resp in ctx.agent_results.values():
            if not self._should_reflect(resp):
                continue

            try:
                reflect_agent = orch._get_or_create_agent(resp.agent_name)
                # P1-7: BaseAgent.reflect() 现在所有子类都有
                reflect_ctx = AgentContext(
                    user_input=ctx.user_input,
                    session_id=ctx.session_id,
                    profile=ctx.session.get("profile", {}),
                    rag_results=ctx.rag_results,
                    extra=extra_ctx,
                )
                reflection = await reflect_agent.reflect(
                    resp.content, reflect_ctx,
                )
                if reflection.get("needs_rewrite"):
                    resp.content = reflection.get(
                        "improved_draft", resp.content,
                    )
                    resp.metadata["reflection"] = {
                        "rewritten": True,
                        "verdict": reflection.get("verdict"),
                        "rounds": reflection.get("rounds", 0),
                        "best_score": reflection.get("best_score", 0.0),
                        "strategy": reflection.get("strategy"),
                        "prompt_version": reflection.get("prompt_version"),
                        "issues": reflection.get("issues", []),
                    }
                else:
                    resp.metadata["reflection"] = {
                        "rewritten": False,
                        "best_score": reflection.get("best_score", 0.0),
                        "strategy": reflection.get("strategy"),
                    }
                ctx.reflection_log[resp.agent_name] = resp.metadata["reflection"]
            except Exception as exc:
                logger.warning(
                    f"[Pipeline] Reflexion skip ({resp.agent_name}): {exc}"
                )

    def _should_reflect(self, resp: AgentResponse) -> bool:
        if not resp.success:
            return False
        if resp.content_type in self.SKIP_REFLECTION_TYPES:
            return False
        if (resp.metadata or {}).get("debate"):
            return False
        return True

    def _build_extra_ctx(self, ctx: PipelineContext) -> dict:
        extra_ctx = {
            "strategy_prompt": ctx.strategy_prompt,
            "realtime_state_summary": (
                ctx.realtime_state.summary() if ctx.realtime_state else ""
            ),
            "role_view": ctx.role_view,
        }
        if ctx.session.get("teacher_context"):
            extra_ctx["teacher_context"] = ctx.session["teacher_context"]
        return extra_ctx

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        return True
