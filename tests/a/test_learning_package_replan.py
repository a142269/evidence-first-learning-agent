"""QWEN-211: 有界重规划的失效检测、上限停止、审计事件与断点恢复。

Every case is driven offline with a scripted structured-output stub; no model,
network or ``.env`` access is possible from this file.
"""
import json

import pytest

from backend.app.agent_runtime.learning_package import LearningPackageGraph
from backend.app.api.v2 import learning_runs
from tests.a.test_learning_runs_v2_lifecycle import api as api, events

PLAN = {"steps": [
    {"id": "explain", "role": "tutor", "goal": "解释 RAG 并指出检索作用", "depends_on": []},
    {"id": "practice", "role": "practice", "goal": "设计三道递进练习", "depends_on": ["explain"]},
]}
LESSON = {"explanation": "检索增强生成先查找课程材料，再根据检索证据组织回答，并明确引用来源。", "source_ids": ["c1"]}
PRACTICE = {"exercises": [
    {"question": f"第 {index} 题：为什么需要先检索？", "answer": "提供资料依据",
     "explanation": "检索提供可追溯的资料，帮助回答使用课程证据。", "source_ids": ["c1"]}
    for index in range(1, 4)
]}
PASS = {"approved": True, "issues": []}
FIRST = {"action": "search_course", "query": "RAG 的检索流程"}
OTHER = {"action": "search_course", "query": "引用如何帮助核对答案"}
FINISH = {"action": "finish"}
HIT = [{"chunk_id": "c1", "source": "chapter.md", "content": "课程证据"}]
LEDGER_KEYS = {"node", "trigger", "round", "plan_version", "model_calls", "tool_calls",
               "input_chars", "search_count", "evidence_count"}
# planner, decide, [失败的检索], planner, decide, decide, tutor, practice, reviewer
DELIVER = [PLAN, FIRST, PLAN, OTHER, FINISH, LESSON, PRACTICE, PASS]


@pytest.fixture
def scripted(api, monkeypatch):
    client, factory = api
    replies, calls = [], []

    async def complete(messages, *, max_tokens):
        calls.append(messages)
        assert max_tokens == 2048
        assert replies, "unexpected extra model call"
        return json.dumps(replies.pop(0), ensure_ascii=False)

    monkeypatch.setattr(learning_runs._runtime, "complete_structured", complete)
    monkeypatch.setattr(learning_runs._runtime, "_profile_context", lambda _: "已保存的学生画像")
    monkeypatch.setattr(learning_runs, "_package_graph", LearningPackageGraph(learning_runs._runtime))
    return client, factory, replies, calls


def package(client, review=False):
    return client.post("/api/v2/learning-runs/stream", headers={"Authorization": "Bearer alice"},
        json={"message": "解释 RAG 并给我三道练习", "mode": "learning_package",
              "session_id": "replan-session", "require_approval": review})


def failing_retrieve(monkeypatch, results=None):
    """Charge a transport failure to the first search, then return optional hits."""
    attempts = []

    def retrieve(query, course):
        attempts.append(query)
        if results is not None and len(attempts) > 1:
            return results
        raise RuntimeError("offline_provider_outage")

    monkeypatch.setattr(learning_runs._runtime, "retrieve", retrieve)
    return attempts


def started_nodes(output):
    return [data["node"] for name, data in output if name == "node.started"]


def replan_events(output):
    return [data for name, data in output if name == "plan.replanned"]


def test_failed_retrieval_replans_once_and_still_delivers(scripted, monkeypatch):
    client, _, replies, calls = scripted
    attempts = failing_retrieve(monkeypatch, results=HIT)
    replies.extend(DELIVER)
    output = events(package(client))
    final = output[-1][1]
    assert output[-1][0] == "run.completed", final
    # guard, planner, decide, tool, planner, decide, tool, decide, tutor, practice, review, compose, verify
    assert started_nodes(output).count("planner") == 2 and started_nodes(output).count("decide") == 3
    assert [item["trigger"] for item in replan_events(output)] == ["tool_failed"]
    assert attempts == [FIRST["query"], OTHER["query"]]
    assert final["budget"]["model_calls"] == 8 and final["budget"]["tool_calls"] == 2
    assert final["learning_package"]["lesson"]["explanation"] == LESSON["explanation"]
    assert len(calls) == 8


def test_replanned_plan_keeps_the_two_step_dependency_contract(scripted, monkeypatch):
    client, _, replies, _ = scripted
    failing_retrieve(monkeypatch, results=HIT)
    replies.extend(DELIVER)
    final = events(package(client))[-1][1]
    plan = final["learning_package"]["plan"]
    assert [step["role"] for step in plan["steps"]] == ["tutor", "practice"]
    assert plan["steps"][1]["depends_on"] == [plan["steps"][0]["id"]]
    assert plan["steps"][0]["depends_on"] == []
    assert final["learning_package"]["revisions"] == 0


def test_second_tool_failure_stops_at_the_replan_cap(scripted, monkeypatch):
    client, _, replies, calls = scripted
    attempts = failing_retrieve(monkeypatch)
    replies.extend([PLAN, FIRST, PLAN, OTHER])
    response = package(client)
    output = events(response)
    assert output[-1][1]["error"] == "learning_package_tool_failed"
    assert "answer.delta" not in response.text
    assert len(replan_events(output)) == 1 and started_nodes(output).count("planner") == 2
    assert len(calls) == 4 and len(attempts) == 2


def test_repeated_query_after_replan_stops_without_executing_it_again(scripted, monkeypatch):
    client, _, replies, calls = scripted
    attempts = failing_retrieve(monkeypatch)
    replies.extend([PLAN, FIRST, PLAN, FIRST])
    output = events(package(client))
    assert output[-1][1]["error"] == "learning_package_repeated_search"
    assert [item["round"] for item in replan_events(output)] == [1]
    # The charged but failed query is recorded, so the replan cannot re-run it.
    assert attempts == [FIRST["query"]] and len(calls) == 4


def test_replan_invalidation_snapshot_records_reason_and_budget(scripted, monkeypatch):
    client, _, replies, _ = scripted
    failing_retrieve(monkeypatch, results=HIT)
    replies.extend(DELIVER)
    entry = replan_events(events(package(client)))[0]
    assert entry["trigger"] == "tool_failed" and entry["round"] == 1
    assert entry["plan_version"] == 1
    assert entry["model_calls"] == 2 and entry["tool_calls"] == 1
    assert entry["search_count"] == 0 and entry["evidence_count"] == 0
    assert entry["input_chars"] > 0
    assert set(entry) == LEDGER_KEYS | {"run_id", "event_sequence"}
    assert not {"message", "prompt", "content", "draft_answer", "evidence", "query", "plan"} & set(entry)


def test_stalled_search_replans_and_recovers_with_a_new_query(scripted, monkeypatch):
    client, _, replies, calls = scripted
    attempts = []

    def retrieve(query, course):
        attempts.append(query)
        return [] if query == FIRST["query"] else HIT

    monkeypatch.setattr(learning_runs._runtime, "retrieve", retrieve)
    replies.extend([PLAN, FIRST, FIRST, PLAN, OTHER, FINISH, LESSON, PRACTICE, PASS])
    output = events(package(client))
    final = output[-1][1]
    assert output[-1][0] == "run.completed", final
    assert [item["trigger"] for item in replan_events(output)] == ["evidence_stalled"]
    assert replan_events(output)[0]["round"] == 1
    assert started_nodes(output).count("planner") == 2 and started_nodes(output).count("decide") == 4
    assert attempts == [FIRST["query"], OTHER["query"]]
    assert final["budget"]["model_calls"] == 9 and final["budget"]["tool_calls"] == 2
    assert final["learning_package"]["lesson"]["explanation"] == LESSON["explanation"]
    assert len(calls) == 9


def test_replan_round_cap_is_an_independent_hard_limit(scripted, monkeypatch):
    client, _, replies, calls = scripted
    monkeypatch.setattr(learning_runs._package_graph, "MAX_REPLAN_ROUNDS", 0)
    attempts = failing_retrieve(monkeypatch)
    replies.extend([PLAN, FIRST])
    output = events(package(client))
    assert output[-1][1]["error"] == "learning_package_tool_failed"
    assert replan_events(output) == [] and started_nodes(output).count("planner") == 1
    assert len(calls) == 2 and len(attempts) == 1


def test_replan_depth_cap_is_an_independent_hard_limit(scripted, monkeypatch):
    client, _, replies, calls = scripted
    monkeypatch.setattr(learning_runs._package_graph, "MAX_REPLAN_DEPTH", 1)
    attempts = failing_retrieve(monkeypatch)
    replies.extend([PLAN, FIRST])
    output = events(package(client))
    assert output[-1][1]["error"] == "learning_package_tool_failed"
    assert replan_events(output) == [] and started_nodes(output).count("planner") == 1
    assert len(calls) == 2 and len(attempts) == 1


def test_search_budget_and_evidence_free_finish_are_never_replanned(scripted, monkeypatch):
    client, _, replies, _ = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: [])
    replies.extend([PLAN, FIRST, FINISH])
    output = events(package(client))
    # A model that finishes without evidence breaks the contract; that is not a
    # plan invalidation and it must not buy an extra planner call.
    assert output[-1][1]["error"] == "learning_package_no_evidence"
    assert replan_events(output) == [] and started_nodes(output).count("planner") == 1


def test_denied_tool_never_triggers_a_replan(scripted, monkeypatch):
    from backend.app.services.v2_learning_tools import ToolResult

    client, _, replies, calls = scripted
    original = learning_runs._runtime.call_tool

    async def call_tool(state, *, role, name, arguments):
        if name == "search_course_evidence":
            return ToolResult(name=name, version="v2-readonly-1", status="denied", data=None,
                              latency_ms=0, request_hash="denied")
        return await original(state, role=role, name=name, arguments=arguments)

    monkeypatch.setattr(learning_runs._runtime, "call_tool", call_tool)
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: HIT)
    replies.extend([PLAN, FIRST])
    output = events(package(client))
    # An authorization refusal is not a transient failure: re-planning cannot
    # make a denied scope permissible.
    assert output[-1][1]["error"] == "learning_package_tool_failed"
    assert replan_events(output) == [] and len(calls) == 2


def test_replan_does_not_replay_planner_context_tools(scripted, monkeypatch):
    client, _, replies, _ = scripted
    attempts = failing_retrieve(monkeypatch, results=HIT)
    observed = []
    original = learning_runs._runtime.call_tool

    async def call_tool(state, *, role, name, arguments):
        observed.append(name)
        return await original(state, role=role, name=name, arguments=arguments)

    monkeypatch.setattr(learning_runs._runtime, "call_tool", call_tool)
    replies.extend(DELIVER)
    assert events(package(client))[-1][0] == "run.completed"
    assert observed.count("get_learning_profile") == 1 and observed.count("get_recent_mistakes") == 1
    assert observed.count("search_course_evidence") == 2 and len(attempts) == 2


def test_replan_audit_event_is_persisted_as_a_checkpoint_row(scripted, monkeypatch):
    from backend.app.core.models import AgentCheckpointRecord

    client, factory, replies, _ = scripted
    failing_retrieve(monkeypatch, results=HIT)
    replies.extend(DELIVER)
    output = events(package(client))
    run_id = output[0][1]["run_id"]
    with factory() as db:
        rows = db.query(AgentCheckpointRecord).filter_by(run_id=run_id).all()
        replanned = [row for row in rows if row.status == "plan.replanned"]
    assert len(replanned) == 1
    assert replanned[0].node_name == "planner"
    state = replanned[0].state_data
    assert state["trigger"] == "tool_failed" and state["round"] == 1
    assert set(state) == LEDGER_KEYS
    assert set(replan_events(output)[0]) == LEDGER_KEYS | {"run_id", "event_sequence"}


def test_consumed_replan_round_survives_a_checkpoint_restart(scripted, monkeypatch):
    client, _, replies, calls = scripted
    attempts = failing_retrieve(monkeypatch)
    replies.extend([PLAN, FIRST, PLAN, OTHER])
    output = events(package(client))
    assert output[-1][1]["error"] == "learning_package_tool_failed"
    run_id = output[0][1]["run_id"]
    assert len(replan_events(output)) == 1 and len(calls) == 4

    calls_after_restart = len(calls)
    resumed = events(client.post(f"/api/v2/learning-runs/{run_id}/continue",
                                 headers={"Authorization": "Bearer alice"}))
    assert resumed[-1][1]["error"] == "learning_package_tool_failed"
    # The consumed round is read back from the checkpoint: recovery replays the
    # failed node and stops without granting a fresh replan or a new model call.
    assert len(calls) == calls_after_restart
    assert replan_events(resumed) == [] and started_nodes(resumed) == ["tool"]
    assert len(attempts) == 3


@pytest.mark.parametrize("review", [False, True])
def test_replanned_package_is_reviewable_without_leaking_the_ledger(scripted, monkeypatch, review):
    client, _, replies, _ = scripted
    failing_retrieve(monkeypatch, results=HIT)
    replies.extend(DELIVER)
    response = package(client, review=review)
    if not review:
        output = events(response)
        assert "plan.replanned" in [name for name, _ in output]
        # The delivered package carries the replanned plan, never the ledger.
        assert "plan_invalidations" not in json.dumps(output[-1][1])
        assert json.dumps(output[-1][1]).count('"trigger"') == 0
        return
    run_id = events(response)[0][1]["run_id"]
    assert events(response)[-1][0] == "review.required"
    pending = client.get(f"/api/v2/learning-runs/{run_id}",
                         headers={"Authorization": "Bearer teacher"}).json()["result"]
    assert "plan_invalidations" not in pending and "plan_invalidation" not in pending
    assert [item["chunk_id"] for item in pending["approval"]["citations"]] == ["c1"]
    approved = client.post(f"/api/v2/learning-runs/{run_id}/resume",
                           headers={"Authorization": "Bearer teacher"}, json={"approved": True})
    assert events(approved)[-1][0] == "run.completed"
    assert len(replies) == 0
