from __future__ import annotations

from backend.app.services.profile_extractor import extract_profile_updates


STANDARD_KEYS = {
    "knowledge_base",
    "cognitive_style",
    "error_pattern",
    "learning_habit",
    "learning_progress",
    "interest_model",
    "resource_preference",
    "self_learning_ability",
}


def test_normalize_profile_outputs_standard_eight_dimensions():
    from backend.app.services.profile_schema import normalize_profile

    profile = normalize_profile(
        {
            "knowledge_base": {"level": "middle"},
            "learning_preference": {"preferred_format": "code+diagram"},
            "weak_points": {"topics": ["backpropagation"]},
        }
    )

    assert STANDARD_KEYS.issubset(profile)
    assert len([key for key in STANDARD_KEYS if key in profile]) == 8
    assert profile["error_pattern"]["topics"] == ["backpropagation"]
    assert profile["learning_habit"]["preferred_format"] == "code+diagram"
    assert profile["resource_preference"]["preferred_format"] == "code+diagram"
    assert profile["learning_preference"]["preferred_format"] == "code+diagram"


def test_normalize_profile_maps_self_regulation_legacy_fields():
    from backend.app.services.profile_schema import normalize_profile

    profile = normalize_profile(
        {
            "time_management": {"score": 0.8, "best_time": "morning"},
            "self_efficacy": {"score": 0.7, "confidence": 0.72},
            "interaction_pattern": {"score": 0.6, "style": "collaborative"},
        }
    )

    assert profile["self_learning_ability"]["best_time"] == "morning"
    assert profile["self_learning_ability"]["confidence"] == 0.72
    assert profile["self_learning_ability"]["style"] == "collaborative"


def test_profile_agent_prompt_requests_canonical_eight_dimension_schema():
    from backend.app.agents.profile_agent import ProfileAgent

    prompt = ProfileAgent().system_prompt

    assert "standard-8" in prompt
    assert "standard-6" not in prompt
    for key in STANDARD_KEYS:
        assert key in prompt


def test_app_config_uses_the_canonical_eight_dimension_keys():
    from backend.app.core.config import AppConfig

    assert set(AppConfig().profile_dimensions) == STANDARD_KEYS


def test_conversational_extraction_maps_legacy_fields_to_standard_schema():
    text = """```profile_update
{
  "learning_preference": {"preferred_format": "video+practice"},
  "weak_points": {"patterns": ["gradient_sign"]},
  "learning_goal": {"target": "exam"}
}
```"""

    profile, status = extract_profile_updates(text)

    assert status == "success"
    assert STANDARD_KEYS.issubset(profile)
    assert profile["learning_habit"]["preferred_format"] == "video+practice"
    assert profile["resource_preference"]["preferred_format"] == "video+practice"
    assert profile["error_pattern"]["patterns"] == ["gradient_sign"]
    assert profile["learning_progress"]["target"] == "exam"
    assert profile["interest_model"]["target"] == "exam"
