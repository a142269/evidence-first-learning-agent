"""Build an evidence-labelled initial learner profile from registration answers.

The registration conversation is intentionally deterministic: it gives every new
learner a useful baseline even when the LLM is unavailable.  Later conversations,
practice results and behaviour evidence continue to update the same standard-8
profile through the existing profile pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.services.profile_schema import normalize_profile

_LEVEL_SCORE = {
    "零基础": 0.2,
    "刚入门": 0.3,
    "有一些基础": 0.48,
    "能够独立应用": 0.68,
    "有项目经验": 0.82,
}

_CONFIDENCE_SCORE = {
    "经常需要帮助": 0.35,
    "有提示就能继续": 0.55,
    "通常能独立解决": 0.72,
    "喜欢主动探索": 0.86,
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _has_answer(section: dict[str, Any]) -> bool:
    return any(value not in (None, "", [], {}) for value in section.values())


def _evidence(*items: str) -> list[str]:
    return [item for item in items if item]


def build_initial_profile(
    answers: dict[str, Any] | None,
    *,
    display_name: str = "",
    registered_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert the eight onboarding turns into the existing standard-8 schema.

    Every inferred dimension is marked ``initial_self_report``.  This distinction
    matters: self-reported preferences are useful for the first recommendation,
    but lower-confidence than mastery and behaviour evidence gathered later.
    """
    source = answers if isinstance(answers, dict) else {}
    academic = _mapping(source.get("academic"))
    goal = _mapping(source.get("goal"))
    foundation = _mapping(source.get("foundation"))
    errors = _mapping(source.get("errors"))
    cognition = _mapping(source.get("cognition"))
    resources = _mapping(source.get("resources"))
    habits = _mapping(source.get("habits"))
    autonomy = _mapping(source.get("autonomy"))

    timestamp = (registered_at or datetime.now(timezone.utc)).isoformat()
    profile: dict[str, Any] = {
        "display_name": display_name,
        "registered_at": timestamp,
        "profile_origin": "registration_conversation",
        "academic_context": {
            "major": _text(academic.get("major")),
            "grade": _text(academic.get("grade")),
            "current_course": _text(academic.get("current_course")),
        },
    }

    answered_sections: list[str] = []

    if _has_answer(foundation):
        answered_sections.append("foundation")
        level = _text(foundation.get("level"))
        known_topics = _strings(foundation.get("known_topics"))
        applied_experience = _text(foundation.get("applied_experience"))
        profile["knowledge_base"] = {
            "status": "initial_self_report",
            "level": level or "待诊断",
            "score": _LEVEL_SCORE.get(level, 0.45),
            "known_topics": known_topics,
            "applied_experience": applied_experience,
            "evidence": _evidence(
                f"注册自述基础：{level}" if level else "",
                f"自述已学：{'、'.join(known_topics)}" if known_topics else "",
                f"实践经历：{applied_experience}" if applied_experience else "",
            ),
        }

    legacy_weak_areas = _strings(foundation.get("weak_areas"))
    difficulty_stages = _strings(errors.get("difficulty_stages")) or legacy_weak_areas
    error_patterns = (
        _strings(errors.get("error_patterns"))
        or _strings(foundation.get("error_patterns"))
    )
    stuck_response = _text(errors.get("stuck_response"))
    if _has_answer(errors) or difficulty_stages or error_patterns:
        answered_sections.append("errors")
        error_signal_count = len(difficulty_stages) + len(error_patterns)
        profile["error_pattern"] = {
            "status": "initial_self_report",
            "score": min(0.85, 0.35 + error_signal_count * 0.08),
            "topics": difficulty_stages,
            "difficulty_stages": difficulty_stages,
            "patterns": error_patterns,
            "stuck_response": stuck_response,
            "evidence": _evidence(
                (
                    f"注册自述易卡环节：{'、'.join(difficulty_stages)}"
                    if difficulty_stages
                    else ""
                ),
                (
                    f"反复出现的模式：{'、'.join(error_patterns)}"
                    if error_patterns
                    else ""
                ),
                f"卡住时通常：{stuck_response}" if stuck_response else "",
            ),
        }

    if _has_answer(cognition):
        answered_sections.append("cognition")
        styles = _strings(cognition.get("styles"))
        profile["cognitive_style"] = {
            "status": "initial_self_report",
            "score": 0.68,
            "primary": styles[0] if styles else "待观察",
            "secondary": styles[1] if len(styles) > 1 else "",
            "styles": styles,
            "explanation_depth": _text(cognition.get("explanation_depth")),
            "information_density": _text(cognition.get("information_density")),
            "evidence": _evidence(
                f"注册偏好理解方式：{'、'.join(styles)}" if styles else "",
                (
                    f"讲解信息密度：{_text(cognition.get('information_density'))}"
                    if cognition.get("information_density")
                    else ""
                ),
            ),
        }

    if _has_answer(resources):
        answered_sections.append("resources")
        formats = _strings(resources.get("formats"))
        profile["resource_preference"] = {
            "status": "initial_self_report",
            "score": 0.7,
            "preferred_formats": formats,
            "preferred_format": "+".join(formats),
            "practice_mode": _text(resources.get("practice_mode")),
            "pace": _text(resources.get("pace")),
            "challenge_level": _text(resources.get("challenge_level")),
            "evidence": _evidence(
                f"注册偏好资源：{'、'.join(formats)}" if formats else "",
                (
                    f"练习反馈：{_text(resources.get('practice_mode'))}"
                    if resources.get("practice_mode")
                    else ""
                ),
            ),
        }

    if _has_answer(habits):
        answered_sections.append("habits")
        try:
            weekly_hours = max(0.0, min(80.0, float(habits.get("weekly_hours", 0) or 0)))
        except (TypeError, ValueError):
            weekly_hours = 0.0
        habit_score = min(0.9, 0.45 + weekly_hours / 100) if weekly_hours else 0.55
        profile["learning_habit"] = {
            "status": "initial_self_report",
            "score": round(habit_score, 2),
            "weekly_hours": weekly_hours,
            "session_length": _text(habits.get("session_length")),
            "best_time": _text(habits.get("best_time")),
            "schedule": _text(habits.get("schedule")),
            "interruption_risks": _strings(habits.get("interruption_risks")),
            "evidence": _evidence(
                f"每周计划学习约 {weekly_hours:g} 小时" if weekly_hours else "",
                f"高效时段：{_text(habits.get('best_time'))}" if habits.get("best_time") else "",
                f"计划方式：{_text(habits.get('schedule'))}" if habits.get("schedule") else "",
            ),
        }

    legacy_confidence = _text(habits.get("confidence"))
    confidence = _text(autonomy.get("confidence")) or legacy_confidence
    help_style = _text(autonomy.get("help_style")) or _text(habits.get("help_style"))
    reflection_habit = _text(autonomy.get("reflection_habit"))
    collaboration = _text(autonomy.get("collaboration"))
    if _has_answer(autonomy) or confidence or help_style:
        answered_sections.append("autonomy")
        profile["self_learning_ability"] = {
            "status": "initial_self_report",
            "score": _CONFIDENCE_SCORE.get(confidence, 0.55),
            "confidence": _CONFIDENCE_SCORE.get(confidence, 0.55),
            "help_seeking": help_style,
            "reflection_habit": reflection_habit,
            "collaboration": collaboration,
            "stuck_response": stuck_response,
            "self_description": confidence,
            "evidence": _evidence(
                f"注册自述自主学习状态：{confidence}" if confidence else "",
                f"期望系统介入方式：{help_style}" if help_style else "",
                f"学习后复盘方式：{reflection_habit}" if reflection_habit else "",
                f"协作偏好：{collaboration}" if collaboration else "",
            ),
        }

    if _has_answer(goal):
        answered_sections.append("goal")
        interests = _strings(goal.get("interests"))
        target = _text(goal.get("target"))
        timeline = _text(goal.get("timeline"))
        profile["interest_model"] = {
            "status": "initial_self_report",
            "score": 0.72,
            "target": target,
            "interests": interests,
            "motivation": _text(goal.get("motivation")),
            "success_evidence": _text(goal.get("success_evidence")),
            "evidence": _evidence(
                f"注册目标：{target}" if target else "",
                f"感兴趣方向：{'、'.join(interests)}" if interests else "",
                (
                    f"学习动力：{_text(goal.get('motivation'))}"
                    if goal.get("motivation")
                    else ""
                ),
            ),
        }
        profile["learning_progress"] = {
            "status": "initial_self_report",
            "score": _LEVEL_SCORE.get(_text(foundation.get("level")), 0.45),
            "current_stage": _text(academic.get("current_course")) or "待诊断",
            "goal": target,
            "timeline": timeline,
            "success_evidence": _text(goal.get("success_evidence")),
            "applied_experience": _text(foundation.get("applied_experience")),
            "evidence": _evidence(
                f"目标周期：{timeline}" if timeline else "",
                (
                    f"当前课程：{_text(academic.get('current_course'))}"
                    if academic.get("current_course")
                    else ""
                ),
            ),
        }

    if _has_answer(academic):
        answered_sections.append("academic")

    profile["onboarding"] = {
        "version": "registration-8-turn-v2",
        "completed": len(set(answered_sections)) >= 6,
        "answered_sections": sorted(set(answered_sections)),
        "answer_count": len(set(answered_sections)),
        "note": "初始画像来自学生自述，后续将结合对话、练习与学习行为持续校准。",
    }
    return normalize_profile(profile, preserve_extra=True)
