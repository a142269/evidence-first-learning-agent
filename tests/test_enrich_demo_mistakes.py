import json
from pathlib import Path

from scripts.enrich_demo_mistakes import CONCRETE_REPLACEMENTS


def test_demo_mistake_enrichment_uses_concrete_questions() -> None:
    payload = json.loads(Path("data/seed_mistakes.json").read_text(encoding="utf-8"))
    curated = [item for item in payload["mistakes"] if item["user_id"] == "demo-student-1"]

    assert len(curated) >= 30
    assert len(CONCRETE_REPLACEMENTS) == 5
    for item in [*curated, *CONCRETE_REPLACEMENTS.values()]:
        question = item["question"]
        assert len(question) >= 15
        assert not question.startswith("关于 AI_")
        assert item["student_answer"]
        assert item["correct_answer"]
