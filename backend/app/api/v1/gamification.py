"""
Gamification API - B owns /api/v1/gamification/*
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any
from fastapi import APIRouter, Body

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gamification", tags=["gamification"])

XP_RULES = {"complete_quiz": 5, "correct_answer": 3, "streak_3_days": 20,
            "streak_7_days": 50, "bloom_analyze": 10, "bloom_create": 15,
            "resource_read": 1, "path_complete": 30}

ACHIEVEMENTS = {
    "first_blood": {"name": "首次答题", "desc": "完成第1道练习题", "xp_bonus": 10},
    "century": {"name": "百题斩", "desc": "累计完成100道题", "xp_bonus": 50},
    "perfectionist": {"name": "满分达成", "desc": "单次测验获得满分", "xp_bonus": 30},
    "streak_7": {"name": "七日坚持", "desc": "连续7天打卡学习", "xp_bonus": 50},
    "bloom_creator": {"name": "创造者", "desc": "完成Bloom Create层级任务", "xp_bonus": 40},
    "master_kp": {"name": "知识达人", "desc": "首次100%掌握一个知识点", "xp_bonus": 25},
}

_db_available = True
try:
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import GamificationProfileRecord
except ImportError:
    _db_available = False

_mem: dict[str, dict] = {}

_ACHIEVEMENT_LABELS = {
    "first_correct": "首次答对",
    "streak_7d": "七日坚持",
    "tutor_socratic_3": "深度追问",
}
_CHECKIN_PREFIX = "__checkin__::"


def _achievement_codes(values: list[Any]) -> list[str]:
    codes: list[str] = []
    for value in values:
        code = str(value.get("code") or "") if isinstance(value, dict) else str(value)
        if code and not code.startswith(_CHECKIN_PREFIX):
            codes.append(code)
    return list(dict.fromkeys(codes))


def _checked_in_today(values: list[Any]) -> bool:
    marker = f"{_CHECKIN_PREFIX}{date.today().isoformat()}"
    return any(str(value) == marker for value in values if not isinstance(value, dict))


def _ensure(user_id: str) -> dict:
    if _db_available:
        try:
            with SessionLocal() as db:
                row = db.get(GamificationProfileRecord, user_id)
                if row is None:
                    row = GamificationProfileRecord(user_id=user_id)
                    db.add(row)
                    db.commit()
                    db.refresh(row)
                return {"xp": row.xp or 0, "level": row.level or 1,
                        "streak_days": row.streak_days or 0,
                        "achievements": list(row.achievements or [])}
        except Exception:
            pass
    if user_id not in _mem:
        _mem[user_id] = {"xp": 0, "level": 1, "streak_days": 0, "achievements": []}
    return _mem[user_id]


def _save(user_id: str, data: dict) -> None:
    if _db_available:
        try:
            with SessionLocal() as db:
                row = db.get(GamificationProfileRecord, user_id)
                if row is None:
                    row = GamificationProfileRecord(user_id=user_id)
                    db.add(row)
                row.xp = data["xp"]
                row.level = data["level"]
                row.streak_days = data.get("streak_days", 0)
                row.achievements = list(data.get("achievements", []))
                row.updated_at = time.time()
                db.commit()
        except Exception:
            _mem[user_id] = data
    else:
        _mem[user_id] = data


@router.get("/{user_id}")
def get_profile(user_id: str):
    data = _ensure(user_id)
    raw_achievements = list(data.get("achievements", []))
    codes = _achievement_codes(raw_achievements)
    labels = [
        ACHIEVEMENTS.get(code, {}).get("name") or _ACHIEVEMENT_LABELS.get(code) or code
        for code in codes
    ]
    return {"user_id": user_id, "xp": data["xp"], "level": data["level"],
            "xp_to_next_level": data["level"] * 100 - (data["xp"] % max(data["level"] * 100, 1)),
            "streak_days": data.get("streak_days", 0),
            "achievements": labels, "achievement_codes": codes,
            "achievements_total": len(ACHIEVEMENTS),
            "achievements_earned": len(codes),
            "checked_in_today": _checked_in_today(raw_achievements)}


@router.post("/{user_id}/xp")
def add_xp(user_id: str, payload: dict[str, Any] = Body(...)):
    action = str(payload.get("action", ""))
    count = int(payload.get("count", 1))
    gain = XP_RULES.get(action, 1) * count
    data = _ensure(user_id)
    data["xp"] += gain
    data["level"] = max(1, (data["xp"] // 100) + 1)
    _save(user_id, data)
    return {"user_id": user_id, "xp_gained": gain, "total_xp": data["xp"], "level": data["level"]}


@router.post("/{user_id}/achievement")
def unlock_achievement(user_id: str, payload: dict[str, Any] = Body(...)):
    key = str(payload.get("achievement_key", ""))
    if key not in ACHIEVEMENTS:
        return {"error": "unknown_achievement", "key": key}
    ach = ACHIEVEMENTS[key]
    data = _ensure(user_id)
    if key in _achievement_codes(list(data.get("achievements", []))):
        return {"status": "already_unlocked", "key": key}
    data["achievements"].append(key)
    data["xp"] += ach["xp_bonus"]
    data["level"] = max(1, (data["xp"] // 100) + 1)
    _save(user_id, data)
    return {"status": "unlocked", "achievement": ach, "xp_bonus": ach["xp_bonus"],
            "total_xp": data["xp"], "level": data["level"]}


@router.post("/{user_id}/checkin")
def daily_checkin(user_id: str):
    data = _ensure(user_id)
    achievements = list(data.get("achievements", []))
    if _checked_in_today(achievements):
        return {
            "status": "already_checked_in", "user_id": user_id,
            "streak_days": data.get("streak_days", 0), "bonus_xp": 0,
            "total_xp": data["xp"], "level": data["level"],
        }
    data["streak_days"] = data.get("streak_days", 0) + 1
    bonus = 0
    if data["streak_days"] % 3 == 0:
        bonus = XP_RULES["streak_3_days"]
    if data["streak_days"] == 7:
        bonus = XP_RULES["streak_7_days"]
    data["xp"] += bonus + 2
    data["level"] = max(1, (data["xp"] // 100) + 1)
    data["achievements"] = [
        item for item in achievements
        if isinstance(item, dict) or not str(item).startswith(_CHECKIN_PREFIX)
    ] + [f"{_CHECKIN_PREFIX}{date.today().isoformat()}"]
    _save(user_id, data)
    return {"status": "checked_in", "user_id": user_id, "streak_days": data["streak_days"],
            "bonus_xp": bonus, "total_xp": data["xp"], "level": data["level"]}
