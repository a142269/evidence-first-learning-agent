"""
Learning path API - B owns /api/v1/learning-path/*

Persistence: prefers LearningPathRepository (SQLite), falls back to in-memory dict.
Chat API accesses _paths directly for backward compatibility.
"""
from __future__ import annotations

import logging
import json
import time as _time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Body, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/learning-path", tags=["learning-path"])

_repository = None
_paths: dict[str, dict] = {}  # chat.py backward-compat entry point

try:
    from backend.app.repositories.path_repo import LearningPathRepository
    _repository = LearningPathRepository()
except ImportError:
    logger.warning("[learning-path] Repository unavailable, using in-memory storage")


def _repair_legacy_text(value: Any) -> str:
    """修复历史种子数据中被 latin1 误解码的 GBK/UTF-8 中文。"""
    text = str(value or "")
    if not text:
        return ""
    candidates = [text]
    for encoding in ("gbk", "utf-8"):
        try:
            candidates.append(text.encode("latin1").decode(encoding))
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return max(candidates, key=lambda item: sum("\u4e00" <= char <= "\u9fff" for char in item))


@lru_cache(maxsize=1)
def _knowledge_catalog() -> dict[str, dict[str, Any]]:
    """课程知识目录：知识图谱为主，题库和持久化知识点为补充。"""
    root = Path(__file__).resolve().parents[4]
    catalog: dict[str, dict[str, Any]] = {}

    try:
        from backend.app.services.course_registry import get_course_registry

        # 聚合全部课程的知识点图谱（旧全局文件 + 各课程级文件）
        for kp_id, meta in get_course_registry().load_map_nodes().items():
            if not isinstance(meta, dict):
                continue
            hours = float(meta.get("estimated_hours", 0) or 0)
            catalog[str(kp_id)] = {
                "name": str(meta.get("name") or kp_id),
                "description": "；".join(str(item) for item in (meta.get("learning_objectives") or [])),
                "bloom_level": str(meta.get("bloom_level") or meta.get("bloom") or ""),
                "difficulty": int(meta.get("difficulty", 0) or 0),
                "estimated_minutes": round(hours * 60) if hours else 0,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learning-path] knowledge map unavailable: %s", exc)

    try:
        bank_payload = json.loads((root / "data" / "question_bank.json").read_text(encoding="utf-8"))
        for question in bank_payload.get("questions", []):
            kp_id = str(question.get("kp_id") or "")
            if not kp_id:
                continue
            entry = catalog.setdefault(kp_id, {})
            entry.setdefault("name", str(question.get("kp_name") or kp_id))
            entry.setdefault("bloom_level", str(question.get("bloom") or ""))
            entry.setdefault("difficulty", question.get("difficulty", 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learning-path] question bank unavailable: %s", exc)

    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord

        with SessionLocal() as db:
            for row in db.query(KnowledgePointRecord).all():
                entry = catalog.setdefault(str(row.id), {})
                entry.setdefault("name", _repair_legacy_text(row.name) or str(row.id))
                entry.setdefault("description", _repair_legacy_text(row.description))
                meta = row.metadata_data or {}
                entry.setdefault("bloom_level", str(meta.get("bloom_level") or meta.get("bloom") or ""))
                entry.setdefault("difficulty", int(meta.get("difficulty", 0) or 0))
                hours = float(meta.get("estimated_hours", 0) or 0)
                entry.setdefault("estimated_minutes", round(hours * 60) if hours else 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learning-path] persisted knowledge points unavailable: %s", exc)

    return catalog


def _path_masteries(user_id: str) -> dict[str, float]:
    if not user_id:
        return {}
    try:
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt

        return dict(get_bkt().get_all_masteries(user_id) or {})
    except Exception:  # noqa: BLE001
        return {}


def _build_stage_content(
    path: dict[str, Any],
    stage_id: str,
    *,
    catalog: dict[str, dict[str, Any]] | None = None,
    masteries: dict[str, float] | None = None,
) -> dict[str, Any]:
    stages = list(path.get("stages") or [])
    selected = next((stage for stage in stages if str(stage.get("id")) == str(stage_id)), None)
    if selected is None and str(stage_id).isdigit():
        index = int(stage_id)
        selected = stages[index] if 0 <= index < len(stages) else None
    if selected is None:
        raise HTTPException(status_code=404, detail="stage_not_found")

    knowledge = catalog if catalog is not None else _knowledge_catalog()
    mastery_map = masteries or {}
    explicit_items = list(selected.get("learning_items") or [])
    # 兼容早期种子与已有路径使用的 ``kps`` 字段。此前这里只认 kp_ids，
    # 导致路线图阶段存在但详情永远返回空数组。
    kp_ids = list(selected.get("kp_ids") or selected.get("kps") or [])
    if not kp_ids:
        kp_ids = [str(item.get("kp_id") or item.get("id") or "") for item in explicit_items]
    topics = list(selected.get("topics") or [])
    per_item_minutes = round(float(selected.get("estimated_minutes", 0) or 0) / max(len(kp_ids), 1))

    items: list[dict[str, Any]] = []
    for index, kp_id in enumerate(kp_ids):
        kp_id = str(kp_id)
        explicit = explicit_items[index] if index < len(explicit_items) and isinstance(explicit_items[index], dict) else {}
        meta = knowledge.get(kp_id, {})
        topic_name = topics[index] if index < len(topics) else ""
        name = str(explicit.get("name") or (topic_name if topic_name and topic_name != kp_id else "") or meta.get("name") or kp_id)
        description = str(explicit.get("description") or meta.get("description") or f"学习{name}的核心概念、方法与应用。")
        estimated_minutes = int(explicit.get("estimated_minutes") or meta.get("estimated_minutes") or per_item_minutes or 30)
        items.append({
            "kp_id": kp_id,
            "name": name,
            "description": description,
            "bloom_level": str(explicit.get("bloom_level") or meta.get("bloom_level") or "understand").lower(),
            "difficulty": int(explicit.get("difficulty") or meta.get("difficulty") or 2),
            "estimated_minutes": estimated_minutes,
            "mastery_pct": round(float(mastery_map.get(kp_id, 0.0)) * 100),
        })

    return {
        "path_id": path.get("id"),
        "stage": {"id": selected.get("id"), "title": selected.get("title", "学习阶段")},
        "items": items,
        "total": len(items),
        "source": "persisted_learning_path × knowledge_catalog × bkt",
    }


@router.get("/list")
def list_paths(user_id: str = Query(default="")):
    if _repository is not None:
        items = _repository.list(user_id=user_id) if user_id else _repository.list()
        # Repair older one-stage teacher recommendations that had already been
        # marked complete before the continuation flow was introduced.
        items = [
            _repository.continue_completed_teacher_path(str(item["id"])) or item
            for item in items
        ]
    else:
        items = list(_paths.values())
        if user_id:
            items = [p for p in items if p.get("user_id") == user_id]
        items.sort(key=lambda p: p.get("created_at", 0), reverse=True)
    return {"paths": items, "total": len(items)}


@router.get("/{path_id}")
def get_path(path_id: str):
    if _repository is not None:
        path = _repository.get(path_id)
    else:
        path = _paths.get(path_id)
    return {"error": "not_found"} if not path else {"path": path}


@router.get("/{path_id}/stages/{stage_id}/content")
def get_stage_content(
    path_id: str,
    stage_id: str,
    user_id: str = Query(default=""),
):
    """按需返回持久化路径中某阶段的真实知识点、目录信息与掌握度。"""
    path = _repository.get(path_id) if _repository is not None else _paths.get(path_id)
    if not path:
        raise HTTPException(status_code=404, detail="path_not_found")
    return _build_stage_content(
        path,
        stage_id,
        masteries=_path_masteries(user_id or str(path.get("user_id") or "")),
    )


@router.post("/save")
def save_path(payload: dict[str, Any] = Body(...)):
    path_id = f"path_{uuid.uuid4().hex[:10]}"
    record = {
        "id": path_id,
        "user_id": payload.get("user_id", ""),
        "title": payload.get("title", "学习路径"),
        "stages": payload.get("stages", []),
        "current_stage": 0,
        "progress": 0.0,
        "created_at": _time.time(),
    }
    if payload.get("metadata"):
        record.update(dict(payload["metadata"]))
    if _repository is not None:
        saved = _repository.save(record)
    else:
        _paths[path_id] = record
        saved = record
    return {"path_id": path_id, "path": saved}


@router.post("/{path_id}/progress")
def update_progress(path_id: str, payload: dict[str, Any] = Body(...)):
    stage_index = payload.get("stage_index", 0)
    completed = payload.get("completed", False)
    if _repository is not None:
        path = _repository.update_progress(path_id, stage_index, completed)
        if path is not None and completed:
            path = _repository.continue_completed_teacher_path(path_id) or path
    else:
        path = _paths.get(path_id)
        if path and completed and stage_index < len(path.get("stages", [])):
            path["current_stage"] = stage_index + 1
            path["progress"] = (stage_index + 1) / max(len(path["stages"]), 1) * 100
    return {"error": "not_found"} if not path else {"path": path}


# ============================================================
# Plan P1-2：双图学习路径（先修图 + 语义相似图）
# ============================================================
@router.post("/dual-graph")
def plan_dual_graph(payload: dict[str, Any] = Body(...)):
    """Plan P1-2 双图路径规划：主路径 / 绕行路径 / 卡点补救路径。

    body: {"user_id": "...", "focus_kp": "...", "mastery_threshold": 0.6, "max_steps": 8}
    """
    from backend.app.services.learning_path_dual_graph import get_dual_graph_path_planner

    user_id = str(payload.get("user_id", "")).strip()
    focus_kp = str(payload.get("focus_kp", "")).strip()
    threshold = float(payload.get("mastery_threshold", 0.6))
    max_steps = int(payload.get("max_steps", 8))
    if not user_id or not focus_kp:
        return {"error": "missing_user_or_focus"}
    planner = get_dual_graph_path_planner()
    return planner.plan(
        user_id=user_id,
        focus_kp=focus_kp,
        mastery_threshold=threshold,
        max_steps=max_steps,
    )
