"""
Chat API compatibility layer - learning state persistence

Provides upsert_profile / save_generated_path / save_evaluation for chat.py.
Tolerates missing Repository files: falls back to in-memory dicts that sync
with the API modules' _profiles / _paths / _assessments dicts.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from backend.app.core.telemetry import get_telemetry, Timer

logger = logging.getLogger(__name__)


def _track(stage: str, user_id: str, mode: str) -> Timer:
    """Helper: build a Timer for a learning_state_store stage."""
    return Timer("learning_state_duration_seconds", stage=stage, user_id=user_id, mode=mode)

_repo_mode = "memory"

try:
    from backend.app.repositories.profile_repo import ProfileRepository
    from backend.app.repositories.path_repo import LearningPathRepository
    from backend.app.repositories.assessment_repo import AssessmentRepository
    _profile_repo = ProfileRepository()
    _path_repo = LearningPathRepository()
    _assessment_repo = AssessmentRepository()
    _repo_mode = "sqlite"
    logger.info("[learning_state_store] SQLite mode (Repositories available)")
except ImportError:
    _profile_repo = None
    _path_repo = None
    _assessment_repo = None
    logger.warning("[learning_state_store] Memory mode (Repositories unavailable)")

# In-memory fallback stores
_mem_profiles: dict[str, dict] = {}
_mem_paths: dict[str, dict] = {}
_mem_assessments: dict[str, list] = {}


def upsert_profile(user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    with _track("upsert_profile", user_id, _repo_mode):
        if not profile:
            if _repo_mode == "sqlite":
                return _profile_repo.get(user_id)
            return _mem_profiles.get(user_id, {})
        if _repo_mode == "sqlite":
            return _profile_repo.replace(user_id, profile)
        _mem_profiles[user_id] = dict(profile)
        _sync_profile_to_api(user_id)
        return _mem_profiles[user_id]


def save_generated_path(user_id: str, path_data: dict[str, Any]) -> dict[str, Any] | None:
    with _track("save_path", user_id, _repo_mode):
        stages = path_data.get("stages") or []
        if not stages:
            return None
        if _repo_mode == "sqlite":
            return _path_repo.save(path_data)
        pid = str(path_data.get("id", ""))
        _mem_paths[pid] = dict(path_data)
        _sync_path_to_api(pid)
        return _mem_paths[pid]


def save_evaluation(user_id: str, evaluation_data: dict[str, Any]) -> dict[str, Any]:
    with _track("save_evaluation", user_id, _repo_mode):
        record = {
            "type": "evaluation",
            "score": float(evaluation_data.get("overall_score", 0)) * 100,
            "topic": "综合评估",
            "duration": 0,
            "timestamp": time.time(),
            "metadata": evaluation_data,
        }
        if _repo_mode == "sqlite":
            return _assessment_repo.add(user_id, record)
        if user_id not in _mem_assessments:
            _mem_assessments[user_id] = []
        _mem_assessments[user_id].append(record)
        _sync_assessment_to_api(user_id)
        return record


def _sync_profile_to_api(user_id: str) -> None:
    try:
        from backend.app.api.v1 import profile as api
        api._profiles[user_id] = _mem_profiles[user_id]
    except Exception:
        pass


def _sync_path_to_api(pid: str) -> None:
    try:
        from backend.app.api.v1 import learning_path as api
        api._paths[pid] = _mem_paths[pid]
    except Exception:
        pass


def _sync_assessment_to_api(user_id: str) -> None:
    try:
        from backend.app.api.v1 import assessment as api
        api._assessments[user_id] = list(_mem_assessments.get(user_id, []))
    except Exception:
        pass
