from backend.app.services import profile_schema


def test_calculate_profile_completeness_excludes_unknown_placeholders():
    profile = profile_schema.normalize_profile({
        "knowledge_base": {"level": "middle", "score": 0.6},
    })

    assert profile_schema.calculate_profile_completeness(profile) == (1, 8, 12.5)


def test_legacy_demo_dimensions_fill_the_standard_eight_dimension_contract():
    profile = profile_schema.normalize_profile({
        "knowledge_base": {"score": 0.8},
        "cognitive_style": {"score": 0.6},
        "weak_points": {"score": 0.2},
        "learning_preference": {"score": 0.7, "mode": "visual"},
        "learning_goal": {"score": 0.75, "target": "exam"},
        "time_management": {"score": 0.65},
        "self_efficacy": {"score": 0.7},
        "interaction_pattern": {"score": 0.6},
    })

    assert profile_schema.calculate_profile_completeness(profile) == (8, 8, 100.0)
    assert profile["resource_preference"]["mode"] == "visual"
    assert profile["self_learning_ability"]["score"] == 0.6


def test_dimension_meaningful_accepts_status_evidence_and_real_fields():
    meaningful = profile_schema.is_profile_dimension_meaningful

    assert meaningful({"status": "unknown", "evidence": []}) is False
    assert meaningful({"status": "ready", "evidence": []}) is True
    assert meaningful({"status": "unknown", "evidence": ["quiz-1"]}) is True
    assert meaningful({"score": 0.6}) is True
