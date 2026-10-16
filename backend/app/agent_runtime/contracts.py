"""Explicit harness contracts shared by LangGraph runs and integration tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunContext:
    user_id: str
    course_id: str
    session_id: str
    permissions: frozenset[str] = frozenset({"learning:read"})
    token_budget: int = 4096
    timeout_seconds: int = 60
    trace_id: str = ""


@dataclass(frozen=True)
class RunPolicy:
    allowed_tools: frozenset[str] = frozenset({"retrieval"})
    max_steps: int = 6
    allow_model_fallback: bool = True
    require_human_review: bool = False


@dataclass
class RunResult:
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, float] = field(default_factory=dict)
    latency_ms: int = 0
    audit_events: list[dict[str, Any]] = field(default_factory=list)
