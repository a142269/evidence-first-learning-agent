"""Create private blinded holdout packets for two independent human reviewers."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.evaluation.ablation_report import ARMS, RUBRICS, summarize_ablation


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    if not directory.is_relative_to((ROOT / "output").resolve()):
        parser.error("review materials must remain under output")
    cases = [x for x in read_jsonl(ROOT / "evals/ablation_tasks_v1.jsonl") if x["split"] == "holdout"]
    cases_by_id = {x["id"]: x for x in cases}
    runs = [x for x in read_jsonl(directory / "runs.jsonl") if x["case_id"] in cases_by_id]
    report = summarize_ablation(cases, runs)
    if any(report["arms"][arm]["run_count"] != len(cases) for arm in ARMS):
        parser.error("all holdout runs must finish before blinding")
    snapshots = read_jsonl(directory / "evidence.jsonl")
    evidence = {x["case_id"]: x for x in snapshots}
    if len(evidence) != len(snapshots):
        parser.error("duplicate evidence snapshots")
    for row in runs:
        if not row["completed"]:
            continue
        snapshot = evidence.get(row["case_id"])
        if not snapshot or "evidence" not in snapshot:
            parser.error("completed run is missing its evidence snapshot")
        digest = hashlib.sha256(json.dumps(snapshot["evidence"], ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != snapshot.get("sha256") or digest != row["evidence_sha256"]:
            parser.error("evidence snapshot does not match run digest")
    if any((directory / name).exists() for name in ("reviewer-a.json", "reviewer-b.json", "blind-mapping.json")):
        parser.error("review materials already exist; preserve existing work")
    randomizer = random.SystemRandom()
    randomizer.shuffle(runs)
    packet, mapping = [], []
    for index, row in enumerate(runs, 1):
        if not row["completed"]:
            continue
        blind_id = f"item-{index:03d}"
        package = row["result"]["package"]
        package_sha = hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        packet.append({"blind_id": blind_id, "question": cases_by_id[row["case_id"]]["question"],
                       "evidence": evidence[row["case_id"]]["evidence"], "package": package,
                       "scores": dict.fromkeys(RUBRICS), "notes": ""})
        mapping.append({"blind_id": blind_id, "case_id": row["case_id"], "arm": row["arm"],
                        "evidence_sha256": row["evidence_sha256"], "package_sha256": package_sha})
    for name, value in (("reviewer-a.json", packet), ("reviewer-b.json", packet), ("blind-mapping.json", mapping)):
        with (directory / name).open("x", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.write("\n")
    print(json.dumps({"holdout_runs": len(runs), "review_items": len(packet), "reviewers_required": 2}))


if __name__ == "__main__":
    main()
