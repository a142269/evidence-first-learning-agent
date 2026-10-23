"""QWEN-202: the cross-session summary reads confirmed memories but never writes back."""
import time

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.core import models  # noqa: F401  (registers every table on Base)
from backend.app.core.database import Base
from backend.app.core.models import AgentRunRecord, MemoryEventRecord, UserMemoryRecord
from backend.app.services import session_summary as summary
from backend.app.services import user_memory as memory

TEACHER = {"actor": "teacher-1", "actor_role": "teacher"}
USER = "learner-9"
# confirm() stamps its own wall-clock instant, so the fixture clock is real time: a frozen
# clock would make every TTL comparison measure the gap between 2023 and now.
NOW = time.time()


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'summary.db').as_posix()}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def add_run(factory, run_id, status):
    with factory() as session:
        session.add(AgentRunRecord(id=run_id, status=status, user_id=USER))
        session.commit()


def counts(factory):
    with factory() as session:
        return (session.scalar(select(func.count()).select_from(UserMemoryRecord)),
                session.scalar(select(func.count()).select_from(MemoryEventRecord)))


def confirm(factory, kind, content, *, run_id="run-1", **overrides):
    proposal = memory.propose(user_id=USER, kind=kind, content=content,
                              source_run_id=run_id, **overrides)
    return memory.confirm(factory, proposal, **TEACHER)


def test_empty_store_returns_an_explicit_empty_state(db):
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["status"] == "empty"
    assert result["reason"] == "no_active_memory"
    assert result["summary"] == ""
    assert result["sections"] == [] and result["used_memory_ids"] == []
    assert result["memory_count"] == 0 and result["estimated_tokens"] == 0
    assert result["persisted"] is False


def test_summary_of_one_memory_is_the_fixed_golden_sample(db):
    add_run(db, "run-1", "completed")
    saved = confirm(db, "weak_point", "分数除法还需要复习")
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["status"] == "summary" and result["reason"] == "ok"
    assert result["summary"] == "- weak_point：分数除法还需要复习"
    assert result["memory_count"] == 1
    assert result["used_memory_ids"] == [saved["memory_id"]]
    assert result["truncated"] is False
    assert result["generated_at"] == NOW
    assert len(result["summary_sha256"]) == 64


def test_summary_lines_quote_confirmed_content_verbatim(db):
    """Fidelity: the summary is composed from stored text, with nothing invented."""
    add_run(db, "run-1", "completed")
    add_run(db, "run-2", "completed")
    first = confirm(db, "weak_point", "通分容易出错")
    second = confirm(db, "preference", "喜欢用画图法验证", run_id="run-2")
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert {section["text"] for section in result["sections"]} == {"通分容易出错",
                                                                   "喜欢用画图法验证"}
    assert set(result["used_memory_ids"]) == {first["memory_id"], second["memory_id"]}
    for line in result["summary"].split("\n"):
        assert line.split("：", 1)[1] in {"通分容易出错", "喜欢用画图法验证"}


def test_summary_writes_nothing_to_the_memory_tables(db):
    """Lead's hard rule: a summary never becomes a memory, and never logs an event."""
    add_run(db, "run-1", "completed")
    confirm(db, "weak_point", "分数除法还需要复习")
    before = counts(db)
    for _ in range(3):
        result = summary.cross_session_summary(db, USER, now=NOW)
        assert result["persisted"] is False
    assert counts(db) == before == (1, 1)


def test_rebuilding_the_same_summary_is_idempotent(db):
    add_run(db, "run-1", "completed")
    confirm(db, "weak_point", "分数除法还需要复习")
    first = summary.cross_session_summary(db, USER, now=NOW)
    second = summary.cross_session_summary(db, USER, now=NOW + 3600)
    assert first["summary_sha256"] == second["summary_sha256"]
    assert {key: value for key, value in first.items() if key != "generated_at"} == \
           {key: value for key, value in second.items() if key != "generated_at"}


def test_a_new_memory_changes_the_digest(db):
    add_run(db, "run-1", "completed")
    confirm(db, "weak_point", "分数除法还需要复习")
    before = summary.cross_session_summary(db, USER, now=NOW)
    confirm(db, "preference", "喜欢用画图法验证")
    assert summary.cross_session_summary(db, USER, now=NOW)["summary_sha256"] \
        != before["summary_sha256"]


def test_unconfirmed_proposal_cannot_be_summarised(db):
    add_run(db, "run-1", "completed")
    memory.propose(user_id=USER, kind="weak_point", content="未确认", source_run_id="run-1")
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["status"] == "empty" and counts(db) == (0, 0)


def test_revoked_memory_is_dropped_from_the_summary(db):
    add_run(db, "run-1", "completed")
    saved = confirm(db, "weak_point", "分数除法还需要复习")
    assert summary.cross_session_summary(db, USER, now=NOW)["memory_count"] == 1
    memory.revoke(db, saved["memory_id"], actor="teacher-1", actor_role="teacher",
                  reason="learner asked")
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["status"] == "empty" and result["used_memory_ids"] == []


def test_expired_memory_is_dropped_from_the_summary(db):
    add_run(db, "run-1", "completed")
    saved = confirm(db, "weak_point", "两周前的判断", ttl_seconds=600)
    # confirm() stamps its own instant, so only the ordering against the fixture clock is
    # asserted — the exact expiry value belongs to QWEN-201, not to this card.
    assert saved["expires_at"] is not None and saved["expires_at"] > NOW
    inside = summary.cross_session_summary(db, USER, now=NOW)
    outside = summary.cross_session_summary(db, USER, now=NOW + 3600)
    assert inside["memory_count"] == 1
    assert outside["status"] == "empty" and outside["reason"] == "no_active_memory"
    assert outside["persisted"] is False


@pytest.mark.parametrize("status", ["partially_completed", "failed", "awaiting_approval",
                                    "reviewing", "interrupted", "rejected", "running"])
def test_a_run_that_degraded_after_confirmation_is_not_summarised(db, status):
    """The card pins 不被 partial 污染 — re-checked at read time, not only at write time."""
    add_run(db, "run-1", "completed")
    saved = confirm(db, "weak_point", "分数除法还需要复习")
    with db() as session:
        session.get(AgentRunRecord, "run-1").status = status
        session.commit()
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["status"] == "empty" and result["reason"] == "no_memory_fit_budget"
    assert result["skipped"] == [{"memory_id": saved["memory_id"],
                                  "reason": f"source_run_not_completed:{status}"}]


def test_a_missing_provenance_run_is_not_summarised(db):
    add_run(db, "run-1", "completed")
    saved = confirm(db, "weak_point", "分数除法还需要复习")
    with db() as session:
        session.delete(session.get(AgentRunRecord, "run-1"))
        session.commit()
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["used_memory_ids"] == []
    assert result["skipped"][0]["reason"] == "source_run_not_completed:None"
    assert result["skipped"][0]["memory_id"] == saved["memory_id"]


def test_a_hand_authored_memory_without_a_run_is_still_summarised(db):
    saved = confirm(db, "goal", "这学期想把应用题练稳", run_id=None)
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["used_memory_ids"] == [saved["memory_id"]]
    assert result["sections"][0]["source_run_id"] is None


def test_window_is_configurable_and_replaces_the_fixed_three(db):
    add_run(db, "run-1", "completed")
    kinds = ["weak_point", "preference", "goal", "pace"]
    for kind in kinds:
        confirm(db, kind, f"{kind} 的内容")
    default = summary.cross_session_summary(db, USER, now=NOW)
    assert default["memory_count"] == 3 and default["window"] == summary.DEFAULT_WINDOW
    assert [item["reason"] for item in default["skipped"]] == ["outside_window"]

    narrow = summary.cross_session_summary(db, USER, window=1, now=NOW)
    assert narrow["memory_count"] == 1 and len(narrow["skipped"]) == 3
    wide = summary.cross_session_summary(db, USER, window=4, now=NOW)
    assert wide["memory_count"] == 4 and wide["skipped"] == []
    assert set(wide["used_memory_ids"]) == {item["memory_id"] for item in
                                            memory.active_memories(db, USER, now=NOW)}


def test_token_budget_bounds_the_summary(db):
    add_run(db, "run-1", "completed")
    for kind in ["weak_point", "preference", "goal"]:
        confirm(db, kind, "这是一段较长的中文记忆内容，用来验证预算能够限制摘要长度。")
    result = summary.cross_session_summary(db, USER, token_budget=30, now=NOW)
    assert result["estimated_tokens"] <= 30
    assert result["memory_count"] < 3
    assert {item["reason"] for item in result["skipped"]} == {"token_budget"}
    assert result["truncated"] is True


def test_a_budget_too_small_for_any_item_is_an_empty_state(db):
    add_run(db, "run-1", "completed")
    long = "字" * 200
    confirm(db, "weak_point", long)
    result = summary.cross_session_summary(db, USER, token_budget=1, now=NOW)
    assert result["status"] == "empty" and result["reason"] == "no_memory_fit_budget"
    assert result["summary"] == "" and result["memory_count"] == 0


def test_an_overlong_memory_is_clipped_and_flagged(db):
    add_run(db, "run-1", "completed")
    saved = confirm(db, "weak_point", "冗" * 400)
    result = summary.cross_session_summary(db, USER, now=NOW)
    section = result["sections"][0]
    assert section["truncated"] is True and result["truncated"] is True
    assert section["text"].endswith(summary._ELLIPSIS)
    assert summary.estimate_tokens(section["text"]) <= summary.MAX_TOKENS_PER_MEMORY
    assert len(section["text"]) < 400
    assert section["memory_id"] == saved["memory_id"]


def test_a_malformed_memory_row_degrades_instead_of_failing(db):
    """失败回退: one unusable row must not take the whole summary down."""
    add_run(db, "run-1", "completed")
    good = confirm(db, "weak_point", "分数除法还需要复习")
    with db() as session:
        session.add(UserMemoryRecord(id="m-blank", user_id=USER, kind="pace",
                                     content="   ", source_type="rule_extraction",
                                     status="active", created_at=NOW, updated_at=NOW))
        session.commit()
    result = summary.cross_session_summary(db, USER, now=NOW)
    assert result["used_memory_ids"] == [good["memory_id"]]
    assert result["skipped"] == [{"memory_id": "m-blank", "reason": "content_missing"}]
    assert result["status"] == "summary"


def test_estimates_are_deterministic_and_never_negative():
    assert summary.estimate_tokens("") == 0
    assert summary.estimate_tokens("中文八个字的短语") == 8
    assert summary.estimate_tokens("abcdefgh") == 2
    for text in ["混合 mixed 文本", "a" * 1000, "。！？，", "emoji 🎓 test"]:
        assert summary.estimate_tokens(text) == summary.estimate_tokens(text) >= 0


def test_clipping_never_exceeds_the_cap():
    for text in ["短", "中" * 500, "word " * 500]:
        clipped = summary._clip_to_tokens(text, 10)
        assert summary.estimate_tokens(clipped) <= 10


@pytest.mark.parametrize("field,value", [("window", 0), ("window", -1), ("window", True),
                                         ("window", "3"), ("window", summary.MAX_WINDOW + 1),
                                         ("token_budget", 0), ("token_budget", -5),
                                         ("token_budget", 1_000_000)])
def test_invalid_budget_arguments_are_refused(field, value):
    with pytest.raises(memory.MemoryPolicyViolation):
        summary.build_summary(USER, [], {}, **{field: value}, now=NOW)


@pytest.mark.parametrize("user_id", ["", "   ", None, 7])
def test_a_missing_user_is_refused(user_id):
    with pytest.raises(memory.MemoryPolicyViolation):
        summary.build_summary(user_id, [], {}, now=NOW)


def test_a_vanished_memory_store_raises_the_stable_code(db):
    def broken():
        raise RuntimeError("database is gone")

    with pytest.raises(memory.MemoryPersistenceError) as blocked:
        summary.cross_session_summary(broken, USER, now=NOW)
    assert str(blocked.value) == "memory_persistence_unavailable"


def test_a_vanished_run_table_raises_the_same_stable_code(db):
    """The second read is guarded too: whichever half breaks, the code is the same."""
    add_run(db, "run-1", "completed")
    confirm(db, "weak_point", "分数除法还需要复习")
    calls = []

    def half_working():
        session = db()
        calls.append(session)
        if len(calls) == 1:
            return session
        session.close()
        raise RuntimeError("agent_runs is gone")

    with pytest.raises(memory.MemoryPersistenceError) as blocked:
        summary.cross_session_summary(half_working, USER, now=NOW)
    assert str(blocked.value) == "memory_persistence_unavailable"


def test_module_never_reaches_a_write_or_a_model():
    """Zero-model, no persistence: the only session use is a SELECT of run statuses."""
    import inspect

    source = inspect.getsource(summary).lower()
    for forbidden in [".add(", ".commit(", ".delete(", "update(", "llm", "provider",
                      "requests", "openai", "http", "os.environ", ".env"]:
        assert forbidden not in source, forbidden
