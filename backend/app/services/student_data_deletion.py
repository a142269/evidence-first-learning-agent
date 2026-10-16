"""Transactional deletion of one student's private learning data.

Public course content, knowledge points, teacher resources and other students'
records are intentionally outside this service's scope.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from backend.app.core.database import SessionLocal
from backend.app.core.models import (
    AgentRunRecord,
    AssessmentRecord,
    BktStateRecord,
    ChatHistoryRecord,
    DebateLogRecord,
    DinaStateRecord,
    GamificationProfileRecord,
    GroupChatMessageRecord,
    LearnerArchetypeRecord,
    LearningPathRecord,
    MistakeRecord,
    MobileRoomMemberRecord,
    MobileRoomMessageRecord,
    MobileRoomReadRecord,
    ProfileRecord,
    ProfileSnapshotRecord,
    RealtimeStateRecord,
    ResourceRecord,
    ReviewEventRecord,
    Sm2ScheduleRecord,
)


def _delete(query) -> int:
    return int(query.delete(synchronize_session=False) or 0)


def delete_student_data(user_id: str) -> dict[str, Any]:
    """Delete all private records owned by ``user_id`` in one DB transaction."""
    normalized = user_id.strip()
    if not normalized:
        error = "user_id_required"
        raise ValueError(error)

    deleted: dict[str, int] = {}
    resource_ids: list[str] = []

    with SessionLocal() as db:
        session_ids = {
            value
            for (value,) in (
                db.query(ChatHistoryRecord.session_id)
                .filter(ChatHistoryRecord.user_id == normalized)
                .distinct()
                .all()
            )
            if value
        }
        session_ids.update(
            value
            for (value,) in (
                db.query(RealtimeStateRecord.session_id)
                .filter(RealtimeStateRecord.user_id == normalized)
                .distinct()
                .all()
            )
            if value
        )
        resource_ids = [
            value
            for (value,) in (
                db.query(ResourceRecord.id)
                .filter(ResourceRecord.user_id == normalized)
                .all()
            )
        ]

        if session_ids:
            deleted["debate_logs"] = _delete(
                db.query(DebateLogRecord).filter(
                    DebateLogRecord.session_id.in_(session_ids)
                )
            )

        user_models = (
            ("agent_runs", AgentRunRecord),
            ("assessments", AssessmentRecord),
            ("bkt_states", BktStateRecord),
            ("chat_history", ChatHistoryRecord),
            ("dina_states", DinaStateRecord),
            ("gamification_profiles", GamificationProfileRecord),
            ("learner_archetypes", LearnerArchetypeRecord),
            ("learning_paths", LearningPathRecord),
            ("mistakes", MistakeRecord),
            ("mobile_room_members", MobileRoomMemberRecord),
            ("mobile_room_reads", MobileRoomReadRecord),
            ("profile_snapshots", ProfileSnapshotRecord),
            ("profiles", ProfileRecord),
            ("realtime_states", RealtimeStateRecord),
            ("resources", ResourceRecord),
            ("review_events", ReviewEventRecord),
            ("sm2_schedule", Sm2ScheduleRecord),
        )
        for label, model in user_models:
            deleted[label] = _delete(
                db.query(model).filter(model.user_id == normalized)
            )

        deleted["mobile_room_messages"] = _delete(
            db.query(MobileRoomMessageRecord).filter(
                MobileRoomMessageRecord.sender_id == normalized
            )
        )
        deleted["group_chat_messages"] = _delete(
            db.query(GroupChatMessageRecord).filter(
                or_(
                    GroupChatMessageRecord.sender_id == normalized,
                    GroupChatMessageRecord.room_id.endswith(f":{normalized}"),
                )
            )
        )
        db.commit()

    # The resource API keeps a read-through memory cache in addition to SQLite.
    # Evict only records deleted by the transaction so stale cards cannot remain.
    if resource_ids:
        from backend.app.api.v1.resources import evict_resource_cache

        evict_resource_cache(resource_ids)

    nonzero = {key: value for key, value in deleted.items() if value}
    return {
        "user_id": normalized,
        "deleted_counts": nonzero,
        "deleted_total": sum(nonzero.values()),
    }
