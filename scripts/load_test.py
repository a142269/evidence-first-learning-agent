"""轻量级压测脚本（K6 风格，无需 uvicorn）

直接用 FastAPI TestClient 打 app，免去启动真实 server 的依赖。适合：
* 演示前 5 分钟跑一遍看 p95 latency
* CI 里跑回归（不依赖端口）
* PromptCache 命中率前后对比

用法:
    python -m scripts.load_test
    python -m scripts.load_test --concurrency 50 --requests 500
    python -m scripts.load_test --endpoint cockpit  # 只压 Cockpit
    python -m scripts.load_test --json              # 机器可读输出（CI）

报告字段:
    endpoint / total_requests / concurrency / success_rate
    latency_ms: { p50, p95, p99, max, mean }
    throughput_rps
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("A3_OFFLINE_DEMO", "1")


# ================================================================
# 数据模型
# ================================================================
@dataclass
class LatencyStats:
    p50: float
    p95: float
    p99: float
    max: float
    mean: float

    @classmethod
    def from_samples(cls, samples: list[float]) -> "LatencyStats":
        if not samples:
            return cls(0, 0, 0, 0, 0)
        sorted_s = sorted(samples)
        n = len(sorted_s)
        return cls(
            p50=sorted_s[int(n * 0.50)],
            p95=sorted_s[min(int(n * 0.95), n - 1)],
            p99=sorted_s[min(int(n * 0.99), n - 1)],
            max=sorted_s[-1],
            mean=statistics.mean(samples),
        )


@dataclass
class EndpointReport:
    name: str
    path: str
    method: str
    total_requests: int
    concurrency: int
    success_count: int
    error_count: int
    duration_s: float
    latency_ms: LatencyStats
    throughput_rps: float
    sample_errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_requests if self.total_requests else 0.0


# ================================================================
# 端点定义
# ================================================================
def _endpoints() -> dict[str, tuple[str, str, Callable | None]]:
    """name → (method, path_template, optional_payload_factory)"""
    return {
        "cockpit": ("GET", "/api/v1/cockpit/student/demo-student-1", None),
        "cockpit_schema": ("GET", "/api/v1/cockpit/schema", None),
        "kg_neighbors": (
            "GET",
            "/api/v1/knowledge-graph/neighbors?kp=cnn&direction=both",
            None,
        ),
        "kg_stats": ("GET", "/api/v1/knowledge-graph/stats", None),
        "profile": ("GET", "/api/v1/profile/demo-student-1", None),
        "system_status": ("GET", "/api/v1/system/status", None),
        "cov_demo_cases": ("GET", "/api/v1/chat/cov-demo-cases", None),
        "forecast": (
            "GET",
            "/api/v1/cognitive/forecast?user_id=demo-student-1&horizon_days=7",
            None,
        ),
    }


# ================================================================
# 压测核心
# ================================================================
def _run_one(client: Any, method: str, path: str) -> tuple[float, int, str]:
    start = time.perf_counter()
    try:
        if method == "GET":
            r = client.get(path)
        elif method == "POST":
            r = client.post(path, json={})
        else:
            r = client.request(method, path)
        elapsed = (time.perf_counter() - start) * 1000
        ok = 200 <= r.status_code < 300
        err = "" if ok else f"HTTP {r.status_code}: {r.text[:80]}"
        return elapsed, r.status_code, err
    except Exception as exc:  # noqa: BLE001
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, 0, f"{type(exc).__name__}: {exc}"


def stress_endpoint(
    client: Any,
    name: str,
    method: str,
    path: str,
    concurrency: int,
    total_requests: int,
) -> EndpointReport:
    latencies: list[float] = []
    errors: list[str] = []
    success = 0

    start_wall = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(_run_one, client, method, path)
            for _ in range(total_requests)
        ]
        for fut in as_completed(futures):
            elapsed, status, err = fut.result()
            latencies.append(elapsed)
            if err:
                errors.append(err)
            else:
                success += 1
    duration = time.perf_counter() - start_wall

    return EndpointReport(
        name=name,
        path=path,
        method=method,
        total_requests=total_requests,
        concurrency=concurrency,
        success_count=success,
        error_count=total_requests - success,
        duration_s=round(duration, 3),
        latency_ms=LatencyStats.from_samples(latencies),
        throughput_rps=round(total_requests / max(duration, 1e-9), 1),
        sample_errors=errors[:3],
    )


# ================================================================
# 渲染
# ================================================================
def render_text(reports: list[EndpointReport]) -> str:
    lines = ["=" * 86, " A3 Load Test Report", "=" * 86]
    head = (
        f"{'endpoint':<18} {'req':>5} {'conc':>5} {'ok%':>6} "
        f"{'p50':>7} {'p95':>7} {'p99':>7} {'max':>7} {'rps':>7}"
    )
    lines.append(head)
    lines.append("-" * 86)
    for r in reports:
        lines.append(
            f"{r.name:<18} {r.total_requests:>5} {r.concurrency:>5} "
            f"{r.success_rate * 100:>5.1f}% "
            f"{r.latency_ms.p50:>6.1f}ms {r.latency_ms.p95:>6.1f}ms "
            f"{r.latency_ms.p99:>6.1f}ms {r.latency_ms.max:>6.1f}ms "
            f"{r.throughput_rps:>6.1f}"
        )
        for err in r.sample_errors:
            lines.append(f"       └─ {err}")
    lines.append("=" * 86)
    return "\n".join(lines)


def render_json(reports: list[EndpointReport]) -> str:
    payload = [{**asdict(r), "success_rate": r.success_rate} for r in reports]
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ================================================================
# Main
# ================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A3 压测脚本（基于 FastAPI TestClient，无需启动 uvicorn）"
    )
    parser.add_argument("--concurrency", type=int, default=10,
                        help="并发线程数（默认 10）")
    parser.add_argument("--requests", type=int, default=100,
                        help="每端点总请求数（默认 100）")
    parser.add_argument("--endpoint", type=str, default="",
                        help="只压指定 endpoint（不传则压全部）；可选: "
                             "cockpit / cockpit_schema / kg_neighbors / "
                             "kg_stats / profile / system_status / "
                             "cov_demo_cases / forecast")
    parser.add_argument("--json", action="store_true",
                        help="JSON 输出（CI 用）")
    args = parser.parse_args(argv)

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    endpoints = _endpoints()
    if args.endpoint:
        if args.endpoint not in endpoints:
            print(f"unknown endpoint: {args.endpoint}; choices: {list(endpoints)}")
            return 2
        endpoints = {args.endpoint: endpoints[args.endpoint]}

    reports: list[EndpointReport] = []
    for name, (method, path, _payload) in endpoints.items():
        if not args.json:
            print(f"  stressing {name} ...", flush=True)
        report = stress_endpoint(
            client, name, method, path,
            concurrency=args.concurrency,
            total_requests=args.requests,
        )
        reports.append(report)

    if args.json:
        print(render_json(reports))
    else:
        print(render_text(reports))

    # 任一 endpoint success_rate < 95% 退出码 1
    return 0 if all(r.success_rate >= 0.95 for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
