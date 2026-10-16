"""Replay frozen PostgreSQL candidate rankings; never changes the live default.

Input JSONL rows: case_id, corpus_sha256, expected_chunk_ids, dense, lexical.
Each candidate includes chunk_id, source, content and score.  The snapshot
must be captured from one pinned course corpus; this measures reranking only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from backend.app.services.enterprise_retriever import diversify_candidates, reciprocal_rank_fusion


def compare(rows: list[dict], *, top_k: int = 5) -> dict:
    if not rows or len({row["corpus_sha256"] for row in rows}) != 1:
        raise ValueError("one_frozen_corpus_required")
    strategies = ("dense", "hybrid", "hybrid_diverse")
    metrics = {name: {"recall": [], "reciprocal_rank": [], "source_diversity": [],
                      "latency_ms": []} for name in strategies}
    for row in rows:
        expected = set(row["expected_chunk_ids"])
        if not expected:
            raise ValueError("expected_chunk_ids_required")
        dense, lexical = row["dense"], row["lexical"]
        for name in strategies:
            started = perf_counter()
            if name == "dense":
                ranked = dense[:top_k]
            else:
                fused = reciprocal_rank_fusion([dense, lexical])
                ranked = (diversify_candidates(fused, top_k) if name == "hybrid_diverse"
                          else fused[:top_k])
            elapsed = (perf_counter() - started) * 1000
            hits = [item["chunk_id"] for item in ranked]
            rank = next((i for i, chunk_id in enumerate(hits, 1) if chunk_id in expected), None)
            item = metrics[name]
            item["recall"].append(len(expected.intersection(hits)) / len(expected))
            item["reciprocal_rank"].append(1 / rank if rank else 0)
            item["source_diversity"].append(len({r.get("source") for r in ranked}) / max(1, len(ranked)))
            item["latency_ms"].append(elapsed)
    result = {name: {"recall_at_k": round(mean(values["recall"]), 4),
                     "mrr_at_k": round(mean(values["reciprocal_rank"]), 4),
                     "source_diversity": round(mean(values["source_diversity"]), 4),
                     "rerank_p95_ms": round(sorted(values["latency_ms"])[int(.95 * (len(rows) - 1))], 3)}
              for name, values in metrics.items()}
    return {"corpus_sha256": rows[0]["corpus_sha256"], "cases": len(rows), "top_k": top_k,
            "metrics": result, "default_strategy": "hybrid",
            "promotion": "pending_live_postgresql_latency_and_safety_regression"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(compare(rows), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
