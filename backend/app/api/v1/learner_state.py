"""Plan P1-7：LearnerState API

GET /api/v1/learner-state/{user_id}             → 当前统一学习者状态 + 推荐解释
GET /api/v1/learner-state/{user_id}/timeline    → 画像/路径调整/错题/评估/资源 事件流
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.learner_state import get_learner_state_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learner-state", tags=["learner-state"])


@router.get("/{user_id}")
def get_learner_state(user_id: str) -> Dict[str, Any]:
    """统一学习者状态快照。

    聚合：profile / mastery / mistakes / review_schedule / resources / strategy /
    assessment / recommendation 八个块，前端 Profile 时间线和"为什么系统这么推荐"
    直接拿这个对象渲染。
    """
    try:
        snap = get_learner_state_service().snapshot(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[learner-state] snapshot failed for %s", user_id)
        raise HTTPException(status_code=500, detail=f"learner_state_failed: {exc}") from exc
    if not snap.get("profile", {}).get("profile"):
        # 用户不存在 / 无画像，返回 404
        raise HTTPException(status_code=404, detail=f"learner_not_found: {user_id}")
    return snap


@router.get("/{user_id}/timeline")
def get_learner_state_timeline(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    """学习者状态时间线：profile_snapshot / path_adjustment / mistake_recorded /
    assessment / resource_generated 五类事件，按 timestamp 倒序。"""
    try:
        return get_learner_state_service().timeline(user_id, limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[learner-state] timeline failed for %s", user_id)
        raise HTTPException(status_code=500, detail=f"learner_timeline_failed: {exc}") from exc


@router.get("/{user_id}/recommendation")
def get_learner_state_recommendation(user_id: str) -> Dict[str, Any]:
    """只返回 recommendation 块，前端低频刷新用。"""
    snap = get_learner_state_service().snapshot(user_id)
    return {
        "user_id": user_id,
        "version": snap.get("version"),
        "generated_at": snap.get("generated_at"),
        "recommendation": snap.get("recommendation"),
    }
