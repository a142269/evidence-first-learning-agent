"""Replay saved learning-package results without loading credentials or calling APIs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evaluation.learning_package import load_cases, load_rows, review_template, summarise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/learning_package_cases_v1.jsonl")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--predictions", type=Path, help="JSONL envelopes: id, scenario, events, result")
    source.add_argument("--validate-only", action="store_true", help="Validate the dataset without generating results")
    parser.add_argument("--split", choices=("dev", "holdout", "all"), default="dev")
    parser.add_argument("--prediction-kind", choices=("synthetic", "recorded"), default="synthetic")
    parser.add_argument("--reviews", type=Path, help="Independent human reviews bound to prediction fingerprints")
    parser.add_argument("--review-template", type=Path, help="Write a blank review JSONL; never auto-approve")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/learning_package_offline_report.json")
    parser.add_argument("--enforce-contracts", action="store_true")
    parser.add_argument("--enforce-human-review", action="store_true")
    args = parser.parse_args(argv)
    try:
        all_cases = load_cases(args.cases)
        cases = [case for case in all_cases if args.split == "all" or case.split == args.split]
        if not cases:
            raise ValueError("No cases selected")
        if args.validate_only:
            print(json.dumps({"case_count": len(cases), "split": args.split,
                              "evaluation_performed": False}, ensure_ascii=False))
            return 0
        predictions = load_rows(args.predictions)
        reviews = load_rows(args.reviews) if args.reviews else {}
        known = {case.id for case in all_cases}
        if set(predictions) - known or set(reviews) - known:
            raise ValueError("Predictions or reviews contain unknown case ids")
        report = summarise(cases, predictions, reviews, prediction_kind=args.prediction_kind)
        report["split"] = args.split
        report["predictions"] = {case.id: predictions[case.id] for case in cases if case.id in predictions}
        report["human_reviews"] = {case.id: reviews[case.id] for case in cases if case.id in reviews}
        outputs = [args.output] + ([args.review_template] if args.review_template else [])
        protected = {path.resolve() for path in (args.cases, args.predictions, args.reviews) if path}
        resolved = [path.resolve() for path in outputs]
        if len(set(resolved)) != len(resolved) or protected.intersection(resolved):
            raise ValueError("Output paths must be distinct from each other and all inputs")
        if any(path.exists() for path in outputs):
            raise ValueError("Output already exists; choose new output paths")
        serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        template = review_template(cases, predictions) if args.review_template else []
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized + "\n")
        if args.review_template:
            args.review_template.parent.mkdir(parents=True, exist_ok=True)
            with args.review_template.open("x", encoding="utf-8") as stream:
                for row in template:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({"evaluation_mode": report["evaluation_mode"], "prediction_kind": args.prediction_kind,
                          "summary": report["summary"], "report": str(args.output)}, ensure_ascii=False))
        passed = not args.enforce_contracts or all(row["contract_passed"] for row in report["cases"])
        if args.enforce_human_review:
            passed = passed and args.prediction_kind == "recorded" and report["summary"]["learning_quality_pass_rate"] == 1.0
        return 0 if passed else 1
    except (ValueError, OSError) as exc:
        # Do not echo raw JSON/answers, credentials or backend exception text.
        if isinstance(exc, OSError):
            parser.exit(2, "Input/output file operation failed; check paths and permissions.\n")
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
