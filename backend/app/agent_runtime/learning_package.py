"""两步学习计划、受限 ReAct-style 检索决策循环、一次有界重规划及一次 Reviewer 返工。

The planner chooses goals and dependency IDs within a two-role contract. Tool
actions are only search_course / finish, with at most three searches. They are
structured JSON, never executable model text, arbitrary URLs or an arbitrary DAG.
A retrieval that fails, or a decision loop that repeats an already-used query
without any evidence, marks the plan invalid: the Planner re-enters at most
once and a second invalidation stops the run instead of looping.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph, LearningState
from backend.app.agent_runtime.observation import Observation, failure_observation
from backend.app.agent_runtime.prompts import PROMPT_VERSION, render
from backend.app.agent_runtime.usage_meter import record_model_usage
from backend.app.evaluation.claim_support import evaluate_rule_based_support


ROLE_CONTRACTS = {
    "Planner": {"input": "authenticated goal, bounded learning context", "output": "LearningPlan",
                "tools": ("get_learning_profile", "get_recent_mistakes", "get_prerequisites"),
                "handoff": "validated tutor/practice dependency"},
    "Tutor": {"input": "plan and course evidence", "output": "Lesson",
              "tools": ("search_course_evidence",), "handoff": "source-checked explanation"},
    "Practice": {"input": "lesson and same evidence", "output": "Practice",
                 "tools": (), "handoff": "three source-checked exercises"},
    "Reviewer": {"input": "plan, artifacts and evidence", "output": "QualityReview",
                 "tools": (), "handoff": "approve or one actionable revision"},
}

# Fixed, model-visible compactness guidance for a retry after a length-truncated
# response. It never echoes model output and never relaxes schema validation.
_TRUNCATION_GUIDANCE = {
    "LearningPlan": "每个 goal 不超过 120 字，只输出一个 JSON 对象。",
    "Lesson": "explanation 压缩到 350 字以内，保留 1-5 个 source_ids，只输出一个 JSON 对象。",
    "Practice": "每题 question 不超过 120 字、answer 不超过 120 字、explanation 不超过 160 字，"
                "保留三道题且每条 source_ids 非空，只输出一个完整 JSON 对象。",
    "QualityReview": "issues 最多 5 条且每条不超过 100 字，只输出一个 JSON 对象。",
}


def _json_object_span(text: str) -> tuple[int, int] | None:
    """Return the span of the first complete top-level JSON object, if any."""
    start = text.find("{")
    if start < 0:
        return None
    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, index + 1
    return None


def _extract_json_object(text: str) -> str:
    """Tolerate a leading Markdown fence or surrounding prose without relaxing validation."""
    stripped = text.strip()
    if stripped.startswith("```"):
        newline = stripped.find("\n")
        if newline >= 0:
            stripped = stripped[newline + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    span = _json_object_span(stripped)
    if span is None:
        return stripped
    return stripped[span[0]:span[1]]


def _looks_truncated(raw: object, finish_reason: object) -> bool:
    """A incomplete top-level object or an explicit provider length stop is truncation."""
    if finish_reason == "length":
        return True
    if not isinstance(raw, str):
        return False
    stripped = raw.strip()
    if stripped.startswith("```"):
        newline = stripped.find("\n")
        if newline >= 0:
            stripped = stripped[newline + 1:]
    return "{" in stripped and _json_object_span(stripped) is None


class PackageFailure(RuntimeError):
    def __init__(self, code: str, observation: Observation | None = None):
        self.code = code
        self.observation = observation
        super().__init__(code)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PlanStep(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    role: Literal["tutor", "practice"]
    goal: str = Field(min_length=1, max_length=500)
    depends_on: list[str] = Field(max_length=1)


class LearningPlan(Contract):
    steps: list[PlanStep] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def valid_dependencies(self):
        by_role = {step.role: step for step in self.steps}
        if set(by_role) != {"tutor", "practice"}:
            raise ValueError("one tutor and one practice step required")
        tutor, practice = by_role["tutor"], by_role["practice"]
        if tutor.id == practice.id or tutor.depends_on or practice.depends_on != [tutor.id]:
            raise ValueError("practice must depend on tutor; cycles and unknown dependencies are forbidden")
        self.steps = [tutor, practice]
        return self


class ToolDecision(Contract):
    action: Literal["search_course", "finish"]
    query: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def query_required(self):
        if self.action == "search_course" and not self.query:
            raise ValueError("search requires a query")
        return self


class Lesson(Contract):
    explanation: str = Field(min_length=20, max_length=5000)
    source_ids: list[str] = Field(min_length=1, max_length=5)


class Exercise(Contract):
    question: str = Field(min_length=5, max_length=600)
    answer: str = Field(min_length=1, max_length=1000)
    explanation: str = Field(min_length=5, max_length=1000)
    source_ids: list[str] = Field(min_length=1, max_length=5)


class Practice(Contract):
    exercises: list[Exercise] = Field(min_length=3, max_length=3)


class QualityReview(Contract):
    """Reviewer verdict for the whole deliverable.

    ``lesson_approved`` / ``practice_approved`` are optional per-part verdicts
    used only for an explicit partial delivery.  When omitted they inherit
    ``approved`` so the historical all-or-nothing contract still holds and a
    partial delivery can never be inferred from an ambiguous rejection.
    ``dropped_exercises`` lists 1-based exercise numbers the reviewer rejects;
    the remaining exercises must still be approved by ``practice_approved``.
    """

    approved: bool = Field(strict=True)
    issues: list[str] = Field(max_length=5)
    repair_target: Literal["lesson", "exercise", "evidence"] = "lesson"
    need_more_evidence: bool = Field(default=False, strict=True)
    suggested_query: str = Field(default="", max_length=500)
    lesson_approved: bool | None = Field(default=None, strict=True)
    practice_approved: bool | None = Field(default=None, strict=True)
    dropped_exercises: list[int] = Field(default_factory=list, max_length=2)

    @property
    def lesson_ok(self) -> bool:
        return self.approved if self.lesson_approved is None else self.lesson_approved

    @property
    def practice_ok(self) -> bool:
        return self.approved if self.practice_approved is None else self.practice_approved

    @property
    def explicit_partial(self) -> bool:
        return (self.lesson_approved is not None or self.practice_approved is not None
                or bool(self.dropped_exercises))

    @model_validator(mode="after")
    def consistent(self):
        if any(not item.strip() or len(item) > 500 for item in self.issues):
            raise ValueError("issues require bounded non-empty text")
        if self.dropped_exercises:
            numbers = self.dropped_exercises
            if numbers != sorted(set(numbers)) or any(not 1 <= number <= 3 for number in numbers):
                raise ValueError("dropped exercises must be unique ascending numbers 1-3")
        if self.dropped_exercises and not self.practice_ok:
            raise ValueError("dropped exercises require an approved remaining practice")
        if self.approved:
            if self.issues:
                raise ValueError("approval requires no issues")
            if not (self.lesson_ok and self.practice_ok):
                raise ValueError("approval requires both parts approved")
            if self.need_more_evidence or self.suggested_query:
                raise ValueError("approved review cannot request additional evidence")
        else:
            if self.lesson_ok and self.practice_ok:
                raise ValueError("a non-approved verdict must withhold a part or drop exercises")
            if not self.issues and not self.explicit_partial:
                raise ValueError("rejection requires actionable issues or an explicit part verdict")
            if (self.need_more_evidence or self.repair_target == "evidence") and not self.suggested_query:
                raise ValueError("evidence repair requires a search query")
        return self


class PackageState(LearningState, total=False):
    plan: dict[str, Any]
    plan_version: int
    replan_rounds: int
    plan_invalidations: list[dict[str, Any]]
    plan_invalidation: dict[str, Any]
    decision: dict[str, Any]
    artifacts: dict[str, Any]
    observations: list[dict[str, Any]]
    searches: list[str]
    budget: dict[str, Any]
    revisions: int
    package_review: dict[str, Any]
    learning_package: dict[str, Any]
    tool_stop_reason: str
    profile_context: str
    planning_context: dict[str, Any]
    tool_audit: list[dict[str, Any]]
    practice_error: str
    partial_completion: dict[str, Any]
    claim_support: dict[str, Any]
    claim_support_checked: bool
    delivery_observations: list[dict[str, Any]]


class LearningPackageGraph(EvidenceFirstGraph):
    MAX_MODEL_CALLS = 12
    MAX_TOOL_CALLS = 3
    MAX_INPUT_CHARS = 100_000
    MAX_OUTPUT_TOKENS_PER_CALL = 2048
    # Baseline replanning caps.  One invalid plan may be replaced once, so a run
    # never carries more than two plans; a second invalidation stops the run.
    MAX_REPLAN_ROUNDS = 1
    MAX_REPLAN_DEPTH = 2

    async def invoke(self, state, on_event=None):
        if not self._builder_available:
            raise PackageFailure("learning_package_unavailable")
        return await super().invoke(state, on_event)

    def _build_graph(self, checkpointer=None, on_event=None):
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(PackageState)
        for name in ("guard", "planner", "decide", "tool", "tutor", "practice", "review",
                     "compose", "claim_check", "approval", "verify", "rejected", "safe_decline"):
            builder.add_node(name, self._observed(name, on_event))
        builder.add_edge(START, "guard")
        builder.add_conditional_edges("guard", lambda s: "safe_decline" if s.get("safety_blocked") else "planner")
        builder.add_edge("planner", "decide")
        builder.add_conditional_edges("decide", self._route_decide,
                                      {"tool": "tool", "tutor": "tutor", "planner": "planner"})
        builder.add_conditional_edges("tool", self._route_after_tool,
                                      {"decide": "decide", "planner": "planner"})
        builder.add_edge("tutor", "practice")
        builder.add_edge("practice", "review")
        builder.add_conditional_edges("review", self._route_package_review)
        # The rule-based claim-support backstop runs on the composed package,
        # immediately before any delivery or human review.  It never calls a
        # model and never opens a second retry loop.
        builder.add_edge("compose", "claim_check")
        builder.add_conditional_edges("claim_check", self._needs_review)
        builder.add_conditional_edges("approval", self._route_review_decision)
        for name in ("verify", "rejected", "safe_decline"):
            builder.add_edge(name, END)
        return builder.compile(checkpointer=checkpointer)

    def _observed(self, name, on_event):
        if name == "approval":
            return self._approval
        observed = super()._observed(name, on_event)

        async def run(state):
            local = dict(state)
            try:
                result = await observed(local)
            except PackageFailure as exc:
                # A failed node still yields one normalized observation before
                # the stable error code is propagated unchanged.
                observation = exc.observation or failure_observation(name, exc.code)
                if on_event:
                    await on_event("observation.recorded", observation.to_dict())
                raise
            except Exception:
                # Never copy exception text; the stable API error stays unchanged.
                if on_event:
                    await on_event("observation.recorded",
                                   failure_observation(name, "run_execution_failed").to_dict())
                raise
            if "budget" in local:
                result["budget"] = local["budget"]
            observation_events = result.pop("_observation_events", [])
            if observation_events:
                result["delivery_observations"] = [
                    *local.get("delivery_observations", []), *observation_events]
                if on_event:
                    for item in observation_events:
                        await on_event("observation.recorded", item)
            tool_events = result.pop("_tool_events", [])
            if tool_events:
                result["tool_audit"] = [*local.get("tool_audit", []), *tool_events]
                if on_event:
                    for item in tool_events:
                        await on_event("tool.completed", {"node": name, **item})
            replan_events = result.pop("_replan_events", [])
            if replan_events:
                result["plan_invalidations"] = [*local.get("plan_invalidations", []), *replan_events]
                if on_event:
                    for item in replan_events:
                        await on_event("plan.replanned", {"node": name, **item})
            if name == "tool" and on_event:
                await on_event("retrieval.completed", {
                    "node": "tool", "evidence_count": len(result["evidence"]),
                    "latency_ms": result.pop("retrieval_ms"),
                    "tool_calls": local["budget"].get("tool_calls", 0),
                })
            else:
                result.pop("retrieval_ms", None)
            return result
        return run

    async def _ask(self, state, role, instruction, payload, schema):
        system = (
            render("system_frame", role=role, prompt_version=PROMPT_VERSION,
                   instruction=instruction).text
            + json.dumps(schema.model_json_schema(), ensure_ascii=False)
        )
        data = json.dumps({"question": state["message"], "history": state.get("history", []),
                           "profile": state.get("profile_context", ""), **payload}, ensure_ascii=False)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": data}]
        retryable_schema = schema in {LearningPlan, Lesson, Practice, QualityReview}
        max_attempts = 2 if retryable_schema else 1
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            budget = dict(state.get("budget", {}))
            calls = budget.get("model_calls", 0) + 1
            chars = budget.get("input_chars", 0) + sum(len(m["content"]) for m in messages)
            if calls > self.MAX_MODEL_CALLS or chars > self.MAX_INPUT_CHARS:
                raise PackageFailure("learning_package_budget_exceeded")
            state["budget"] = {**budget, "model_calls": calls, "input_chars": chars,
                               "output_token_limit": calls * self.MAX_OUTPUT_TOKENS_PER_CALL}
            response = await self.runtime.complete_structured(
                messages, max_tokens=self.MAX_OUTPUT_TOKENS_PER_CALL)
            if isinstance(response, dict):
                raw = response["text"]
                finish_reason = response.get("finish_reason")
            else:
                raw = response
                finish_reason = None
                response = {"text": raw, "usage": None}
            state["budget"] = record_model_usage(state["budget"], response)
            text = ""
            try:
                if not isinstance(raw, str) or len(raw) > 24000:
                    raise ValueError("invalid response")
                text = _extract_json_object(raw)
                return schema.model_validate_json(text).model_dump()
            except (ValidationError, ValueError) as exc:
                truncated = _looks_truncated(raw, finish_reason)
                if retryable_schema and truncated and attempt < 3:
                    # Length truncation is near-deterministic; allow one extra
                    # compact retry, still bounded by the overall call budget.
                    max_attempts = max(max_attempts, 3)
                if not retryable_schema or attempt >= max_attempts:
                    raise PackageFailure("learning_package_invalid_output") from None
                try:
                    repairable = (truncated or schema is not LearningPlan
                                  or isinstance(json.loads(text), dict))
                except (ValueError, TypeError):
                    repairable = truncated or schema is not LearningPlan
                if not repairable:
                    raise PackageFailure("learning_package_invalid_output") from None
                # Do not copy model-provided values or field names into the retry prompt.
                if truncated:
                    guidance = ("上次输出不是完整的 JSON（可能在长度上限处被截断）；"
                                + _TRUNCATION_GUIDANCE.get(
                                    schema.__name__, "请精简文本并闭合所有括号与字符串。"))
                elif isinstance(exc, ValidationError) and any(
                    error.get("type") == "json_invalid" for error in exc.errors()
                ):
                    guidance = "上次输出不是完整的 JSON；请闭合所有括号与字符串，避免多余文本。"
                else:
                    guidance = "检查字段类型、长度和必填字段。"
                messages.append({"role": "user", "content":
                    f"上一条输出未通过 {schema.__name__} JSON Schema 校验。{guidance}请仅输出符合该 Schema 的 JSON。"})
        raise PackageFailure("learning_package_invalid_output")

    def _invalidate_plan(self, state, trigger: str, stop_code: str) -> dict[str, Any]:
        """Mark the current plan invalid, or stop the run when the cap is used up.

        The returned update drops plan-derived artifacts but never touches the
        call/tool budgets, the searches already made, the evidence or the
        revision counter, so a replan cannot launder any existing limit.  Once
        the caps are spent the run stops with the failure code of the underlying
        cause, so the documented user-facing codes do not change.
        """
        rounds = state.get("replan_rounds", 0)
        version = state.get("plan_version", 1)
        if rounds >= self.MAX_REPLAN_ROUNDS or version >= self.MAX_REPLAN_DEPTH:
            raise PackageFailure(stop_code)
        budget = state.get("budget", {})
        entry = {"trigger": trigger, "round": rounds + 1, "plan_version": version,
                 "model_calls": budget.get("model_calls", 0),
                 "tool_calls": budget.get("tool_calls", 0),
                 "input_chars": budget.get("input_chars", 0),
                 "search_count": len(state.get("searches", [])),
                 "evidence_count": len(state.get("evidence", []))}
        return {"plan_invalidation": entry, "artifacts": {}, "practice_error": "",
                "partial_completion": {}, "decision": {"action": "finish", "query": ""}}

    @staticmethod
    def _route_decide(state):
        if state.get("plan_invalidation"):
            return "planner"
        return "tool" if state["decision"]["action"] == "search_course" else "tutor"

    @staticmethod
    def _route_after_tool(state):
        return "planner" if state.get("plan_invalidation") else "decide"

    async def _planner(self, state):
        invalidation = state.get("plan_invalidation") or {}
        replan = bool(invalidation)
        audits: list[dict[str, Any]] = []
        if replan:
            # Reuse the checkpointed learning context: a replan must not spend a
            # second round of profile, mistake or prerequisite reads.
            planning_context = state.get("planning_context", {})
        else:
            planning_context = {}
            if hasattr(self.runtime, "call_tool"):
                for name in ("get_learning_profile", "get_recent_mistakes"):
                    tool = await self.runtime.call_tool(state, role="planner", name=name, arguments={})
                    audits.append(tool.audit())
                    if tool.status == "success":
                        planning_context[name] = tool.data
                    elif tool.status not in {"no_data", "failed"}:
                        raise PackageFailure("learning_package_tool_failed")
                weak_points = planning_context.get("get_learning_profile", {}).get("weak_points", [])
                if weak_points:
                    tool = await self.runtime.call_tool(state, role="planner", name="get_prerequisites",
                        arguments={"knowledge_point_id": weak_points[0]["knowledge_point_id"]})
                    audits.append(tool.audit())
                    if tool.status == "success":
                        planning_context["get_prerequisites"] = tool.data
                    elif tool.status not in {"no_data", "failed"}:
                        raise PackageFailure("learning_package_tool_failed")
        instruction = render("planner_instruction").text
        if replan:
            # Registry names come from our own failure classes only; an unknown
            # trigger is an internal contract bug, not a model-visible error.
            reason = render(f"replan_reason_{invalidation['trigger']}").text
            instruction += render("planner_replan_suffix",
                                  round=invalidation["round"], reason=reason).text
        plan = await self._ask(state, "Planner", instruction,
                               {"learning_context": planning_context}, LearningPlan)
        if not replan:
            return {"plan": plan, "artifacts": {}, "evidence": [], "observations": [],
                    "searches": [], "revisions": 0, "planning_context": planning_context,
                    "plan_version": 1, "replan_rounds": 0, "plan_invalidations": [],
                    "_tool_events": audits}
        return {"plan": plan, "artifacts": {}, "planning_context": planning_context,
                "plan_version": invalidation["plan_version"] + 1,
                "replan_rounds": invalidation["round"], "plan_invalidation": {},
                "_tool_events": audits, "_replan_events": [invalidation]}

    async def _decide(self, state):
        searches = state.get("searches", [])
        if len(searches) >= self.MAX_TOOL_CALLS:
            if not state.get("evidence"):
                raise PackageFailure("learning_package_no_evidence")
            return {"decision": {"action": "finish", "query": ""}, "tool_stop_reason": "tool_budget"}
        decision = await self._ask(state, "Tutor", render("decide_instruction").text,
                                   {"plan": state["plan"], "observations": state.get("observations", [])}, ToolDecision)
        # A model that tries to finish without evidence breaks the contract and
        # stops immediately; that is never a plan invalidation.
        if decision["action"] == "finish" and not state.get("evidence"):
            raise PackageFailure("learning_package_no_evidence")
        if decision["action"] == "search_course" and decision["query"].casefold() in searches:
            if not state.get("evidence"):
                return self._invalidate_plan(state, "evidence_stalled", "learning_package_repeated_search")
            return {"decision": {"action": "finish", "query": ""}, "tool_stop_reason": "repeated_search"}
        return {"decision": decision}

    async def _tool(self, state):
        from backend.app.services.safety.run_guard import get_learning_run_guard

        query = ToolDecision.model_validate(state["decision"]).query
        if state["decision"]["action"] != "search_course" or get_learning_run_guard().decide(query).blocked:
            raise PackageFailure("learning_package_tool_denied")
        budget = dict(state.get("budget", {}))
        if budget.get("tool_calls", 0) >= self.MAX_TOOL_CALLS:
            raise PackageFailure("learning_package_budget_exceeded")
        state["budget"] = {**budget, "tool_calls": budget.get("tool_calls", 0) + 1}
        started = time.perf_counter()
        # Scope comes only from the authenticated request, never model arguments.
        if hasattr(self.runtime, "call_tool"):
            tool = await self.runtime.call_tool(state, role="tutor", name="search_course_evidence",
                                                arguments={"query": query})
            # A refusal is an authorization stop, not a transient failure: it is
            # never answered by re-planning.
            if tool.status in {"denied", "invalid_args"}:
                raise PackageFailure("learning_package_tool_failed")
            if tool.status not in {"success", "no_data"}:
                invalidation = self._invalidate_plan(state, "tool_failed", "learning_package_tool_failed")
                # The failed call is still charged: recording the query keeps the
                # replanned plan from re-issuing it verbatim.
                return {"evidence": state.get("evidence", []),
                        "searches": [*state.get("searches", []), query.casefold()],
                        "observations": [*state.get("observations", []),
                                         {"query": query, "results": [], "tool_status": tool.status}],
                        "retrieval_ms": int((time.perf_counter() - started) * 1000),
                        "_tool_events": [tool.audit()],
                        "_observation_events": [self._retrieval_observation(
                            "failed", tool_status=tool.status, result_count=0,
                            evidence_count=len(state.get("evidence", [])), retryable=True)],
                        **invalidation}
            hits = tool.data or []
            tool_events = [tool.audit()]
            tool_status = tool.status
        else:
            hits = await asyncio.to_thread(self.runtime.retrieve, query, state["course_id"])
            tool_events = []
            tool_status = "success" if hits else "no_data"
        evidence = {item["chunk_id"]: item for item in state.get("evidence", [])}
        observations = []
        for item in hits[:5]:
            if not item.get("chunk_id") or not item.get("source") or not item.get("content"):
                continue
            clean = {key: item[key] for key in ("chunk_id", "source", "content")}
            clean["content"] = str(clean["content"])[:2000]
            evidence[clean["chunk_id"]] = clean
            observations.append(clean)
        return {"evidence": list(evidence.values())[:15],
                "searches": [*state.get("searches", []), query.casefold()],
                "observations": [*state.get("observations", []), {"query": query, "results": observations}],
                "retrieval_ms": int((time.perf_counter() - started) * 1000),
                "_tool_events": tool_events,
                "_observation_events": [self._retrieval_observation(
                    "success" if observations else "partial", tool_status=tool_status,
                    result_count=len(hits), valid_count=len(observations),
                    evidence_count=len(evidence), retryable=not observations)]}

    @staticmethod
    def _retrieval_observation(status, *, tool_status: str, result_count: int,
                               evidence_count: int, valid_count: int = 0,
                               retryable: bool = False) -> dict[str, Any]:
        """Project one retrieval outcome into the unified observation schema."""
        return Observation(
            node="tool", status=status, retryable=retryable,
            detail={"tool_status": tool_status, "result_count": result_count,
                    "valid_count": valid_count, "evidence_count": evidence_count},
        ).to_dict()

    def _step(self, state, role):
        plan = LearningPlan.model_validate(state["plan"])
        step = next(step for step in plan.steps if step.role == role)
        if any(dependency not in state.get("artifacts", {}) for dependency in step.depends_on):
            raise PackageFailure("learning_package_dependency_missing")
        return step

    @staticmethod
    def _check_sources(source_ids, state):
        allowed = {item["chunk_id"] for item in state.get("evidence", [])}
        if not source_ids or not set(source_ids).issubset(allowed):
            raise PackageFailure("learning_package_invalid_citation")

    async def _tutor(self, state):
        step = self._step(state, "tutor")
        lesson = await self._ask(state, "Tutor", render("tutor_instruction").text,
                                {"goal": step.goal, "evidence": state["evidence"],
                                 "review_feedback": state.get("package_review", {}).get("issues", [])}, Lesson)
        self._check_sources(lesson["source_ids"], state)
        # Invalidate downstream artifacts when the upstream lesson changes.
        return {"artifacts": {step.id: lesson}}

    async def _practice(self, state):
        step = self._step(state, "practice")
        dependencies = {key: state["artifacts"][key] for key in step.depends_on}
        try:
            practice = await self._ask(state, "Practice", render("practice_instruction").text,
                                       {"goal": step.goal, "dependencies": dependencies, "evidence": state["evidence"],
                                        "review_feedback": state.get("package_review", {}).get("issues", [])}, Practice)
            for exercise in practice["exercises"]:
                self._check_sources(exercise["source_ids"], state)
        except PackageFailure as exc:
            # A rejected practice batch must not silently discard a lesson that
            # may already be deliverable.  Only contract failures of this part
            # are degradable; budget, tool and safety failures still abort run.
            if exc.code not in {"learning_package_invalid_output", "learning_package_invalid_citation"}:
                raise
            # Drop a superseded practice batch: a failed rework must not leave
            # previously rejected exercises in state as if they were current.
            remaining = {key: value for key, value in state.get("artifacts", {}).items()
                         if key != step.id}
            return {"practice_error": exc.code, "artifacts": remaining}
        return {"artifacts": {**state["artifacts"], step.id: practice}}

    async def _review(self, state):
        plan = LearningPlan.model_validate(state["plan"])
        practice_step = next(step for step in plan.steps if step.role == "practice")
        practice_missing = practice_step.id not in state.get("artifacts", {})
        instruction = render("reviewer_instruction").text
        if practice_missing:
            instruction += render("reviewer_partial_suffix").text
        review = await self._ask(state, "Reviewer", instruction,
                                 {"plan": state["plan"], "artifacts": state["artifacts"],
                                  "evidence": state["evidence"], "practice_available": not practice_missing},
                                 QualityReview)
        lesson_ok = review["approved"] if review["lesson_approved"] is None else review["lesson_approved"]
        practice_ok = review["approved"] if review["practice_approved"] is None else review["practice_approved"]
        revisions = state.get("revisions", 0)
        if practice_missing and (review["approved"] or practice_ok or review["dropped_exercises"]):
            # An artifact that was never produced cannot be reviewed as delivered.
            raise PackageFailure("learning_package_quality_failed")
        updates: dict[str, Any] = {"package_review": review, "revisions": revisions}
        if lesson_ok and practice_ok:
            # Fully approved deliverable; a non-empty drop list still withholds
            # the rejected exercises, so the run settles as partially_completed.
            if review["dropped_exercises"]:
                updates.update(self._drop_exercises(state, review["dropped_exercises"]))
            return updates
        if review["need_more_evidence"] or review["repair_target"] == "evidence":
            query = review["suggested_query"]
            if state.get("budget", {}).get("tool_calls", 0) >= self.MAX_TOOL_CALLS or query.casefold() in state.get("searches", []):
                raise PackageFailure("learning_package_evidence_revision_unavailable")
            updates["revisions"] = revisions + 1
            updates["decision"] = {"action": "search_course", "query": query}
            return updates
        if not lesson_ok:
            if revisions >= 1:
                raise PackageFailure("learning_package_quality_failed")
            updates["revisions"] = revisions + 1
            return updates  # one bounded repair, routed by repair_target
        # The lesson is reviewed as deliverable; the practice part is not.
        if practice_missing or revisions >= 1:
            updates.update(self._withhold_practice(state))
            return updates
        updates["revisions"] = revisions + 1
        return updates  # one bounded repair attempt for the practice part

    def _drop_exercises(self, state, dropped):
        plan = LearningPlan.model_validate(state["plan"])
        tutor = next(step for step in plan.steps if step.role == "tutor")
        practice = next(step for step in plan.steps if step.role == "practice")
        rejected = set(dropped)
        kept = [exercise for index, exercise in enumerate(state["artifacts"][practice.id]["exercises"], 1)
                if index not in rejected]
        return {
            "artifacts": {tutor.id: state["artifacts"][tutor.id],
                          practice.id: {"exercises": kept}},
            "partial_completion": {
                "status": "partially_completed", "delivered_parts": ["lesson", "practice"],
                "withheld_parts": [], "withheld_exercise_numbers": list(dropped),
                "reason": "exercise_not_approved",
            },
        }

    def _withhold_practice(self, state):
        plan = LearningPlan.model_validate(state["plan"])
        tutor = next(step for step in plan.steps if step.role == "tutor")
        practice = next(step for step in plan.steps if step.role == "practice")
        reason = "practice_unavailable" if practice.id not in state.get("artifacts", {}) else "practice_not_approved"
        return {
            # Drop the rejected practice artifact from the checkpointed state so
            # unreviewed exercises are not retained as if they were deliverable.
            "artifacts": {tutor.id: state["artifacts"][tutor.id]},
            "partial_completion": {
                "status": "partially_completed", "delivered_parts": ["lesson"],
                "withheld_parts": ["practice"], "withheld_exercise_numbers": [],
                "reason": reason,
            },
        }

    @staticmethod
    def _route_package_review(state):
        review = state["package_review"]
        if review["approved"] or state.get("partial_completion"):
            return "compose"
        if review.get("need_more_evidence") or review.get("repair_target") == "evidence":
            return "tool"
        lesson_ok = review["approved"] if review.get("lesson_approved") is None else review["lesson_approved"]
        if lesson_ok:
            # The lesson is already acceptable; only the practice part may be repaired.
            return "practice"
        return "practice" if review.get("repair_target") == "exercise" else "tutor"

    def _source_evidence(self, source_ids, state):
        self._check_sources(source_ids, state)
        by_id = {item["chunk_id"]: item for item in state.get("evidence", [])}
        return [by_id[source_id] for source_id in dict.fromkeys(source_ids)]

    def _with_citations(self, artifact, state):
        # Citation metadata comes from retrieved evidence, never model output.
        evidence = self._source_evidence(artifact["source_ids"], state)
        return {**artifact, "citations": self.runtime.citations(evidence)}

    def _used_evidence(self, state):
        package = state.get("learning_package")
        if not package:
            # A human replacement has no verified source mapping of its own.
            return []
        source_ids = [source_id
                      for artifact in [package["lesson"], *package["exercises"]]
                      for source_id in artifact["source_ids"]]
        return self._source_evidence(source_ids, state)

    @staticmethod
    def _citation_text(artifact):
        return "依据：" + "；".join(
            f"{item['source']}（{item['chunk_id']}）" for item in artifact["citations"]
        )

    async def _compose(self, state):
        tutor, practice = LearningPlan.model_validate(state["plan"]).steps
        lesson = self._with_citations(state["artifacts"][tutor.id], state)
        practice_artifact = state["artifacts"].get(practice.id)
        exercises = [self._with_citations(item, state)
                     for item in practice_artifact["exercises"]] if practice_artifact else []
        partial = state.get("partial_completion") or {}
        text = ["## 学习讲解", lesson["explanation"], self._citation_text(lesson)]
        if exercises:
            text.append("## 练习与解析")
            for index, exercise in enumerate(exercises, 1):
                text.append(f"### 第 {index} 题\n{exercise['question']}\n\n答案：{exercise['answer']}\n\n解析：{exercise['explanation']}")
                text.append(self._citation_text(exercise))
        if partial:
            # Fixed wording only: the withheld part is described by status, never
            # by unreviewed model text.
            if "practice" in partial.get("withheld_parts", []):
                text.append("> 说明：本次仅交付已通过内容审核的讲解；练习题未通过内容检查，未随本次结果交付。")
            elif partial.get("withheld_exercise_numbers"):
                numbers = "、".join(str(number) for number in partial["withheld_exercise_numbers"])
                text.append(f"> 说明：本次仅交付已通过内容审核的讲解与其余练习；原第 {numbers} 题未通过内容检查，未交付。")
        review_out = state["package_review"]
        if partial:
            # Reviewer issue/query text may quote the withheld artifacts; keep it
            # in the internal review state for audit, never in the delivered package.
            review_out = {**review_out, "issues": [], "suggested_query": "",
                          "withheld_issue_count": len(review_out.get("issues", [])),
                          "withheld_suggested_query": bool(review_out.get("suggested_query"))}
        package = {
            "plan": state["plan"], "lesson": lesson, "exercises": exercises,
            "review": review_out, "revisions": state.get("revisions", 0),
        }
        if partial:
            package["partial_completion"] = partial
        return {"answer": "\n\n".join(text), "learning_package": package}

    async def _claim_check(self, state):
        """One rule-based claim-support check on the composed, deliverable package.

        The check runs after composition and before human review or delivery;
        it never calls a model.  A failure is fail-closed with the existing
        stable error code, so no new retry loop or user-visible code is added.
        """
        package = state.get("learning_package") or {}
        if not package:
            raise PackageFailure("learning_package_quality_failed")
        if state.get("claim_support_checked"):
            return {}
        lesson = package.get("lesson") or {}
        items = [{"text": lesson.get("explanation", ""), "source_ids": lesson.get("source_ids", [])}]
        for exercise in package.get("exercises", []):
            text = " ".join(str(exercise.get(key, "")) for key in ("question", "answer", "explanation"))
            items.append({"text": text, "source_ids": exercise.get("source_ids", [])})
        support = evaluate_rule_based_support(items, state.get("evidence", []))
        citation_failure = bool(support["missing_citations"] or support["invalid_citations"])
        observation = Observation(
            node="claim_check",
            status=("failed" if not support["passed"]
                    else "partial" if package.get("partial_completion") else "success"),
            error_class=None if support["passed"] else ("citation" if citation_failure else "claim_support"),
            retryable=False,
            evidence_strength=support["evidence_strength"],
            citation_support=support["citation_support"],
            detail={"item_count": support["item_count"],
                    "evaluated_items": support["evaluated_items"],
                    "supported_items": support["supported_items"],
                    "unsupported_items": support["unsupported_items"],
                    "missing_citations": support["missing_citations"],
                    "invalid_citations": support["invalid_citations"],
                    "reasons": support["reasons"],
                    "partial": bool(package.get("partial_completion"))},
        )
        if not support["passed"]:
            code = ("learning_package_invalid_citation" if citation_failure
                    else "learning_package_quality_failed")
            raise PackageFailure(code, observation=observation)
        return {"claim_support": {**support, "checked": True},
                "claim_support_checked": True,
                "_observation_events": [observation.to_dict()]}

    def _approval(self, state, config):
        updates = super()._approval({**state, "evidence": self._used_evidence(state)}, config)
        # A human-edited answer replaces the rendered package, not its old copy.
        if "answer" in updates or updates["review_status"] == "rejected":
            updates["learning_package"] = {}
            updates["partial_completion"] = {}
            # A human replacement is not model content, so the model-side
            # claim-support verdict and observations no longer apply.
            updates["claim_support"] = {}
            updates["delivery_observations"] = []
        return updates

    async def _verify(self, state):
        # Filter the verification input without discarding evidence from the audit state.
        result = await super()._verify({**state, "evidence": self._used_evidence(state)})
        result["quality"]["reviewer_passed"] = bool(state.get("learning_package") and state.get("package_review", {}).get("approved"))
        result["quality"]["human_edited"] = not bool(state.get("learning_package"))
        result["quality"]["claim_support"] = state.get("claim_support") or {}
        result["quality"]["delivery_observations"] = state.get("delivery_observations", [])
        partial = state.get("partial_completion") or {}
        if partial:
            # Mark the delivery so reviewers/clients cannot mistake it for a
            # complete plan pass, even when the delivered part is approved.
            result["quality"]["partial_completion"] = True
            result["quality"]["delivered_parts"] = list(partial.get("delivered_parts", []))
        return result
