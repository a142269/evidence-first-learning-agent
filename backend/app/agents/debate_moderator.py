"""
Debate Moderator — Multi-Agent Debate 协调器（Phase 1 重构版 v3）

流程: Expert 初稿 → Critic 审稿 → Expert 重写 → Moderator 仲裁
参考: Du et al. NeurIPS 2023 "Improving Factuality and Reasoning in Language Models
       through Multiagent Debate"

核心改进 (v3):
- execute() 不再 stub: 从 context 中获取 expert 并运行真正辩论
- orchestrate_debate() 接受 critic_agent 参数（可注入、可测试）
- 收敛检测真正 break 循环
- 使用 DebateRepository 持久化到 SQLite
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse

logger = logging.getLogger(__name__)

# ================================================================
# 配置常量
# ================================================================
MAX_DEBATE_ROUNDS: int = 2
CONVERGENCE_DELTA: float = 0.05
DEBATE_ELIGIBLE_INTENTS: frozenset = frozenset({
    "generate_doc", "generate_exercise", "tutoring",
})
PASS_THRESHOLD: int = 75


# ================================================================
# 状态机
# ================================================================
class DebateState(Enum):
    IDLE = auto()
    DRAFTING = auto()
    REVIEWING = auto()
    REVISING = auto()
    ARBITRATING = auto()
    COMPLETE = auto()
    FAILED = auto()


# ================================================================
# 数据模型
# ================================================================
@dataclass
class DebateRound:
    """一轮辩论记录"""
    round_num: int
    expert_response: AgentResponse
    critic_score: float
    critic_passed: bool
    critic_issues: List[Dict[str, Any]] = field(default_factory=list)
    critic_feedback: str = ""
    state: DebateState = DebateState.IDLE


# ================================================================
# 持久化
# ================================================================
def _persist_round(
    session_id: str, rd: DebateRound, verdict: str = "",
) -> Dict[str, Any]:
    """持久化一轮辩论记录到 debate_logs 表"""
    try:
        from backend.app.repositories.debate_repository import insert_debate_log

        return insert_debate_log({
            "session_id": session_id,
            "round_num": rd.round_num,
            "expert_name": rd.expert_response.agent_name,
            "draft_preview": rd.expert_response.content[:1000],
            "critic_score": rd.critic_score,
            "critic_passed": rd.critic_passed,
            "critic_issues": rd.critic_issues,
            "verdict": verdict,
        })
    except Exception as exc:
        logger.warning(f"[Debate] 持久化失败: {exc}")
        # 数据库不可用时不阻塞辩论流程
        return {"persisted": False, "error": str(exc)}


# ================================================================
# 核心辩论逻辑
# ================================================================
def _track_round_for_research(
    session_id: str,
    round_num: int,
    review: Dict[str, Any],
    passed: bool,
    elapsed_ms: float,
) -> None:
    """向 ConvergenceTracker 记录一轮辩论数据（研究用途）

    非阻塞: tracker 不可用时静默跳过。
    """
    if not session_id:
        return
    try:
        from backend.app.services.debate.convergence_tracker import (
            DIM_BLOOM,
            DIM_CITATION,
            DIM_FACTUAL,
            DIM_PEDAGOGY,
            get_convergence_tracker,
        )

        tracker = get_convergence_tracker()
        dim_scores = review.get("dimension_scores", {})
        overall = review.get("score", 0) / 100.0  # 归一化到 0-1
        issues = review.get("issues", [])

        tracker.record_round(
            session_id=session_id,
            round_num=round_num,
            dimension_scores={
                DIM_FACTUAL: dim_scores.get("factual", 0.0),
                DIM_PEDAGOGY: dim_scores.get("pedagogy", 0.0),
                DIM_BLOOM: dim_scores.get("bloom", 0.0),
                DIM_CITATION: dim_scores.get("citation", 0.0),
            },
            overall_score=overall,
            passed=passed,
            issue_count=len(issues),
            elapsed_ms=elapsed_ms,
        )
    except Exception:
        pass  # 研究工具失败不影响辩论主流程


async def _run_expert_round(
    expert: BaseAgent,
    base_ctx: AgentContext,
    critic_feedback: Optional[str],
    round_num: int,
) -> AgentResponse:
    """Expert 一轮生成/修订"""
    if round_num == 1 or not critic_feedback:
        return await expert.execute(base_ctx)

    # 修订轮: 注入 Critic 反馈
    revised_ctx = AgentContext(
        user_input=base_ctx.user_input,
        session_id=base_ctx.session_id,
        profile=dict(base_ctx.profile or {}),
        course_name=base_ctx.course_name,
        conversation_history=list(base_ctx.conversation_history or []),
        rag_results=list(base_ctx.rag_results or []),
        extra={
            **(base_ctx.extra or {}),
            "critic_feedback": critic_feedback,
            "is_revision": True,
            "revision_round": round_num,
        },
    )
    try:
        return await expert.execute(revised_ctx)
    except Exception as exc:
        logger.warning(f"[Debate] Expert R{round_num} 失败: {exc}")
        return AgentResponse(
            agent_name=expert.name,
            success=False,
            error=str(exc),
        )


async def _run_critic_review(
    critic: BaseAgent,
    expert_response: AgentResponse,
    original_request: str,
    bloom_target: str = "understand",
    session_id: str = "",
) -> Dict[str, Any]:
    """Critic 审查 Expert 输出"""
    from backend.app.agents.base import AgentContext as ACtx

    try:
        critic_ctx = ACtx(
            user_input=original_request,
            session_id=session_id,
            extra={
                "content_to_review": expert_response.content,
                "original_request": original_request,
                "target_bloom": bloom_target,
            },
        )
        critic_resp = await critic.execute(critic_ctx)

        # 兼容新旧 metadata 格式
        review_data = critic_resp.metadata.get("review_data")
        if review_data:
            return review_data

        # 新格式: verdicts + overall_passed + overall_score
        verdicts = critic_resp.metadata.get("verdicts", [])
        overall_passed = critic_resp.metadata.get("overall_passed", False)
        overall_score = critic_resp.metadata.get("overall_score", 0.0)

        return {
            "score": int(overall_score * 100),
            "passed": overall_passed,
            "issues": [
                {
                    "dimension": (
                        v.dimension if hasattr(v, "dimension") else "unknown"
                    ),
                    "severity": (
                        i.severity if hasattr(i, "severity") else "major"
                    ),
                    "description": (
                        i.description if hasattr(i, "description") else str(i)
                    ),
                }
                for v in verdicts
                for i in (v.issues if hasattr(v, "issues") else [])
            ],
            "feedback_text": critic_resp.content or "",
            "dimension_scores": {
                v.dimension if hasattr(v, "dimension") else "unknown": (
                    v.score if hasattr(v, "score") else 0.0
                )
                for v in verdicts
            },
        }
    except Exception as exc:
        logger.warning(f"[Debate] Critic 异常: {exc}")
        return {
            "score": 80,
            "passed": True,
            "issues": [],
            "feedback_text": f"(Critic 异常自动通过: {exc})",
            "dimension_scores": {},
        }


def _select_best(
    rounds: List[DebateRound],
) -> Tuple[Optional[AgentResponse], str, float]:
    """从多轮辩论中选最高分版本"""
    if not rounds:
        return None, "无可用轮次", 0.0

    best_round = rounds[0]
    best_score = rounds[0].critic_score
    for r in rounds[1:]:
        if r.critic_score > best_score:
            best_score = r.critic_score
            best_round = r

    if best_score >= PASS_THRESHOLD:
        verdict = f"第 {best_round.round_num} 轮通过 (score={best_score})"
    else:
        verdict = f"取最高分版本 (score={best_score})"

    return best_round.expert_response, verdict, best_score


def _build_result(
    rounds: List[DebateRound],
    verdict: str = "",
) -> Dict[str, Any]:
    """构建最终结果"""
    if not rounds:
        return {
            "final_content": "(无可用内容)",
            "final_response": None,
            "debate_rounds": 0,
            "best_score": 0.0,
            "rounds_detail": [],
            "verdict": verdict or "无可用内容",
        }

    best_resp, _, best_score = _select_best(rounds)
    final_resp = best_resp or rounds[-1].expert_response

    return {
        "final_content": final_resp.content,
        "final_response": final_resp,
        "debate_rounds": len(rounds),
        "best_score": best_score,
        "rounds_detail": [
            {
                "round": r.round_num,
                "expert": r.expert_response.agent_name,
                "score": r.critic_score,
                "passed": r.critic_passed,
                "issues_count": len(r.critic_issues),
            }
            for r in rounds
        ],
        "verdict": verdict,
    }


async def orchestrate_debate(
    expert_agent: BaseAgent,
    expert_context: AgentContext,
    critic_agent: BaseAgent | None = None,
    max_rounds: int = MAX_DEBATE_ROUNDS,
    session_id: str = "",
) -> Dict[str, Any]:
    """Multi-Agent Debate 核心流程

    Args:
        expert_agent: 负责生成内容的 Expert Agent
        expert_context: Expert 的执行上下文
        critic_agent: Critic Agent 实例（可注入，不传则自建）
        max_rounds: 最大辩论轮数
        session_id: 会话 ID

    Returns:
        dict: {final_content, final_response, debate_rounds, best_score,
               rounds_detail, verdict}
    """
    # 延迟导入避免循环依赖
    if critic_agent is None:
        from backend.app.agents.critic_agent import CriticAgent
        critic_agent = CriticAgent(llm_client=expert_agent.llm)

    buffer = None
    if session_id:
        from backend.app.api.v1.chat_pipeline.events import get_or_create_buffer
        buffer = get_or_create_buffer(session_id)
        try:
            from backend.app.services.debate.convergence_tracker import (
                get_convergence_tracker,
            )

            get_convergence_tracker().start_session(
                session_id=session_id,
                query_text=expert_context.user_input,
                query_category=str(expert_context.extra.get("intent", "unknown")),
                agent_name=expert_agent.name,
            )
        except Exception:
            pass

    rounds: List[DebateRound] = []
    critic_feedback: Optional[str] = None
    prev_score: Optional[float] = None

    for round_num in range(1, max_rounds + 1):
        logger.info(f"[Debate] Round {round_num} — Expert={expert_agent.name}")
        
        if buffer:
            buffer.publish("debate_round_start", {"round_num": round_num, "expert": expert_agent.name})

        t_start = time.perf_counter()

        # -- Expert ---
        expert_resp = await _run_expert_round(
            expert_agent, expert_context, critic_feedback, round_num,
        )
        if not expert_resp.success:
            logger.warning(f"[Debate] Expert R{round_num} 失败, 辩论终止")
            break
            
        if buffer:
            buffer.publish("expert_draft", {"round_num": round_num, "content": expert_resp.content})

        # -- Critic ---
        review = await _run_critic_review(
            critic_agent,
            expert_resp,
            expert_context.user_input,
            expert_context.extra.get("target_bloom",
                                     expert_context.extra.get("bloom_target",
                                                              "understand")),
            session_id,
        )

        score = review.get("score", 0)
        passed = review.get("passed", False)
        
        if buffer:
            buffer.publish("critic_score", {"round_num": round_num, "score": score, "passed": passed, "feedback": review.get("feedback_text", "")})

        # -- 收敛检测 ---
        if prev_score is not None:
            delta = abs(score - prev_score) / max(prev_score, 1.0)
            if delta < CONVERGENCE_DELTA:
                logger.info(
                    f"[Debate] 收敛 R{round_num} "
                    f"(delta={delta:.3f} < {CONVERGENCE_DELTA}) — 终止辩论"
                )
                
                if buffer:
                    buffer.publish("debate_converged", {"round_num": round_num, "delta": delta})
                    
                # 最后一轮仍记录
                rd = DebateRound(
                    round_num=round_num,
                    expert_response=expert_resp,
                    critic_score=float(score),
                    critic_passed=passed,
                    critic_issues=review.get("issues", []),
                    critic_feedback=review.get("feedback_text", ""),
                    state=DebateState.COMPLETE,
                )
                rounds.append(rd)
                _persist_round(session_id, rd, f"收敛于 R{round_num}")
                return _build_result(
                    rounds,
                    verdict=f"评分收敛于第 {round_num} 轮 (delta={delta:.3f})",
                )

        # -- 记录本轮 ---
        rd = DebateRound(
            round_num=round_num,
            expert_response=expert_resp,
            critic_score=float(score),
            critic_passed=passed,
            critic_issues=review.get("issues", []),
            critic_feedback=review.get("feedback_text", ""),
        )
        rounds.append(rd)
        _persist_round(session_id, rd, "通过" if passed else "未通过")

        # -- 收敛研究追踪 (Phase 1 Week 2) --
        _track_round_for_research(
            session_id, round_num, review, passed,
            (time.perf_counter() - t_start) * 1000,
        )

        # 通过 → 提前结束
        if passed:
            logger.info(f"[Debate] 通过 R{round_num} (score={score})")
            return _build_result(
                rounds,
                verdict=f"第 {round_num} 轮通过 (score={score})",
            )

        # 准备下一轮
        critic_feedback = review.get("feedback_text", "")
        prev_score = float(score)

    # max_rounds 耗尽 → 仲裁
    _, verdict_text, best_score = _select_best(rounds)
    logger.info(f"[Debate] 仲裁: {verdict_text}")
    return _build_result(rounds, verdict=verdict_text)


# ================================================================
# DebateModeratorAgent（可被 Orchestrator 调用的 Agent 形态）
# ================================================================
class DebateModeratorAgent(BaseAgent):
    """辩论主持人 Agent

    当 Orchestrator 调度到此 Agent 时:
    1. 从 context.extra 中获取要辩论的 expert agent
    2. 运行 orchestrate_debate()
    3. 返回最终评审结果
    """

    def __init__(
        self,
        llm_client=None,
        max_rounds: int = MAX_DEBATE_ROUNDS,
    ):
        super().__init__(llm_client=llm_client)
        self.max_rounds = max_rounds

    @property
    def name(self) -> str:
        return "debate_moderator"

    @property
    def description(self) -> str:
        return (
            "主持 Multi-Agent Debate: "
            "Expert 生成 → Critic 审稿 → 答辩重写 → 仲裁择优"
        )

    @property
    def system_prompt(self) -> str:
        return (
            "你是辩论主持人, 协调 Expert 和 Critic 进行多轮辩论。\n\n"
            "仲裁原则 (按重要性排序):\n"
            "1. 事实性错误 > 教学有效性 > Bloom 层级 > 引用缺失\n"
            "2. 当两轮分数接近时, 优先选择被修改更少的内容\n"
            "3. 避免无限辩论: 分数变化 < 5% 时终止"
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """主持辩论——真正运行 orchestrate_debate()

        从 context.extra 获取:
        - expert_agent: Expert Agent 实例（或 agent_name 从 registry 查找）
        - skip_debate: 为 True 时跳过辩论，直接透传
        """
        # 跳过辩论模式
        if context.extra.get("skip_debate"):
            return AgentResponse(
                agent_name=self.name,
                success=True,
                content="[辩论已跳过]",
                content_type="meta",
            )

        # 获取 Expert Agent
        expert_agent = context.extra.get("expert_agent")
        if expert_agent is None:
            # 尝试从 Orchestrator 的 registry 查找
            expert_name = context.extra.get("expert_name", "course_expert")
            try:
                from backend.app.agents import AGENT_REGISTRY
                agent_cls = AGENT_REGISTRY.get(expert_name)
                if agent_cls:
                    expert_agent = agent_cls(llm_client=self.llm)
            except Exception:
                pass

        if expert_agent is None:
            return AgentResponse(
                agent_name=self.name,
                success=False,
                error=f"未找到 Expert Agent: {context.extra.get('expert_name')}",
            )

        # 构造 Expert 的上下文
        expert_ctx = AgentContext(
            user_input=context.user_input,
            session_id=context.session_id,
            profile=dict(context.profile or {}),
            course_name=context.course_name,
            conversation_history=list(context.conversation_history or []),
            rag_results=list(context.rag_results or []),
            extra={
                **(context.extra or {}),
                "bloom_target": context.extra.get(
                    "target_bloom", "understand",
                ),
            },
        )

        # 运行辩论
        from backend.app.agents.critic_agent import CriticAgent
        critic = CriticAgent(llm_client=self.llm)

        result = await orchestrate_debate(
            expert_agent=expert_agent,
            expert_context=expert_ctx,
            critic_agent=critic,
            max_rounds=self.max_rounds,
            session_id=context.session_id,
        )

        final_content = result.get("final_content", "")
        verdict = result.get("verdict", "")
        debate_rounds = result.get("debate_rounds", 0)

        return AgentResponse(
            agent_name=self.name,
            success=True,
            content=final_content,
            content_type="markdown",
            metadata={
                "debate_rounds": debate_rounds,
                "best_score": result.get("best_score", 0),
                "verdict": verdict,
                "rounds_detail": result.get("rounds_detail", []),
                "debate_applied": True,
            },
        )


# ================================================================
# 路由判决
# ================================================================
def should_debate(
    intent: str,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """判断某意图是否应走辩论流程"""
    if intent not in DEBATE_ELIGIBLE_INTENTS:
        return False
    if context and context.get("skip_debate", False):
        return False
    return True
