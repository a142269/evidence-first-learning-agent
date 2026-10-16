"""Rebuild existing indexed vectors for the configured Embedding model.

No provider call occurs in --dry-run. A paid run requires the shared V2
evaluation budget variables; secrets come only from the runtime environment.
"""
from __future__ import annotations

import argparse
import json
import os

from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.models import KnowledgeDocumentRecord
from backend.app.services.vector_reindex import reembed_document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and (not os.getenv("V2_EVAL_BUDGET_CNY") or not os.getenv("V2_EVAL_BUDGET_ID")):
        raise SystemExit("shared_eval_budget_required")
    with SessionLocal() as db:
        ids = list(db.scalars(select(KnowledgeDocumentRecord.id).where(
            KnowledgeDocumentRecord.course == args.course,
            KnowledgeDocumentRecord.status == "indexed").order_by(KnowledgeDocumentRecord.id)))
    if args.limit > 0:
        ids = ids[:args.limit]
    results = {"documents": len(ids), "embedded": 0, "unchanged": 0, "failed": 0,
               "dry_run": args.dry_run}
    if not args.dry_run:
        for document_id in ids:
            try:
                item = reembed_document(document_id)
            except RuntimeError as exc:
                if str(exc).startswith("eval_budget_"):
                    raise SystemExit("evaluation_budget_stopped") from None
                results["failed"] += 1
            except ValueError:
                results["failed"] += 1
            else:
                results[item["status"]] += 1
    print(json.dumps({"summary": results}, ensure_ascii=False))
    return 1 if results["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
