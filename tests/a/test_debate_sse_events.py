"""Tests for the T1.5 Multi-Agent debate SSE event stream.

The debate moderator publishes four event types on the per-session
EventBuffer so a browser EventSource can render the debate in real time:

  * `debate_round_start`  — start of each round (round_num, expert)
  * `expert_draft`        — expert produced a draft this round
  * `critic_score`        — critic returned a score for the draft
  * `debate_converged`    — final round, score delta below threshold

These tests use deterministic mock LLM agents so they pass offline.
"""
# ruff: noqa: RUF001
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.agents.base import AgentContext, AgentResponse
from backend.app.agents.critic_agent import CriticIssue, CriticVerdict
from backend.app.agents.debate_moderator import orchestrate_debate
from backend.app.api.v1.chat_pipeline.events import (
    EventBuffer,
    clear_buffer,
    get_or_create_buffer,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------
def _make_expert(name: str, content: str) -> MagicMock:
    expert = MagicMock()
    expert.name = name
    expert.llm = MagicMock()
    expert.execute = AsyncMock(
        return_value=AgentResponse(agent_name=name, success=True, content=content)
    )
    return expert


def _make_critic(scores: list[float]) -> MagicMock:
    """Critic that walks through `scores` round by round; first score → first round."""
    critic = MagicMock()
    critic.name = "critic"
    call_index = {"n": -1}

    async def execute(_ctx: AgentContext) -> AgentResponse:
        call_index["n"] += 1
        idx = min(call_index["n"], len(scores) - 1)
        score = scores[idx]
        passed = score >= 0.75
        return AgentResponse(
            agent_name="critic",
            success=True,
            content="PASS" if passed else "FAIL",
            metadata={
                "verdicts": [
                    CriticVerdict(
                        dimension="factual",
                        passed=passed,
                        score=score,
                        issues=[]
                        if passed
                        else [CriticIssue(severity="major", description="需扩充")],
                        suggestions=[] if passed else ["补充例子"],
                    )
                ],
                "overall_passed": passed,
                "overall_score": score,
            },
        )

    critic.execute = AsyncMock(side_effect=execute)
    return critic


def _events_of(buffer: EventBuffer, event_type: str) -> list[dict[str, Any]]:
    return [
        {"id": evt.event_id, "payload": evt.payload}
        for evt in buffer.replay_after(0)
        if evt.event_type == event_type
    ]


@pytest.fixture(autouse=True)
def _reset_buffer() -> Any:
    """Each test starts with a clean buffer for the chosen session id."""
    session_ids: list[str] = []

    def _register(sid: str) -> str:
        session_ids.append(sid)
        clear_buffer(sid)
        return sid

    yield _register
    for sid in session_ids:
        clear_buffer(sid)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_debate_round_start_event_fires_each_round(_reset_buffer: Any) -> None:
    sid = _reset_buffer("sse-test-round-start")
    expert = _make_expert("course_expert", "短内容。")
    critic = _make_critic([0.40, 0.50])

    await orchestrate_debate(
        expert_agent=expert,
        expert_context=AgentContext(user_input="讲解 CNN", session_id=sid),
        critic_agent=critic,
        max_rounds=2,
        session_id=sid,
    )

    events = _events_of(get_or_create_buffer(sid), "debate_round_start")
    assert len(events) == 2
    assert events[0]["payload"]["round_num"] == 1
    assert events[1]["payload"]["round_num"] == 2
    assert events[0]["payload"]["expert"] == "course_expert"


@pytest.mark.asyncio
async def test_expert_draft_event_carries_content(_reset_buffer: Any) -> None:
    sid = _reset_buffer("sse-test-expert-draft")
    content = "# CNN 详解\n卷积神经网络包含卷积层与池化层。"
    expert = _make_expert("course_expert", content)
    critic = _make_critic([0.95])

    await orchestrate_debate(
        expert_agent=expert,
        expert_context=AgentContext(user_input="讲解 CNN", session_id=sid),
        critic_agent=critic,
        max_rounds=2,
        session_id=sid,
    )

    drafts = _events_of(get_or_create_buffer(sid), "expert_draft")
    assert len(drafts) >= 1
    assert drafts[0]["payload"]["round_num"] == 1
    assert drafts[0]["payload"]["content"] == content


@pytest.mark.asyncio
async def test_critic_score_event_has_score_and_pass_flag(_reset_buffer: Any) -> None:
    sid = _reset_buffer("sse-test-critic-score")
    expert = _make_expert("course_expert", "内容稍短，需要补充。" * 4)
    critic = _make_critic([0.40, 0.95])

    await orchestrate_debate(
        expert_agent=expert,
        expert_context=AgentContext(user_input="讲解 CNN", session_id=sid),
        critic_agent=critic,
        max_rounds=2,
        session_id=sid,
    )

    scores = _events_of(get_or_create_buffer(sid), "critic_score")
    assert len(scores) == 2
    first, second = scores
    assert first["payload"]["round_num"] == 1
    assert first["payload"]["score"] == 40
    assert first["payload"]["passed"] is False
    assert second["payload"]["score"] == 95
    assert second["payload"]["passed"] is True


@pytest.mark.asyncio
async def test_debate_converged_event_fires_on_convergence(_reset_buffer: Any) -> None:
    sid = _reset_buffer("sse-test-converged")
    # Two identical low scores → second round delta == 0 < 0.05 → converged.
    expert = _make_expert("course_expert", "稳定内容。" * 6)
    critic = _make_critic([0.45, 0.45])

    await orchestrate_debate(
        expert_agent=expert,
        expert_context=AgentContext(user_input="讲解 CNN", session_id=sid),
        critic_agent=critic,
        max_rounds=5,
        session_id=sid,
    )

    converged = _events_of(get_or_create_buffer(sid), "debate_converged")
    assert len(converged) == 1
    assert converged[0]["payload"]["round_num"] == 2
    assert converged[0]["payload"]["delta"] < 0.05


@pytest.mark.asyncio
async def test_all_four_event_types_present_in_two_round_run(
    _reset_buffer: Any,
) -> None:
    sid = _reset_buffer("sse-test-all-four")
    expert = _make_expert("course_expert", "内容。" * 30)
    critic = _make_critic([0.40, 0.40])

    await orchestrate_debate(
        expert_agent=expert,
        expert_context=AgentContext(user_input="讲解", session_id=sid),
        critic_agent=critic,
        max_rounds=5,
        session_id=sid,
    )

    types = {evt.event_type for evt in get_or_create_buffer(sid).replay_after(0)}
    assert {
        "debate_round_start",
        "expert_draft",
        "critic_score",
        "debate_converged",
    }.issubset(types)


@pytest.mark.asyncio
async def test_no_sse_events_without_session_id(_reset_buffer: Any) -> None:
    sid = _reset_buffer("sse-test-no-session")
    expert = _make_expert("course_expert", "内容。" * 30)
    critic = _make_critic([0.40, 0.40])

    # Empty session_id → debate moderator must skip buffer publishing.
    await orchestrate_debate(
        expert_agent=expert,
        expert_context=AgentContext(user_input="讲解", session_id=""),
        critic_agent=critic,
        max_rounds=2,
        session_id="",
    )

    # The tracked buffer must be empty (no foreign events leaked in).
    assert get_or_create_buffer(sid).replay_after(0) == []


@pytest.mark.asyncio
async def test_event_ids_are_monotonic(_reset_buffer: Any) -> None:
    sid = _reset_buffer("sse-test-monotonic")
    expert = _make_expert("course_expert", "内容。" * 30)
    critic = _make_critic([0.40, 0.95])

    await orchestrate_debate(
        expert_agent=expert,
        expert_context=AgentContext(user_input="讲解", session_id=sid),
        critic_agent=critic,
        max_rounds=2,
        session_id=sid,
    )

    ids = [evt.event_id for evt in get_or_create_buffer(sid).replay_after(0)]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)
