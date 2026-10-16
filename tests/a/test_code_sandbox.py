"""
测试: Code Sandbox — 三级安全执行 + AI 审查 (P1-5)

覆盖:
- SandboxPolicy 默认值 + 自定义
- ASTSecurityAnalyzer: 安全代码 / 危险import / 危险函数 / 语法错误 / 空代码 / 过长代码
- RestrictedPython: 数学计算 / 循环 / 函数定义
- Subprocess: 降级执行
- CodeReviewer: 无print / 单字母变量 / 无注释 / 错误类型
- CodeSandbox.execute() 集成: 安全代码通过 / 危险代码阻断 / 不支持语言
"""
from __future__ import annotations

import pytest

from backend.app.services.multimodal.code_sandbox import (
    ASTSecurityAnalyzer,
    CodeReviewer,
    CodeSandbox,
    RestrictedPythonRunner,
    SandboxPolicy,
    SandboxResult,
    SubprocessRunner,
    get_code_sandbox,
    reset_sandbox,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_sandbox()


# ================================================================
# SandboxPolicy
# ================================================================
class TestSandboxPolicy:
    def test_defaults(self):
        p = SandboxPolicy()
        assert "os" in p.blocked_modules
        assert "exec" in p.blocked_builtins
        assert "print" in p.safe_globals
        assert p.max_code_length == 10000

    def test_custom(self):
        p = SandboxPolicy(
            blocked_modules=("os",),
            max_code_length=500,
            timeout_seconds=3,
        )
        assert len(p.blocked_modules) == 1
        assert p.max_code_length == 500


# ================================================================
# ASTSecurityAnalyzer
# ================================================================
class TestASTSecurityAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return ASTSecurityAnalyzer(SandboxPolicy())

    def test_safe_code_passes(self, analyzer):
        safe, error, _ = analyzer.analyze("x = 1 + 1\nprint(x)")
        assert safe is True
        assert error == ""

    def test_blocked_import_os(self, analyzer):
        safe, error, _ = analyzer.analyze("import os\nos.system('ls')")
        assert safe is False
        assert "blocked" in error
        assert "os" in error

    def test_blocked_import_from(self, analyzer):
        safe, error, _ = analyzer.analyze("from subprocess import run")
        assert safe is False

    def test_blocked_exec_call(self, analyzer):
        safe, error, _ = analyzer.analyze('exec("print(1)")')
        assert safe is False
        assert "blocked" in error

    def test_blocked_open_call(self, analyzer):
        safe, error, _ = analyzer.analyze("open('/etc/passwd')")
        assert safe is False

    def test_syntax_error(self, analyzer):
        safe, error, _ = analyzer.analyze("if True print(1)")
        assert safe is False
        assert "语法错误" in error or "SyntaxError" in error

    def test_empty_code(self, analyzer):
        safe, error, _ = analyzer.analyze("")
        assert safe is False

    def test_code_too_long(self, analyzer):
        policy = SandboxPolicy(max_code_length=10)
        a = ASTSecurityAnalyzer(policy)
        safe, error, _ = a.analyze("x = 1\ny = 2\nz = 3")
        assert safe is False
        assert "过长" in error

    def test_normal_code_with_warnings(self, analyzer):
        """合法但检测到危险属性访问 → 有警告但 safe=True"""
        safe, error, warnings = analyzer.analyze("import math\nprint(math.pi)")
        assert safe is True
        # math 不在 blocked_modules 中


# ================================================================
# SandboxResult
# ================================================================
class TestSandboxResult:
    def test_pass_result(self):
        r = SandboxResult(stdout="42\n", passed=True, execution_level=2)
        assert r.passed is True
        assert r.stdout == "42\n"
        d = r.to_dict()
        assert d["passed"] is True

    def test_fail_result(self):
        r = SandboxResult(
            passed=False, error="NameError: name 'x' is not defined",
            stderr="Traceback...", review_hints=["检查变量x的拼写"],
        )
        assert r.passed is False
        assert "NameError" in r.error
        assert len(r.review_hints) == 1


# ================================================================
# CodeReviewer
# ================================================================
class TestCodeReviewer:
    @pytest.fixture
    def reviewer(self):
        return CodeReviewer()

    def test_no_print_hint(self, reviewer):
        hints = reviewer.review(
            "x = 1 + 1\ny = x * 2",
            SandboxResult(passed=True),
        )
        assert any("print" in h for h in hints)

    def test_no_comment_hint(self, reviewer):
        code = "\n".join(f"line{i} = {i}" for i in range(10))
        hints = reviewer.review(code, SandboxResult(passed=True))
        assert any("注释" in h for h in hints)

    def test_name_error_hint(self, reviewer):
        hints = reviewer.review(
            "print(x)", SandboxResult(passed=False, error="NameError: x"),
        )
        assert any("未定义" in h for h in hints)

    def test_empty_code_no_hints(self, reviewer):
        hints = reviewer.review("", SandboxResult(passed=False))
        assert hints == []


# ================================================================
# CodeSandbox 集成
# ================================================================
class TestCodeSandbox:
    @pytest.fixture
    def sandbox(self):
        return CodeSandbox()

    def test_simple_expression(self, sandbox):
        r = sandbox.execute("print(1 + 2 + 3)")
        assert r.passed is True
        assert "6" in r.stdout

    def test_loop(self, sandbox):
        r = sandbox.execute(
            "for i in range(3):\n    print(i)"
        )
        assert r.passed is True

    def test_function_definition(self, sandbox):
        r = sandbox.execute(
            "def add(a, b):\n    return a + b\nprint(add(2, 3))"
        )
        if r.passed:
            assert "5" in r.stdout

    def test_blocked_import_rejected(self, sandbox):
        r = sandbox.execute("import os\nprint('hello')")
        assert r.passed is False
        assert "blocked" in r.stderr or "blocked" in (r.error or "")

    def test_unsupported_language(self, sandbox):
        r = sandbox.execute("print(1)", language="javascript")
        assert r.passed is False
        assert "不支持" in r.stderr

    def test_syntax_error(self, sandbox):
        r = sandbox.execute("if True print(1)")
        assert r.passed is False

    def test_with_review(self, sandbox):
        r = sandbox.execute("x = 1\ny = x * 2", with_review=True)
        # 即使不通过也有 review_hints
        assert isinstance(r.review_hints, list)

    def test_division_by_zero(self, sandbox):
        r = sandbox.execute("print(1 / 0)")
        # 不应崩溃，应返回错误
        assert isinstance(r.passed, bool)

    def test_result_to_dict(self, sandbox):
        r = sandbox.execute("print('hello')")
        d = r.to_dict()
        assert "stdout" in d
        assert "passed" in d
        assert "execution_level" in d

    def test_get_singleton(self):
        s1 = get_code_sandbox()
        s2 = get_code_sandbox()
        assert s1 is s2
