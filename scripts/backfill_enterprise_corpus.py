"""Backfill bundled Markdown course material into PostgreSQL/pgvector.

Run this inside the backend container after configuring an embedding provider:

    docker compose ... exec backend python scripts/backfill_enterprise_corpus.py

Teacher uploads are intentionally excluded because they already pass through
the asynchronous audited ingestion workflow.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.config import get_config
from backend.app.services.knowledge_ingest import backfill_curated_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill curated Markdown into pgvector")
    parser.add_argument("--course", default="artificial_intelligence")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary-only", action="store_true", help="Print only the final count summary")
    args = parser.parse_args()

    if not args.dry_run and (not os.getenv("V2_EVAL_BUDGET_CNY") or not os.getenv("V2_EVAL_BUDGET_ID")):
        raise SystemExit("shared_eval_budget_required")

    course = str(args.course).strip().lower()
    root = Path(get_config().rag.knowledge_base_path) / course
    if not root.is_dir():
        raise SystemExit(f"course_not_found: {course}")

    files = [path for path in sorted(root.rglob("*.md")) if "uploads" not in path.parts]
    results: list[dict[str, object]] = []
    stopped_early = False
    for path in files:
        storage_key = path.relative_to(Path(get_config().rag.knowledge_base_path)).as_posix()
        if args.dry_run:
            result: dict[str, object] = {"storage_key": storage_key, "status": "planned"}
        else:
            try:
                result = backfill_curated_markdown(
                    course=course,
                    storage_key=storage_key,
                    text=path.read_text(encoding="utf-8"),
                )
            except RuntimeError as exc:
                if str(exc).startswith("eval_budget_"):
                    raise SystemExit("evaluation_budget_stopped") from None
                raise
        results.append(result)
        if not args.summary_only:
            print(json.dumps(result, ensure_ascii=False))
        if (not args.dry_run and result.get("status") == "indexed"
                and isinstance(result.get("embedding"), dict)
                and result["embedding"].get("status") != "embedded"):
            stopped_early = True
            break

    summary = {
        "course": course,
        "documents": len(results),
        "planned_documents": len(files),
        "stopped_early": stopped_early,
        "indexed": sum(item.get("status") == "indexed" for item in results),
        "unchanged": sum(item.get("status") == "unchanged" for item in results),
        "embedded": sum(item.get("status") == "indexed"
                        and isinstance(item.get("embedding"), dict)
                        and item["embedding"].get("status") == "embedded" for item in results),
        "embedding_failed": sum(item.get("status") == "indexed"
                                and isinstance(item.get("embedding"), dict)
                                and item["embedding"].get("status") != "embedded" for item in results),
        "dry_run": args.dry_run,
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 1 if summary["embedding_failed"] or stopped_early else 0


if __name__ == "__main__":
    raise SystemExit(main())
