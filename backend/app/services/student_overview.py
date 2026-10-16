"""Shared student statistics used by learner and teacher-facing APIs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import time
from typing import Any

from backend.app.core.database import SessionLocal
from backend.app.core.models import (
    AssessmentRecord,
    BktStateRecord,
    GamificationProfileRecord,
    GroupChatMessageRecord,
    KnowledgePointRecord,
    LearningPathRecord,
    MistakeRecord,
    ProfileRecord,
    ProfileSnapshotRecord,
    ReviewEventRecord,
    Sm2ScheduleRecord,
)


ERROR_TYPE_LABELS = {
    # 与 ERROR_CATEGORIES（mistake_review.py）同步的中文分类
    "知识缺漏": "知识缺漏",
    "计算失误": "计算失误",
    "概念混淆": "概念混淆",
    "阅读理解": "阅读理解",
    "审题不清": "审题不清",
    "方法选择错": "方法选择错",
    "计算粗心": "计算粗心",
    "概念边界混淆": "概念边界混淆",
    # 兼容旧的英文 code
    "conceptual_misunderstanding": "概念理解偏差",
    "calculation_error": "计算错误",
    "application_transfer": "迁移应用困难",
    "careless_error": "审题疏忽",
    "reading_comprehension": "题意理解偏差",
    "memory_gap": "知识记忆缺口",
    "strategy_error": "解题策略不当",
    "incomplete_answer": "作答不完整",
    "concept": "概念理解偏差",
    "application": "迁移应用困难",
    "calculation": "计算错误",
    "careless": "审题疏忽",
    "unknown": "待进一步诊断",
}


def error_type_label(code: str | None) -> str:
    return ERROR_TYPE_LABELS.get(str(code or "unknown"), str(code or "待进一步诊断"))


def _display_date(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _duration_minutes(row: AssessmentRecord) -> tuple[float, bool]:
    value = max(0.0, float(row.duration or 0.0))
    metadata = row.metadata_data or {}
    explicit_minutes = metadata.get("duration_unit") == "minutes"
    normalized = value > 180 and not explicit_minutes
    return (round(value / 60, 2), True) if normalized else (round(value, 2), False)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_student_overview(
    user_id: str,
    now_ts: float | None = None,
    course: str = "",
) -> dict[str, Any]:
    now = float(now_ts or time.time())
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    today_start = datetime(now_dt.year, now_dt.month, now_dt.day, tzinfo=timezone.utc)
    week_start = today_start - timedelta(days=today_start.weekday())
    this_week_start = week_start.timestamp()
    last_week_start = (week_start - timedelta(days=7)).timestamp()
    thirty_days_ago = now - 30 * 86400

    with SessionLocal() as db:
        profile_row = db.get(ProfileRecord, user_id)
        profile_data = dict(profile_row.profile_data or {}) if profile_row else {}
        assessments = (
            db.query(AssessmentRecord)
            .filter(AssessmentRecord.user_id == user_id)
            .order_by(AssessmentRecord.timestamp.desc())
            .all()
        )
        bkt_rows = (
            db.query(BktStateRecord)
            .filter(BktStateRecord.user_id == user_id)
            .order_by(BktStateRecord.p_learned.desc())
            .all()
        )
        mistakes = (
            db.query(MistakeRecord)
            .filter(MistakeRecord.user_id == user_id)
            .order_by(MistakeRecord.created_at.desc())
            .all()
        )
        snapshots = (
            db.query(ProfileSnapshotRecord)
            .filter(ProfileSnapshotRecord.user_id == user_id)
            .order_by(ProfileSnapshotRecord.created_at)
            .all()
        )
        path_rows = (
            db.query(LearningPathRecord)
            .filter(LearningPathRecord.user_id == user_id)
            .order_by(LearningPathRecord.updated_at.desc())
            .all()
        )
        game = db.get(GamificationProfileRecord, user_id)
        review_events = (
            db.query(ReviewEventRecord)
            .filter(ReviewEventRecord.user_id == user_id)
            .order_by(ReviewEventRecord.reviewed_at.desc())
            .all()
        )
        schedules = db.query(Sm2ScheduleRecord).filter(Sm2ScheduleRecord.user_id == user_id).all()
        messages = (
            db.query(GroupChatMessageRecord)
            .filter(GroupChatMessageRecord.room_id.like(f"%:{user_id}"))
            .all()
        )
        kp_rows = db.query(KnowledgePointRecord).all()
        kp_names = {row.id: row.name for row in kp_rows}
        kp_courses = {row.id: row.course for row in kp_rows}

        normalized_course = str(course or "").strip().lower()

        def _path_metadata(row: LearningPathRecord) -> dict[str, Any]:
            """Read both the current flat metadata format and older nested rows."""
            data = dict(row.metadata_data or {})
            nested = data.pop("metadata", {})
            if isinstance(nested, dict):
                return {**nested, **data}
            return data

        if normalized_course:
            course_bkt_rows = [
                row for row in bkt_rows
                if str(kp_courses.get(row.knowledge_point_id, "")).lower() == normalized_course
            ]
            if course_bkt_rows:
                bkt_rows = course_bkt_rows

        def _path_course_score(row: LearningPathRecord) -> int:
            if not normalized_course:
                return 1
            metadata = _path_metadata(row)
            metadata_course = str(metadata.get("course") or "").lower()
            if metadata_course:
                return 3 if metadata_course == normalized_course else 0
            kp_ids = {
                str(kp_id)
                for stage in (row.stages or [])
                for kp_id in (stage.get("kp_ids") or stage.get("kps") or [])
            }
            matching = sum(1 for kp_id in kp_ids if str(kp_courses.get(kp_id, "")).lower() == normalized_course)
            if matching:
                return 2
            title = str(row.title or "").lower()
            if normalized_course == "python_programming" and "python" in title:
                return 2
            if normalized_course == "artificial_intelligence" and ("ai" in title or "人工智能" in title):
                return 2
            return 0

        matching_paths = [row for row in path_rows if _path_course_score(row) > 0]
        path_candidates = matching_paths or path_rows
        path = max(
            path_candidates,
            key=lambda row: (
                _path_course_score(row),
                str(_path_metadata(row).get("recommended_role") or "") == "teacher",
                str(_path_metadata(row).get("planned_by") or "") == "path_planner",
                float(row.updated_at or 0),
                float(row.progress or 0),
            ),
            default=None,
        )

        normalized_records: list[dict[str, Any]] = []
        daily_minutes: dict[str, float] = defaultdict(float)
        hour_minutes: dict[int, float] = defaultdict(float)
        weekday_minutes: dict[int, float] = defaultdict(float)
        this_week_minutes = 0.0
        last_week_minutes = 0.0
        normalized_legacy_count = 0
        active_days: set[str] = set()
        for row in assessments:
            minutes, normalized = _duration_minutes(row)
            dt = datetime.fromtimestamp(float(row.timestamp), tz=timezone.utc)
            day = dt.date().isoformat()
            daily_minutes[day] += minutes
            hour_minutes[dt.hour] += minutes
            weekday_minutes[dt.weekday()] += minutes
            if row.timestamp >= thirty_days_ago:
                active_days.add(day)
            if row.timestamp >= this_week_start:
                this_week_minutes += minutes
            elif row.timestamp >= last_week_start:
                last_week_minutes += minutes
            normalized_legacy_count += int(normalized)
            normalized_records.append({
                "external_id": row.external_id or str(row.id),
                "record_type": row.record_type,
                "topic": row.topic,
                "score_pct": round(float(row.score or 0), 1),
                "duration_minutes": minutes,
                "normalized_from_legacy": normalized,
                "timestamp": float(row.timestamp),
                "display_date": _display_date(row.timestamp),
            })

        average_mastery_pct = round(_average([float(row.p_learned) for row in bkt_rows]) * 100, 1)
        mastered_count = sum(1 for row in bkt_rows if row.p_learned >= 0.8)
        dimensions = {
            key: profile_data.get(key, {})
            for key in (
                "knowledge_base", "learning_preference", "weak_points",
                "time_management", "self_efficacy", "cognitive_style",
                "learning_goal", "interaction_pattern",
            )
        }
        present_dimensions = sum(1 for value in dimensions.values() if value)
        profile_completeness_pct = round(present_dimensions / len(dimensions) * 100, 1)

        calendar = []
        for offset in range(89, -1, -1):
            current = (today_start - timedelta(days=offset)).date().isoformat()
            calendar.append({"date": current, "minutes": round(daily_minutes.get(current, 0), 1)})

        this_week_scores = [float(row.score) for row in assessments if row.score is not None and row.timestamp >= this_week_start]
        last_week_scores = [float(row.score) for row in assessments if row.score is not None and last_week_start <= row.timestamp < this_week_start]
        this_week_average = _average(this_week_scores)
        last_week_average = _average(last_week_scores)
        week_score_change = this_week_average - last_week_average if last_week_scores else 0.0

        knowledge_points = [
            {"kp_id": row.knowledge_point_id, "kp_name": kp_names.get(row.knowledge_point_id, row.knowledge_point_id), "mastery_pct": round(float(row.p_learned) * 100, 1), "updated_at": float(row.updated_at), "updated_date": _display_date(row.updated_at)}
            for row in bkt_rows
        ]
        strengths = [item for item in knowledge_points if item["mastery_pct"] >= 80][:3]
        risks = sorted(knowledge_points, key=lambda item: item["mastery_pct"])[:3]
        mastery_trend = []
        for snapshot in snapshots:
            snapshot_data = snapshot.profile_data or {}
            score = ((snapshot_data.get("knowledge_base") or {}).get("score"))
            if score is not None:
                mastery_trend.append({"timestamp": float(snapshot.created_at), "display_date": _display_date(snapshot.created_at), "mastery_pct": round(float(score) * 100, 1)})

        raw_stages = list(path.stages or []) if path else []
        mastery_by_kp = {row.knowledge_point_id: float(row.p_learned) for row in bkt_rows}
        stages: list[dict[str, Any]] = []
        stage_mastery: list[dict[str, Any]] = []
        for index, raw_stage in enumerate(raw_stages):
            stage = dict(raw_stage or {})
            kp_ids = list(stage.get("kp_ids") or stage.get("kps") or [])
            topics = list(stage.get("topics") or [kp_names.get(kp_id, kp_id) for kp_id in kp_ids])
            values = [mastery_by_kp[kp_id] for kp_id in kp_ids if kp_id in mastery_by_kp]
            mastery_pct = round(_average(values) * 100, 1) if values else 0.0
            stage.update({
                "id": stage.get("id", index),
                "kp_ids": kp_ids,
                "topics": topics,
                "mastery_pct": mastery_pct,
            })
            stages.append(stage)
            stage_mastery.append({
                "stage_id": stage["id"],
                "title": stage.get("title", f"阶段 {index + 1}"),
                "mastery_pct": mastery_pct,
            })
        path_metadata = dict(path.metadata_data or {}) if path else {}
        current_stage_index = min(max(int(path.current_stage or 0), 0), max(len(stages) - 1, 0)) if path else 0
        today_tasks: list[dict[str, Any]] = []
        for raw_task in path_metadata.get("today_tasks") or []:
            task = dict(raw_task or {})
            kp_id = str(task.get("kp_id") or "").strip()
            if kp_id:
                kp_name = str(kp_names.get(kp_id) or kp_id)
                task["kp_name"] = kp_name
                title = str(task.get("title") or "").strip()
                if not title:
                    title = f"学习「{kp_name}」"
                elif kp_name != kp_id and kp_id in title:
                    title = title.replace(kp_id, f"「{kp_name}」")
                task["title"] = title
            today_tasks.append(task)
        if not today_tasks and stages:
            current_stage_data = stages[current_stage_index]
            ranked_kps = sorted(
                current_stage_data.get("kp_ids") or [],
                key=lambda kp_id: mastery_by_kp.get(kp_id, 0.0),
            )
            today_tasks = [
                {
                    "id": f"{path.id}:{current_stage_index}:{kp_id}",
                    "title": f"学习「{kp_names.get(kp_id, kp_id)}」",
                    "description": "完成概念学习，并进行一次理解检查",
                    "kp_id": kp_id,
                    "kp_name": kp_names.get(kp_id, kp_id),
                    "estimated_minutes": 12 if index == 0 else 10,
                    "type": "优先学习" if index == 0 else "继续学习",
                    "route": f"/graph?kp={kp_id}",
                }
                for index, kp_id in enumerate(ranked_kps[:3])
            ]
        milestones = list(path_metadata.get("milestones") or [])
        if not milestones:
            milestones = [
                {
                    "id": f"stage-{stage['id']}",
                    "title": stage.get("title", f"阶段 {index + 1}"),
                    "completed": index < current_stage_index,
                    "mastery_pct": stage.get("mastery_pct", 0.0),
                }
                for index, stage in enumerate(stages)
            ]
        path_payload = {
            "id": path.id if path else "",
            "title": path.title if path else "",
            "course": normalized_course or path_metadata.get("course", ""),
            "current_stage": current_stage_index,
            "progress_pct": round(float(path.progress or 0), 1) if path else 0.0,
            "stages": stages,
            "stage_mastery": stage_mastery,
            "milestones": milestones,
            "today_tasks": today_tasks,
            "updated_at": float(path.updated_at) if path else None,
            "updated_date": _display_date(path.updated_at) if path else "",
        }

        due_today = sum(1 for row in schedules if row.due_at <= now)
        completed_7d = sum(1 for row in review_events if row.reviewed_at >= now - 7 * 86400)
        completion_rate_pct = round(completed_7d / (completed_7d + due_today) * 100, 1) if completed_7d + due_today else 0.0
        recent_reviews = [{"id": row.id, "item_id": row.item_id, "item_type": row.item_type, "rating": row.rating, "before_mastery_pct": round(float(row.before_mastery or 0) * 100, 1), "after_mastery_pct": round(float(row.after_mastery or 0) * 100, 1), "duration_minutes": round(float(row.duration_minutes or 0), 1), "reviewed_at": float(row.reviewed_at), "display_date": _display_date(row.reviewed_at)} for row in review_events[:10]]

        current_stage = path.current_stage if path else -1
        peer_count = 0
        if path:
            peer_count = db.query(LearningPathRecord).filter(LearningPathRecord.user_id != user_id, LearningPathRecord.current_stage == current_stage).count()

        return {
            "user_id": user_id,
            "generated_at": now,
            "generated_date": _display_date(now),
            "summary": {"average_mastery_pct": average_mastery_pct, "mastered_knowledge_points": mastered_count, "mistake_count": len(mistakes), "unresolved_mistake_count": sum(1 for row in mistakes if row.resolved_at is None), "streak_days": int(game.streak_days or 0) if game else 0, "profile_completeness_pct": profile_completeness_pct},
            "activity": {"total_minutes": round(sum(daily_minutes.values()), 1), "this_week_minutes": round(this_week_minutes, 1), "last_week_minutes": round(last_week_minutes, 1), "week_over_week_pct": round((this_week_minutes - last_week_minutes) / last_week_minutes * 100, 1) if last_week_minutes else 0.0, "active_days_30d": len(active_days), "hour_distribution": [{"hour": hour, "minutes": round(hour_minutes.get(hour, 0), 1)} for hour in range(24)], "weekday_distribution": [{"weekday": weekday, "minutes": round(weekday_minutes.get(weekday, 0), 1)} for weekday in range(7)], "calendar": calendar, "normalized_from_legacy_count": normalized_legacy_count},
            "assessment": {"total": len(assessments), "average_score_pct": round(_average([float(row.score) for row in assessments if row.score is not None]), 1), "this_week_average_score_pct": round(this_week_average, 1), "week_score_change_pct": round(week_score_change, 1), "recent": normalized_records[:20]},
            "profile": {"display_name": profile_data.get("display_name") or profile_data.get("nickname") or user_id, "registered_at": profile_data.get("registered_at") or (profile_row.created_at if profile_row else None), "registered_date": _display_date(profile_data.get("registered_at") or (profile_row.created_at if profile_row else None)), "snapshot_count": len(snapshots), "dimensions": dimensions, "strengths": strengths, "risks": risks, "mastery_trend": mastery_trend, "knowledge_points": knowledge_points},
            "path": path_payload,
            "collaboration": {"message_count": len(messages), "question_count": sum(1 for row in messages if row.sender_role == "student" and ("?" in row.content or "？" in row.content or "吗" in row.content)), "similar_stage_peer_count": peer_count},
            "review": {"due_today": due_today, "completed_7d": completed_7d, "completion_rate_pct": completion_rate_pct, "recent": recent_reviews},
            "mistake_types": [{"code": code, "label": error_type_label(code), "count": sum(1 for row in mistakes if row.error_type == code)} for code in sorted({row.error_type for row in mistakes})],
        }
