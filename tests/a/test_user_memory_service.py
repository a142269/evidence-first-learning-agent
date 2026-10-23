"""QWEN-201: only a human-confirmed proposal from a fully completed run becomes memory."""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.core import models  # noqa: F401  (registers every table on Base)
from backend.app.core.database import Base
from backend.app.core.models import AgentRunRecord, MemoryEventRecord, UserMemoryRecord
from backend.app.services import user_memory as memory

TEACHER = {"actor": "teacher-1", "actor_role": "teacher"}
LEARNER = {"actor": "learner-9", "actor_role": "student"}


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'memory.db').as_posix()}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def add_run(factory, run_id, status):
    with factory() as session:
        session.add(AgentRunRecord(id=run_id, status=status, user_id="learner-9"))
        session.commit()


def counts(factory):
    with factory() as session:
        return (session.scalar(select(func.count()).select_from(UserMemoryRecord)),
                session.scalar(select(func.count()).select_from(MemoryEventRecord)))


def proposal(**overrides):
    values = {"user_id": "learner-9", "kind": "weak_point",
              "content": "分数除法还需要复习", "source_type": "rule_extraction"}
    values.update(overrides)
    return memory.propose(**values)


def test_propose_touches_no_table():
    """A model proposal is only a dict; the DoD pins that nothing is persisted."""
    drafted = proposal(source_run_id="run-1", confidence=0.8)
    assert drafted["persisted"] is False and drafted["record"] == "proposed"
    assert drafted["content"] == "分数除法还需要复习"


def test_unconfirmed_proposal_is_never_readable(db):
    add_run(db, "run-1", "completed")
    memory.propose(user_id="learner-9", kind="weak_point", content="未确认",
                   source_run_id="run-1")
    assert memory.active_memories(db, "learner-9") == []
    assert counts(db) == (0, 0)


def test_confirm_persists_the_proposal_and_one_audit_event(db):
    add_run(db, "run-1", "completed")
    saved = memory.confirm(db, proposal(source_run_id="run-1", confidence=0.75), **TEACHER)
    assert saved["persisted"] is True and saved["status"] == "active"
    assert saved["source_run_id"] == "run-1" and saved["confidence"] == 0.75
    assert saved["expires_at"] is None and saved["expired"] is False
    assert [item["memory_id"] for item in memory.active_memories(db, "learner-9")] == [saved["memory_id"]]
    assert [event["action"] for event in memory.memory_audit(db, saved["memory_id"])] == ["confirmed"]
    assert counts(db) == (1, 1)


@pytest.mark.parametrize("status", ["partially_completed", "failed", "awaiting_approval",
                                    "reviewing", "interrupted", "rejected", "running"])
def test_partial_or_failed_run_never_becomes_memory(db, status):
    add_run(db, "run-bad", status)
    with pytest.raises(memory.MemoryPolicyViolation) as caught:
        memory.confirm(db, proposal(source_run_id="run-bad"), **TEACHER)
    assert str(caught.value) == "source_run_not_completed"
    assert counts(db) == (0, 0)


def test_completed_run_is_the_only_eligible_source(db):
    add_run(db, "run-ok", "completed")
    assert memory.confirm(db, proposal(source_run_id="run-ok"), **LEARNER)["status"] == "active"


def test_a_missing_source_run_is_refused(db):
    with pytest.raises(memory.MemoryPolicyViolation) as caught:
        memory.confirm(db, proposal(source_run_id="run-ghost"), **TEACHER)
    assert str(caught.value) == "source_run_not_found"
    assert counts(db) == (0, 0)


def test_a_memory_without_a_run_source_still_needs_a_human(db):
    """Rule extraction aside, a learner statement is allowed — but never self-confirmed."""
    drafted = proposal(source_type="user_input")
    with pytest.raises(memory.MemoryPolicyViolation):
        memory.confirm(db, drafted, actor="learner-9", actor_role="agent")
    assert counts(db) == (0, 0)
    assert memory.confirm(db, drafted, **LEARNER)["source_run_id"] is None


@pytest.mark.parametrize("role", ["agent", "system", "anonymous", "", None])
def test_confirm_requires_a_human_actor(db, role):
    with pytest.raises(memory.MemoryPolicyViolation) as caught:
        memory.confirm(db, proposal(), actor="someone", actor_role=role)
    assert str(caught.value) == "confirmation_requires_human_actor"
    assert counts(db) == (0, 0)


def test_an_empty_actor_is_not_an_actor(db):
    with pytest.raises(memory.MemoryPolicyViolation) as caught:
        memory.confirm(db, proposal(), actor="   ", actor_role="teacher")
    assert str(caught.value) == "actor_required"


def test_confirm_refuses_anything_that_is_not_a_proposal(db):
    for impostor in [{}, {"record": "active"}, None, "proposal"]:
        with pytest.raises(memory.MemoryPolicyViolation) as caught:
            memory.confirm(db, impostor, **TEACHER)
        assert str(caught.value) == "confirmation_requires_a_proposal"


def test_same_user_and_kind_supersedes_the_previous_active_row(db):
    first = memory.confirm(db, proposal(content="旧判断"), **TEACHER)
    second = memory.confirm(db, proposal(content="新判断"), **LEARNER)

    readable = memory.active_memories(db, "learner-9")
    assert [item["memory_id"] for item in readable] == [second["memory_id"]]
    assert readable[0]["content"] == "新判断"
    with db() as session:
        retired = session.get(UserMemoryRecord, first["memory_id"])
    assert retired.status == "revoked" and retired.content == "旧判断"
    assert [event["action"] for event in memory.memory_audit(db, first["memory_id"])] == [
        "confirmed", "superseded"]
    assert memory.memory_audit(db, first["memory_id"])[1]["actor"] == "learner-9"
    assert memory.memory_audit(db, second["memory_id"])[0]["reason"] == "role:student"
    # The retired row stays for the audit trail, so only one of the two is readable.
    assert counts(db) == (2, 3)


def test_a_different_kind_for_the_same_user_coexists(db):
    memory.confirm(db, proposal(kind="weak_point"), **TEACHER)
    memory.confirm(db, proposal(kind="pace_preference", content="喜欢短课程"), **TEACHER)
    assert {item["kind"] for item in memory.active_memories(db, "learner-9")} == {
        "weak_point", "pace_preference"}
    assert memory.active_memories(db, "learner-9", kind="weak_point")[0]["kind"] == "weak_point"


def test_another_user_cannot_read_or_shadow_it(db):
    memory.confirm(db, proposal(user_id="learner-9"), **TEACHER)
    memory.confirm(db, proposal(user_id="learner-10"), **LEARNER)
    assert len(memory.active_memories(db, "learner-9")) == 1
    assert len(memory.active_memories(db, "learner-10")) == 1


def test_revoked_memory_is_unreadable_but_keeps_its_audit(db):
    saved = memory.confirm(db, proposal(), **TEACHER)
    retired = memory.revoke(db, saved["memory_id"], reason="学生否认", **LEARNER)
    assert retired["status"] == "revoked" and retired["changed"] is True
    assert memory.active_memories(db, "learner-9") == []
    assert [event["action"] for event in memory.memory_audit(db, saved["memory_id"])] == [
        "confirmed", "revoked"]
    assert memory.memory_audit(db, saved["memory_id"])[1]["reason"] == "学生否认"


def test_replaying_a_revoke_does_not_inflate_the_audit(db):
    saved = memory.confirm(db, proposal(), **TEACHER)
    memory.revoke(db, saved["memory_id"], **TEACHER)
    again = memory.revoke(db, saved["memory_id"], **TEACHER)
    assert again["changed"] is False
    assert [event["action"] for event in memory.memory_audit(db, saved["memory_id"])] == [
        "confirmed", "revoked"]


@pytest.mark.parametrize("role", ["agent", "system", None])
def test_revocation_also_needs_a_human_actor(db, role):
    saved = memory.confirm(db, proposal(), **TEACHER)
    with pytest.raises(memory.MemoryPolicyViolation) as caught:
        memory.revoke(db, saved["memory_id"], actor="bot", actor_role=role)
    assert str(caught.value) == "revocation_requires_human_actor"
    assert memory.active_memories(db, "learner-9") != []


def test_revoking_an_unknown_memory_is_refused(db):
    with pytest.raises(memory.MemoryPolicyViolation) as caught:
        memory.revoke(db, "no-such-memory", **TEACHER)
    assert str(caught.value) == "memory_not_found"


def test_expired_memory_is_not_read_but_the_row_stays(db):
    saved = memory.confirm(db, proposal(ttl_seconds=60), **TEACHER)
    assert memory.active_memories(db, "learner-9", now=saved["expires_at"] - 1) != []
    assert memory.active_memories(db, "learner-9", now=saved["expires_at"]) == []
    assert saved["expires_at"] > saved["created_at"]
    with db() as session:
        row = session.get(UserMemoryRecord, saved["memory_id"])
    assert row.status == "active"  # TTL hides the row from reads; it never deletes it


def test_a_superseded_expired_row_is_labelled_in_the_audit(db):
    stale = memory.confirm(db, proposal(ttl_seconds=60), **TEACHER)
    with db() as session:
        # Backdate the stored TTL so the row is expired by the time it is superseded.
        session.get(UserMemoryRecord, stale["memory_id"]).expires_at -= 120
        session.commit()
    replacement = memory.confirm(db, proposal(content="替换", ttl_seconds=60), **TEACHER)
    assert [(event["action"], event["reason"])
            for event in memory.memory_audit(db, stale["memory_id"])] == [
                ("confirmed", "role:teacher"), ("superseded", "ttl_expired")]
    assert [item["memory_id"] for item in memory.active_memories(db, "learner-9")] == [
        replacement["memory_id"]]


@pytest.mark.parametrize("bad", [1.5, -1, float("inf"), float("nan"), "0.5", True])
def test_unusable_confidence_is_rejected_at_proposal_time(db, bad):
    with pytest.raises(memory.MemoryPolicyViolation):
        proposal(confidence=bad)
    assert counts(db) == (0, 0)


@pytest.mark.parametrize("bad", [0, -1, float("inf"), float("nan"), "60", True])
def test_unusable_ttl_is_rejected_at_proposal_time(db, bad):
    with pytest.raises(memory.MemoryPolicyViolation):
        proposal(ttl_seconds=bad)


@pytest.mark.parametrize("field,value", [("user_id", ""), ("kind", "  "), ("content", ""),
                                         ("source_type", ""), ("kind", "k" * 65)])
def test_a_proposal_needs_its_shape(field, value):
    with pytest.raises(memory.MemoryPolicyViolation):
        proposal(**{field: value})


def test_a_tampered_proposal_is_validated_again_at_confirm(db):
    drafted = proposal()
    drafted["content"] = "   "
    with pytest.raises(memory.MemoryPolicyViolation) as caught:
        memory.confirm(db, drafted, **TEACHER)
    assert str(caught.value) == "content_required"
    assert counts(db) == (0, 0)


def test_a_write_failure_never_leaks_database_text(db):
    def broken():
        raise RuntimeError("no such table: user_memories")

    with pytest.raises(memory.MemoryPersistenceError) as caught:
        memory.confirm(broken, proposal(), **TEACHER)
    assert str(caught.value) == "memory_persistence_unavailable"
    with pytest.raises(memory.MemoryPersistenceError):
        memory.active_memories(broken, "learner-9")
    with pytest.raises(memory.MemoryPersistenceError):
        memory.memory_audit(broken, "anything")
