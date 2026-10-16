"""Code Sandbox 基线 —— 3 级安全模式各采一次"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.bench


def test_bench_sandbox_ast_simple(benchmark):
    from backend.app.services.multimodal.code_sandbox import CodeSandbox

    sandbox = CodeSandbox()
    code = "x = 1 + 2 + 3\nprint(x)\n"

    result = benchmark.pedantic(
        sandbox.execute, args=(code,),
        rounds=3, iterations=1,
    )
    assert result.passed is True
    assert "6" in result.stdout


def test_bench_sandbox_ast_loop(benchmark):
    from backend.app.services.multimodal.code_sandbox import CodeSandbox

    sandbox = CodeSandbox()
    code = "for i in range(5):\n    print(i * 2)\n"

    result = benchmark.pedantic(
        sandbox.execute, args=(code,),
        rounds=3, iterations=1,
    )
    assert result.passed is True
    assert "8" in result.stdout


def test_bench_sandbox_ast_rejects_import_os(benchmark):
    from backend.app.services.multimodal.code_sandbox import CodeSandbox

    sandbox = CodeSandbox()
    code = "import os\nprint(os.getcwd())\n"

    result = benchmark.pedantic(
        sandbox.execute, args=(code,),
        rounds=3, iterations=1,
    )
    assert result.passed is False
