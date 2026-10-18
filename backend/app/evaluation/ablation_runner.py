"""Isolated fixed-evidence ablation using the production role contracts.

This deliberately does not expose experimental modes on the production API.
The full arm uses the production Planner/Tutor/Practice/Reviewer methods, but
does not execute the production retrieval loop or human-approval lifecycle.
"""
from __future__ import annotations

import time
from typing import Any

from backend.app.agent_runtime.learning_package import Contract, LearningPackageGraph, Lesson, PackageFailure, Practice


class SinglePackage(Contract):
    lesson: Lesson
    practice: Practice


async def run_arm(runtime: Any, case: dict, evidence: list[dict], arm: str) -> dict:
    if arm not in {"single", "without_reviewer", "full"}:
        raise ValueError("unknown arm")
    if not evidence or any(not all(item.get(k) for k in ("chunk_id", "source", "content")) for item in evidence):
        raise ValueError("fixed evidence required")
    class ModelOnlyRuntime:
        async def complete_structured(self, messages, *, max_tokens):
            return await runtime.complete_structured(messages, max_tokens=max_tokens)

    graph = LearningPackageGraph(ModelOnlyRuntime())
    # Each arm has an 8192-token aggregate output-request budget. The single
    # agent gets it in one call; the multi-role arms can request 8 x 1024.
    graph.MAX_MODEL_CALLS = 1 if arm == "single" else 8
    graph.MAX_OUTPUT_TOKENS_PER_CALL = 8192 if arm == "single" else 1024
    state: dict[str, Any] = {"message": case["question"], "course_id": case["course_id"],
                             "history": [], "budget": {}, "evidence": evidence, "artifacts": {},
                             "revisions": 0, "searches": []}
    started = time.perf_counter()
    result: dict[str, Any] = {"completed": False, "reviewer_initially_rejected": None,
                              "reviewer_revision_succeeded": None}
    try:
        if graph._guard(state).get("safety_blocked"):
            raise PackageFailure("ablation_guard_blocked")
        if arm == "single":
            package = await graph._ask(state, "Tutor", "仅使用证据，一次生成讲解与三道递进练习，"
                                       "source_ids 必须是证据中的 chunk_id。",
                                       {"evidence": evidence}, SinglePackage)
            graph._check_sources(package["lesson"]["source_ids"], state)
            for exercise in package["practice"]["exercises"]:
                graph._check_sources(exercise["source_ids"], state)
            result["package"] = package
        else:
            # Hide optional identity-dependent tools in this controlled experiment;
            # the common evidence snapshot is supplied to all three arms.
            plan = await graph._planner(state)
            state.update(plan)
            state["evidence"] = evidence
            state.update(await graph._tutor(state))
            state.update(await graph._practice(state))
            if arm == "full":
                state.update(await graph._review(state))
                initial = state["package_review"]
                result["reviewer_initially_rejected"] = not initial["approved"]
                if not initial["approved"]:
                    target = graph._route_package_review(state)
                    if target == "tool":
                        # The snapshot is fixed across arms; no new retrieval is allowed.
                        raise PackageFailure("ablation_fixed_evidence_revision_unavailable")
                    if target == "compose":
                        # The Reviewer explicitly approved a partial delivery
                        # instead of asking for another repair.
                        result["partial_completion"] = state.get("partial_completion", {})
                    else:
                        if target == "tutor":
                            state.update(await graph._tutor(state))
                        state.update(await graph._practice(state))
                        state.update(await graph._review(state))
                        if state.get("partial_completion"):
                            result["partial_completion"] = state["partial_completion"]
                    result["reviewer_revision_succeeded"] = True
            steps = state["plan"]["steps"]
            package = {"lesson": state["artifacts"][steps[0]["id"]]}
            # A partial delivery has no practice artifact; never fabricate one.
            if steps[1]["id"] in state["artifacts"]:
                package["practice"] = state["artifacts"][steps[1]["id"]]
            result["package"] = package
            if "practice" not in package:
                # The ablation metric is "complete package produced": a degraded
                # lesson-only delivery is not a complete task, even though the
                # production API may legitimately settle it as partially completed.
                result["completed"] = False
                result["error"] = result.get("error") or "learning_package_incomplete_package"
        if not result.get("error"):
            result["completed"] = True
    except Exception as exc:
        result["error"] = exc.code if isinstance(exc, PackageFailure) else type(exc).__name__
        if result["reviewer_initially_rejected"]:
            result["reviewer_revision_succeeded"] = False
    result["budget"] = state.get("budget", {})
    result["model_calls"] = state.get("budget", {}).get("model_calls", 0)
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result
