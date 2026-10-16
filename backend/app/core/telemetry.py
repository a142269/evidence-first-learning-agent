"""
Telemetry - 后端指标收集 + Prometheus 暴露

设计:
- 纯 Python 实现, 无 prometheus_client 强依赖
- 提供 Counter / Histogram / Gauge 3 种指标
- 单例 TelemetryRegistry 集中管理
- Prometheus exposition format 输出 (供 /metrics 端点)

跨模块约定:
    - LLM 调用: increment llm_calls_total{provider,status}
    - LLM 延迟: observe llm_call_duration_seconds
    - Pipeline 阶段耗时: observe pipeline_stage_duration_seconds{stage}
    - 资源生成: increment artifact_generated_total{type,status}
    - Agent 失败: increment agent_failure_total{agent}
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


# ================================================================
# 默认 Histogram 桶 (秒)
# ================================================================
DEFAULT_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0,
    2.5, 5.0, 10.0, 30.0, 60.0,
)


# ================================================================
# 单条 metric
# ================================================================
class Counter:
    """单调递增计数器"""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._values: Dict[Tuple, float] = defaultdict(float)
        self._lock = threading.RLock()

    def inc(self, value: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] += value

    def value(self, **labels: str) -> float:
        key = tuple(sorted(labels.items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def export(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.help_text or 'no help'}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            for key, v in self._values.items():
                label_str = self._fmt_labels(key)
                lines.append(f"{self.name}{label_str} {v}")
        return lines

    @staticmethod
    def _fmt_labels(key: Tuple) -> str:
        if not key:
            return ""
        parts = [f'{k}="{_escape(v)}"' for k, v in key]
        return "{" + ",".join(parts) + "}"


class Histogram:
    """Histogram with predefined buckets"""

    def __init__(
        self,
        name: str,
        help_text: str = "",
        buckets: Tuple[float, ...] = DEFAULT_BUCKETS,
    ):
        self.name = name
        self.help_text = help_text
        self.buckets = buckets
        self._counts: Dict[Tuple, List[int]] = defaultdict(
            lambda: [0] * len(buckets),
        )
        self._sum: Dict[Tuple, float] = defaultdict(float)
        self._total: Dict[Tuple, int] = defaultdict(int)
        self._lock = threading.RLock()

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._sum[key] += value
            self._total[key] += 1
            for i, b in enumerate(self.buckets):
                if value <= b:
                    self._counts[key][i] += 1

    def export(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.help_text or 'no help'}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            for key in self._sum:
                label_dict = dict(key)
                cumulative = 0
                # bucket lines (cumulative)
                for i, b in enumerate(self.buckets):
                    cumulative += self._counts[key][i]
                    le_labels = {**label_dict, "le": str(b)}
                    lines.append(
                        f"{self.name}_bucket"
                        f"{Counter._fmt_labels(tuple(sorted(le_labels.items())))} "
                        f"{cumulative}"
                    )
                # +Inf
                lines.append(
                    f"{self.name}_bucket"
                    f"{Counter._fmt_labels(tuple(sorted({**label_dict, 'le': '+Inf'}.items())))} "
                    f"{self._total[key]}"
                )
                lines.append(
                    f"{self.name}_sum"
                    f"{Counter._fmt_labels(key)} "
                    f"{self._sum[key]}"
                )
                lines.append(
                    f"{self.name}_count"
                    f"{Counter._fmt_labels(key)} "
                    f"{self._total[key]}"
                )
        return lines


class Gauge:
    """瞬时数值 (e.g. session_active_count)"""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._values: Dict[Tuple, float] = defaultdict(float)
        self._lock = threading.RLock()

    def set(self, value: float, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1.0, **labels: str) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] += value

    def dec(self, value: float = 1.0, **labels: str) -> None:
        self.inc(-value, **labels)

    def value(self, **labels: str) -> float:
        key = tuple(sorted(labels.items()))
        with self._lock:
            return self._values.get(key, 0.0)

    def export(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.help_text or 'no help'}",
            f"# TYPE {self.name} gauge",
        ]
        with self._lock:
            for key, v in self._values.items():
                lines.append(f"{self.name}{Counter._fmt_labels(key)} {v}")
        return lines


def _escape(v: Any) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# ================================================================
# 全局 Registry
# ================================================================
class TelemetryRegistry:
    """中心化指标登记 + Prometheus 导出"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}

    def counter(self, name: str, help_text: str = "") -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, help_text)
            return self._counters[name]

    def histogram(
        self, name: str, help_text: str = "",
        buckets: Tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, help_text, buckets)
            return self._histograms[name]

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, help_text)
            return self._gauges[name]

    def export_prometheus(self) -> str:
        """渲染所有指标为 Prometheus exposition format"""
        lines: List[str] = []
        with self._lock:
            for c in self._counters.values():
                lines.extend(c.export())
            for h in self._histograms.values():
                lines.extend(h.export())
            for g in self._gauges.values():
                lines.extend(g.export())
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """测试用"""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()


# ================================================================
# 全局单例
# ================================================================
_registry: Optional[TelemetryRegistry] = None


def get_telemetry() -> TelemetryRegistry:
    global _registry
    if _registry is None:
        _registry = TelemetryRegistry()
        _bootstrap_default_metrics(_registry)
    return _registry


def reset_telemetry() -> None:
    global _registry
    _registry = None


def _bootstrap_default_metrics(reg: TelemetryRegistry) -> None:
    """预注册业务指标 (即使没事件也在 /metrics 里出现, 监控 dashboard 不会因 missing 报错)"""
    reg.counter("llm_calls_total",       "Total LLM API calls")
    reg.counter("artifact_generated_total", "Total artifacts generated")
    reg.counter("agent_failure_total",   "Total agent execution failures")
    reg.counter("pipeline_stages_total", "Total pipeline stages executed")
    # B 补充：token 用量 + 成本统计（供 /metrics/llm-cost 端点）
    reg.counter("llm_tokens_total",      "Total LLM tokens consumed")
    reg.counter("cognitive_operations_total", "Cognitive diagnosis operations")

    reg.histogram(
        "llm_call_duration_seconds",
        "LLM API call latency",
    )
    reg.histogram(
        "pipeline_stage_duration_seconds",
        "Per-stage pipeline duration",
    )
    reg.histogram(
        "artifact_generation_duration_seconds",
        "Resource generation latency",
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )
    # B 补充：学情服务阶段耗时
    reg.histogram(
        "learning_state_duration_seconds",
        "Learning state store operation latency",
    )
    reg.histogram(
        "cognitive_stage_duration_seconds",
        "Cognitive diagnosis stage latency",
    )

    reg.gauge("session_active_count", "Active chat sessions")
    reg.gauge("artifact_registry_size", "Currently registered artifacts")
    # B 补充：累计成本（元）— Gauge 便于实时查询当前总花费
    reg.gauge("llm_cost_yuan", "Accumulated LLM cost in CNY")


# ================================================================
# 便捷计时器 (with 块 / 装饰器)
# ================================================================
class Timer:
    """`with Timer(histogram_name, **labels):` 自动 observe 耗时"""

    def __init__(self, hist_name: str, **labels: str):
        self.hist_name = hist_name
        self.labels = labels
        self._start: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed = time.perf_counter() - self._start
        get_telemetry().histogram(self.hist_name).observe(
            elapsed, **self.labels,
        )
