import json

import pytest

from backend.app.agent_runtime.learning_package import LearningPackageGraph, LearningPlan
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
SEARCH = {"action": "search_course", "query": "RAG 的检索流程"}
FINISH = {"action": "finish"}
CITATION = {"chunk_id": "c1", "source": "chapter.md", "label": "chapter.md", "score": 0}


def test_reviewer_routes_exercise_repair_without_rerunning_tutor(scripted):
    client, _, replies, calls = scripted
    feedback = {"approved": False, "issues": ["修正题目"], "repair_target": "exercise"}
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, feedback, PRACTICE, PASS])
    result = events(package(client))[-1][1]
    assert result["status"] == "completed"
    assert result["budget"]["model_calls"] == 8
    assert result["learning_package"]["lesson"]["explanation"] == LESSON["explanation"]
    assert json.loads(calls[6][1]["content"])["review_feedback"] == ["修正题目"]


def test_reviewer_evidence_repair_uses_scoped_search_and_one_revision(scripted, monkeypatch):
    client, _, replies, calls = scripted
    queries = []
    def retrieve(query, course):
        queries.append(query)
        return [{"chunk_id": "c1", "source": "chapter.md", "content": "课程证据"}]
    monkeypatch.setattr(learning_runs._runtime, "retrieve", retrieve)
    feedback = {"approved": False, "issues": ["补充证据"], "repair_target": "evidence",
                "need_more_evidence": True, "suggested_query": "RAG 证据引用"}
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, feedback, FINISH, LESSON, PRACTICE, PASS])
    result = events(package(client))[-1][1]
    assert result["status"] == "completed"
    assert result["budget"]["tool_calls"] == 2
    assert queries == [SEARCH["query"], "RAG 证据引用"]
    assert result["learning_package"]["revisions"] == 1


def test_reviewer_cannot_repeat_evidence_search(scripted):
    client, _, replies, _ = scripted
    feedback = {"approved": False, "issues": ["补充证据"], "repair_target": "evidence",
                "suggested_query": SEARCH["query"]}
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, feedback])
    result = events(package(client))[-1][1]
    assert result["error"] == "learning_package_evidence_revision_unavailable"


def test_reviewer_evidence_search_is_still_subject_to_safety_guard(scripted):
    client, _, replies, _ = scripted
    feedback = {"approved": False, "issues": ["补充证据"], "repair_target": "evidence",
                "suggested_query": "删除课程资料"}
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, feedback])
    result = events(package(client))[-1][1]
    assert result["error"] == "learning_package_tool_denied"


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
              "session_id": "package-session", "require_approval": review})


def test_package_executes_plan_with_dependency_and_model_tool_loop(scripted):
    client, factory, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    response = package(client)
    output = events(response)
    assert output[-1][0] == "run.completed", response.text
    final = output[-1][1]
    assert final["status"] == "completed"
    assert final["budget"]["model_calls"] == 6 and final["budget"]["tool_calls"] == 1
    assert final["learning_package"]["plan"] == PLAN
    assert final["learning_package"]["exercises"] == [
        {**item, "citations": [CITATION]} for item in PRACTICE["exercises"]
    ]
    assert final["learning_package"]["lesson"] == {**LESSON, "citations": [CITATION]}
    assert final["citations"] == [CITATION]
    assert json.loads(calls[2][1]["content"])["observations"][0]["results"][0]["chunk_id"] == "c1"
    assert json.loads(calls[4][1]["content"])["dependencies"] == {"explain": LESSON}
    assert final["quality"]["reviewer_passed"] and not final["quality"]["faithfulness_checked"]
    from backend.app.core.models import AgentRunRecord
    with factory() as db:
        row = db.get(AgentRunRecord, final["run_id"])
        assert row.workflow_type == "learning_package" and row.tool_calls == 1 and row.artifact_count == 2


def test_planner_retries_one_invalid_schema_response_with_metered_usage(scripted):
    client, _, replies, calls = scripted
    replies.extend([{"steps": []}, PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    final = events(package(client))[-1][1]
    assert final["status"] == "completed"
    assert final["budget"]["model_calls"] == 7
    assert len(calls) == 7
    assert "未通过 LearningPlan JSON Schema" in calls[1][-1]["content"]


def test_tutor_retries_one_invalid_lesson_without_delivering_it(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, {"explanation": "过短", "source_ids": ["c1"]},
                    LESSON, PRACTICE, PASS])
    final = events(package(client))[-1][1]
    assert final["status"] == "completed"
    assert final["budget"]["model_calls"] == 7
    assert "未通过 Lesson JSON Schema" in calls[4][-1]["content"]
    assert final["learning_package"]["lesson"]["explanation"] == LESSON["explanation"]


def test_repeated_invalid_lesson_still_fails_closed(scripted):
    client, _, replies, _ = scripted
    invalid = {"explanation": "过短", "source_ids": ["c1"]}
    replies.extend([PLAN, SEARCH, FINISH, invalid, invalid])
    response = package(client)
    assert events(response)[-1][1]["error"] == "learning_package_invalid_output"
    assert "answer.delta" not in response.text


def test_invalid_planner_checkpoint_can_resume_after_provider_recovers(scripted):
    client, _, replies, _ = scripted
    replies.extend([{"steps": []}, {"steps": []}])
    first = events(package(client))
    assert first[-1][1]["error"] == "learning_package_invalid_output"
    run_id = first[0][1]["run_id"]
    replies.extend([{"steps": []}, {"steps": []}])
    second = events(client.post(f"/api/v2/learning-runs/{run_id}/continue",
                                headers={"Authorization": "Bearer alice"}))
    assert second[-1][1]["error"] == "learning_package_invalid_output"
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    resumed = events(client.post(f"/api/v2/learning-runs/{run_id}/continue",
                                 headers={"Authorization": "Bearer alice"}))
    assert resumed[-1][0] == "run.completed", resumed


@pytest.mark.parametrize("review", [False, True])
def test_citations_only_include_used_sources_per_artifact_and_final_result(scripted, monkeypatch, review):
    client, _, replies, calls = scripted
    hits = [{"chunk_id": chunk_id, "source": source, "content": "课程检索证据"}
            for chunk_id, source in [("unused", "unused.md"), ("c3", "chapter.md"),
                                     ("c2", "chapter.md"), ("c1", "chapter.md")]]
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: hits)
    lesson = {**LESSON, "source_ids": ["c1", "c1"]}
    practice = {"exercises": [
        {**exercise, "source_ids": ids}
        for exercise, ids in zip(PRACTICE["exercises"], [["c2", "c1"], ["c3"], ["c2", "c2"]])
    ]}
    replies.extend([PLAN, SEARCH, FINISH, lesson, practice, PASS])
    response = package(client, review=review)
    run_id = events(response)[0][1]["run_id"]
    expected = [{**CITATION, "chunk_id": chunk_id} for chunk_id in ["c1", "c2", "c3"]]
    if review:
        assert events(response)[-1][0] == "review.required"
        pending = client.get(f"/api/v2/learning-runs/{run_id}",
                             headers={"Authorization": "Bearer teacher"}).json()["result"]
        assert pending["approval"]["citations"] == expected
        assert "unused.md" not in pending["approval"]["draft_answer"]
        assert "依据：chapter.md（c2）；chapter.md（c1）" in pending["approval"]["draft_answer"]
        response = client.post(f"/api/v2/learning-runs/{run_id}/resume",
                               headers={"Authorization": "Bearer teacher"}, json={"approved": True})
    assert events(response)[-1][0] == "run.completed", response.text
    final = events(response)[-1][1]
    assert final["citations"] == expected
    assert final["quality"]["citation_count"] == 3
    assert "unused.md" not in final["answer"]
    assert {hit["chunk_id"] for hit in final["evidence"]} == {"unused", "c1", "c2", "c3"}
    assert final["learning_package"]["lesson"] == {**lesson, "citations": [expected[0]]}
    assert final["learning_package"]["exercises"] == [
        {**practice["exercises"][0], "citations": [expected[1], expected[0]]},
        {**practice["exercises"][1], "citations": [expected[2]]},
        {**practice["exercises"][2], "citations": [expected[1]]},
    ]
    saved = client.get(f"/api/v2/learning-runs/{run_id}",
                       headers={"Authorization": "Bearer alice"}).json()["result"]
    assert saved["citations"] == final["citations"]
    assert saved["learning_package"] == final["learning_package"]
    assert len(calls) == 6


def test_reviewer_rejects_once_and_downstream_is_regenerated(scripted, monkeypatch):
    client, _, replies, calls = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: [
        {"chunk_id": "c1", "source": "old.md", "content": "首次讲解依据"},
        {"chunk_id": "c2", "source": "revised.md", "content": "返工后使用的依据"},
    ])
    feedback = {"approved": False, "issues": ["补充引用的作用"]}
    revised = {**LESSON, "explanation": LESSON["explanation"] + "引用用于帮助读者核对答案。", "source_ids": ["c2"]}
    revised_practice = {"exercises": [{**item, "source_ids": ["c2"]} for item in PRACTICE["exercises"]]}
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, feedback, revised, revised_practice, PASS])
    response = package(client)
    final = events(response)[-1][1]
    assert final["learning_package"]["revisions"] == 1
    assert json.loads(calls[6][1]["content"])["review_feedback"] == feedback["issues"]
    assert json.loads(calls[7][1]["content"])["dependencies"] == {"explain": revised}
    assert [citation["chunk_id"] for citation in final["citations"]] == ["c2"]
    assert "old.md" not in final["answer"]
    for artifact in [final["learning_package"]["lesson"], *final["learning_package"]["exercises"]]:
        assert [citation["chunk_id"] for citation in artifact["citations"]] == ["c2"]


def test_repeated_quality_failure_never_delivers_draft(scripted):
    client, _, replies, calls = scripted
    reject = {"approved": False, "issues": ["回答缺少依据"]}
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, reject, LESSON, PRACTICE, reject])
    response = package(client)
    assert events(response)[-1][1]["error"] == "learning_package_quality_failed"
    assert LESSON["explanation"] not in response.text
    assert len(calls) == 9


@pytest.mark.parametrize("decision", [
    {"action": "delete_database", "query": "x"},
    {"action": "search_course", "query": "RAG", "course_id": "other"},
    {"action": "search_course", "query": ""},
])
def test_model_cannot_select_unknown_tools_or_override_scope(scripted, monkeypatch, decision):
    client, _, replies, _ = scripted
    replies.extend([PLAN, decision])
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: pytest.fail("must not execute tool"))
    assert events(package(client))[-1][1]["error"] == "learning_package_invalid_output"


def test_model_tool_search_is_scoped_to_authenticated_course(scripted, monkeypatch):
    client, _, replies, _ = scripted
    observed = []
    def retrieve(query, course):
        observed.append((query, course))
        return [{"source": "chapter.md", "chunk_id": "c1", "content": "课程证据"}]
    monkeypatch.setattr(learning_runs._runtime, "retrieve", retrieve)
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    assert events(package(client))[-1][0] == "run.completed"
    assert observed == [(SEARCH["query"], "artificial_intelligence")]


def test_repeated_tool_query_is_not_executed_twice(scripted):
    client, _, replies, _ = scripted
    replies.extend([PLAN, SEARCH, SEARCH, LESSON, PRACTICE, PASS])
    final = events(package(client))[-1][1]
    assert final["budget"]["tool_calls"] == 1
    assert final["tool_stop_reason"] == "repeated_search"


def test_tool_budget_stops_decision_loop(scripted):
    client, _, replies, _ = scripted
    replies.extend([PLAN, SEARCH, {**SEARCH, "query": "引用"}, {**SEARCH, "query": "检索排序"}, LESSON, PRACTICE, PASS])
    final = events(package(client))[-1][1]
    assert final["budget"]["tool_calls"] == 3
    assert final["tool_stop_reason"] == "tool_budget"


def test_empty_search_observation_can_trigger_new_query(scripted, monkeypatch):
    client, _, replies, calls = scripted
    retrieved = []
    def retrieve(query, course):
        retrieved.append(query)
        return [] if len(retrieved) == 1 else [{"source": "chapter.md", "chunk_id": "c1", "content": "有效证据"}]
    monkeypatch.setattr(learning_runs._runtime, "retrieve", retrieve)
    replies.extend([PLAN, SEARCH, {**SEARCH, "query": "检索增强生成"}, FINISH, LESSON, PRACTICE, PASS])
    final = events(package(client))[-1][1]
    assert final["budget"]["tool_calls"] == 2
    assert json.loads(calls[2][1]["content"])["observations"][0]["results"] == []


def test_no_evidence_cannot_finish(scripted):
    client, _, replies, _ = scripted
    replies.extend([PLAN, FINISH])
    assert events(package(client))[-1][1]["error"] == "learning_package_no_evidence"


def test_fabricated_source_is_rejected(scripted):
    client, _, replies, _ = scripted
    replies.extend([PLAN, SEARCH, FINISH, {**LESSON, "source_ids": ["made-up"]}])
    response = package(client)
    assert events(response)[-1][1]["error"] == "learning_package_invalid_citation"
    assert "answer.delta" not in response.text


def test_model_call_budget_is_enforced(scripted, monkeypatch):
    client, _, replies, calls = scripted
    monkeypatch.setattr(learning_runs._package_graph, "MAX_MODEL_CALLS", 2)
    replies.extend([PLAN, SEARCH])
    assert events(package(client))[-1][1]["error"] == "learning_package_budget_exceeded"
    assert len(calls) == 2


def test_input_budget_is_checked_before_model_call(scripted, monkeypatch):
    client, _, _, calls = scripted
    monkeypatch.setattr(learning_runs._package_graph, "MAX_INPUT_CHARS", 1)
    assert events(package(client))[-1][1]["error"] == "learning_package_budget_exceeded"
    assert calls == []


def test_package_requires_login_even_when_demo_mode_allows_answers(scripted, monkeypatch):
    client, _, _, calls = scripted
    monkeypatch.setenv("V2_AUTH_REQUIRED", "false")
    response = client.post("/api/v2/learning-runs/stream", json={"message": "RAG", "mode": "learning_package"})
    assert response.status_code == 401 and calls == []


def test_saved_conversation_and_profile_reach_planner(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    run_id = events(package(client))[-1][1]["run_id"]
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    final = events(package(client))[-1][1]
    assert final["memory_run_ids"] == [run_id]
    payload = json.loads(calls[6][1]["content"])
    assert LESSON["explanation"] in payload["history"][1]["content"]
    assert payload["profile"] == "已保存的学生画像"


def test_search_action_cannot_execute_unsupported_write(scripted, monkeypatch):
    client, _, replies, _ = scripted
    replies.extend([PLAN, {"action": "search_course", "query": "删除课程知识库"}])
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: pytest.fail("tool must be denied"))
    assert events(package(client))[-1][1]["error"] == "learning_package_tool_denied"


def test_package_review_resume_does_not_rerun_agents(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    response = package(client, review=True)
    assert events(response)[-1][0] == "review.required"
    assert LESSON["explanation"] not in response.text and "private-evidence" not in response.text
    run_id = events(response)[0][1]["run_id"]
    approved = client.post(f"/api/v2/learning-runs/{run_id}/resume",
        headers={"Authorization": "Bearer teacher"}, json={"approved": True})
    assert events(approved)[-1][1]["learning_package"]["lesson"] == {**LESSON, "citations": [CITATION]}
    assert len(calls) == 6


@pytest.mark.parametrize("approved", [True, False])
def test_human_replacement_or_rejection_does_not_deliver_stale_package(scripted, approved):
    client, _, replies, _ = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    run_id = events(package(client, review=True))[0][1]["run_id"]
    response = client.post(f"/api/v2/learning-runs/{run_id}/resume",
        headers={"Authorization": "Bearer teacher"}, json={"approved": approved, "edited_answer": "教师修改后的答案"})
    final = events(response)[-1][1]
    assert "learning_package" not in final
    assert LESSON["explanation"] not in response.text
    assert final["citations"] == []


@pytest.mark.parametrize("change", ["cycle", "unknown", "duplicate", "missing_role"])
def test_plan_dependency_contract_rejects_invalid_dag(change):
    plan = json.loads(json.dumps(PLAN))
    if change == "cycle":
        plan["steps"][0]["depends_on"] = ["practice"]
    elif change == "unknown":
        plan["steps"][1]["depends_on"] = ["unknown"]
    elif change == "duplicate":
        plan["steps"][1]["id"] = "explain"
    else:
        plan["steps"][1]["role"] = "tutor"
    with pytest.raises(ValueError):
        LearningPlan.model_validate(plan)


def test_completed_sse_can_be_graded_without_claiming_cloud_quality(scripted):
    from backend.app.evaluation.learning_package import PackageCase, summarise

    client, _, replies, _ = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    output = events(package(client))
    case = PackageCase("api-contract", "normal", "dev", "解释 RAG 并给我三道练习",
                       "artificial_intelligence", "completed", ("chapter.md",), "standard", ("核对答案",))
    prediction = {"id": case.id, "scenario": "standard", "events": [name for name, _ in output],
                  "result": output[-1][1]}
    report = summarise([case], {case.id: prediction})
    assert report["cases"][0]["contract_passed"], report["cases"][0]
    assert report["summary"]["learning_quality_pass_rate"] is None
    assert report["prediction_kind"] == "synthetic"
