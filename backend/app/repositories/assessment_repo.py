from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Callable

from backend.app.core.database import SessionLocal
from backend.app.core.models import AssessmentRecord


class AssessmentRepository:
    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory

    @staticmethod
    def _serialize(row: AssessmentRecord) -> dict[str, Any]:
        return {
            "type": row.record_type,
            "score": row.score,
            "topic": row.topic,
            "duration": row.duration,
            "timestamp": row.timestamp,
            "metadata": deepcopy(row.metadata_data or {}),
        }

    def add(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as db:
            try:
                external_id = record.get("external_id")
                if external_id:
                    existing = (
                        db.query(AssessmentRecord)
                        .filter(AssessmentRecord.external_id == str(external_id))
                        .one_or_none()
                    )
                    if existing:
                        return self._serialize(existing)
                row = AssessmentRecord(
                    external_id=str(external_id) if external_id else None,
                    user_id=user_id,
                    record_type=str(record.get("type", "activity")),
                    score=(
                        float(record["score"])
                        if record.get("score") is not None
                        else None
                    ),
                    topic=str(record.get("topic", "")),
                    duration=float(record.get("duration", 0)),
                    timestamp=float(record.get("timestamp", time.time())),
                    metadata_data=deepcopy(record.get("metadata", {})),
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return self._serialize(row)
            except Exception:
                db.rollback()
                raise

    def list(self, user_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        with self.session_factory() as db:
            query = (
                db.query(AssessmentRecord)
                .filter(AssessmentRecord.user_id == user_id)
                .order_by(AssessmentRecord.timestamp.asc(), AssessmentRecord.id.asc())
            )
            rows = query.all()
            if limit is not None:
                rows = rows[-limit:]
            return [self._serialize(row) for row in rows]

    def summary(self, user_id: str) -> dict[str, Any]:
        records = self.list(user_id)
        quiz_scores = [
            float(row["score"])
            for row in records
            if row["type"] == "quiz" and row["score"] is not None
        ]
        average = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0.0
        completed_task_ids = list(dict.fromkeys(
            str((row.get("metadata") or {}).get("task_id", ""))
            for row in records
            if row["type"] == "task_completed" and (row.get("metadata") or {}).get("task_id")
        ))
        return {
            "user_id": user_id,
            "total_sessions": len(records),
            "quiz_avg_score": round(average, 1),
            "resources_used": sum(row["type"] == "resource_view" for row in records),
            "questions_asked": sum(row["type"] == "question" for row in records),
            "completed_task_ids": completed_task_ids,
            "recent_records": records[-10:],
        }
