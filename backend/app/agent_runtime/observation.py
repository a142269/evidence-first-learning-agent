"""Unified observation records for learning-package runs.

An observation is a bounded projection of a node or delivery outcome.  It keeps
existing event payloads, error codes and checkpoints untouched: observations are
additional records only.  No prompt, model text, retrieved content or
credential is ever copied into an observation.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ObservationStatus = Literal["success", "partial", "failed", "skipped"]

# ``retryable`` means the existing bounded recovery path can retry this run
# without a new user request.  It is deliberately narrower than "the operation
# could ever succeed later".
_FAILURE_POLICY: dict[str, tuple[str, bool]] = {
    "learning_package_invalid_output": ("schema", True),
    "learning_package_tool_failed": ("tool", True),
    "learning_package_repeated_search": ("planning", True),
    "learning_package_invalid_citation": ("citation", False),
    "learning_package_evidence_revision_unavailable": ("citation", False),
    "learning_package_budget_exceeded": ("budget", False),
    "learning_package_no_evidence": ("evidence", False),
    "learning_package_tool_denied": ("safety", False),
    "learning_package_quality_failed": ("quality", False),
    "learning_package_dependency_missing": ("dependency", False),
    "learning_package_unavailable": ("runtime", False),
    "ablation_guard_blocked": ("safety", False),
    "ablation_fixed_evidence_revision_unavailable": ("citation", False),
}


class Observation(BaseModel):
    """One normalized node/delivery observation with bounded numeric metrics."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    node: str = Field(min_length=1, max_length=64)
    status: ObservationStatus
    error_class: str | None = Field(default=None, max_length=32)
    retryable: bool = False
    evidence_strength: float | None = Field(default=None, ge=0, le=1)
    citation_support: float | None = Field(default=None, ge=0, le=1)
    detail: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def classify_failure(code: str) -> tuple[str, bool]:
    """Map a stable error code to ``(error_class, retryable)``."""
    return _FAILURE_POLICY.get(code, ("runtime", False))


def failure_observation(
    node: str,
    code: str,
    *,
    retryable: bool | None = None,
    evidence_strength: float | None = None,
    citation_support: float | None = None,
    detail: dict[str, Any] | None = None,
) -> Observation:
    """Build a failed observation without copying exception text."""
    error_class, default_retryable = classify_failure(code)
    return Observation(
        node=node,
        status="failed",
        error_class=error_class,
        retryable=default_retryable if retryable is None else retryable,
        evidence_strength=evidence_strength,
        citation_support=citation_support,
        detail={"error_code": code, **(detail or {})},
    )
