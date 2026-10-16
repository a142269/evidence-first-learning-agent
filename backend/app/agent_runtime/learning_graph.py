"""LangGraph-backed, evidence-first learning-answer workflow.

The module deliberately has a deterministic fallback so the legacy offline demo
continues to run before optional LangGraph dependencies are installed.
"""
from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypedDict

EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


def _latest_execution_id(_previous: str, current: str) -> str:
    # Repeated failed node replays can leave more than one Command(update)
    # write in a checkpoint step. The lease check permits only the newest ID.
    return current


class LearningState(TypedDict, total=False):
    execution_id: Annotated[str, _latest_execution_id]
    run_id: str
    message: str
    course_id: str
    user_id: str
    thread_id: str
    require_approval: bool
    evidence: list[dict[str, Any]]
    answer: str
    citations: list[dict[str, Any]]
    quality: dict[str, Any]
    review_status: str
    reviewer_note: str
    safety_blocked: bool
    safety_category: str
    review_before_execution: bool
    history: list[dict[str, str]]
    memory_run_ids: list[str]
    budget: dict[str, Any]


class EvidenceFirstGraph:
    """Small, auditable graph with retrieval, generation and verification nodes."""

    def __init__(self, runtime: Any):
        self.runtime = runtime
        self._builder_available = self._check_builder_available()

    @staticmethod
    def _check_builder_available() -> bool:
        try:
            import langgraph.graph  # noqa: F401
        except ImportError:
            return False
        return True

    def _build_graph(self, checkpointer: Any | None = None, on_event: EventSink | None = None) -> Any | None:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None

        builder = StateGraph(LearningState)
        for name in ("guard", "retrieve", "generate", "approval", "verify", "rejected", "safe_decline"):
            builder.add_node(name, self._observed(name, on_event))
        builder.add_edge(START, "guard")
        builder.add_conditional_edges(
            "guard",
            self._route_guard,
            {
                "retrieve": "retrieve",
                "approval": "approval",
                "safe_decline": "safe_decline",
            },
        )
        builder.add_edge("retrieve", "generate")
        builder.add_conditional_edges(
            "generate",
            self._needs_review,
            {"approval": "approval", "verify": "verify"},
        )
        builder.add_conditional_edges(
            "approval",
            self._route_review_decision,
            {"retrieve": "retrieve", "verify": "verify", "rejected": "rejected"},
        )
        builder.add_edge("verify", END)
        builder.add_edge("rejected", END)
        builder.add_edge("safe_decline", END)
        return builder.compile(checkpointer=checkpointer)

    def _observed(self, name: str, on_event: EventSink | None):
        if name == "approval":
            # A synchronous node can explicitly restore runnable context on
            # Python 3.10; the actual pause is exposed by review.required.
            return self._approval
        async def execute(state: LearningState) -> dict[str, Any]:
            started = time.perf_counter()
            if on_event:
                await on_event("node.started", {"node": name})
            result = getattr(self, f"_{name}")(state)
            if inspect.isawaitable(result):
                result = await result
            if on_event:
                elapsed = int((time.perf_counter() - started) * 1000)
                if name == "retrieve":
                    # Source contents stay private until content review passes.
                    await on_event("retrieval.completed", {
                        "evidence_count": len(result.get("evidence", [])), "latency_ms": elapsed,
                    })
                await on_event("node.completed", {"node": name, "latency_ms": elapsed})
            return result
        return execute

    async def invoke(self, state: LearningState, on_event: EventSink | None = None) -> LearningState:
        if not state.get("thread_id"):
            raise ValueError("thread_id_required")
        # Unsupported operations are never made permissible by approval.
        guard = self._guard(state)
        if state.get("require_approval") and not guard["safety_blocked"] and not self.supports_human_review():
            raise RuntimeError("durable_review_unavailable")
        if self._builder_available:
            from backend.app.agent_runtime.checkpointing import get_checkpointer

            graph = self._build_graph(get_checkpointer(), on_event)
            if graph is not None:
                config = {"configurable": {"thread_id": state["thread_id"]}}
                return await graph.ainvoke(state, config=config)
        state.update(await self._observed("guard", on_event)(state))
        if state.get("safety_blocked"):
            state.update(await self._observed("safe_decline", on_event)(state))
            return state
        for name in ("retrieve", "generate", "verify"):
            state.update(await self._observed(name, on_event)(state))
        return state

    def supports_human_review(self) -> bool:
        """Whether this process can durably pause and resume a run."""
        if not self._builder_available:
            return False
        from backend.app.agent_runtime.checkpointing import get_checkpointer

        return get_checkpointer() is not None

    async def resume(self, thread_id: str, decision: dict[str, Any], on_event: EventSink | None = None,
                     execution_id: str = "") -> LearningState:
        """Resume a previously interrupted run from its persisted thread state."""
        if not self.supports_human_review():
            raise RuntimeError("Durable human review is unavailable in this runtime")
        from langgraph.types import Command

        from backend.app.agent_runtime.checkpointing import get_checkpointer

        graph = self._build_graph(get_checkpointer(), on_event)
        if graph is None:  # defensive guard for an optional dependency
            raise RuntimeError("LangGraph is unavailable")
        config = {"configurable": {"thread_id": thread_id}}
        return await graph.ainvoke(Command(resume=decision, update={"execution_id": execution_id} if execution_id else None), config=config)

    async def unfinished_checkpoint(self, thread_id: str) -> dict[str, Any]:
        """Inspect an ordinary pending node without running it or bypassing review."""
        from backend.app.agent_runtime.checkpointing import get_checkpointer

        if not self.supports_human_review():
            raise RuntimeError("durable_review_unavailable")
        graph = self._build_graph(get_checkpointer())
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        if not snapshot.values or not snapshot.next or not snapshot.config:
            raise ValueError("checkpoint_not_unfinished")
        if any(getattr(task, "interrupts", ()) for task in snapshot.tasks):
            raise ValueError("checkpoint_requires_review")
        if "approval" in snapshot.next:
            raise ValueError("checkpoint_requires_review")
        return dict(snapshot.values)

    async def continue_unfinished(self, thread_id: str, *, previous_execution_id: str,
                                  execution_id: str, on_event: EventSink | None = None) -> LearningState:
        """Replay only the pending node(s) after the last committed checkpoint.

        An in-flight model call may be charged twice if it finished remotely but
        never committed locally.  No exactly-once claim is made here.
        """
        from langgraph.types import Command
        from backend.app.agent_runtime.checkpointing import get_checkpointer

        state = await self.unfinished_checkpoint(thread_id)
        if not previous_execution_id or state.get("execution_id") != previous_execution_id:
            raise ValueError("checkpoint_identity_mismatch")
        graph = self._build_graph(get_checkpointer(), on_event)
        config = {"configurable": {"thread_id": thread_id}}
        return await graph.ainvoke(Command(update={"execution_id": execution_id}), config=config)

    async def _retrieve(self, state: LearningState) -> dict[str, Any]:
        evidence = await asyncio.to_thread(self.runtime.retrieve, state["message"], state["course_id"])
        return {"evidence": evidence}

    async def settled_checkpoint(self, thread_id: str) -> dict[str, Any]:
        """Read only a committed terminal or human-review state; never execute nodes."""
        from backend.app.agent_runtime.checkpointing import get_checkpointer

        if not self.supports_human_review():
            raise RuntimeError("durable_review_unavailable")
        graph = self._build_graph(get_checkpointer())
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        if not snapshot.values or not snapshot.config:
            raise ValueError("checkpoint_not_settled")
        # An interrupted/erroring non-review node is not safe to publish or rerun.
        if any(getattr(task, "error", None) for task in snapshot.tasks):
            raise ValueError("checkpoint_not_settled")
        state = dict(snapshot.values)
        if snapshot.next == ("approval",):
            interrupts = [item for task in snapshot.tasks for item in task.interrupts]
            if len(interrupts) != 1:
                raise ValueError("checkpoint_not_settled")
            state["__interrupt__"] = interrupts
        elif snapshot.next or not isinstance(state.get("answer"), str) or not state["answer"]:
            raise ValueError("checkpoint_not_settled")
        return state

    @staticmethod
    def _guard(state: LearningState) -> dict[str, Any]:
        from backend.app.services.safety.run_guard import get_learning_run_guard

        decision = get_learning_run_guard().decide(state.get("message", ""))
        return {
            "safety_blocked": decision.blocked,
            "safety_category": decision.category,
            "review_before_execution": False,
        }

    @staticmethod
    def _route_guard(state: LearningState) -> str:
        return "safe_decline" if state.get("safety_blocked") else "retrieve"

    @staticmethod
    def _safe_decline(_state: LearningState) -> dict[str, Any]:
        return {
            "answer": "为保护系统和课程数据，我无法回答或执行该请求。请改为基于已授权课程资料提出学习问题。",
            "evidence": [],
            "citations": [],
            "quality": {"grounded": True, "citation_count": 0, "safety_refusal": True},
        }

    async def _generate(self, state: LearningState) -> dict[str, Any]:
        args = [state["message"], state.get("evidence", []), state.get("user_id", "")]
        if state.get("history"):
            args.append(state["history"])
        response = await self.runtime.generate(*args)
        if isinstance(response, dict):
            from backend.app.agent_runtime.usage_meter import record_model_usage
            return {"answer": response["text"],
                    "budget": record_model_usage({"model_calls": 1}, response)}
        return {"answer": response}

    @staticmethod
    def _needs_review(state: LearningState) -> str:
        return "approval" if state.get("require_approval") and state.get("review_status") != "approved" else "verify"

    def _approval(self, state: LearningState, config) -> dict[str, Any]:
        """Pause before a sensitive action; resumed decision controls the route."""
        from langgraph.types import interrupt
        from langchain_core.runnables.config import set_config_context

        citations = self.runtime.citations(state.get("evidence", []))
        payload = {
                "action": "review_learning_answer",
                "reason": "learning_content_review",
                "run_id": state.get("run_id", ""),
                "message": state.get("message", ""),
                "draft_answer": state.get("answer", ""),
                "citations": citations,
            }
        # Explicit injection also supports local Python 3.10; the framework
        # automatically propagates this context on Python 3.11+.
        with set_config_context(config) as context:
            decision = context.run(interrupt, payload)
        if not isinstance(decision, dict) or not isinstance(decision.get("approved"), bool):
            raise ValueError("Review decision must include a boolean approved field")
        approved = decision["approved"]
        updates: dict[str, Any] = {
            "review_status": "approved" if approved else "rejected",
            "reviewer_note": str(decision.get("note", ""))[:1000],
        }
        edited_answer = decision.get("edited_answer")
        if approved and isinstance(edited_answer, str) and edited_answer.strip():
            updates["answer"] = edited_answer.strip()
        return updates

    @staticmethod
    def _route_review_decision(state: LearningState) -> str:
        if state.get("review_status") != "approved":
            return "rejected"
        return "verify"

    @staticmethod
    async def _rejected(_state: LearningState) -> dict[str, Any]:
        return {
            "answer": "该学习内容未通过人工审核，系统未交付待审内容。",
            "evidence": [],
            "citations": [],
            "quality": {"grounded": True, "citation_count": 0, "review_rejected": True},
        }

    async def _verify(self, state: LearningState) -> dict[str, Any]:
        citations = self.runtime.citations(state.get("evidence", []))
        answer = state.get("answer", "")
        if citations:
            answer = f"{answer}\n\n**参考资料**\n" + "\n".join(
                f"- [{item['label']}] {item['source']}" for item in citations
            )
        return {
            "answer": answer,
            "citations": citations,
            "quality": {"citation_present": bool(citations), "citation_count": len(citations),
                        "faithfulness_checked": False},
        }
