"""Summarize human claim reviews from JSON without model calls or credentials."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.evaluation.claim_support import evaluate_claims


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.input.resolve() == args.output.resolve() or args.output.exists():
            raise ValueError("output must be a new file distinct from input")
        data = json.loads(args.input.read_text(encoding="utf-8"))
        result = evaluate_claims(data["claims"], data["evidence_ids"])
        result["evaluation_mode"] = "human_review_offline"
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
