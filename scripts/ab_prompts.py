"""Offline A/B harness for the prompt registry (QWEN-312).

Dry-run by default and zero provider calls, period:

- default: builds the trial plan - variants with name/version/digest only,
  registry integrity, fixed synthetic samples, budget estimate - and writes a
  desensitized JSON report.  No model runs.
- ``--execute``: additionally runs the fixed samples OFFLINE through
  ``LearningPackageGraph`` with a scripted runtime, comparing variant A
  (registry baseline) against variant B (candidate overrides from
  ``--candidate``).  Still zero paid calls.  Refused when the environment is
  not offline (``LLM_PROVIDER != none`` and ``A3_OFFLINE_DEMO != true``): a
  live paid comparison is deliberately out of scope for QWEN-312.
- Budget gate: the estimated model calls (samples x flow calls) must not
  exceed ``--max-model-calls`` before execution, and the actual per-sample
  maximum is re-checked afterwards.

The report never contains prompt text, model text or retrieved content: only
names, versions, digests, sample ids and structure-level results.  Exit codes:
0 = report written, 2 = refused by a gate, 1 = unexpected failure.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.agent_runtime import prompts  # noqa: E402
from backend.app.agent_runtime.learning_package import (  # noqa: E402
    LearningPackageGraph,
    PackageFailure,
)

# Fixed synthetic samples; ids travel into the report, the messages do not.
SAMPLES = [
    {"id": "sample-1", "message": "什么是 RAG？请讲解并给我三道练习"},
    {"id": "sample-2", "message": "解释哈希表与二分查找的适用场景"},
]

# The offline package flow issues exactly six model calls per sample with the
# scripted runtime below (planner, decide x2, tutor, practice, review).
ESTIMATED_MODEL_CALLS_PER_SAMPLE = 6

PLAN = {"steps": [
    {"id": "tutor_explain", "role": "tutor", "goal": "讲清检索增强生成的动机与流程", "depends_on": []},
    {"id": "practice_apply", "role": "practice", "goal": "用三道递进题练习检索增强生成", "depends_on": ["tutor_explain"]},
]}
SEARCH = {"action": "search_course", "query": "检索增强生成 流程"}
FINISH = {"action": "finish", "query": ""}
LESSON = {"explanation": "脚本化讲解文本：先检索课程证据，再依据证据组织讲解并标注来源，便于结构断言。",
          "source_ids": ["ab-c1"]}
PRACTICE = {"exercises": [
    {"question": "脚本化问题一：检索增强生成的核心步骤是什么？", "answer": "先检索后生成。",
     "explanation": "依据证据解析一：先检索课程材料，再依据证据生成回答。", "source_ids": ["ab-c1"]},
    {"question": "脚本化问题二：引用来源在交付中如何标注？", "answer": "由服务端附 citations。",
     "explanation": "依据证据解析二：引用元数据来自实际检索证据，非模型自造。", "source_ids": ["ab-c1"]},
    {"question": "脚本化问题三：预算超限时运行会怎样？", "answer": "稳定错误码失败。",
     "explanation": "依据证据解析三：预算是有界上限，不静默放宽。", "source_ids": ["ab-c1"]},
]}
PASS = {"approved": True, "issues": [], "lesson_approved": True, "practice_approved": True}
REPLIES = (PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS)
EVIDENCE = [{"chunk_id": "ab-c1", "source": "ab-chapter.md", "content": "脚本化证据文本，供引用断言使用。"}]


class _ScriptedRuntime:
    """Offline runtime with fixed replies; no network, no model access."""

    def __init__(self):
        self._replies = list(REPLIES)

    @staticmethod
    def citations(evidence):
        return [{"chunk_id": item["chunk_id"], "source": item["source"],
                 "label": item["source"], "score": 0} for item in evidence]

    def retrieve(self, *_args):
        return list(EVIDENCE)

    async def complete_structured(self, _messages, **_kwargs):
        if not self._replies:
            raise PackageFailure("learning_package_invalid_output")
        return {"text": json.dumps(self._replies.pop(0), ensure_ascii=False),
                "finish_reason": "stop", "usage": None}


def _digest(text: str) -> str:
    return prompts.sha256(text)


def _prompt_entries(names: list[str]) -> list[dict[str, Any]]:
    """Name/version/digest listing; never the prompt text itself."""
    entries = []
    for name in names:
        prompt = prompts.render(name)
        entries.append({"name": name, "version": prompt.version,
                        "digest": prompt.hash, "source": prompt.source})
    return entries


def _variant_digests(overrides: dict[str, str]) -> dict[str, str]:
    """Digest per prompt for one variant; text never enters the report."""
    return {name: _digest(overrides.get(name, prompts.render(name).text))
            for name in sorted(prompts._SPECS)}


def _run_sample(sample: dict[str, str]) -> dict[str, Any]:
    """One offline package run; returns structure-level facts only."""
    graph = LearningPackageGraph(_ScriptedRuntime())
    state = {"run_id": sample["id"], "thread_id": sample["id"],
             "message": sample["message"], "execution_id": "",
             "course_id": "artificial_intelligence", "user_id": "ab-harness",
             "require_approval": False, "history": [], "memory_run_ids": [],
             "budget": {}}
    try:
        final = asyncio.run(graph.invoke(state))
    except PackageFailure as exc:
        return {"sample": sample["id"], "outcome": "failed", "error_code": exc.code}
    package = final.get("learning_package") or {}
    lesson = package.get("lesson") or {}
    review = package.get("review") or {}
    quality = final.get("quality") or {}
    citations = lesson.get("citations") or []
    return {
        "sample": sample["id"],
        "outcome": "completed",
        "plan_steps": [step["id"] for step in (final.get("plan") or {}).get("steps", [])],
        "lesson_source_ids": sorted(lesson.get("source_ids", [])),
        "lesson_citation_keys": sorted(citations[0].keys()) if citations else [],
        "exercise_count": len(package.get("exercises", [])),
        "exercise_source_ids": sorted({sid for exercise in package.get("exercises", [])
                                       for sid in exercise.get("source_ids", [])}),
        "review_approved": review.get("approved"),
        "claim_support_passed": (quality.get("claim_support") or {}).get("passed"),
        "revisions": package.get("revisions"),
        "model_calls": (final.get("budget") or {}).get("model_calls", 0),
        "input_chars": (final.get("budget") or {}).get("input_chars", 0),
    }


def _refused(report_path: Path, reason: str, detail: str) -> int:
    report = {"mode": "refused", "generated_by": "QWEN-312",
              "status": "refused", "reason": reason, "detail": detail}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REFUSED reason={reason}")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", type=Path, default=None,
                        help="candidate manifest JSON: {prompt_name: candidate_text}")
    parser.add_argument("--execute", action="store_true",
                        help="run the fixed samples offline (still no paid calls)")
    parser.add_argument("--max-model-calls", type=int, default=12,
                        help="budget gate: estimated total model calls must not exceed this")
    parser.add_argument("--report", type=Path, default=None,
                        help="report path (default output/ab-prompts/report-<ts>.json)")
    args = parser.parse_args(argv)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = args.report or (REPO_ROOT / "output" / "ab-prompts" / f"report-{timestamp}.json")
    offline = (os.environ.get("LLM_PROVIDER") == "none"
               or os.environ.get("A3_OFFLINE_DEMO") == "true")

    candidate: dict[str, str] = {}
    if args.candidate is not None:
        try:
            candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return _refused(report_path, "candidate_unreadable", type(exc).__name__)
        unknown = sorted(set(candidate) - set(prompts._SPECS))
        if unknown:
            return _refused(report_path, "unknown_prompt", ",".join(unknown))
        if not candidate:
            return _refused(report_path, "candidate_empty", "manifest has no entries")

    estimated = ESTIMATED_MODEL_CALLS_PER_SAMPLE * len(SAMPLES)
    if args.execute and estimated > args.max_model_calls:
        return _refused(report_path, "budget_gate",
                        f"estimated {estimated} > cap {args.max_model_calls}")
    if args.execute and not offline:
        return _refused(report_path, "offline_harness_only",
                        "live paid comparison is out of scope for QWEN-312; "
                        "run the offline harness with LLM_PROVIDER=none / A3_OFFLINE_DEMO=true")

    report: dict[str, Any] = {
        "generated_by": "QWEN-312",
        "prompt_version": prompts.PROMPT_VERSION,
        "mode": "dry-run" if not args.execute else "offline-execute",
        "status": "ok",
        "integrity": prompts.verify_registry(),
        "variants": [
            {"label": "A-baseline", "kind": "baseline",
             "digests": _variant_digests({}),
             "prompts": _prompt_entries(sorted(prompts._SPECS))},
        ],
        "samples": [sample["id"] for sample in SAMPLES],
        "budget": {"estimated_model_calls_total": estimated,
                   "max_model_calls": args.max_model_calls,
                   "gate": "pass"},
    }
    if candidate:
        report["variants"].append({"label": "B-candidate", "kind": "candidate",
                                   "digests": _variant_digests(candidate),
                                   "prompts": _prompt_entries(sorted(candidate))})

    exit_code = 0
    if args.execute:
        results: dict[str, Any] = {}
        try:
            for variant in report["variants"]:
                prompts.apply_overrides(candidate if variant["kind"] == "candidate" else {})
                results[variant["label"]] = [_run_sample(sample) for sample in SAMPLES]
        except prompts.PromptRegistryError as exc:
            return _refused(report_path, exc.code, exc.name)
        finally:
            prompts.clear_overrides()
        report["results"] = results
        actual = max((run.get("model_calls", 0) for runs in results.values() for run in runs),
                     default=0)
        report["budget"]["actual_model_calls_per_sample_max"] = actual
        if actual > args.max_model_calls:
            report["status"] = "budget_exceeded"
            exit_code = 2

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REPORT={report_path}")
    print(f"MODE={report['mode']} STATUS={report['status']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
