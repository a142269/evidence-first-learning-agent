"""tests/benchmarks/ 子包配置

* 所有用例自动打 `bench` marker（pyproject 已声明），便于 `-m "not bench"` 过滤。
* 默认 5 类资源 + 7 阶段 Pipeline 的 baseline 测量；不依赖外部服务（mmdc / ffmpeg / LLM 走 fallback / mock）。
* 运行：
    pytest tests/benchmarks/ --no-cov --benchmark-only
"""
from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items):
    bench_marker = pytest.mark.bench
    for item in items:
        if item.nodeid.startswith("tests/benchmarks/") or "tests\\benchmarks\\" in item.nodeid:
            item.add_marker(bench_marker)
