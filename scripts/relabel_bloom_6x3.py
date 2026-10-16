#!/usr/bin/env python3
"""Relabel question-bank items with Bloom 6x3 detail fields."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.cognitive_diagnosis.bloom_6x3 import get_bloom6x3_config

QUESTION_BANK_PATH = PROJECT_ROOT / "data" / "question_bank.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "bloom_6x3_relabel_20260623.md"


def _annotate_question(question: dict[str, Any]) -> dict[str, Any]:
    cfg = get_bloom6x3_config()
    text = str(question.get("stem", "") or "")
    result = cfg.classify_text(text)

    annotated = dict(question)
    annotated["bloom_6x3"] = {
        "level": result["level"],
        "sub_level": result["sub_level"],
        "knowledge_dimension": result["knowledge_dim"],
        "method": result.get("method", "keyword"),
        "score": result.get("score", 0),
    }
    return annotated


def relabel_question_bank(path: Path = QUESTION_BANK_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    level_counter: Counter[str] = Counter()
    sub_level_counter: Counter[str] = Counter()
    knowledge_counter: Counter[str] = Counter()
    sample_annotations: list[dict[str, str]] = []
    annotated_questions: list[dict[str, Any]] = []

    for question in questions:
        annotated = _annotate_question(question)
        detail = annotated["bloom_6x3"]
        level_counter[detail["level"]] += 1
        sub_level_counter[detail["sub_level"]] += 1
        knowledge_counter[detail["knowledge_dimension"]] += 1
        annotated_questions.append(annotated)

        if len(sample_annotations) < 8:
            sample_annotations.append(
                {
                    "id": str(annotated.get("id", "")),
                    "level": str(detail["level"]),
                    "sub_level": str(detail["sub_level"]),
                    "knowledge_dimension": str(detail["knowledge_dimension"]),
                }
            )

    payload["questions"] = annotated_questions
    payload.setdefault("_meta", {})
    payload["_meta"]["bloom_6x3_relabelled"] = True
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "total_questions": len(annotated_questions),
        "level_distribution": dict(level_counter),
        "sub_level_distribution": dict(sub_level_counter),
        "knowledge_dimension_distribution": dict(knowledge_counter),
        "sample_annotations": sample_annotations,
    }


def render_relabel_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Bloom 6x3 Relabel Report",
        "",
        f"- total_questions: {summary['total_questions']}",
        "",
        "## Level Distribution",
        "",
    ]
    for key, value in summary["level_distribution"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Sub-level Distribution", ""])
    for key, value in summary["sub_level_distribution"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Knowledge Dimension Distribution", ""])
    for key, value in summary["knowledge_dimension_distribution"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Sample Annotations", ""])
    for sample in summary["sample_annotations"]:
        lines.append(
            f"- {sample['id']}: level={sample['level']}, sub_level={sample['sub_level']}, "
            f"knowledge_dimension={sample['knowledge_dimension']}"
        )

    lines.extend(
        [
            "",
            "## Spot Check",
            "",
            "- Manual spot-check recommendation: inspect at least one item from remember/apply/analyze buckets before demo use.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    summary = relabel_question_bank()
    REPORT_PATH.write_text(render_relabel_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
