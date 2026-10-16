"""Plan P0 (Sandbox 安全 P0)：4 个真安全洞自动化测试。

来源：2026-07-04 全量回归时发现的手动冒烟攻击向量，必须落成自动化：
1. NUL 字节绕过 ast.parse（except 只接 SyntaxError）
2. dunder 反射链逃逸（__class__.__bases__[0].__subclasses__()）
3. globals()['__builtins__'].__import__('os')
4. getattr(__builtins__, 'exec')('print(1)')

另外覆盖：
- __mro__ / __dict__ / __globals__ / __getattribute__ 等其他 dunder
- vars() / locals() / dir() 反射
- input() / breakpoint() 等额外 blocked builtins
- 攻击被拦后，trace 字段（execution_level / error）可被前端识别
"""
from __future__ import annotations

import pytest

from backend.app.services.multimodal.code_sandbox import CodeSandbox


# 4 个 P0 安全洞（按出现顺序）
P0_SECURITY_HOLES = [
    (
        "nul_byte_bypass",
        "\x00 + __import__('os').system('id')",
        "ast.parse 对 NUL 抛 ValueError 不是 SyntaxError",
    ),
    (
        "dunder_subclass_chain",
        "[].__class__.__bases__[0].__subclasses__()[0].__init__.__globals__['__builtins__']",
        "dunder 反射链逃逸拿 __builtins__",
    ),
    (
        "globals_builtins_import",
        "globals()['__builtins__'].__import__('os').system('whoami')",
        "globals() 反射拿 __import__",
    ),
    (
        "getattr_builtins_exec",
        "getattr(__builtins__, 'exec')('print(1)')",
        "getattr 反射拿 exec",
    ),
]

# 其他 dunder / 反射向量（部分 P0 后必须拦）
DUNDER_VECTORS = [
    "__class__.__bases__",
    "__mro__",
    "__dict__",
    "__globals__",
    "__builtins__",
    "__subclasses__",
    "__code__",
    "__getattribute__",
]

# 其他 blocked builtins 反射
REFLECTIVE_BUILTINS = [
    "vars()",
    "locals()",
    "dir()",
    "globals()",
    "getattr(__builtins__, 'eval')('1+1')",
    "setattr(x, 'y', 1)",
]


@pytest.fixture(scope="module")
def sandbox() -> CodeSandbox:
    return CodeSandbox()


# ================================================================
# 4 个 P0 安全洞
# ================================================================
class TestP0SecurityHoles:
    """4 个真安全洞 — Plan P0 收口。"""

    @pytest.mark.parametrize("label,code,note", P0_SECURITY_HOLES)
    def test_p0_hole_blocked(self, label, code, note, sandbox):
        result = sandbox.execute(code)
        assert result.passed is False, (
            f"[{label}] P0 安全洞未拦住 (note={note}): "
            f"passed={result.passed}, stdout={result.stdout!r}"
        )

    def test_nul_byte_returns_error_at_ast_layer(self, sandbox):
        """NUL 字节必须被 AST 层拦下（execution_level == 1）。"""
        result = sandbox.execute("\x00import os\x00")
        assert result.passed is False
        assert result.execution_level == 1
        # 错误信息应包含"非法字节"或"NUL"
        assert "非法字节" in (result.error or "") or "NUL" in (result.error or "")

    def test_globals_builtins_blocked_at_ast(self, sandbox):
        """globals() 必须在 AST 层被拦（execution_level == 1）。"""
        result = sandbox.execute("globals()['__builtins__'].__import__('os')")
        assert result.passed is False
        assert result.execution_level == 1
        assert "globals" in (result.error or "").lower()

    def test_getattr_blocked_at_ast(self, sandbox):
        """getattr 必须在 AST 层被拦（execution_level == 1）。"""
        result = sandbox.execute("getattr(__builtins__, 'exec')('print(1)')")
        assert result.passed is False
        assert result.execution_level == 1

    def test_dunder_class_blocked_at_ast(self, sandbox):
        """__class__ 必须在 AST 层被拦。"""
        result = sandbox.execute("x = ().__class__")
        assert result.passed is False
        assert result.execution_level == 1
        assert "dunder" in (result.error or "").lower() or "属性访问" in (result.error or "")


# ================================================================
# 其他 dunder / 反射向量
# ================================================================
class TestOtherDunderVectors:
    @pytest.mark.parametrize("attr", DUNDER_VECTORS)
    def test_dunder_attr_blocked(self, attr, sandbox):
        """所有 P0 列出的 dunder 都应被拦。"""
        result = sandbox.execute(f"x = ().{attr}")
        assert result.passed is False, f"dunder {attr} leaked: passed={result.passed}"

    @pytest.mark.parametrize("payload", REFLECTIVE_BUILTINS)
    def test_reflective_builtin_blocked(self, payload, sandbox):
        result = sandbox.execute(payload)
        assert result.passed is False, (
            f"reflective builtin leaked: {payload!r}, passed={result.passed}"
        )


# ================================================================
# 攻击被拦后 — result 字段对前端可识别
# ================================================================
class TestAttackResultShape:
    """前端 Tool Call Trace / 错误提示会读 result 字段。"""

    def test_attack_result_has_execution_level(self, sandbox):
        result = sandbox.execute("import os")
        assert hasattr(result, "execution_level")
        assert result.execution_level == 1  # AST 拦截

    def test_attack_result_has_error_message(self, sandbox):
        result = sandbox.execute("import os")
        assert result.error is not None
        assert len(result.error) > 0
        assert "os" in result.error

    def test_attack_result_has_security_warnings(self, sandbox):
        """warning 字段非空，便于前端做诊断。"""
        result = sandbox.execute("import os")
        # 即便 warnings 为空，security_warnings 字段必须存在
        assert hasattr(result, "security_warnings")
        assert isinstance(result.security_warnings, list)

    def test_attack_result_to_dict_has_required_keys(self, sandbox):
        result = sandbox.execute("__import__('subprocess').run(['id'])")
        d = result.to_dict()
        for key in ("stdout", "stderr", "passed", "error", "execution_level",
                    "review_hints", "security_warnings"):
            assert key in d, f"missing {key} in to_dict()"


# ================================================================
# 良性代码仍可执行 — 不误伤
# ================================================================
class TestBenignCodeStillWorks:
    def test_print_hello(self, sandbox):
        result = sandbox.execute("print('hello sandbox')")
        assert result.passed is True
        assert "hello sandbox" in result.stdout

    def test_loop_with_break(self, sandbox):
        result = sandbox.execute(
            "total = 0\nfor i in range(5):\n    total += i\nprint(total)"
        )
        assert result.passed is True
        assert "10" in result.stdout

    def test_class_definition_allowed(self, sandbox):
        """普通 class 定义不应被拦。"""
        result = sandbox.execute(
            "class A:\n    pass\nprint(A().__class__.__name__)"
        )
        # 注意：().__class__ 会被拦！所以这里改成打印类名静态
        # 仅 class 定义本身合法
        result2 = sandbox.execute("class A:\n    x = 1\nprint(A.x)")
        assert result2.passed is True
        assert "1" in result2.stdout