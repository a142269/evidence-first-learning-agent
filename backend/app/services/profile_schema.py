from __future__ import annotations

from copy import deepcopy
from typing import Any


PROFILE_SCHEMA_VERSION = "standard-8-v1"

STANDARD_PROFILE_DIMENSIONS: dict[str, dict[str, str]] = {
    "knowledge_base": {
        "label": "Knowledge Base",
        "description": "Known topics, mastery evidence, prerequisite strength.",
    },
    "cognitive_style": {
        "label": "Cognitive Style",
        "description": "Preferred reasoning mode, abstraction level, visual/verbal tendency.",
    },
    "error_pattern": {
        "label": "Error Pattern",
        "description": "Frequent misconception, wrong-answer pattern, weak knowledge points.",
    },
    "learning_habit": {
        "label": "Learning Habit",
        "description": "Learning rhythm, preferred media, interaction and practice habit.",
    },
    "learning_progress": {
        "label": "Learning Progress",
        "description": "Current stage, recent activity, mastered and pending topics.",
    },
    "interest_model": {
        "label": "Interest Model",
        "description": "Learning goals, preferred examples, motivation and domain interests.",
    },
    "resource_preference": {
        "label": "Resource Preference",
        "description": "Preferred media, difficulty, format and resource interaction pattern.",
    },
    "self_learning_ability": {
        "label": "Self Learning Ability",
        "description": "Self regulation, confidence, initiative, reflection and collaboration habit.",
    },
}

STANDARD_PROFILE_KEYS = tuple(STANDARD_PROFILE_DIMENSIONS.keys())

LEGACY_PROFILE_DIMENSIONS: dict[str, dict[str, str]] = {
    "learning_preference": {
        "label": "Learning Preference",
        "maps_to": "learning_habit",
    },
    "weak_points": {
        "label": "Weak Points",
        "maps_to": "error_pattern",
    },
    "learning_goal": {
        "label": "Learning Goal",
        "maps_to": "learning_progress,interest_model",
    },
    "time_management": {
        "label": "Time Management",
        "maps_to": "learning_habit",
    },
    "self_efficacy": {
        "label": "Self Efficacy",
        "maps_to": "learning_habit",
    },
    "interaction_pattern": {
        "label": "Interaction Pattern",
        "maps_to": "learning_habit",
    },
}

_LEGACY_TO_STANDARD: dict[str, tuple[str, ...]] = {
    "learning_preference": (
        "learning_habit",
        "interest_model",
        "resource_preference",
    ),
    "weak_points": ("error_pattern",),
    "learning_goal": ("learning_progress", "interest_model"),
    "time_management": ("learning_habit", "self_learning_ability"),
    "self_efficacy": ("self_learning_ability",),
    "interaction_pattern": ("learning_habit", "self_learning_ability"),
}

PROFILE_FIELD_KEYS = set(STANDARD_PROFILE_KEYS) | set(LEGACY_PROFILE_DIMENSIONS)


def is_profile_payload(payload: dict[str, Any]) -> bool:
    return bool(set(payload) & PROFILE_FIELD_KEYS)


def _default_dimension() -> dict[str, Any]:
    return {"status": "unknown", "evidence": []}


def _merge_value(current: Any, incoming: Any) -> Any:
    if isinstance(current, dict) and isinstance(incoming, dict):
        merged = deepcopy(current)
        for key, value in incoming.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = _merge_value(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    if incoming not in (None, "", [], {}):
        return deepcopy(incoming)
    return deepcopy(current)


def normalize_profile(
    profile: dict[str, Any] | None,
    *,
    preserve_extra: bool = True,
) -> dict[str, Any]:
    """Return a profile with the fixed standard eight dimensions.

    Legacy fields remain available for backward compatibility, but their
    content is also copied into the standard acceptance schema.
    """
    source = deepcopy(profile or {})
    normalized: dict[str, Any] = {}

    if preserve_extra:
        normalized.update(source)

    for key in STANDARD_PROFILE_KEYS:
        value = source.get(key)
        normalized[key] = deepcopy(value) if value not in (None, "", [], {}) else _default_dimension()

    for legacy_key, target_keys in _LEGACY_TO_STANDARD.items():
        value = source.get(legacy_key)
        if value in (None, "", [], {}):
            continue
        for target_key in target_keys:
            normalized[target_key] = _merge_value(normalized.get(target_key), value)

    normalized["_schema"] = {
        "version": PROFILE_SCHEMA_VERSION,
        "required_dimensions": list(STANDARD_PROFILE_KEYS),
    }
    return normalized


def standard_profile_only(profile: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_profile(profile, preserve_extra=False)
    return {key: normalized[key] for key in STANDARD_PROFILE_KEYS}


def is_profile_dimension_meaningful(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, dict):
        real_keys = {
            key for key in value if key not in ("status", "evidence", "_schema")
        }
        if real_keys:
            return True
        status = value.get("status", "")
        if status and status != "unknown":
            return True
        return bool(value.get("evidence", []))
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def calculate_profile_completeness(
    profile: dict[str, Any] | None,
) -> tuple[int, int, float]:
    values = profile or {}
    total = len(STANDARD_PROFILE_KEYS)
    filled = sum(
        1
        for key in STANDARD_PROFILE_KEYS
        if is_profile_dimension_meaningful(values.get(key))
    )
    return filled, total, round(filled / total * 100, 1)
