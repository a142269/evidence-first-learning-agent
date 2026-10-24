"""QWEN-231: unified observations and the one-shot claim-support delivery check.

Every case is driven offline with a scripted structured-output stub; no model,
network or ``.env`` access is possible from this file.
"""
import json

import pytest
from pydantic import ValidationError

from backend.app.agent_runtime.observation import Observation, classify_failure, failure_observation
from backend.app.api.v2 import learning_runs
from backend.app.core.models import AgentCheckpointRecord
from tests.a.test_learning_package import (
    FINISH, LESSON, PASS, PLAN, PRACTICE, SEARCH, package, scripted as scripted,
)
from tests.a.test_learning_runs_v2_lifecycle import api as api, events

LONG_HIT = [{"chunk_id": "c1", "source": "chapter.md", "content":
             "检索增强生成（RAG）先检索课程材料，再依据检索证据组织回答，并明确标注引用来源，便于读者核对。"}]
UNRELATED_HIT = [{"chunk_id": "c1", "source": "chapter.md", "content":
                 "微积分与线性代数的矩阵分解、特征值计算、概率分布公式推导以及随机过程的极限定理证明，均为纯数学推导。"}]
REWORK = {"approved": False, "issues": ["修正题目"], "repair_target": "exercise"}


def observations(output, node):
    return [data for name, data in output
            if name == "observation.recorded" and data.get("node") == node]


def test_observation_schema_is_bounded_and_classifies_stable_errors():
    with pytest.raises(ValidationError):
        Observation(node="review", status="ok")
    with pytest.raises(ValidationError):
        Observation(node="review", status="success", evidence_strength=1.5)
    observation = Observation(node="review", status="failed", error_class="claim_support",
                              retryable=False, evidence_strength=0.0, citation_support=1.0,
                              detail={"unsupported_items": 2})
    assert observation.to_dict() == {
        "node": "review", "status": "failed", "error_class": "claim_support",
        "retryable": False, "evidence_strength": 0.0, "citation_support": 1.0,
        "detail": {"unsupported_items": 2},
    }
    assert classify_failure("learning_package_invalid_output") == ("schema", True)
    assert classify_failure("learning_package_tool_failed") == ("tool", True)
    assert classify_failure("learning_package_quality_failed") == ("quality", False)
    assert failure_observation("tool", "unknown_code").error_class == "runtime"


def test_claim_support_pass_is_observed_and_delivered(scripted, monkeypatch):
    client, _, replies, calls = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: LONG_HIT)
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    output = events(package(client))
    final = output[-1][1]
    assert output[-1][0] == "run.completed", final
    assert final["quality"]["claim_support"]["passed"] is True
    assert final["quality"]["claim_support"]["checked"] is True
    assert final["quality"]["claim_support"]["evidence_strength"] == 1.0
    assert final["quality"]["claim_support"]["citation_support"] == 1.0
    checks = observations(output, "claim_check")
    assert len(checks) == 1
    assert checks[0]["status"] == "success" and checks[0]["error_class"] is None
    assert checks[0]["retryable"] is False
    assert checks[0]["evidence_strength"] == 1.0
    assert checks[0]["detail"]["unsupported_items"] == 0
    # Retrieval is projected into the same schema without replacing its old payload.
    assert observations(output, "tool")[0]["status"] == "success"
    assert len(calls) == 6


def test_unsupported_long_evidence_blocks_delivery_and_is_checkpointed(scripted, monkeypatch):
    client, factory, replies, calls = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: UNRELATED_HIT)
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    response = package(client)
    output = events(response)
    assert output[-1][0] == "run.failed", response.text
    assert output[-1][1]["error"] == "learning_package_quality_failed"
    assert "answer.delta" not in response.text
    assert LESSON["explanation"] not in response.text
    assert len(calls) == 6
    checks = observations(output, "claim_check")
    assert len(checks) == 1
    assert checks[0]["status"] == "failed" and checks[0]["error_class"] == "claim_support"
    assert checks[0]["retryable"] is False
    assert checks[0]["evidence_strength"] == 0.0
    assert checks[0]["detail"]["unsupported_items"] == 4
    run_id = output[0][1]["run_id"]
    with factory() as db:
        rows = db.query(AgentCheckpointRecord).filter_by(
            run_id=run_id, status="observation.recorded", node_name="claim_check").all()
    assert len(rows) == 1
    assert rows[0].state_data["error_class"] == "claim_support"


def test_invalid_citation_is_observed_as_a_citation_failure(scripted, monkeypatch):
    client, _, replies, _ = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: LONG_HIT)
    replies.extend([PLAN, SEARCH, FINISH, {**LESSON, "source_ids": ["made-up"]}])
    output = events(package(client))
    assert output[-1][0] == "run.failed"
    assert output[-1][1]["error"] == "learning_package_invalid_citation"
    failures = observations(output, "tutor")
    assert len(failures) == 1
    assert failures[0]["error_class"] == "citation" and failures[0]["retryable"] is False


def test_existing_reviewer_rework_delivers_after_one_support_check(scripted, monkeypatch):
    client, _, replies, calls = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: LONG_HIT)
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, REWORK, PRACTICE, PASS])
    output = events(package(client))
    final = output[-1][1]
    assert output[-1][0] == "run.completed", final
    assert final["learning_package"]["revisions"] == 1
    assert final["quality"]["claim_support"]["passed"] is True
    assert len(observations(output, "claim_check")) == 1
    assert len(calls) == 8


def test_claim_check_never_calls_a_model_after_a_support_failure(scripted, monkeypatch):
    client, _, replies, calls = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: UNRELATED_HIT)
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    output = events(package(client))
    assert output[-1][1]["error"] == "learning_package_quality_failed"
    # The rule check itself adds no provider call; the failed run stops there.
    assert len(calls) == 6
    assert len(observations(output, "claim_check")) == 1


def test_observation_is_added_to_the_checkpoint_without_breaking_events(scripted, monkeypatch):
    client, factory, replies, _ = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: LONG_HIT)
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    output = events(package(client))
    names = [name for name, _ in output]
    assert "node.started" in names and "node.completed" in names
    assert "observation.recorded" in names
    run_id = output[0][1]["run_id"]
    with factory() as db:
        rows = db.query(AgentCheckpointRecord).filter_by(
            run_id=run_id, status="observation.recorded", node_name="claim_check").all()
    assert len(rows) == 1
    assert rows[0].state_data["status"] == "success"


def test_human_replacement_clears_model_claim_support_and_observations(scripted, monkeypatch):
    client, _, replies, _ = scripted
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: LONG_HIT)
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    pending = package(client, review=True)
    assert events(pending)[-1][0] == "review.required"
    run_id = events(pending)[0][1]["run_id"]
    approved = client.post(f"/api/v2/learning-runs/{run_id}/resume",
                           headers={"Authorization": "Bearer teacher"},
                           json={"approved": True, "edited_answer": "教师修改后的答案"})
    final = events(approved)[-1][1]
    assert "learning_package" not in final
    assert final["quality"]["claim_support"] == {}
    assert final["quality"]["delivery_observations"] == []


def test_observation_projection_rejects_invalid_metrics():
    with pytest.raises(ValidationError):
        Observation(node="tool", status="partial", citation_support=-0.1)


def test_observation_projection_is_json_serialisable():
    payload = Observation(node="tool", status="skipped").to_dict()
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload
