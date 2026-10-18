"""Dedicated PostgreSQL restart probe for a partially completed learning package.

Suspend exits without closing the saver/event loop after committing the human
review checkpoint for a review-approved partial delivery (one exercise dropped).
Resume must not re-run retrieval or any model. Only TEST_V2_POSTGRES_URL is used.
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
from backend.app.agent_runtime.learning_package import LearningPackageGraph


def citations(evidence):
    return [{"source": item["source"], "chunk_id": item["chunk_id"], "label": item["source"]}
            for item in evidence]


PLAN = {"steps": [
    {"id": "tutor_explain", "role": "tutor", "goal": "讲解检索的作用", "depends_on": []},
    {"id": "practice_apply", "role": "practice", "goal": "三道递进练习", "depends_on": ["tutor_explain"]},
]}
LESSON = {"explanation": "检索增强生成先查找课程材料，再依据检索证据组织回答并标注引用来源。",
          "source_ids": ["c1"]}
PRACTICE = {"exercises": [
    {"question": f"第 {index} 题：为什么先检索？", "answer": "获得课程证据",
     "explanation": "检索先定位资料，回答再引用证据。", "source_ids": ["c1"]}
    for index in range(1, 4)
]}
# Keep only exercises 1 and 3; the Reviewer explicitly withholds exercise 2.
PARTIAL_REVIEW = {"approved": True, "issues": [], "dropped_exercises": [2]}

SCRIPT = [("Planner", PLAN), ("Tutor", {"action": "search_course", "query": "RAG 检索"}),
          ("Tutor", {"action": "finish"}), ("Tutor", LESSON), ("Practice", PRACTICE),
          ("Reviewer", PARTIAL_REVIEW)]


class PartialRuntime:
    citations = staticmethod(citations)

    def __init__(self):
        self.script = list(SCRIPT)

    def retrieve(self, *_):
        return [{"chunk_id": "c1", "source": "chapter.md", "content": "课程证据"}]

    async def complete_structured(self, messages, *, max_tokens):
        assert self.script, "unexpected_model_call"
        role, payload = self.script.pop(0)
        assert f" {role}。" in messages[0]["content"]
        return json.dumps(payload, ensure_ascii=False)


class ResumeRuntime:
    """Resuming a content review must not re-run retrieval or any model."""
    citations = staticmethod(citations)

    def retrieve(self, *_):
        raise AssertionError("unexpected_retrieval_after_restart")

    async def complete_structured(self, *_, **__):
        raise AssertionError("unexpected_model_after_restart")


def emit(payload):
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def selected(state):
    return {
        "learning_package": state.get("learning_package", {}),
        "partial_completion": state.get("partial_completion", {}),
        "revisions": state.get("revisions", 0),
        "review_status": state.get("review_status", ""),
        "quality": state.get("quality", {}),
    }


async def run(phase, thread_id):
    os.environ["DATABASE_URL"] = os.environ["TEST_V2_POSTGRES_URL"]
    assert await checkpointing.initialize_checkpointer(), "test_checkpointer_unavailable"
    saver = checkpointing.get_checkpointer()
    if phase == "cleanup":
        await saver.adelete_thread(thread_id)
        assert await saver.aget_tuple({"configurable": {"thread_id": thread_id}}) is None
        await checkpointing.shutdown_checkpointer()
        emit({"deleted": True})
        return

    if phase == "suspend":
        graph = LearningPackageGraph(PartialRuntime())
        state = await graph.invoke({
            "run_id": thread_id, "thread_id": thread_id,
            "message": "解释 RAG 并给我三道练习", "course_id": "artificial_intelligence",
            "user_id": "partial-checkpoint-test", "require_approval": True,
        })
        assert state["__interrupt__"], "review_required_not_reached"
        snapshot = await graph._build_graph(saver).aget_state(
            {"configurable": {"thread_id": thread_id}})
        assert snapshot.next == ("approval",)
        payload = state.pop("__interrupt__")[0].value
        assert payload["partial_completion"]["withheld_exercise_numbers"] == [2]
        emit({"pid": os.getpid(), "state": selected(state), "review": payload,
              "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
              "next": list(snapshot.next)})
        os._exit(73)

    assert phase == "resume"
    graph = LearningPackageGraph(ResumeRuntime())
    compiled = graph._build_graph(saver)
    config = {"configurable": {"thread_id": thread_id}}
    before = await compiled.aget_state(config)
    assert before.next == ("approval",)
    state = await graph.resume(thread_id, {"approved": True, "note": "approve partial"})
    after = await compiled.aget_state(config)
    assert after.next == ()
    assert "__interrupt__" not in state
    await checkpointing.shutdown_checkpointer()
    emit({"pid": os.getpid(), "state": selected(state), "next": list(after.next),
          "restored_checkpoint_id": before.config["configurable"]["checkpoint_id"]})


if __name__ == "__main__":
    os.environ.update({"A3_OFFLINE_DEMO": "1", "OTEL_SDK_DISABLED": "true",
                       "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"})
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    with ExitStack() as stack:
        for target in ("httpx.Client.send", "httpx.AsyncClient.send", "requests.Session.request"):
            stack.enter_context(patch(target, side_effect=AssertionError("HTTP disabled")))
        try:
            asyncio.run(run(*sys.argv[1:]))
        except Exception as exc:
            print(f"partial checkpoint worker failed: {type(exc).__name__}", file=sys.stderr)
            sys.exit(1)
