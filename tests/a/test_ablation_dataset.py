import json
from pathlib import Path


def test_ablation_dataset_has_fixed_unique_tasks_and_existing_sources():
    root = Path(__file__).resolve().parents[2]
    rows = [json.loads(line) for line in (root / "evals/ablation_tasks_v1.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 24
    assert len({row["id"] for row in rows}) == 24
    assert len({row["question"] for row in rows}) == 24
    assert sum(row["split"] == "dev" for row in rows) == 12
    assert sum(row["split"] == "holdout" for row in rows) == 12
    for row in rows:
        assert row["course_id"] == "artificial_intelligence"
        assert row["expected_sources"]
        assert all((root / "knowledge_base" / source).is_file() for source in row["expected_sources"])
