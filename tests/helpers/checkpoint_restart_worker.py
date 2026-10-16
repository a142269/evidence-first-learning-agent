"""Dedicated PostgreSQL restart probe: no app config, cloud models or HTTP.

Suspend exits without closing the saver/event loop, after committing a review
checkpoint. Only TEST_V2_POSTGRES_URL is used; no business database fallback.
"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from backend.app.agent_runtime import checkpointing
from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph
from backend.app.agent_runtime.learning_package import LearningPackageGraph
from backend.app.evaluation.learning_package import load_cases
from backend.app.evaluation.package_collection import ScriptedRuntime


def citations(evidence):
    return [{"source": item["source"], "chunk_id": item["chunk_id"], "label": item["source"]}
            for item in evidence]


class AnswerRuntime:
    citations = staticmethod(citations)

    def retrieve(self, *_):
        return [{"source": "test.md", "chunk_id": "test-chunk", "content": "test evidence"}]

    async def generate(self, *_):
        return "test answer"


class ResumeRuntime:
    """Resuming a content review must not re-run retrieval or any model."""
    citations = staticmethod(citations)

    def retrieve(self, *_):
        raise AssertionError("unexpected_retrieval_after_restart")

    async def generate(self, *_):
        raise AssertionError("unexpected_generation_after_restart")

    async def complete_structured(self, *_, **__):
        raise AssertionError("unexpected_model_after_restart")


def emit(payload):
    print(json.dumps(payload, ensure_ascii=True), flush=True)


async def run(phase, thread_id, scenario, decision):
    os.environ["DATABASE_URL"] = os.environ["TEST_V2_POSTGRES_URL"]
    assert await checkpointing.initialize_checkpointer(), "test_checkpointer_unavailable"
    saver = checkpointing.get_checkpointer()
    if phase == "cleanup":
        await saver.adelete_thread(thread_id)
        assert await saver.aget_tuple({"configurable": {"thread_id": thread_id}}) is None
        await checkpointing.shutdown_checkpointer()
        emit({"deleted": True})
        return

    graph_type = EvidenceFirstGraph if scenario == "answer" else LearningPackageGraph
    if phase == "suspend":
        if scenario == "answer":
            runtime = AnswerRuntime()
        else:
            cases = load_cases(Path(__file__).resolve().parents[2] / "evals/learning_package_cases_v1.jsonl")
            case = next(case for case in cases if case.scenario == scenario)
            runtime = ScriptedRuntime(case, citations)
        graph = graph_type(runtime)
        state = await graph.invoke({
            "run_id": thread_id, "thread_id": thread_id, "message": "解释 RAG 并给我三道练习",
            "course_id": "artificial_intelligence", "user_id": "checkpoint-test", "require_approval": True,
        })
        assert state["__interrupt__"]
        snapshot = await graph._build_graph(saver).aget_state({"configurable": {"thread_id": thread_id}})
        assert snapshot.next == ("approval",)
        payload = state.pop("__interrupt__")[0].value
        emit({"pid": os.getpid(), "state": state, "review": payload,
              "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"], "next": list(snapshot.next)})
        # No context exit, saver shutdown or graph memory survives this exit.
        os._exit(73)

    assert phase == "resume"
    graph = graph_type(ResumeRuntime())
    compiled = graph._build_graph(saver)
    config = {"configurable": {"thread_id": thread_id}}
    before = await compiled.aget_state(config)
    assert before.next == ("approval",)
    decisions = {
        "approve": {"approved": True, "note": "test approval"},
        "edit": {"approved": True, "edited_answer": "教师修改后的测试答案", "note": "test edit"},
        "reject": {"approved": False, "note": "test rejection"},
    }
    state = await graph.resume(thread_id, decisions[decision])
    after = await compiled.aget_state(config)
    assert after.next == ()
    assert "__interrupt__" not in state
    await checkpointing.shutdown_checkpointer()
    emit({"pid": os.getpid(), "state": state, "next": list(after.next),
          "restored_checkpoint_id": before.config["configurable"]["checkpoint_id"]})


if __name__ == "__main__":
    os.environ.update({"A3_OFFLINE_DEMO": "1", "OTEL_SDK_DISABLED": "true",
                       "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"})
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    with ExitStack() as stack:
        for target in ("httpx.Client.send", "httpx.AsyncClient.send", "requests.Session.request"):
            stack.enter_context(patch(target, side_effect=AssertionError("HTTP disabled in checkpoint test")))
        try:
            asyncio.run(run(*sys.argv[1:]))
        except Exception as exc:
            # Do not print connection strings or driver exception bodies.
            print(f"checkpoint worker failed: {type(exc).__name__}", file=sys.stderr)
            sys.exit(1)
