"""Code-sandbox resilience under adversarial input.

The 3-tier sandbox (AST -> RestrictedPython -> Subprocess) is the
most security-critical surface in the system. These tests assert that
nothing in `DANGEROUS_CODE_INPUTS` succeeds, that nothing in
`ALL_BAD_TEXT_INPUTS` (when passed as Python source) crashes the
sandbox, and that resource exhaustion attempts are caught.
"""
from __future__ import annotations

import pytest

import threading

from backend.app.services.multimodal.code_sandbox import CodeSandbox

from tests.regression.bad_inputs import (
    ALL_BAD_TEXT_INPUTS,
    DANGEROUS_CODE_INPUTS,
    DOS_CODE_INPUTS,
)


@pytest.fixture(scope="module")
def sandbox() -> CodeSandbox:
    return CodeSandbox()


@pytest.mark.parametrize("label,code", DANGEROUS_CODE_INPUTS)
def test_dangerous_code_is_rejected_or_safely_failed(label, code, sandbox):
    """No dangerous payload should run successfully."""
    result = sandbox.execute(code)
    assert result.passed is False, (
        f"[{label}] dangerous payload passed sandbox: stdout={result.stdout!r}"
    )


@pytest.mark.parametrize("label,text", ALL_BAD_TEXT_INPUTS)
def test_bad_text_does_not_crash_sandbox(label, text, sandbox):
    """The sandbox should never raise — it always returns a SandboxResult.

    Exception: ill-formed Unicode surrogates cannot be encoded by Python
    itself for ast.parse(); we treat raising UnicodeEncodeError as
    acceptable (the caller layer above is responsible for cleaning
    surrogates before reaching the sandbox)."""
    try:
        result = sandbox.execute(text)
    except UnicodeEncodeError:
        # Acceptable: lone surrogate is fundamentally non-encodable. The
        # production API layer would surface this as a 400 before reaching
        # the sandbox.
        return
    assert hasattr(result, "passed")
    assert hasattr(result, "stdout")
    assert hasattr(result, "stderr")


def test_dangerous_code_never_leaks_filesystem(sandbox):
    """`open()` calls must be blocked even if the payload looks innocuous."""
    result = sandbox.execute("open('/etc/passwd').read()")
    assert result.passed is False


def test_dangerous_code_never_imports_os(sandbox):
    """All `import os` attempts must be rejected at AST or runtime."""
    for payload in (
        "import os",
        "from os import system",
        "__import__('os')",
        "globals()['__builtins__'].__import__('os')",
    ):
        result = sandbox.execute(payload)
        assert result.passed is False, f"payload leaked: {payload!r}"


def test_dangerous_code_never_imports_subprocess(sandbox):
    for payload in (
        "import subprocess",
        "from subprocess import run",
        "__import__('subprocess')",
    ):
        result = sandbox.execute(payload)
        assert result.passed is False, f"payload leaked: {payload!r}"


def test_dangerous_code_never_runs_eval(sandbox):
    """Calls to `eval` / `exec` should be blocked at the AST layer."""
    for payload in (
        "eval('1+1')",
        "exec('x = 1')",
        "compile('1+1', '<s>', 'eval')",
    ):
        result = sandbox.execute(payload)
        assert result.passed is False, f"payload leaked: {payload!r}"


@pytest.mark.parametrize("label,code", DOS_CODE_INPUTS)
def test_dos_code_either_rejected_or_caught_by_threaded_timeout(label, code, sandbox):
    """DoS payloads (infinite loop / memory bomb) must be either rejected at
    the AST/RestrictedPython gate OR caught by the existing runtime timeout.
    A threaded outer timeout prevents the test itself from hanging pytest.

    Hardened 2026-06-24: AST analyzer now detects ``while True`` without
    explicit ``break``/``return``/``raise``, large literal-sequence
    multiplications, and ``range`` arguments above ``max_range_argument``.
    """
    result_holder: dict = {}

    def _run() -> None:
        try:
            result_holder["result"] = sandbox.execute(code)
        except Exception as exc:  # noqa: BLE001
            result_holder["exc"] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=8.0)
    if t.is_alive():
        pytest.fail(f"[{label}] sandbox hung past 8s -- AST timeout missing")

    if "exc" in result_holder:
        return
    result = result_holder.get("result")
    assert result is not None, f"[{label}] sandbox returned no result"
    assert result.passed is False, (
        f"[{label}] DoS payload reported as passed: {result.stdout!r}"
    )


# ============================================================
# DoS-hardening targeted regression (2026-06-24)
# ============================================================
def test_dos_infinite_loop_rejected_at_ast_layer(sandbox):
    """``while True:`` with no break must be rejected at Level 1 (AST)."""
    result = sandbox.execute("while True:\n    pass")
    assert result.passed is False
    assert result.execution_level == 1
    assert "无限循环" in (result.error or "") or "while" in (result.error or "").lower()


def test_dos_while_with_break_allowed(sandbox):
    """``while True`` *with* an explicit break path must still execute."""
    result = sandbox.execute(
        "n = 0\nwhile True:\n    n += 1\n    if n >= 3:\n        break\nprint(n)"
    )
    assert result.passed is True, f"break-bounded loop rejected: {result.error}"
    assert "3" in result.stdout


def test_dos_memory_bomb_rejected_at_ast_layer(sandbox):
    """``[0] * (10**9)`` must be rejected before allocation."""
    result = sandbox.execute("x = [0] * (10**9)")
    assert result.passed is False
    assert result.execution_level == 1
    assert "内存炸弹" in (result.error or "") or "序列乘法" in (result.error or "")


def test_dos_small_list_multiply_allowed(sandbox):
    """Reasonable list multiplications (under threshold) must still run."""
    result = sandbox.execute("x = [0] * 100\nprint(len(x))")
    assert result.passed is True
    assert "100" in result.stdout


def test_dos_range_huge_rejected(sandbox):
    """``range(10**12)`` must be rejected before iteration."""
    result = sandbox.execute("for _ in range(10**12):\n    pass")
    assert result.passed is False
    assert result.execution_level == 1
    assert "range" in (result.error or "").lower()


def test_dos_range_small_allowed(sandbox):
    """Reasonable range iterations must still run."""
    result = sandbox.execute(
        "total = 0\nfor i in range(100):\n    total += i\nprint(total)"
    )
    assert result.passed is True
    assert "4950" in result.stdout


def test_dos_blocked_threading_module(sandbox):
    """Newly blocked threading/asyncio/multiprocessing must be rejected."""
    for payload in ("import threading", "import asyncio", "import multiprocessing"):
        result = sandbox.execute(payload)
        assert result.passed is False, f"newly-blocked import leaked: {payload!r}"
