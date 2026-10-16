"""
Prometheus-compatible metrics — pure Python stdlib, zero external dependencies.

Counters and Histograms for:
  - LLM calls (count, latency, tokens, errors)
  - RAG retrievals (count, latency, hit_rate)
  - Agent invocations (count, success_rate, latency)
  - Debate rounds (count, distribution)
  - API requests (count, latency, status)
  - Cognitive diagnosis (DINA/BKT/SM-2 operations)
  - Database operations (reads, writes)

Exposed via GET /metrics with Content-Type: text/plain; version=0.0.4

Usage:
  from backend.app.core.metrics import (
      llm_calls_total, llm_call_duration_seconds,
      rag_retrievals_total, api_requests_total,
  )
  llm_calls_total.labels(provider="spark", status="success").inc()
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, List


# ── Core metric types ──────────────────────────────────


class Counter:
    """Prometheus-compatible Counter — monotonic increasing."""

    def __init__(self, name: str, help_text: str, label_names: List[str]):
        self.name = name
        self.help = help_text
        self.label_names = label_names
        self._lock = threading.Lock()
        self._values: Dict[tuple, float] = defaultdict(float)

    def labels(self, **kwargs) -> "_BoundCounter":
        key = tuple(kwargs.get(ln, "") for ln in self.label_names)
        return _BoundCounter(self, key)

    def _inc(self, key: tuple, amount: float = 1.0) -> None:
        with self._lock:
            self._values[key] += amount

    def _render(self) -> List[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        with self._lock:
            for key, value in self._values.items():
                labels = ",".join(
                    f'{ln}="{kv}"'
                    for ln, kv in zip(self.label_names, key)
                )
                lines.append(f"{self.name}{{{labels}}} {value}")
        return lines


class _BoundCounter:
    def __init__(self, parent: Counter, key: tuple):
        self._parent = parent
        self._key = key

    def inc(self, amount: float = 1.0) -> None:
        self._parent._inc(self._key, amount)


class _BoundHistogram:
    def __init__(self, parent: "Histogram", key: tuple):
        self._parent = parent
        self._key = key

    def observe(self, value: float) -> None:
        self._parent._observe(self._key, float(value))


class Histogram:
    """Prometheus-compatible Histogram — bucket-based."""

    def __init__(self, name: str, help_text: str, label_names: List[str],
                 buckets: List[float] | None = None):
        self.name = name
        self.help = help_text
        self.label_names = label_names
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._lock = threading.Lock()
        self._values: Dict[tuple, Dict[str, float]] = defaultdict(
            lambda: {"sum": 0.0, "count": 0, **{f"le_{b}": 0.0 for b in self.buckets}}
        )

    def labels(self, **kwargs) -> "_BoundHistogram":
        key = tuple(kwargs.get(ln, "") for ln in self.label_names)
        return _BoundHistogram(self, key)

    def _observe(self, key: tuple, value: float) -> None:
        with self._lock:
            rec = self._values[key]
            rec["sum"] += value
            rec["count"] += 1
            for b in self.buckets:
                if value <= b:
                    rec[f"le_{b}"] += 1.0

    def _render(self) -> List[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        with self._lock:
            for key, rec in self._values.items():
                label_str = ",".join(
                    f'{ln}="{kv}"' for ln, kv in zip(self.label_names, key)
                )
                lines.append(f"{self.name}_sum{{{label_str}}} {rec['sum']}")
                lines.append(f"{self.name}_count{{{label_str}}} {rec['count']}")
                for b in self.buckets:
                    bucket_label = f'{label_str},le="{b}"'
                    lines.append(f"{self.name}_bucket{{{bucket_label}}} {rec[f'le_{b}']}")
                lines.append(f"{self.name}_bucket{{{label_str},le=\"+Inf\"}} {rec['count']}")
        return lines


# ── Metric definitions ─────────────────────────────────

# LLM
llm_calls_total = Counter(
    "a3_llm_calls_total", "Total LLM API calls", ["provider", "status"]
)
llm_call_duration_seconds = Histogram(
    "a3_llm_call_duration_seconds", "LLM call latency", ["provider"]
)
llm_tokens_total = Counter(
    "a3_llm_tokens_total", "Total LLM tokens consumed", ["provider", "type"]  # type: input|output
)

# RAG
rag_retrievals_total = Counter(
    "a3_rag_retrievals_total", "Total RAG retrieval calls", ["backend", "status"]
)
rag_retrieval_duration_seconds = Histogram(
    "a3_rag_retrieval_duration_seconds", "RAG retrieval latency", ["backend"]
)
rag_hit_rate = Histogram(
    "a3_rag_hit_rate", "RAG hit count per query", ["backend"]
)

# Agent
agent_invocations_total = Counter(
    "a3_agent_invocations_total", "Total Agent invocations", ["agent_name", "status"]
)
agent_duration_seconds = Histogram(
    "a3_agent_duration_seconds", "Agent execution latency", ["agent_name"]
)

# Debate
debate_rounds_total = Counter(
    "a3_debate_rounds_total", "Total debate rounds across all sessions", ["status"]
)
debate_round_distribution = Histogram(
    "a3_debate_rounds_per_session", "Debate rounds per session", []
)

# API
api_requests_total = Counter(
    "a3_api_requests_total", "Total API requests", ["method", "endpoint", "status_code"]
)
api_request_duration_seconds = Histogram(
    "a3_api_request_duration_seconds", "API request latency", ["method", "endpoint"]
)

# Cognitive Diagnosis
cognitive_operations_total = Counter(
    "a3_cognitive_operations_total", "Cognitive diagnosis operations", ["algorithm", "operation"]
)

# Database
db_operations_total = Counter(
    "a3_db_operations_total", "Database operations", ["table", "operation"]  # operation: read|write
)


# ── Metrics collection helpers ─────────────────────────

class MetricsCollector:
    """Decorator/context-manager for collecting latency metrics.

    Usage:
        @MetricsCollector.timed(llm_call_duration_seconds, provider="spark")
        def call_llm(): ...

        with MetricsCollector.track(api_request_duration_seconds, method="POST", endpoint="/chat/send"):
            handle_request()
    """

    @staticmethod
    def timed(histogram: Histogram, **labels):
        """Decorator that records duration of the wrapped function."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    histogram.labels(**labels).observe(time.perf_counter() - start)
            return wrapper
        return decorator


# ── Render all metrics ─────────────────────────────────

_registry: List[Counter | Histogram] = []


def _collect_all() -> List[Counter | Histogram]:
    """Lazy registration of all metric objects."""
    if _registry:
        return _registry
    _registry.extend([
        llm_calls_total, llm_call_duration_seconds, llm_tokens_total,
        rag_retrievals_total, rag_retrieval_duration_seconds, rag_hit_rate,
        agent_invocations_total, agent_duration_seconds,
        debate_rounds_total, debate_round_distribution,
        api_requests_total, api_request_duration_seconds,
        cognitive_operations_total, db_operations_total,
    ])
    return _registry


def render_metrics() -> str:
    """Render all registered metrics in Prometheus text format."""
    lines: List[str] = []
    for metric in _collect_all():
        lines.extend(metric._render())
        lines.append("")
    return "\n".join(lines)
