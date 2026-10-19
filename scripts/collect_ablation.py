"""Collect a controlled, fixed-evidence ablation into a private local directory.

Provider configuration comes from the process environment. This script makes
paid retrieval and model calls. Never publish its raw output without redaction.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.evaluation.ablation_runner import run_arm
from backend.app.api.v2.learning_runs import LearningRuntime


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


ALL_ARMS = ("single", "without_reviewer", "full")


async def collect(args):
    arms = tuple(dict.fromkeys(args.arm)) or ALL_ARMS
    if set(arms) - set(ALL_ARMS):
        raise ValueError("invalid arms")
    from backend.app.core.config import get_config
    config = get_config().llm
    if config.provider != "openai_compatible" or not config.openai_api_key or not config.openai_model:
        raise ValueError("online model configuration required")
    dataset = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.case_id:
        selected = set(args.case_id)
        dataset = [row for row in dataset if row["id"] in selected]
        if {row["id"] for row in dataset} != selected:
            raise ValueError("unknown case IDs")
    if not dataset or len({row["id"] for row in dataset}) != len(dataset):
        raise ValueError("invalid cases")
    if not args.output_dir.resolve().is_relative_to((ROOT / "output").resolve()):
        raise ValueError("raw evaluation output must be under ignored output directory")
    args.output_dir.mkdir(parents=True, exist_ok=args.resume)
    runtime = LearningRuntime()
    snapshot_path = args.output_dir / "evidence.jsonl"
    progress_path = args.output_dir / "runs.jsonl"
    dataset_signature = hashlib.sha256(canonical(dataset).encode()).hexdigest()
    manifest_path = args.output_dir / "manifest.json"
    manifest = {"dataset_sha256": dataset_signature, "model": config.openai_model,
                "max_output_tokens": 8192, "collector_version": 1,
                "runner_sha256": hashlib.sha256((ROOT / "backend/app/evaluation/ablation_runner.py").read_bytes()).hexdigest()}
    if manifest_path.exists():
        if not args.resume or json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("resume manifest mismatch")
    else:
        manifest_path.write_text(canonical(manifest), encoding="utf-8")
    snapshots_by_case = {}
    if snapshot_path.exists():
        for line in snapshot_path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            case_id = item["case_id"]
            if case_id in snapshots_by_case or case_id not in {c["id"] for c in dataset}:
                raise ValueError("invalid snapshot")
            if item["sha256"] is not None and hashlib.sha256(canonical(item["evidence"]).encode()).hexdigest() != item["sha256"]:
                raise ValueError("snapshot checksum mismatch")
            snapshots_by_case[case_id] = (item["sha256"], item["evidence"], item.get("error"))
    with snapshot_path.open("a", encoding="utf-8") as snapshots:
        for case in dataset:
            if case["id"] in snapshots_by_case:
                continue
            error = None
            try:
                hits = await asyncio.to_thread(runtime.retrieve, case["question"], case["course_id"])
                evidence = [{"chunk_id": str(hit["chunk_id"]), "source": str(hit["source"]),
                             "content": str(hit["content"])[:2000]} for hit in hits[:5]
                            if hit.get("chunk_id") and hit.get("source") and hit.get("content")]
                if not evidence:
                    raise ValueError("no evidence")
            except Exception as exc:
                error = type(exc).__name__
                evidence = []
                print(json.dumps({"case_id": case["id"], "retrieval_error": error}), flush=True)
            snapshot = hashlib.sha256(canonical(evidence).encode()).hexdigest() if not error else None
            snapshots.write(canonical({"case_id": case["id"], "sha256": snapshot, "evidence": evidence, "error": error}) + "\n")
            snapshots.flush()
            os.fsync(snapshots.fileno())
            snapshots_by_case[case["id"]] = (snapshot, evidence, error)
    # Global digest binds every group to this same frozen set of retrieved evidence.
    evidence_signature = hashlib.sha256(canonical({key: val[0] for key, val in snapshots_by_case.items()}).encode()).hexdigest()
    count = 0
    completed_keys = set()
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            key = (row["case_id"], row["arm"])
            expected_config = {"model": config.openai_model, "knowledge_snapshot": evidence_signature,
                               "max_output_tokens": 8192, "max_cost_cny": None}
            if key in completed_keys or key[0] not in snapshots_by_case or key[1] not in ALL_ARMS or row["config"] != expected_config or row.get("dataset_sha256") != dataset_signature or row["evidence_sha256"] != snapshots_by_case[key[0]][0]:
                raise ValueError("invalid existing run")
            completed_keys.add(key)
    with progress_path.open("a", encoding="utf-8") as progress:
        for case in dataset:
            snapshot, evidence, retrieval_error = snapshots_by_case[case["id"]]
            for arm in arms:
                if (case["id"], arm) in completed_keys:
                    continue
                result = await run_arm(runtime, case, evidence, arm) if not retrieval_error else {
                    "completed": False, "error": "retrieval_" + retrieval_error,
                    "budget": {}, "latency_ms": None, "model_calls": 0}
                cost = result["budget"].get("cost", {})
                row = {"case_id": case["id"], "arm": arm, "completed": result["completed"],
                       "config": {"model": config.openai_model, "knowledge_snapshot": evidence_signature,
                                  "max_output_tokens": 8192, "max_cost_cny": None},
                       "dataset_sha256": dataset_signature, "evidence_sha256": snapshot, "latency_ms": result["latency_ms"],
                       "model_calls": result["model_calls"],
                       "cost_cny": cost.get("amount_cny") if cost.get("status") == "estimated" else None,
                       "invalid_tool_calls": None, "reviews": [], "result": result}
                progress.write(canonical(row) + "\n")
                progress.flush()
                os.fsync(progress.fileno())
                count += 1
                print(json.dumps({"case_id": case["id"], "arm": arm, "completed": row["completed"],
                                  "error": result.get("error"), "model_calls": row["model_calls"]}), flush=True)
    print(json.dumps({"recorded_runs": count, "requested_cases": len(dataset),
                      "dataset_signature": dataset_signature, "evidence_signature": evidence_signature}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/ablation_tasks_v1.jsonl")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--arm", action="append", choices=ALL_ARMS, default=[],
                        help="Collect only the selected arm(s); defaults to all three")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(collect(args))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"ablation setup failed: {type(exc).__name__}\n")


if __name__ == "__main__":
    main()
