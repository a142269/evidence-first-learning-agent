"""Learner 视角查询 API — 供知识图谱页做「学习路径叠加」与「掌握度趋势」。

补齐前端既有调用（GraphView 一直在请求这两个端点但后端此前不存在）:
  GET /learner/learning_path    — 学生最新学习路径（stage → kp 映射）
  GET /learner/mastery_history  — 某知识点的掌握度日历史（BKT 历史聚合）
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/learner", tags=["learner"])


def _kp_name_index(course: str) -> Dict[str, str]:
    """course 下 name → kp_id 的索引（stage 名称模糊解析用）。"""
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord

        with SessionLocal() as db:
            query = db.query(KnowledgePointRecord)
            if course:
                query = query.filter(KnowledgePointRecord.course == course)
            return {kp.name: kp.id for kp in query.all()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner] kp index failed: %s", exc)
        return {}


def _resolve_kp(stage: Any, name_index: Dict[str, str]) -> tuple[str, str]:
    """stage（dict 或 str）→ (kp_id, name)。优先显式 kp_id，再按名称精确/包含匹配。"""
    if isinstance(stage, str):
        name = stage
        explicit = ""
    else:
        name = str(stage.get("name") or stage.get("kp_name") or stage.get("title") or "")
        explicit = str(stage.get("kp_id") or "")
    if explicit:
        return explicit, name
    if name in name_index:
        return name_index[name], name
    for kp_name, kp_id in name_index.items():
        if kp_name and (kp_name in name or name in kp_name):
            return kp_id, name
    return "", name


@router.get("/learning_path")
def learning_path(
    user_id: str = Query(...),
    course: str = Query(default="artificial_intelligence"),
) -> Dict[str, Any]:
    """学生最新学习路径 → 图谱可叠加的 [{kp_id, name, order}] 序列。"""
    try:
        from backend.app.repositories.path_repo import LearningPathRepository
        paths = LearningPathRepository().list(user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner] path load failed: %s", exc)
        paths = []

    if not paths:
        return {"user_id": user_id, "path": [], "current_index": 0, "note": "no_path_yet"}

    latest = paths[0]  # list 已按 created_at 倒序
    name_index = _kp_name_index(course)
    path_items: List[Dict[str, Any]] = []
    for i, stage in enumerate(latest.get("stages") or []):
        kp_id, name = _resolve_kp(stage, name_index)
        path_items.append({"kp_id": kp_id, "name": name, "order": i + 1})

    return {
        "user_id": user_id,
        "path_id": latest.get("id"),
        "title": latest.get("title"),
        "path": path_items,
        "current_index": int(latest.get("current_stage") or 0),
    }


@router.get("/mastery_history")
def mastery_history(
    user_id: str = Query(...),
    kp_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=180),
) -> Dict[str, Any]:
    """某知识点掌握度日历史。

    数据源: BKT 答题历史（{correct, p_before, p_after, ts?}）。
    2026-07-09 起新记录带 ts 时间戳，按真实日期聚合；
    历史旧记录无 ts，按「最近一条 = 今天」向前均匀铺开（近似，供趋势图用）。
    """
    kp_name = kp_id
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord

        with SessionLocal() as db:
            kp = db.get(KnowledgePointRecord, kp_id)
            if kp is not None:
                kp_name = kp.name
    except Exception:  # noqa: BLE001
        pass

    try:
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt
        entries = list(get_bkt().get_history(user_id, kp_id) or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner] bkt history failed: %s", exc)
        entries = []

    if not entries:
        return {"user_id": user_id, "kp_id": kp_id, "kp_name": kp_name,
                "history": [], "note": "no_practice_yet"}

    # 补时间戳：无 ts 的旧记录按最近一条=现在、每条间隔一天向前铺
    now = time.time()
    day_seconds = 86400.0
    stamped: List[Dict[str, Any]] = []
    missing = sum(1 for e in entries if not e.get("ts"))
    synthetic_offset = missing
    for entry in entries:
        ts = float(entry.get("ts") or 0.0)
        if ts <= 0:
            synthetic_offset -= 1
            ts = now - synthetic_offset * day_seconds
        stamped.append({**entry, "ts": ts})

    cutoff = now - days * day_seconds
    stamped = [e for e in stamped if e["ts"] >= cutoff]

    # 按日聚合：mastery 取当日最后一条 p_after
    buckets: Dict[str, Dict[str, Any]] = {}
    for entry in sorted(stamped, key=lambda e: e["ts"]):
        date = datetime.fromtimestamp(entry["ts"]).strftime("%Y-%m-%d")
        bucket = buckets.setdefault(date, {"date": date, "mastery": 0.0, "attempts": 0, "correct": 0})
        bucket["attempts"] += 1
        bucket["correct"] += 1 if entry.get("correct") else 0
        bucket["mastery"] = round(float(entry.get("p_after") or 0.0), 4)

    return {
        "user_id": user_id,
        "kp_id": kp_id,
        "kp_name": kp_name,
        "history": list(buckets.values()),
    }
