"""Run learning-package cases with injected providers through the local ASGI app.

Offline only. No cloud URL, credentials or online mode is accepted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evaluation.learning_package import load_cases, review_template, summarise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/learning_package_cases_v1.jsonl")
    parser.add_argument("--split", choices=("dev", "holdout", "all"), default="dev")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True, help="New local output directory; never overwritten")
    args = parser.parse_args(argv)
    try:
        cases = [case for case in load_cases(args.cases) if args.split == "all" or case.split == args.split]
        if args.case_id:
            if set(args.case_id) - {case.id for case in cases}:
                raise ValueError("Case id absent from selected split")
            cases = [case for case in cases if case.id in args.case_id]
        if not cases:
            raise ValueError("No cases selected")
        args.output_dir.mkdir(parents=True, exist_ok=False)
        from backend.app.evaluation.package_collection import COLLECTOR_VERSION, collect_cases

        with (args.output_dir / "predictions.jsonl").open("x", encoding="utf-8") as stream:
            def save(prediction):
                stream.write(json.dumps(prediction, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
            predictions = asyncio.run(collect_cases(cases, args.output_dir / "runs.sqlite3", save))
        report = summarise(cases, predictions, prediction_kind="synthetic")
        report.update(split=args.split, collector_version=COLLECTOR_VERSION,
                      collection_mode="synthetic_asgi", predictions=predictions)
        with (args.output_dir / "report.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        with (args.output_dir / "review-template.jsonl").open("x", encoding="utf-8") as stream:
            for row in review_template(cases, predictions):
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({"collection_mode": "synthetic_asgi", "summary": report["summary"],
                          "output_dir": str(args.output_dir)}, ensure_ascii=False))
        return 0 if all(row["contract_passed"] for row in report["cases"]) else 1
    except (ValueError, OSError, RuntimeError, ImportError):
        # Never print adapter exceptions, connection strings or partial answer text.
        parser.exit(2, "Offline collection failed; check dependencies, case selection and a fresh output directory.\n")


if __name__ == "__main__":
    raise SystemExit(main())
