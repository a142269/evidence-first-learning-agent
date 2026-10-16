"""Metered pgvector retrieval comparison over eligible Golden Set factual cases.

This reports retrieval only, never the 76-case answer-quality score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from time import perf_counter

from sqlalchemy import text

from backend.app.core.database import SessionLocal
from backend.app.evaluation.golden_set import FACTUAL_BEHAVIOR, load_golden_set
from backend.app.services.embedding_provider import get_embedding_provider
from backend.app.services.enterprise_retriever import EnterpriseRetriever


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="evals/golden_set_zh_v2.jsonl")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--compare", action="store_true", help="Compare dense, hybrid and diverse")
    args = parser.parse_args()
    if not os.getenv("V2_EVAL_BUDGET_CNY") or not os.getenv("V2_EVAL_BUDGET_ID"):
        raise SystemExit("shared_eval_budget_required")
    model = get_embedding_provider().model
    with SessionLocal() as db:
        corpus = list(db.execute(text("""
            SELECT kd.storage_key, dv.version, dv.content_hash FROM knowledge_documents kd
            JOIN document_versions dv ON dv.document_id = kd.id
            WHERE kd.status = 'indexed' AND dv.status = 'indexed'
              AND dv.version = (SELECT MAX(v.version) FROM document_versions v
                                WHERE v.document_id = kd.id AND v.status = 'indexed')
              AND dv.metadata -> 'embedding' ->> 'model' = :model
              AND dv.metadata -> 'embedding' ->> 'status' = 'embedded'
        """), {"model": model}).all())
    sources = {row.storage_key for row in corpus}
    corpus_signature = hashlib.sha256(json.dumps(sorted([tuple(row) for row in corpus]),
                                               ensure_ascii=False).encode()).hexdigest()
    all_cases = [case for case in load_golden_set(args.cases)
                 if case.expected_behavior == FACTUAL_BEHAVIOR]
    eligible = [case for case in all_cases if set(case.expected_sources).issubset(sources)]
    selected = eligible[: max(0, args.limit)]
    retriever = EnterpriseRetriever()
    strategies = ("dense", "hybrid", "hybrid_diverse") if args.compare else ("hybrid",)
    metrics = {}
    for strategy in strategies:
        hits, recall, zero_results = 0, 0.0, 0
        latencies = []
        for case in selected:
            started = perf_counter()
            ranked = retriever.retrieve(case.question, course_id=case.course_id,
                                        top_k=5, strategy=strategy)
            latencies.append((perf_counter() - started) * 1000)
            zero_results += not bool(ranked)
            found = set(case.expected_sources) & {item["source"] for item in ranked}
            hits += bool(found)
            recall += len(found) / len(case.expected_sources)
        latencies.sort()
        metrics[strategy] = {"hit_at_5": round(hits / len(selected), 4) if selected else None,
                             "recall_at_5": round(recall / len(selected), 4) if selected else None,
                             "zero_result_count": zero_results,
                             "p95_latency_ms": round(latencies[int(.95 * (len(latencies) - 1))], 1)
                             if latencies else None}
    full_factual_set = len(selected) == len(all_cases)
    print(json.dumps({"mode": "full_factual_retrieval_probe" if full_factual_set else "partial_pgvector_retrieval_probe", "model": model,
                      "corpus_sha256": corpus_signature, "embedded_sources": len(sources),
                      "factual_cases": len(all_cases),
                      "eligible_cases": len(eligible), "tested_cases": len(selected),
                      "metrics": metrics, "promotion": "comparison_only_no_automatic_promotion" if full_factual_set else "not_eligible_incomplete_corpus_or_limit"},
                     ensure_ascii=False))
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
