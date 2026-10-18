"""Regression tests for the ``partially_completed`` delivery chain.

A partial delivery may only be produced by an explicit Reviewer verdict: either
``dropped_exercises`` for exercises that were generated but rejected, or
``lesson_approved=true / practice_approved=false`` when the practice part is
unavailable or stays rejected after its single bounded repair.  Everything else
must keep failing closed, and no unreviewed model text may be persisted,
streamed or recalled from memory.
"""
import json

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from backend.app.agent_runtime import run_audit
from backend.app.agent_runtime.learning_package import QualityReview
from backend.app.api.v2 import learning_runs
from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord
from tests.a.test_learning_package import (
    CITATION, FINISH, LESSON, PASS, PLAN, PRACTICE, SEARCH,
    package, scripted as scripted,
)
from tests.a.test_learning_runs_v2_lifecycle import api as api, events

ALICE = {"Authorization": "Bearer alice"}
TEACHER = {"Authorization": "Bearer teacher"}
MESSAGE = "解释 RAG 并给我三道练习"

# Distinct exercise texts so an assertion that withheld content is absent can
# never accidentally match a kept exercise that was only renumbered.
PARTIAL_PRACTICE = {"exercises": [
    {"question": "练习甲：为什么需要先检索？", "answer": "为了获得课程证据",
     "explanation": "检索先定位资料，回答再引用证据。", "source_ids": ["c1"]},
    {"question": "练习乙：检索结果应当如何排序？", "answer": "按相关性排序",
     "explanation": "排序帮助选出与问题最相关的片段。", "source_ids": ["c1"]},
    {"question": "练习丙：答案如何标注来源？", "answer": "引用 chunk_id",
     "explanation": "标注来源便于读者核对答案。", "source_ids": ["c1"]},
]}
WITHHELD_QUESTION = PARTIAL_PRACTICE["exercises"][1]["question"]

# Two invalid Practice replies: a one-exercise list violates the 3-exercise
# contract, so the schema retry is exhausted and practice generation degrades.
INVALID_PRACTICE = {"exercises": [{
    "question": "未通过校验的练习文本：检索是什么？", "answer": "提供资料依据",
    "explanation": "检索提供可追溯的课程资料。", "source_ids": ["c1"],
}]}
INVALID_PRACTICE_TEXT = INVALID_PRACTICE["exercises"][0]["question"]

LESSON_ONLY = {"approved": False, "issues": [], "lesson_approved": True, "practice_approved": False}
PRACTICE_REWORK = {"approved": False, "issues": ["修正题目"], "repair_target": "exercise",
                   "lesson_approved": True, "practice_approved": False}
PRACTICE_STILL_REJECTED = {"approved": False, "issues": ["仍未通过"], "repair_target": "exercise",
                           "lesson_approved": True, "practice_approved": False}
LESSON_REJECT = {"approved": False, "issues": ["讲解存在事实错误"], "repair_target": "lesson"}


def partial_pass(*dropped):
    """An all-approved verdict that withholds the given 1-based exercise numbers."""
    return {**PASS, "dropped_exercises": list(dropped)}


def fail_next_finish(monkeypatch, status):
    """Fail the first persisted finish for ``status`` (same as reconciliation tests)."""
    original = run_audit.finish_run
    failures = []

    def write(**kwargs):
        if kwargs["status"] == status and not failures:
            failures.append(status)
            raise run_audit.RunPersistenceError("injected_result_write_failure")
        return original(**kwargs)

    monkeypatch.setattr(run_audit, "finish_run", write)
    return failures


def forbid_execution(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("reconciliation must not invoke model or retrieval")
    monkeypatch.setattr(learning_runs._runtime, "retrieve", forbidden)
    monkeypatch.setattr(learning_runs._runtime, "generate", forbidden)
    monkeypatch.setattr(learning_runs._runtime, "complete_structured", forbidden)


def expected_exercises(*indexes):
    return [{**PARTIAL_PRACTICE["exercises"][index], "citations": [CITATION]} for index in indexes]


def stream_in_session(client, session_id, *, review=False):
    return client.post("/api/v2/learning-runs/stream", headers=ALICE,
                       json={"message": MESSAGE, "mode": "learning_package",
                             "session_id": session_id, "require_approval": review})


# 1. Reviewer drops one exercise: review the rest as a partial delivery.
def test_reviewer_dropped_exercise_delivers_partial_package(scripted):
    client, factory, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, partial_pass(2)])
    response = package(client)
    transcript = events(response)
    final = transcript[-1][1]
    assert transcript[-1][0] == "run.completed", response.text
    assert final["status"] == "partially_completed"
    assert final["learning_package"]["lesson"] == {**LESSON, "citations": [CITATION]}
    assert final["learning_package"]["exercises"] == expected_exercises(0, 2)
    assert final["learning_package"]["revisions"] == 0
    assert final["partial_completion"] == {
        "status": "partially_completed", "delivered_parts": ["lesson", "practice"],
        "withheld_parts": [], "withheld_exercise_numbers": [2],
        "reason": "exercise_not_approved",
    }
    assert final["quality"]["partial_completion"] is True
    assert final["quality"]["delivered_parts"] == ["lesson", "practice"]
    assert final["quality"]["reviewer_passed"] is True
    assert "原第 2 题未通过内容检查，未交付" in final["answer"]
    assert WITHHELD_QUESTION not in response.text
    assert len(calls) == 6 and final["budget"]["model_calls"] == 6

    run_id = final["run_id"]
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == final["status"]
    sse_result = {key: value for key, value in final.items()
                  if key not in {"run_id", "event_sequence", "status"}}
    assert saved["result"] == sse_result
    assert WITHHELD_QUESTION not in json.dumps(saved, ensure_ascii=False)

    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "partially_completed"
        # Partial delivery is never counted as success; both kept artifacts exist.
        assert row.success_count == 0 and row.artifact_count == 2
        metadata = json.dumps(row.metadata_data, ensure_ascii=False)
        assert WITHHELD_QUESTION not in metadata
        assert row.metadata_data["result"] == saved["result"]
        terminal = db.scalars(select(AgentCheckpointRecord).where(
            AgentCheckpointRecord.run_id == run_id,
            AgentCheckpointRecord.status == "run.completed",
        )).all()
        assert len(terminal) == 1
        assert terminal[0].state_data == {"status": "partially_completed"}


# 2. Practice generation fails twice; the reviewed lesson is still delivered.
def test_practice_generation_failure_delivers_reviewed_lesson_only(scripted):
    client, factory, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, INVALID_PRACTICE, INVALID_PRACTICE, LESSON_ONLY])
    response = package(client)
    transcript = events(response)
    final = transcript[-1][1]
    assert transcript[-1][0] == "run.completed", response.text
    assert final["status"] == "partially_completed"
    assert final["learning_package"]["lesson"] == {**LESSON, "citations": [CITATION]}
    assert final["learning_package"]["exercises"] == []
    assert final["learning_package"]["revisions"] == 0
    assert final["partial_completion"] == {
        "status": "partially_completed", "delivered_parts": ["lesson"],
        "withheld_parts": ["practice"], "withheld_exercise_numbers": [],
        "reason": "practice_unavailable",
    }
    assert final["quality"]["partial_completion"] is True
    assert final["quality"]["delivered_parts"] == ["lesson"]
    # A withheld practice part is not a full review pass.
    assert final["quality"]["reviewer_passed"] is False
    assert "练习题未通过内容检查" in final["answer"]
    assert final["learning_package"]["review"]["practice_approved"] is False
    assert INVALID_PRACTICE_TEXT not in response.text
    assert len(calls) == 7 and final["budget"]["model_calls"] == 7

    run_id = final["run_id"]
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "partially_completed"
    assert saved["result"]["learning_package"] == final["learning_package"]
    assert saved["result"]["partial_completion"] == final["partial_completion"]
    assert INVALID_PRACTICE_TEXT not in json.dumps(saved, ensure_ascii=False)
    with factory() as db:
        metadata = json.dumps(db.get(AgentRunRecord, run_id).metadata_data, ensure_ascii=False)
    assert INVALID_PRACTICE_TEXT not in metadata


# 3. Practice part gets exactly one bounded rework, then the run delivers the
# reviewed lesson only.
def test_practice_rejected_after_one_repair_delivers_lesson_only(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE,
                    PRACTICE_REWORK, PRACTICE, PRACTICE_STILL_REJECTED])
    response = package(client)
    transcript = events(response)
    final = transcript[-1][1]
    assert transcript[-1][0] == "run.completed", response.text
    assert final["status"] == "partially_completed"
    assert final["learning_package"]["revisions"] == 1
    assert final["learning_package"]["exercises"] == []
    assert final["partial_completion"]["withheld_parts"] == ["practice"]
    assert final["partial_completion"]["reason"] == "practice_not_approved"
    assert final["quality"]["reviewer_passed"] is False
    assert len(calls) == 8 and final["budget"]["model_calls"] == 8

    # Exactly one Practice rework: two Practice payloads, both bound to the same
    # reviewed lesson, and only the rework carries the Reviewer feedback.
    payloads = [json.loads(call[1]["content"]) for call in calls]
    practice_payloads = [payload for payload in payloads if "dependencies" in payload]
    assert len(practice_payloads) == 2
    assert all(payload["dependencies"] == {"explain": LESSON} for payload in practice_payloads)
    assert practice_payloads[0]["review_feedback"] == []
    assert practice_payloads[1]["review_feedback"] == PRACTICE_REWORK["issues"]


# 4. A lesson rejection without an explicit part verdict still fails closed.
def test_lesson_rejected_twice_still_fails_closed(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE,
                    LESSON_REJECT, LESSON, PRACTICE, LESSON_REJECT])
    response = package(client)
    transcript = events(response)
    assert transcript[-1][0] == "run.failed", response.text
    assert transcript[-1][1]["error"] == "learning_package_quality_failed"
    assert "answer.delta" not in response.text
    assert LESSON["explanation"] not in response.text
    assert len(calls) == 9

    run_id = transcript[0][1]["run_id"]
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "failed"
    assert saved["result"]["error"] == "learning_package_quality_failed"
    assert "partial_completion" not in saved["result"]


# 5. The Reviewer cannot approve an artifact that was never generated.
def test_reviewer_cannot_approve_practice_never_generated(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, INVALID_PRACTICE, INVALID_PRACTICE, PASS])
    response = package(client)
    transcript = events(response)
    assert transcript[-1][0] == "run.failed", response.text
    assert transcript[-1][1]["error"] == "learning_package_quality_failed"
    assert "answer.delta" not in response.text
    assert LESSON["explanation"] not in response.text
    assert len(calls) == 7

    run_id = transcript[0][1]["run_id"]
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "failed"
    assert saved["result"]["error"] == "learning_package_quality_failed"
    assert "learning_package" not in saved["result"]
    assert "partial_completion" not in saved["result"]


# 6a. Teacher review of a dropped-exercise partial delivery, then approval.
def test_teacher_review_of_partial_package_then_approves(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, partial_pass(3)])
    response = package(client, review=True)
    transcript = events(response)
    assert transcript[-1][0] == "review.required", response.text
    run_id = transcript[0][1]["run_id"]
    path = f"/api/v2/learning-runs/{run_id}"

    student = client.get(path, headers=ALICE)
    assert student.json()["result"] == {"review_required": True}
    assert LESSON["explanation"] not in student.text
    assert PARTIAL_PRACTICE["exercises"][2]["question"] not in student.text

    teacher = client.get(path, headers=TEACHER)
    approval = teacher.json()["result"]["approval"]
    assert approval["action"] == "review_learning_answer"
    assert approval["partial_completion"] == {
        "status": "partially_completed", "delivered_parts": ["lesson", "practice"],
        "withheld_parts": [], "withheld_exercise_numbers": [3],
        "reason": "exercise_not_approved",
    }
    approval_text = json.dumps(approval, ensure_ascii=False)
    assert PARTIAL_PRACTICE["exercises"][2]["question"] not in approval_text
    assert PARTIAL_PRACTICE["exercises"][0]["question"] in approval["draft_answer"]

    resumed = client.post(f"{path}/resume", headers=TEACHER, json={"approved": True})
    final = events(resumed)[-1][1]
    assert final["status"] == "partially_completed"
    assert final["review"] == {"approved": True}
    assert final["learning_package"]["exercises"] == expected_exercises(0, 1)
    assert final["partial_completion"]["withheld_exercise_numbers"] == [3]
    assert len(calls) == 6  # human review never reruns the agents


# 6b. Teacher rejects the reviewed partial package: nothing is delivered.
def test_teacher_rejection_of_partial_package_delivers_nothing(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, partial_pass(3)])
    transcript = events(package(client, review=True))
    assert transcript[-1][0] == "review.required"
    run_id = transcript[0][1]["run_id"]

    rejected = client.post(f"/api/v2/learning-runs/{run_id}/resume",
                           headers=TEACHER, json={"approved": False})
    transcript = events(rejected)
    final = transcript[-1][1]
    assert transcript[-1][0] == "run.completed", rejected.text
    assert final["status"] == "rejected"
    assert final["citations"] == [] and final["evidence"] == []
    assert "learning_package" not in final
    assert "partial_completion" not in final
    assert final["answer"] == "该学习内容未通过人工审核，系统未交付待审内容。"
    assert LESSON["explanation"] not in rejected.text
    assert PARTIAL_PRACTICE["exercises"][2]["question"] not in rejected.text
    assert len(calls) == 6

    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "rejected"
    assert saved["result"]["citations"] == saved["result"]["evidence"] == []
    assert "learning_package" not in saved["result"]


# 7. A lesson-only partial delivery also waits for teacher review when required.
def test_lesson_only_partial_requires_teacher_review_then_approves(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, INVALID_PRACTICE, INVALID_PRACTICE, LESSON_ONLY])
    response = package(client, review=True)
    transcript = events(response)
    assert transcript[-1][0] == "review.required", response.text
    run_id = transcript[0][1]["run_id"]
    path = f"/api/v2/learning-runs/{run_id}"

    student = client.get(path, headers=ALICE)
    assert student.json()["result"] == {"review_required": True}
    assert LESSON["explanation"] not in student.text

    approval = client.get(path, headers=TEACHER).json()["result"]["approval"]
    assert approval["partial_completion"]["withheld_parts"] == ["practice"]
    assert approval["partial_completion"]["reason"] == "practice_unavailable"

    final = events(client.post(f"{path}/resume", headers=TEACHER,
                               json={"approved": True}))[-1][1]
    assert final["status"] == "partially_completed"
    assert final["learning_package"]["exercises"] == []
    assert final["partial_completion"]["withheld_parts"] == ["practice"]
    assert final["quality"]["reviewer_passed"] is False
    assert INVALID_PRACTICE_TEXT not in response.text
    assert len(calls) == 7


# 8. A failed result write after a settled partial delivery is repairable from
# the checkpoint without any model or retrieval call.
def test_failed_partial_result_write_recovers_via_reconcile(scripted, monkeypatch):
    client, factory, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, partial_pass(1)])
    failures = fail_next_finish(monkeypatch, "partially_completed")
    transcript = events(package(client))
    assert failures == ["partially_completed"]
    assert transcript[-1][0] == "run.failed", transcript
    run_id = transcript[0][1]["run_id"]
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "failed"

    forbid_execution(monkeypatch)
    settled = client.portal.call(learning_runs._package_graph.settled_checkpoint, run_id)
    repaired = client.post(f"/api/v2/learning-runs/{run_id}/reconcile", headers=TEACHER)
    assert repaired.status_code == 200, repaired.text
    body = repaired.json()
    assert body["status"] == "partially_completed"
    result = body["result"]
    # The published result is exactly the settled checkpoint result.
    assert result["answer"] == settled["answer"]
    assert result["learning_package"] == settled["learning_package"]
    assert result["partial_completion"] == settled["partial_completion"]
    assert result["citations"] == settled["citations"]
    assert result["quality"] == settled["quality"]
    assert result["partial_completion"]["withheld_exercise_numbers"] == [1]
    assert len(calls) == 6  # reconciliation used no model call

    assert client.post(f"/api/v2/learning-runs/{run_id}/reconcile",
                       headers=TEACHER).status_code == 409
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "partially_completed" and row.success_count == 0
        assert row.artifact_count == 2
        assert row.metadata_data["result"] == result
        reconciled = db.scalars(select(AgentCheckpointRecord).where(
            AgentCheckpointRecord.run_id == run_id,
            AgentCheckpointRecord.status == "run.reconciled",
        )).all()
        assert len(reconciled) == 1
        assert reconciled[0].state_data == {
            "from_status": "failed", "to_status": "partially_completed"}


# 9a. A partial run is owner-only and course-scoped.
def test_partial_run_isolation_and_course_scope(scripted, monkeypatch):
    client, _, replies, _ = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, partial_pass(2)])
    final = events(package(client))[-1][1]
    assert final["status"] == "partially_completed"
    run_id = final["run_id"]
    path = f"/api/v2/learning-runs/{run_id}"

    assert client.get(path, headers={"Authorization": "Bearer bob"}).status_code == 403
    teacher = client.get(path, headers=TEACHER)
    assert teacher.status_code == 200 and teacher.json()["status"] == "partially_completed"
    assert client.get(path, headers=ALICE).status_code == 200

    bob_events = client.get(f"{path}/events", headers={"Authorization": "Bearer bob"})
    assert bob_events.status_code == 403
    owner_events = client.get(f"{path}/events", headers=ALICE)
    assert owner_events.status_code == 200 and owner_events.json()["events"]
    event_text = json.dumps(owner_events.json(), ensure_ascii=False)
    assert LESSON["explanation"] not in event_text
    assert WITHHELD_QUESTION not in event_text

    monkeypatch.setenv("V2_STUDENT_COURSES", "another_course")
    denied = client.get(path, headers=ALICE)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "course_access_denied"
    monkeypatch.setenv("V2_STUDENT_COURSES", "artificial_intelligence")
    assert client.get(path, headers=ALICE).status_code == 200


# 9b. Only fully completed runs may be recalled as conversation memory.
def test_partial_run_excluded_from_conversation_memory(scripted):
    client, _, replies, _ = scripted

    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, partial_pass(2)])
    partial = events(stream_in_session(client, "partial-memory"))[-1][1]
    assert partial["status"] == "partially_completed"

    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    after_partial = events(stream_in_session(client, "partial-memory"))[-1][1]
    assert after_partial["status"] == "completed"
    assert after_partial["memory_run_ids"] == []

    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    completed = events(stream_in_session(client, "completed-memory"))[-1][1]
    assert completed["status"] == "completed" and completed["memory_run_ids"] == []

    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    after_completed = events(stream_in_session(client, "completed-memory"))[-1][1]
    assert after_completed["memory_run_ids"] == [completed["run_id"]]


# 10. QualityReview contract units: an ambiguous verdict can never authorize a
# partial delivery.
@pytest.mark.parametrize("verdict", [
    {"approved": True, "issues": ["仍有问题"]},
    {"approved": True, "issues": [], "lesson_approved": False},
    {"approved": False, "issues": []},
    {"approved": False, "issues": [], "lesson_approved": True, "practice_approved": False,
     "dropped_exercises": [2]},
    {"approved": True, "issues": [], "dropped_exercises": [3, 2]},
    {"approved": True, "issues": [], "dropped_exercises": [4]},
], ids=["approved-with-issues", "approved-with-rejected-lesson", "implicit-rejection-without-issues",
        "drops-with-rejected-practice", "unsorted-drops", "out-of-range-drop"])
def test_quality_review_rejects_inconsistent_verdicts(verdict):
    with pytest.raises(ValidationError):
        QualityReview.model_validate(verdict)


@pytest.mark.parametrize("verdict", [
    {"approved": False, "issues": [], "lesson_approved": True, "practice_approved": False},
    {"approved": True, "issues": [], "dropped_exercises": [2]},
], ids=["explicit-lesson-only-partial", "approved-with-dropped-exercise"])
def test_quality_review_accepts_explicit_partial_verdicts(verdict):
    review = QualityReview.model_validate(verdict)
    assert review.explicit_partial is True
    assert review.lesson_ok is True


# 11. Idempotent replay of a partial run must not execute the workflow again.
def test_partial_run_idempotent_replay_returns_same_result(scripted):
    client, _, replies, calls = scripted
    idem = "partial-idempotency-test-0001"

    def send():
        return client.post("/api/v2/learning-runs/stream",
                           headers={**ALICE, "Idempotency-Key": idem},
                           json={"message": MESSAGE, "mode": "learning_package",
                                 "session_id": "partial-idempotent"})

    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, partial_pass(2)])
    first = events(send())
    assert first[-1][0] == "run.completed"
    assert first[-1][1]["status"] == "partially_completed"
    run_id = first[-1][1]["run_id"]
    assert len(calls) == 6

    replay = events(send())
    assert [name for name, _ in replay] == ["run.started", "run.completed"]
    assert replay[0][1]["idempotent_replay"] is True
    final = replay[-1][1]
    assert final["run_id"] == run_id
    assert final["status"] == "partially_completed"
    assert final["partial_completion"]["withheld_exercise_numbers"] == [2]
    assert final["learning_package"] == first[-1][1]["learning_package"]
    assert len(calls) == 6  # replay performed no extra model call


# 12. A failed practice rework must not leave the superseded practice batch in
# state as if it were current: a later Reviewer PASS cannot deliver stale text.
def test_failed_practice_rework_cannot_deliver_stale_exercises(scripted):
    client, _, replies, calls = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PARTIAL_PRACTICE, PRACTICE_REWORK,
                    INVALID_PRACTICE, INVALID_PRACTICE, PASS])
    response = package(client)
    transcript = events(response)
    final = transcript[-1][1]
    assert transcript[-1][0] == "run.failed", response.text
    assert final["error"] == "learning_package_quality_failed"
    assert "answer.delta" not in [name for name, _ in transcript]
    # The first, rejected exercise batch is never delivered as a fresh approval.
    for exercise in PARTIAL_PRACTICE["exercises"]:
        assert exercise["question"] not in response.text
    assert INVALID_PRACTICE_TEXT not in response.text


# 13. Reviewer issue text may quote withheld content; the delivered partial
# package must not carry that text, and the audit-only reviewer verdict stays
# internal.
def test_partial_delivery_does_not_embed_withheld_reviewer_issue_text(scripted):
    client, factory, replies, _ = scripted
    leaky_verdict = {"approved": False, "issues": [f"题目「{INVALID_PRACTICE_TEXT}」答案错误"],
                     "suggested_query": f"请补充检索：{INVALID_PRACTICE_TEXT}",
                     "lesson_approved": True, "practice_approved": False}
    replies.extend([PLAN, SEARCH, FINISH, LESSON, INVALID_PRACTICE, INVALID_PRACTICE, leaky_verdict])
    response = package(client)
    transcript = events(response)
    final = transcript[-1][1]
    assert transcript[-1][0] == "run.completed", response.text
    assert final["status"] == "partially_completed"
    assert final["learning_package"]["review"]["issues"] == []
    assert final["learning_package"]["review"]["suggested_query"] == ""
    assert final["learning_package"]["review"]["withheld_issue_count"] == 1
    assert final["learning_package"]["review"]["withheld_suggested_query"] is True
    assert final["learning_package"]["review"]["practice_approved"] is False
    assert INVALID_PRACTICE_TEXT not in response.text

    saved = client.get(f"/api/v2/learning-runs/{final['run_id']}", headers=ALICE).json()
    assert INVALID_PRACTICE_TEXT not in json.dumps(saved, ensure_ascii=False)
    with factory() as db:
        metadata = json.dumps(db.get(AgentRunRecord, final["run_id"]).metadata_data, ensure_ascii=False)
    assert INVALID_PRACTICE_TEXT not in metadata

