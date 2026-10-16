"""Tests for Bloom 6x3 relabel artifacts."""
from __future__ import annotations

import json
from pathlib import Path


def test_relabel_question_bank_adds_bloom_6x3_fields(tmp_path: Path) -> None:
    from scripts.relabel_bloom_6x3 import relabel_question_bank

    src = tmp_path / "question_bank.json"
    src.write_text(
        json.dumps(
            {
                "_meta": {"version": "test", "total": 2, "kp_count": 1},
                "questions": [
                    {
                        "id": "q1",
                        "kp_id": "cnn",
                        "kp_name": "卷积神经网络",
                        "bloom": "Remember",
                        "stem": "回忆卷积核的定义",
                        "type": "multiple_choice",
                    },
                    {
                        "id": "q2",
                        "kp_id": "transformer",
                        "kp_name": "Transformer",
                        "bloom": "Apply",
                        "stem": "用 PyTorch 实现一个注意力机制",
                        "type": "open_ended",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = relabel_question_bank(src)
    data = json.loads(src.read_text(encoding="utf-8"))

    assert summary["total_questions"] == 2
    assert "knowledge_dimension_distribution" in summary
    assert all("bloom_6x3" in q for q in data["questions"])
    assert data["questions"][0]["bloom_6x3"]["level"] == "remember"
    assert data["questions"][1]["bloom_6x3"]["knowledge_dimension"] == "procedural"


def test_render_relabel_report_contains_summary() -> None:
    from scripts.relabel_bloom_6x3 import render_relabel_report

    report = render_relabel_report(
        {
            "total_questions": 2,
            "level_distribution": {"remember": 1, "apply": 1},
            "sub_level_distribution": {"recalling": 1, "implementing": 1},
            "knowledge_dimension_distribution": {"factual": 1, "procedural": 1},
            "sample_annotations": [
                {"id": "q1", "level": "remember", "sub_level": "recalling", "knowledge_dimension": "factual"},
                {"id": "q2", "level": "apply", "sub_level": "implementing", "knowledge_dimension": "procedural"},
            ],
        }
    )

    assert "# Bloom 6x3 Relabel Report" in report
    assert "remember" in report
    assert "procedural" in report
