from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs" / "API-CONTRACT.md"


def test_contract_document_freezes_shared_interfaces():
    assert CONTRACT.exists(), "docs/API-CONTRACT.md must exist"
    text = CONTRACT.read_text(encoding="utf-8")

    required_terms = [
        "bloom_level",
        "kp_ids",
        "archetype_code",
        "zpd_kps",
        "reflection_trace",
        "strategy_prompt",
        "dina_snapshot",
        "archetype",
        "rag_mode",
        "role_view",
        "narrative_summary",
        "svg_assets",
        "process_turn",
        "learning_state_store",
        "profiles",
        "realtime_states",
        "learning_paths",
        "assessments",
        "mistakes",
        "knowledge_points",
        "kp_relations",
        "learner_archetypes",
        "dina_states",
        "bkt_states",
        "sm2_schedule",
        "gamification_profiles",
    ]
    for term in required_terms:
        assert f"`{term}`" in text, f"contract must define {term}"

    assert "禁止修改参数签名" in text
    assert "DB 17 张表所有权" in text

    for code in [
        "high_achiever",
        "effort_chaser",
        "rhythm_broken",
        "habit_breakdown",
        "introverted_explorer",
        "social_learner",
        "stable_average",
        "exam_oriented",
        "concept_explorer",
    ]:
        assert f"`{code}`" in text

    for route in [
        "/api/v1/profile/*",
        "/api/v1/learning-path/*",
        "/api/v1/assessment/*",
        "/api/v1/mistakes/*",
        "/api/v1/cognitive/*",
        "/api/v1/knowledge-graph/*",
        "/api/v1/gamification/*",
    ]:
        assert f"`{route}`" in text
