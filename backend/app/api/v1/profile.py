"""
Learning profile API.

The public profile contract is the fixed six-dimension acceptance schema. Older
dimension keys are still accepted and preserved, then mapped into the standard
fields for backward compatibility.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body

from backend.app.services.profile_schema import (
    LEGACY_PROFILE_DIMENSIONS,
    PROFILE_FIELD_KEYS,
    PROFILE_SCHEMA_VERSION,
    STANDARD_PROFILE_DIMENSIONS,
    STANDARD_PROFILE_KEYS,
    calculate_profile_completeness,
    normalize_profile,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])

_repository = None
_profiles: dict[str, dict] = {}  # chat.py backward-compat entry point

try:
    from backend.app.repositories.profile_repo import ProfileRepository

    _repository = ProfileRepository()
except ImportError:
    logger.warning("[profile] Repository unavailable, using in-memory storage")

PROFILE_DIMENSIONS = STANDARD_PROFILE_DIMENSIONS


@lru_cache(maxsize=1)
def _seed_profiles() -> dict[str, dict[str, Any]]:
    data_dir = Path(__file__).resolve().parents[4] / "data"
    profiles: dict[str, dict[str, Any]] = {}
    sources = (("seed.json", "students"), ("seed_extended.json", "extra_students"))
    for filename, key in sources:
        try:
            seed = json.loads((data_dir / filename).read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[profile] seed fallback unavailable (%s): %s", filename, exc)
            continue
        for student in seed.get(key, []):
            user_id = str(student.get("user_id", ""))
            profile = student.get("profile", {})
            if user_id and isinstance(profile, dict):
                profiles[user_id] = normalize_profile(profile, preserve_extra=True)
    return profiles


def _fallback_profile(user_id: str) -> dict[str, Any]:
    if user_id.startswith("demo-student-"):
        return dict(_seed_profiles().get(user_id, {}))
    return {}


def _complete_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_profile(profile or {}, preserve_extra=True)


@router.get("/dimensions")
def get_dimensions():
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "dimensions": PROFILE_DIMENSIONS,
        "required_dimensions": list(STANDARD_PROFILE_KEYS),
        "legacy_dimensions": LEGACY_PROFILE_DIMENSIONS,
    }


@router.get("/{user_id}/history")
def get_profile_history(user_id: str, limit: int = 20):
    if _repository is not None and hasattr(_repository, "history"):
        snapshots = _repository.history(user_id, limit=limit)
    else:
        snapshots = []
    dim_labels = {
        **{k: v["label"] for k, v in PROFILE_DIMENSIONS.items()},
        **{k: v["label"] for k, v in LEGACY_PROFILE_DIMENSIONS.items()},
    }
    for snap in snapshots:
        snap["profile"] = _complete_profile(snap.get("profile", {}))
        snap["changed_labels"] = [
            dim_labels.get(k, k) for k in snap.get("changed_keys", [])
        ]
    return {"user_id": user_id, "count": len(snapshots), "snapshots": snapshots}


@router.get("/{user_id}")
def get_profile(user_id: str):
    if _repository is not None:
        profile = _repository.get(user_id)
    else:
        profile = _profiles.get(user_id, {})
    if not profile:
        profile = _fallback_profile(user_id)

    # demo 学生：用 seed 数据补充 DB 中 unknown/空的维度
    if user_id.startswith("demo-student-"):
        seed_profile = _seed_profiles().get(user_id)
        if seed_profile and isinstance(profile, dict):
            # seed 作为完整演示基线，DB 中真实更新按字段覆盖。这样旧数据库里
            # 已存在但缺少 score 的维度也能补齐，不会整张雷达图落在 0。
            merged = dict(seed_profile)
            for key, db_value in profile.items():
                seed_value = merged.get(key)
                if isinstance(seed_value, dict) and isinstance(db_value, dict):
                    merged[key] = {**seed_value, **db_value}
                elif db_value not in (None, "", [], {}):
                    merged[key] = db_value
            profile = merged

    profile = _complete_profile(profile)

    filled, total, completeness = calculate_profile_completeness(profile)
    return {
        "user_id": user_id,
        "profile": profile,
        "schema_version": PROFILE_SCHEMA_VERSION,
        "required_dimensions": list(STANDARD_PROFILE_KEYS),
        "completeness": completeness,
        "filled_dimensions": filled,
        "total_dimensions": total,
    }


@router.post("/{user_id}/update")
def update_profile(user_id: str, payload: dict[str, Any] = Body(...)):
    updates = payload.get("updates", {})
    if not isinstance(updates, dict):
        return get_profile(user_id)

    filtered = {k: v for k, v in updates.items() if k in PROFILE_FIELD_KEYS}
    if not filtered:
        return get_profile(user_id)

    normalized = _complete_profile(filtered)
    if _repository is not None:
        _repository.upsert(user_id, normalized, source=str(payload.get("source", "manual")))
    else:
        if user_id not in _profiles:
            _profiles[user_id] = {}
        current = _complete_profile(_profiles[user_id])
        current.update(normalized)
        _profiles[user_id] = current

    return get_profile(user_id)


@router.post("/{user_id}/reset")
def reset_profile(user_id: str):
    if _repository is not None:
        _repository.reset(user_id)
    else:
        _profiles.pop(user_id, None)
    return {"status": "reset", "user_id": user_id}
