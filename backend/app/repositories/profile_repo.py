from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from backend.app.core.database import SessionLocal
from backend.app.core.models import ProfileRecord, ProfileSnapshotRecord


def _deep_merge(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(current)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


class ProfileRepository:
    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory

    def get(self, user_id: str) -> dict[str, Any]:
        with self.session_factory() as db:
            row = db.get(ProfileRecord, user_id)
            return deepcopy(row.profile_data) if row else {}

    def upsert(
        self, user_id: str, updates: dict[str, Any], source: str = "manual"
    ) -> dict[str, Any]:
        with self.session_factory() as db:
            try:
                row = db.get(ProfileRecord, user_id)
                if row is None:
                    row = ProfileRecord(user_id=user_id, profile_data={}, version=0)
                    db.add(row)
                row.profile_data = _deep_merge(row.profile_data or {}, updates or {})
                row.version = max(1, int(row.version or 0) + 1)
                db.add(ProfileSnapshotRecord(
                    user_id=user_id,
                    version=row.version,
                    profile_data=deepcopy(row.profile_data),
                    changed_keys=sorted((updates or {}).keys()),
                    source=source,
                ))
                db.commit()
                db.refresh(row)
                return deepcopy(row.profile_data)
            except Exception:
                db.rollback()
                raise

    def history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """画像演变时间线（新→旧），「随学随新」的可追溯证据。"""
        with self.session_factory() as db:
            rows = (
                db.query(ProfileSnapshotRecord)
                .filter(ProfileSnapshotRecord.user_id == user_id)
                .order_by(ProfileSnapshotRecord.created_at.desc(),
                          ProfileSnapshotRecord.id.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "version": r.version,
                    "changed_keys": list(r.changed_keys or []),
                    "source": r.source,
                    "profile": deepcopy(r.profile_data or {}),
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def replace(
        self, user_id: str, profile: dict[str, Any], source: str = "chat"
    ) -> dict[str, Any]:
        with self.session_factory() as db:
            try:
                row = db.get(ProfileRecord, user_id)
                if row is None:
                    row = ProfileRecord(user_id=user_id)
                    db.add(row)
                old = row.profile_data or {}
                new = deepcopy(profile or {})
                changed = sorted(
                    k for k in set(old) | set(new) if old.get(k) != new.get(k)
                )
                row.profile_data = new
                row.version = max(1, int(row.version or 0) + 1)
                if changed:
                    db.add(ProfileSnapshotRecord(
                        user_id=user_id,
                        version=row.version,
                        profile_data=deepcopy(new),
                        changed_keys=changed,
                        source=source,
                    ))
                db.commit()
                db.refresh(row)
                return deepcopy(row.profile_data)
            except Exception:
                db.rollback()
                raise

    def reset(self, user_id: str) -> bool:
        with self.session_factory() as db:
            try:
                row = db.get(ProfileRecord, user_id)
                if row is None:
                    return False
                db.delete(row)
                db.query(ProfileSnapshotRecord).filter(
                    ProfileSnapshotRecord.user_id == user_id
                ).delete(synchronize_session=False)
                db.commit()
                return True
            except Exception:
                db.rollback()
                raise
