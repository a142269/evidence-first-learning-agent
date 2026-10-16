"""
Cognitive diagnosis API - B owns /api/v1/cognitive/*
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cognitive", tags=["cognitive"])

BLOOM_LEVELS = ["remember","understand","apply","analyze","evaluate","create"]
BLOOM_LABELS = {"remember":"记忆","understand":"理解","apply":"应用","analyze":"分析","evaluate":"评价","create":"创造"}

_bkt = None
_bloom = None


class ReversePlanRequest(BaseModel):
    """Target-driven learning plan request."""

    current_mastery: float = Field(ge=0.0, le=1.0)
    target_mastery: float = Field(gt=0.0, le=1.0)
    horizon_days: int = Field(default=30, ge=1, le=365)
    questions_per_full_practice_day: int = Field(default=10, ge=1, le=200)
    user_id: str = ""
    kp_id: str = ""


class ReversePlanSchedulePoint(BaseModel):
    day: int
    expected_mastery: float
    cumulative_questions: int


class ReversePlanMilestone(BaseModel):
    day: int
    target: float
    projected: float
    label: str


class ReversePlanResponse(BaseModel):
    """Minimum daily practice required to reach a mastery target."""

    status: str
    current_mastery: float
    target_mastery: float
    horizon_days: int
    daily_practice_rate: float | None
    daily_questions: int | None
    projected_mastery: float
    schedule: list[ReversePlanSchedulePoint] = []
    milestones: list[ReversePlanMilestone] = []
    narrative: str = ""

try:
    from backend.app.services.cognitive_diagnosis.bkt import get_bkt
    from backend.app.services.cognitive_diagnosis.bloom_taxonomy import get_bloom
    _bkt = get_bkt()
    _bloom = get_bloom()
except ImportError:
    logger.warning("[cognitive] cognitive diagnosis service not available")


@router.get("/bloom/levels")
def bloom_levels():
    return {"levels": [{"key": lvl, "label": BLOOM_LABELS[lvl], "index": i}
                       for i, lvl in enumerate(BLOOM_LEVELS)]}


@router.get("/bloom/detail")
def bloom_detail(text: str = Query(..., description="题目文本或学习目标描述")):
    """Bloom 6×3 子层级详细分类（Anderson & Krathwohl 2001）。

    返回：主层级 + 子层级 + 知识维度 + 关键词匹配分数。
    """
    from backend.app.services.cognitive_diagnosis.bloom_6x3 import get_bloom6x3_config

    cfg = get_bloom6x3_config()
    result = cfg.classify_text(text)
    sub_info = cfg.get_sub_level(result["level"], result["sub_level"])
    kd_info = cfg.get_knowledge_dim(result["knowledge_dim"])
    return {
        "text": text,
        "level": result["level"],
        "level_label": BLOOM_LABELS.get(result["level"], ""),
        "sub_level": result["sub_level"],
        "sub_level_label": sub_info.get("label", ""),
        "definition": sub_info.get("definition", ""),
        "sub_definition": sub_info.get("definition", ""),
        "knowledge_dimension": result["knowledge_dim"],
        "knowledge_dim_label": kd_info.get("label", ""),
        "keywords_matched": result.get("score", 0),
        "examples": sub_info.get("examples", []),
        "anti_examples": sub_info.get("anti_examples", []),
    }



@router.post("/bloom/classify")
def classify_bloom(payload: dict[str, Any] = Body(...)):
    text = str(payload.get("text", ""))
    if not text:
        return {"error": "text_required"}
    if _bloom is None:
        return {"level": "understand", "label": "理解", "method": "fallback"}
    return _bloom.classify(text)


@router.get("/bkt/{user_id}")
def bkt_status(user_id: str):
    if _bkt is None:
        return {"user_id": user_id, "masteries": {}, "note": "BKT unavailable"}
    masteries = _bkt.get_all_masteries(user_id)
    return {"user_id": user_id, "masteries": masteries,
            "trends": {kp: _bkt.trend(user_id, kp) for kp in masteries}}


@router.post("/bkt/update")
def bkt_update(payload: dict[str, Any] = Body(...)):
    user_id = str(payload.get("user_id", ""))
    kp_id = str(payload.get("kp_id", ""))
    correct = bool(payload.get("correct", False))
    if not user_id or not kp_id:
        return {"error": "user_id and kp_id required"}
    if _bkt is None:
        return {"user_id": user_id, "kp_id": kp_id, "note": "BKT unavailable"}
    p = _bkt.update(user_id, kp_id, correct)
    return {"user_id": user_id, "kp_id": kp_id, "p_learned": round(p, 4),
            "trend": _bkt.trend(user_id, kp_id)}


@router.post("/diagnose")
def diagnose(payload: dict[str, Any] = Body(...)):
    try:
        from backend.app.services.cognitive_diagnosis.dina import diagnose_student
    except ImportError:
        return {"error": "DINA service unavailable"}
    responses = payload.get("responses", {})
    items = payload.get("items", [])
    kp_ids = payload.get("kp_ids", [])
    if not responses or not items or not kp_ids:
        return {"error": "responses, items, and kp_ids required"}
    responses_int = {int(sid): {int(iid): int(val) for iid, val in its.items()}
                     for sid, its in responses.items()}
    return diagnose_student(responses_int, items, kp_ids)


@router.get("/forecast")
def get_forecast(
    user_id: str = Query(...),
    kp_id: str = Query(default=""),
    horizon_days: int = Query(30, ge=1, le=90),
    use_kalman: bool = Query(True, description="是否对历史数据做 Kalman 平滑"),
):
    """学习时光机预测 — 基于真实 BKT 历史 + Kalman 平滑 + ASCII 可视化"""
    from backend.app.core.telemetry import get_telemetry, Timer
    from backend.app.services.timemachine_service import get_timemachine_service

    tele = get_telemetry()
    tele.counter("cognitive_operations_total").inc(algorithm="timemachine_forecast")

    try:
        svc = get_timemachine_service()
    except ImportError:
        return {"error": "TimeMachine service unavailable"}

    with Timer("cognitive_stage_duration_seconds", stage="timemachine_forecast"):
        if not kp_id:
            # 聚合：取所有 KP 的平均
            if _bkt is None:
                return {"error": "BKT service unavailable"}
            masteries = _bkt.get_all_masteries(user_id)
            if not masteries:
                return {"user_id": user_id, "forecast": [], "note": "no BKT data yet"}
            # 选一个代表性 KP（最低掌握度，最需要关注）
            kp_id = min(masteries, key=masteries.get)

        data = svc.forecast(
            user_id=user_id,
            kp_id=kp_id,
            horizon_days=horizon_days,
            use_kalman=use_kalman,
        )

    return {
        "user_id": user_id,
        "kp_id": kp_id,
        "current_mastery": data["current_mastery"],
        "forecast": data["forecast"],
        "milestones": data["milestones"],
        "summary_text": data["summary_text"],
        "ascii_chart": data["ascii_chart"],
        "svg": data.get("svg", ""),
    }



@router.get("/counterfactual")
def get_counterfactual(
    user_id: str = Query(...),
    kp_id: str = Query(default=""),
    horizon_days: int = Query(30, ge=1, le=90),
    daily_rates: list[float] = Query(default=[0.3, 0.5, 0.7, 0.9]),
):
    """反事实分析：不同每日练习强度下的 mastery 预测对比"""
    from backend.app.services.timemachine_service import get_timemachine_service

    try:
        svc = get_timemachine_service()
    except ImportError:
        return {"error": "TimeMachine service unavailable"}

    if not kp_id:
        if _bkt is None:
            return {"error": "BKT service unavailable"}
        masteries = _bkt.get_all_masteries(user_id)
        if not masteries:
            return {"user_id": user_id, "note": "no BKT data yet"}
        kp_id = min(masteries, key=masteries.get)

    result = svc.counterfactual(
        user_id=user_id,
        kp_id=kp_id,
        horizon_days=horizon_days,
        daily_rates=daily_rates,
    )
    result["user_id"] = user_id
    result["kp_id"] = kp_id
    return result


def _reverse_plan_payload(payload: dict[str, Any]):
    """目标倒推计划：给定当前/目标掌握度与期限，二分搜索最小每日练习强度。

    前端调用方：AnalyticsView「倒推计划」卡 + 「练习强度模拟器」。
    复用 BKTForecaster.reverse_plan（此前只有 service 无端点，前端一直 404）。
    """
    from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster

    current = max(0.0, min(1.0, float(payload.get("current_mastery", 0.3))))
    target = max(0.0, min(1.0, float(payload.get("target_mastery", 0.8))))
    horizon = max(1, min(90, int(payload.get("horizon_days", 30))))
    questions_per_day = max(
        1, min(50, int(payload.get("questions_per_full_practice_day", 10))),
    )

    # 可选 user_id/kp_id：提供时用该学生的个性化 BKT 参数（slip/guess/transit）
    user_id = str(payload.get("user_id", "")).strip()
    kp_id = str(payload.get("kp_id", "")).strip()
    if user_id and kp_id:
        try:
            from backend.app.services.timemachine_service import get_timemachine_service
            result = get_timemachine_service().reverse_plan(
                user_id=user_id,
                kp_id=kp_id,
                target_mastery=target,
                horizon_days=horizon,
                questions_per_full_practice_day=questions_per_day,
            )
            result["projected_mastery"] = round(float(result.get("projected_mastery") or 0.0), 4)
            return result
        except Exception:
            pass  # 回退到通用参数

    result = BKTForecaster().reverse_plan(
        current_mastery=current,
        target_mastery=target,
        horizon_days=horizon,
        questions_per_full_practice_day=questions_per_day,
    )
    result["current_mastery"] = round(current, 4)
    result["projected_mastery"] = round(float(result.get("projected_mastery") or 0.0), 4)
    return result


@router.post("/next-best-question")
def next_best_question(
    user_id: str = Query(..., description="学生 ID"),
    kp_id: str | None = Query(default=None, description="可选：限定知识点范围"),
    bloom: str | None = Query(default=None, description="可选：限定 Bloom 层级"),
    top_k: int = Query(default=5, ge=1, le=20),
    strategy: str = Query(default="entropy", description="entropy | margin | least_confident"),
):
    """Active Learning: 推荐下一道最有信息增益的题目。

    基于 BKT/DINA 后验预测熵，选择模型最不确定（p≈0.5）的题，
    最大化学习收益（Settles 2009 Active Learning Survey）。
    """
    from backend.app.core.telemetry import get_telemetry, Timer
    from backend.app.services.active_learning.uncertainty_sampler import get_active_learning_service

    tele = get_telemetry()
    tele.counter("cognitive_operations_total").inc(algorithm="active_learning")

    try:
        svc = get_active_learning_service()
    except ImportError:
        return {"error": "Active Learning service unavailable"}

    with Timer("cognitive_stage_duration_seconds", stage="active_learning"):
        result = svc.next_best_questions(
            user_id=user_id,
            kp_id=kp_id,
            bloom=bloom,
            top_k=top_k,
            strategy=strategy,
        )

    return result


@router.post(
    "/reverse-plan",
    response_model=ReversePlanResponse,
    summary="Reverse-plan a mastery target",
    description=(
        "Calculate the minimum daily practice rate and question count required "
        "to reach a target mastery within a bounded horizon. "
        "根据目标掌握度倒推出最低每日练习强度。"
    ),
)
def reverse_plan(payload: ReversePlanRequest) -> ReversePlanResponse:
    result = _reverse_plan_payload(payload.model_dump())
    schedule, milestones = _build_reverse_plan_schedule(
        current_mastery=float(result.get("current_mastery", payload.current_mastery)),
        target_mastery=payload.target_mastery,
        horizon_days=payload.horizon_days,
        daily_rate=result.get("daily_practice_rate"),
        daily_questions=result.get("daily_questions"),
    )
    return ReversePlanResponse(
        status=result["status"],
        current_mastery=float(result.get("current_mastery", payload.current_mastery)),
        target_mastery=payload.target_mastery,
        horizon_days=payload.horizon_days,
        daily_practice_rate=result.get("daily_practice_rate"),
        daily_questions=result.get("daily_questions"),
        projected_mastery=result["projected_mastery"],
        schedule=schedule,
        milestones=milestones,
        narrative=_build_reverse_plan_narrative(
            result["status"],
            payload.target_mastery,
            payload.horizon_days,
            result.get("daily_practice_rate"),
            result.get("daily_questions"),
        ),
    )


def _build_reverse_plan_schedule(
    *,
    current_mastery: float,
    target_mastery: float,
    horizon_days: int,
    daily_rate: float | None,
    daily_questions: int | None,
) -> tuple[list[ReversePlanSchedulePoint], list[ReversePlanMilestone]]:
    """基于 BKTForecaster 生成逐日预测 + 25%/50%/75%/100% 四个里程碑。"""
    if daily_rate is None:
        return [], []
    from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster

    forecaster = BKTForecaster(daily_practice_rate=max(0.0, min(1.0, float(daily_rate))))
    points = forecaster.forecast(current_mastery=current_mastery, horizon_days=horizon_days)
    per_day_questions = int(daily_questions or 0)
    schedule: list[ReversePlanSchedulePoint] = []
    # 只挑几个代表性节点，避免 30~90 天的 schedule 太占屏幕
    step = max(1, horizon_days // 8)
    for p in points:
        if p.day == 0 or p.day == horizon_days or p.day % step == 0:
            schedule.append(
                ReversePlanSchedulePoint(
                    day=p.day,
                    expected_mastery=round(float(p.p_learned), 4),
                    cumulative_questions=per_day_questions * p.day,
                )
            )

    milestones: list[ReversePlanMilestone] = []
    delta = max(0.0, target_mastery - current_mastery)
    for ratio, label in ((0.25, "四分之一"), (0.5, "半程"), (0.75, "三分之二"), (1.0, "达成")):
        goal_mastery = round(min(1.0, current_mastery + delta * ratio), 4)
        # 找到首个满足该里程碑的日子
        milestone_day = horizon_days
        for p in points:
            if p.p_learned >= goal_mastery:
                milestone_day = p.day
                break
        milestones.append(
            ReversePlanMilestone(
                day=milestone_day,
                target=goal_mastery,
                projected=round(float(points[milestone_day].p_learned), 4) if milestone_day < len(points) else round(float(points[-1].p_learned), 4),
                label=label,
            )
        )
    return schedule, milestones


def _build_reverse_plan_narrative(
    status: str,
    target: float,
    horizon: int,
    daily_rate: float | None,
    daily_questions: int | None,
) -> str:
    """一句话说明当前计划难度。"""
    if status == "unreachable":
        return f"在 {horizon} 天内即使全力练习也难以到达 {target:.0%}，建议放宽期限或降低目标。"
    # 已达标（无需练习）
    if not daily_questions or not daily_rate:
        return f"目标 {target:.0%} 已达成，可以直接进入下一阶段挑战。"
    if daily_rate < 0.3:
        tone = "轻量"
    elif daily_rate < 0.6:
        tone = "适中"
    else:
        tone = "高强度"
    return (
        f"在 {horizon} 天内达到 {target:.0%} 掌握度，建议每日约 {daily_questions} 题 "
        f"（{tone}练习节奏），可穿插短时复盘保证稳定推进。"
    )


