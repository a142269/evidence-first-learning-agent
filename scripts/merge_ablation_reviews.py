"""Merge two completed blinded review packets into a new private run file."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.evaluation.ablation_report import RUBRICS


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--reviewer-a", required=True)
    p.add_argument("--reviewer-b", required=True)
    p.add_argument("--adjudications", help="JSON filename inside run directory")
    p.add_argument("--adjudicator", help="independent adjudicator identifier")
    args = p.parse_args()
    directory = args.run_dir.resolve()
    if not directory.is_relative_to((ROOT / "output").resolve()) or not args.reviewer_a.strip() or not args.reviewer_b.strip() or args.reviewer_a.strip() == args.reviewer_b.strip():
        p.error("private directory and two distinct reviewer names required")
    if bool(args.adjudications) != bool(args.adjudicator):
        p.error("adjudications and adjudicator must be supplied together")
    if args.adjudications and (Path(args.adjudications).name != args.adjudications or
            not args.adjudicator.strip() or args.adjudicator.strip() in {args.reviewer_a.strip(), args.reviewer_b.strip()}):
        p.error("adjudications must be a local filename and the adjudicator must be independent")
    def load(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))
    mapping = load("blind-mapping.json")
    cases = {row["id"]: row for row in (json.loads(line) for line in (ROOT / "evals/ablation_tasks_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
    if len({x["blind_id"] for x in mapping}) != len(mapping) or len({(x["case_id"], x["arm"]) for x in mapping}) != len(mapping):
        p.error("duplicate mapping entries")
    packets = [load("reviewer-a.json"), load("reviewer-b.json")]
    by_id = [{item["blind_id"]: item for item in packet} for packet in packets]
    if any(len(index) != len(packet) or set(index) != {x["blind_id"] for x in mapping} for index, packet in zip(by_id, packets)):
        p.error("review packet items do not match mapping")
    reviews = {}
    for item in mapping:
        collected = []
        for index, reviewer in zip(by_id, (args.reviewer_a.strip(), args.reviewer_b.strip())):
            record = index[item["blind_id"]]
            digest = hashlib.sha256(json.dumps(record["package"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            evidence_digest = hashlib.sha256(json.dumps(record["evidence"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            scores = record["scores"]
            if record["question"] != cases[item["case_id"]]["question"] or digest != item["package_sha256"] or evidence_digest != item["evidence_sha256"] or set(scores) != set(RUBRICS) or any(v is not None and type(v) is not bool for v in scores.values()):
                p.error("package, evidence or score validation failed")
            collected.append({"reviewer": reviewer, **scores})
        reviews[(item["case_id"], item["arm"])] = collected
    decisions = {}
    if args.adjudications:
        entries = load(args.adjudications)
        if not isinstance(entries, list):
            p.error("adjudications must be a list")
        mapped = {item["blind_id"]: item for item in mapping}
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("blind_id") not in mapped or entry["blind_id"] in decisions:
                p.error("unknown or duplicate adjudication")
            item = mapped[entry["blind_id"]]
            existing = reviews[(item["case_id"], item["arm"])]
            scores = entry.get("scores")
            if not isinstance(scores, dict) or set(scores) != set(RUBRICS) or any(v is not None and type(v) is not bool for v in scores.values()):
                p.error("invalid adjudication scores")
            if not any(type(existing[0][k]) is bool and type(existing[1][k]) is bool and
                       existing[0][k] != existing[1][k] for k in RUBRICS):
                p.error("adjudication requires a disagreement")
            decisions[entry["blind_id"]] = {"reviewer": args.adjudicator.strip(), **scores}
    rows = [json.loads(line) for line in (directory / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    run_keys = [(row["case_id"], row["arm"]) for row in rows]
    if len(run_keys) != len(set(run_keys)) or not set(reviews).issubset(set(run_keys)):
        p.error("review mapping has missing or duplicate runs")
    for row in rows:
        key = (row["case_id"], row["arm"])
        if key in reviews:
            mapping_item = next(x for x in mapping if (x["case_id"], x["arm"]) == key)
            if not row.get("completed") or row.get("evidence_sha256") != mapping_item["evidence_sha256"]:
                p.error("review mapping does not match completed run evidence")
            actual = hashlib.sha256(json.dumps(row["result"]["package"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            expected = mapping_item["package_sha256"]
            if actual != expected:
                p.error("run package changed")
            row["reviews"] = reviews[key]
            blind_id = mapping_item["blind_id"]
            if blind_id in decisions:
                row["adjudication"] = decisions[blind_id]
    filename = "adjudicated-runs.jsonl" if args.adjudications else "reviewed-runs.jsonl"
    with (directory / filename).open("x", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"reviewed_items": len(reviews), "rows": len(rows)}))


if __name__ == "__main__":
    main()
