"""Prepare blinded disputed items for an independent human adjudicator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.evaluation.ablation_report import RUBRICS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    if not directory.is_relative_to((ROOT / "output").resolve()):
        parser.error("private run directory must be inside output")
    packets = [json.loads((directory / name).read_text(encoding="utf-8"))
               for name in ("reviewer-a.json", "reviewer-b.json")]
    if any(not isinstance(packet, list) for packet in packets):
        parser.error("review packets must be lists")
    indexes = []
    for packet in packets:
        if any(not isinstance(item, dict) or not isinstance(item.get("blind_id"), str) or not item["blind_id"] for item in packet):
            parser.error("invalid blind ID")
        index = {item["blind_id"]: item for item in packet}
        if len(index) != len(packet):
            parser.error("duplicate blind ID")
        indexes.append(index)
    if set(indexes[0]) != set(indexes[1]):
        parser.error("review packets do not match")
    output = []
    for blind_id, first in indexes[0].items():
        second = indexes[1][blind_id]
        if any(key not in first or first[key] != second.get(key) for key in ("question", "package", "evidence")):
            parser.error("review packet content does not match")
        for item in (first, second):
            scores = item.get("scores")
            if not isinstance(scores, dict) or set(scores) != set(RUBRICS) or any(
                value is not None and type(value) is not bool for value in scores.values()
            ):
                parser.error("invalid review scores")
        disputed = [key for key in RUBRICS if type(first["scores"][key]) is bool
                    and type(second["scores"][key]) is bool and first["scores"][key] != second["scores"][key]]
        if disputed:
            output.append({"blind_id": blind_id, "question": first["question"],
                           "package": first["package"], "evidence": first["evidence"],
                           "disputed_metrics": disputed, "scores": dict.fromkeys(RUBRICS)})
    with (directory / "adjudication-packet.json").open("x", encoding="utf-8") as out:
        json.dump(output, out, ensure_ascii=False, indent=2)
        out.write("\n")
    print(json.dumps({"disputed_items": len(output)}))


if __name__ == "__main__":
    main()
