"""
ConversationPipeline - 7 阶段对话流水线核心

设计目标:
- 每个阶段是独立可测、可降级、可监控的 Stage 子类
- Stage 五件套: name / timeout / retry / fallback / metrics
- ConversationTelemetry 统一记录: 每阶段耗时 / Agent 调用链 / token 用量 / 错误
- 失败兜底: 单阶段失败不能拖垮整条流水线 (除非阶段标记为 fatal)

学术参考:
- Microservice Saga 模式
- LangGraph state machine
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ================================================================
# Telemetry
# ================================================================
@dataclass
class StageMetrics:
    """单阶段执行指标"""
    name: str
    duration_ms: float = 0.0
    success: bool = True
    retries: int = 0
    error: str = ""
    fallback_used: bool = False
    fatal: bool = False


@dataclass
class ConversationTelemetry:
    """整条流水线遥测数据

    用法:
        telemetry.add_stage(StageMetrics(...))
        telemetry.record_agent("course_expert")
        telemetry.record_tokens(prompt=120, completion=480)
        telemetry.summary()  # 导出给前端
    """
    session_id: str = ""
    pipeline_started_at: float = field(default_factory=time.time)
    stage_metrics: List[StageMetrics] = field(default_factory=list)
    agent_call_chain: List[str] = field(default_factory=list)
    token_usage: Dict[str, int] = field(
        default_factory=lambda: {"prompt": 0, "completion": 0, "total": 0}
    )
    total_ms: float = 0.0

    def add_stage(self, m: StageMetrics) -> None:
        self.stage_metrics.append(m)
        self.total_ms += m.duration_ms

    def record_agent(self, name: str) -> None:
        if name:
            self.agent_call_chain.append(name)

    def record_tokens(self, prompt: int = 0, completion: int = 0) -> None:
        self.token_usage["prompt"] += int(prompt)
        self.token_usage["completion"] += int(completion)
        self.token_usage["total"] = (
            self.token_usage["prompt"] + self.token_usage["completion"]
        )

    def has_fatal(self) -> bool:
        return any(m.fatal for m in self.stage_metrics)

    def summary(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_ms": round(self.total_ms, 2),
            "stages": [
                {
                    "name": m.name,
                    "ms": round(m.duration_ms, 2),
                    "success": m.success,
                    "retries": m.retries,
                    "fallback": m.fallback_used,
                    "fatal": m.fatal,
                    "error": m.error,
                }
                for m in self.stage_metrics
            ],
            "agents": list(self.agent_call_chain),
            "token_usage": dict(self.token_usage),
        }


# ================================================================
# Pipeline Context — 阶段间共享数据载体
# ================================================================
@dataclass
class PipelineContext:
    """阶段间共享上下文 - 替代原 _process_turn 局部变量大杂烩

    设计原则:
    - 早期阶段填充字段, 后期阶段消费
    - 字段命名清晰, 避免 dict[str, Any] 黑箱
    - extra 仅作为可选透传通道, 不放主路径数据
    """
    # ---- 输入 ----
    session_id: str = ""
    session: Dict[str, Any] = field(default_factory=dict)
    user_input: str = ""
    course: str = "artificial_intelligence"
    role_view: str = "student"

    # ---- 单 Agent 模式 (实验场私聊) ----
    target_agent: Optional[str] = None       # 前端 partner.key (planner/tutor/...)
    single_agent_mode: bool = False           # True 时跳过 profile/debate/reflection

    # ---- 阶段 1 输出: 校验通过 ----
    validated: bool = False
    abort_reason: str = ""

    # ---- 阶段 2 输出: RAG 检索 ----
    rag_results: List[Dict[str, Any]] = field(default_factory=list)

    # ---- 阶段 3 输出: 实时学情 ----
    realtime_state: Any = None
    strategy_prompt: str = ""

    # ---- 阶段 4 输出: Agent 编排 ----
    agent_results: Dict[str, Any] = field(default_factory=dict)

    # ---- 阶段 5 输出: 辩论 + 反思 ----
    debate_log: Optional[Dict[str, Any]] = None
    reflection_log: Dict[str, Any] = field(default_factory=dict)

    # ---- 阶段 6 输出: 聚合 + 安全 + 质量 ----
    primary_response: Any = None
    profile_response: Any = None
    aggregated_text: str = ""
    other_resources: List[Dict[str, Any]] = field(default_factory=list)
    safety_flag: str = "pass"
    safety_reason: str = ""
    quality: Dict[str, Any] = field(default_factory=dict)

    # ---- 阶段 7 输出: 持久化结果 ----
    saved_resources: List[Dict[str, Any]] = field(default_factory=list)

    # ---- 遥测 ----
    telemetry: ConversationTelemetry = field(default_factory=ConversationTelemetry)

    # ---- 可注入服务 (便于测试) ----
    services: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """流水线最终输出 - 直接送给 API 层序列化"""
    session_id: str
    primary_agent: str
    content: str
    content_type: str
    resources: List[Dict[str, Any]]
    saved_resources: List[Dict[str, Any]]
    profile: Dict[str, Any]
    realtime_state: Dict[str, Any]
    rag_hits: List[Dict[str, Any]]
    agents_invoked: List[Dict[str, Any]]
    quality: Dict[str, Any]
    safety: Dict[str, str]
    debate: Optional[Dict[str, Any]]
    reflection: Dict[str, Any]
    success: bool
    error: str
    telemetry: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "primary_agent": self.primary_agent,
            "content": self.content,
            "content_type": self.content_type,
            "resources": self.resources,
            "saved_resources": self.saved_resources,
            "profile": self.profile,
            "realtime_state": self.realtime_state,
            "rag_hits": self.rag_hits,
            "agents_invoked": self.agents_invoked,
            "quality": self.quality,
            "safety": self.safety,
            "debate": self.debate,
            "reflection": self.reflection,
            "success": self.success,
            "error": self.error,
            "telemetry": self.telemetry,
        }


# ================================================================
# Stage 抽象基类
# ================================================================
class Stage(ABC):
    """流水线阶段基类

    子类只需实现 run(ctx)。基类负责:
    - 超时控制
    - 重试 (可选)
    - 失败兜底
    - 自动遥测

    属性:
    - name:         阶段名 (用于日志 + 遥测)
    - timeout_seconds: 单次执行超时
    - retry_count:  重试次数 (0 = 不重试)
    - fatal_on_fail: 失败后是否终止整条流水线
    """

    name: str = "stage"
    timeout_seconds: float = 30.0
    retry_count: int = 0
    fatal_on_fail: bool = False

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> None:
        """阶段核心逻辑 - 子类必须实现"""

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        """失败兜底

        返回值:
        - True:  降级成功, 流水线继续
        - False: 降级失败, 视 fatal_on_fail 决定是否终止
        """
        logger.warning(f"[Pipeline] {self.name} fallback (no override): {error}")
        return True


# ================================================================
# Pipeline 调度器
# ================================================================
class ConversationPipeline:
    """7 阶段对话流水线调度器

    用法:
        pipeline = ConversationPipeline([
            InputValidationStage(),
            RAGRetrievalStage(),
            RealtimeStateStage(),
            OrchestrationStage(),
            DebateReflectionStage(),
            AggregationStage(),
            PersistStage(),
        ])
        ctx = PipelineContext(session_id=sid, ...)
        result_ctx = await pipeline.execute(ctx)

    设计:
    - 串行执行: 每阶段依赖前一阶段输出
    - 隔离失败: 单阶段失败 → fallback → 流水线继续
    - 阶段可独立替换 (测试时注入 mock)
    """

    def __init__(self, stages: List[Stage]):
        if not stages:
            msg = "Pipeline must have at least one stage"
            raise ValueError(msg)
        self.stages = stages

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """执行整条流水线"""
        if not ctx.telemetry.session_id:
            ctx.telemetry.session_id = ctx.session_id
        ctx.telemetry.pipeline_started_at = time.time()

        for stage in self.stages:
            should_continue = await self._run_stage(stage, ctx)
            if not should_continue:
                logger.info(
                    f"[Pipeline] terminated after stage={stage.name} "
                    f"reason={ctx.abort_reason or 'fatal'}"
                )
                break

        return ctx

    async def _run_stage(
        self, stage: Stage, ctx: PipelineContext,
    ) -> bool:
        """运行单个阶段, 返回 should_continue"""
        # Plan D · 2.1 阶段进入 SSE thinking 提示
        emit_thinking(ctx, _stage_label(stage.name, "start"))
        attempts = 0
        max_attempts = max(1, stage.retry_count + 1)
        start = time.perf_counter()
        metrics = StageMetrics(name=stage.name)
        last_error: Optional[Exception] = None

        while attempts < max_attempts:
            attempts += 1
            try:
                await asyncio.wait_for(
                    stage.run(ctx), timeout=stage.timeout_seconds,
                )
                metrics.success = True
                metrics.retries = attempts - 1
                last_error = None
                break
            except asyncio.TimeoutError as exc:
                last_error = exc
                metrics.error = f"timeout after {stage.timeout_seconds}s"
                logger.warning(
                    f"[Pipeline] {stage.name} timeout "
                    f"(attempt {attempts}/{max_attempts})"
                )
                emit_thinking(ctx, _stage_label(stage.name, "retry", metrics.error))
            except Exception as exc:
                last_error = exc
                metrics.error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    f"[Pipeline] {stage.name} error: {exc} "
                    f"(attempt {attempts}/{max_attempts})"
                )
                emit_thinking(ctx, _stage_label(stage.name, "error", metrics.error))

        # 全部尝试失败 → fallback
        if last_error is not None:
            metrics.success = False
            metrics.retries = attempts - 1
            try:
                metrics.fallback_used = await stage.fallback(ctx, last_error)
            except Exception as fb_exc:
                logger.exception(
                    f"[Pipeline] {stage.name} fallback raised: {fb_exc}"
                )
                metrics.fallback_used = False

            if not metrics.fallback_used and stage.fatal_on_fail:
                metrics.fatal = True

        metrics.duration_ms = (time.perf_counter() - start) * 1000
        ctx.telemetry.add_stage(metrics)

        # Plan D · 2.1 阶段完成 SSE thinking 提示
        if metrics.success:
            emit_thinking(
                ctx,
                _stage_label(stage.name, "done", f"{metrics.duration_ms:.0f}ms"),
            )
        elif metrics.fallback_used:
            emit_thinking(
                ctx,
                _stage_label(stage.name, "fallback", f"{metrics.duration_ms:.0f}ms"),
            )

        # ---- Prometheus 桥接 ----
        try:
            from backend.app.core.telemetry import get_telemetry
            tel = get_telemetry()
            status = "ok" if metrics.success else (
                "fallback" if metrics.fallback_used else "fail"
            )
            tel.counter("pipeline_stages_total").inc(
                stage=stage.name, status=status,
            )
            tel.histogram("pipeline_stage_duration_seconds").observe(
                metrics.duration_ms / 1000.0, stage=stage.name,
            )
        except Exception:
            # 指标收集不能影响业务
            pass

        # 决策: 是否继续
        if ctx.abort_reason:
            return False
        if metrics.fatal:
            return False
        return True


# ============================================================
# Plan D · 2.1 — Pipeline Stage thinking 推送辅助
# ============================================================
#
# Stage run 前后通过 emit_thinking(ctx, text) 主动推送 SSE thinking 事件；
# 这样前端能在回答到达前的 5-10s 等待里，看到 7 阶段逐步推进的提示。
#
# 数据流: stage.run() -> emit_thinking() -> buffer.publish("thinking", text)
#        -> chat.py event_generator 中 _process_turn 用 buffer.replay_after
#           把这些 thinking 事件实时 yield 给前端 SSE。
#
_STAGE_PROMPTS: dict[str, dict[str, str]] = {
    "input_validation": {
        "start": "正在准备会话...",
        "done": "会话就绪",
        "error": "会话准备失败",
    },
    "rag_retrieval": {
        "start": "正在检索知识库...",
        "done": "知识检索完成",
        "error": "知识检索失败",
        "retry": "知识检索超时，重试中",
    },
    "realtime_state": {
        "start": "正在分析你的学习状态...",
        "done": "学习状态分析完成",
        "error": "学习状态分析失败",
    },
    "orchestration": {
        "start": "Agent 团队正在协作（画像分析师 + 课程专家 + ...）...",
        "done": "多 Agent 协作完成",
        "error": "Agent 协作失败",
    },
    "debate_reflection": {
        "start": "Agent 正在辩论与反思...",
        "done": "辩论与反思完成",
        "error": "辩论/反思失败",
        "fallback": "辩论阶段跳过，进入下一步",
    },
    "aggregation": {
        "start": "正在进行内容安全审核...",
        "done": "内容安全审核通过",
        "error": "内容安全审核报警",
    },
    "persist": {
        "start": "正在保存学习记录...",
        "done": "学习记录已保存",
        "error": "学习记录保存失败",
    },
}


def _stage_label(stage_name: str, kind: str, detail: str = "") -> str:
    """从 _STAGE_PROMPTS 中查中文提示，没有就退化成 stage_name。"""
    prompts = _STAGE_PROMPTS.get(stage_name, {})
    base = prompts.get(kind) or f"[{stage_name}] {kind}"
    if detail and kind in {"retry", "error"}:
        return f"{base}（{detail}）"
    return base


def emit_thinking(ctx: PipelineContext, text: str) -> None:
    """把提示文本塞进 SSE buffer；前端 WorkflowView thinking 面板会订阅。

    ctx.services["sse_buffer"] 是 chat.py event_generator 里塞进来的
    EventBuffer。如果 buffer 不可用（比如走 _process_turn 同步调用），
    安全降级为只记到 logger，不抛错。
    """
    buffer = ctx.services.get("sse_buffer") if isinstance(ctx.services, dict) else None
    if buffer is not None and hasattr(buffer, "publish"):
        try:
            evt = buffer.publish("thinking", text)
            logger.debug(f"[Pipeline/thinking] {text} (id={evt.event_id})")
            return
        except Exception as exc:  # pragma: no cover
            logger.warning(f"[Pipeline/thinking] buffer.publish failed: {exc}")
    logger.info(f"[Pipeline/thinking] {text}")
