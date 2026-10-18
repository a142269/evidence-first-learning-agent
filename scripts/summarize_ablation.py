"""Summarize existing ablation records; never calls an API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.evaluation.ablation_report import summarize_ablation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/ablation_tasks_v1.jsonl")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("dev", "holdout", "all"), default="holdout")
    args = parser.parse_args()
    try:
        if args.output.exists() or args.output.resolve() in {args.cases.resolve(), args.runs.resolve()}:
            raise ValueError("output must be a new file")
        cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
        runs = [json.loads(line) for line in args.runs.read_text(encoding="utf-8").splitlines() if line.strip()]
        all_ids = {row["id"] for row in cases}
        if any(row.get("case_id") not in all_ids for row in runs):
            raise ValueError("unknown case")
        cases = [row for row in cases if args.split == "all" or row["split"] == args.split]
        selected_ids = {row["id"] for row in cases}
        runs = [row for row in runs if row["case_id"] in selected_ids]
        result = summarize_ablation(cases, runs)
        result.update(split=args.split, evaluation_mode="offline_record_summary")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write("\n")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError):
        parser.exit(2, "Invalid input or output path; no model was called.\n")


if __name__ == "__main__":
    raise SystemExit(main())
