"""
Code Sandbox — 三级安全执行环境 (Phase 1 重构版 v2)

安全模型:
    Level 1: AST 静态分析 — 阻塞危险模块/函数，毫秒级
    Level 2: RestrictedPython — 受限字节码执行（推荐）
    Level 3: subprocess — 隔离子进程执行（降级）

设计:
    - SandboxPolicy 配置化安全策略（可通过 YAML 覆盖）
    - SandboxResult 标准化输出，包含 AI 代码审查建议
    - 每个 Level 独立失败可降级到下一级
    - 全局单例 + 测试可注入

安全参考:
    - RestrictedPython (Zope project)
    - OWASP Code Injection Prevention
    - Python AST Security Analysis
"""
from __future__ import annotations

import ast
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ================================================================
# 数据模型
# ================================================================
@dataclass
class SandboxResult:
    """沙箱执行结果"""
    stdout: str = ""
    stderr: str = ""
    passed: bool = False
    error: Optional[str] = None
    exit_code: int = 0
    execution_level: int = 0          # 1/2/3 — 实际使用的安全级别
    review_hints: List[str] = field(default_factory=list)  # AI 代码审查建议
    security_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "passed": self.passed,
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_level": self.execution_level,
            "review_hints": self.review_hints,
            "security_warnings": self.security_warnings,
        }


@dataclass
class SandboxPolicy:
    """沙箱安全策略配置

    可通过 YAML 覆盖默认值（configs/sandbox.yaml）
    """
    # 阻塞的顶级模块
    blocked_modules: Tuple[str, ...] = (
        "os", "sys", "subprocess", "shutil", "ctypes",
        "socket", "requests", "urllib", "http", "pickle",
        "importlib", "io", "pathlib", "glob", "fnmatch",
        "asyncio", "threading", "multiprocessing", "concurrent",
    )
    # 阻塞的内置函数
    blocked_builtins: Tuple[str, ...] = (
        "exec", "eval", "compile", "__import__", "open",
        "input", "breakpoint",
        # 反射 / 名字空间逃逸向量（即使 RestrictedPython 模式不可用也得拦）
        "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir",
    )
    # 阻塞的 dunder 属性访问（防止 __class__.__bases__[0].__subclasses__() 这种链式逃逸）
    blocked_dunder_attrs: Tuple[str, ...] = (
        "__class__", "__bases__", "__subclasses__", "__mro__",
        "__dict__", "__globals__", "__builtins__", "__code__",
        "__func__", "__self__", "__module__", "__init_subclass__",
        "__getattribute__", "__getattr__",
    )
    # DoS 保护：序列字面量 * N 时 N 的上限（防 [0]*10**9 内存炸弹）
    max_literal_multiplier: int = 10_000_000
    # DoS 保护：range(N) 时 N 的上限（防 range(10**12) 死循环）
    max_range_argument: int = 10_000_000
    # 安全的全局变量（RestrictedPython 模式）
    safe_globals: Tuple[str, ...] = (
        "True", "False", "None",
        "abs", "all", "any", "bin", "bool", "chr", "dict", "dir",
        "enumerate", "filter", "float", "format", "frozenset",
        "getattr", "hasattr", "hash", "hex", "id", "int",
        "isinstance", "issubclass", "iter", "len", "list",
        "map", "max", "min", "next", "oct", "ord", "pow",
        "print", "range", "repr", "reversed", "round",
        "set", "sorted", "str", "sum", "tuple", "type", "zip",
        "Exception", "ValueError", "TypeError", "KeyError",
        "IndexError", "StopIteration",
    )
    # 最大代码长度
    max_code_length: int = 10000
    # 最大输出长度
    max_output_length: int = 5000
    # 执行超时（秒）
    timeout_seconds: int = 5


# ================================================================
# AST 分析器 — Level 1
# ================================================================
class ASTSecurityAnalyzer:
    """AST 静态安全分析

    在代码执行前完成安全检查:
    - 语法错误检测
    - 危险模块导入检测
    - 危险函数调用检测
    - 代码长度限制
    """

    def __init__(self, policy: SandboxPolicy):
        self._policy = policy

    def analyze(self, code: str) -> Tuple[bool, str, List[str]]:
        """分析代码安全性

        Returns:
            (safe, error_message, warnings)
        """
        warnings: List[str] = []

        # 0. 长度检查
        if len(code) > self._policy.max_code_length:
            return False, f"代码过长 ({len(code)} > {self._policy.max_code_length})", warnings

        if not code.strip():
            return False, "代码为空", warnings

        if "\x00" in code:
            return False, "代码包含非法字节 (NUL)", warnings

        # 1. 语法检查
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return False, f"语法错误 L{exc.lineno}: {exc.msg}", warnings
        except ValueError as exc:
            # ast.parse 对包含 NUL 字节的 source 抛 ValueError (bpo-94215)
            return False, f"代码包含非法字节 (NUL 等): {exc}", warnings

        # 2. AST 遍历 — 危险模块
        for node in ast.walk(tree):
            # import os / import os.path
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in self._policy.blocked_modules:
                        return False, f"blocked: import {alias.name}", warnings

            # from os import ...
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in self._policy.blocked_modules:
                        return False, f"blocked: from {node.module} import ...", warnings

            # exec() / eval() / open() 等
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in self._policy.blocked_builtins:
                    return False, f"blocked: {node.func.id}()", warnings

            # 属性访问: os.system() 等（即便没 import 也标记）
            if isinstance(node, ast.Attribute):
                # 拦截 dunder 链式逃逸（__class__.__bases__[0].__subclasses__() 等）
                if node.attr in self._policy.blocked_dunder_attrs:
                    return False, f"blocked: 属性访问 {node.attr} (dunder 反射向量)", warnings
                if isinstance(node.value, ast.Name):
                    if node.value.id in self._policy.blocked_modules:
                        warnings.append(f"检测到 {node.value.id}.{node.attr} 调用")

            # ---- DoS 模式 1: while True / while 1 没有 break/return/raise ----
            if isinstance(node, (ast.While, )) and self._is_constant_truthy(node.test):
                if not self._loop_has_exit(node):
                    return False, "blocked: 检测到无限循环 (while True 无 break/return)", warnings

            # ---- DoS 模式 2: 序列字面量 * 大整数（[0]*10**9 内存炸弹）----
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                multiplier = self._static_int_value(node.right) or self._static_int_value(node.left)
                if multiplier is not None and multiplier > self._policy.max_literal_multiplier:
                    target_is_seq = (
                        isinstance(node.left, (ast.List, ast.Tuple, ast.Constant))
                        or isinstance(node.right, (ast.List, ast.Tuple, ast.Constant))
                    )
                    if target_is_seq:
                        return False, (
                            f"blocked: 序列乘法过大 ({multiplier} > "
                            f"{self._policy.max_literal_multiplier})，疑似内存炸弹"
                        ), warnings

            # ---- DoS 模式 3: range(大整数) ----
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "range"
                and node.args
            ):
                last_arg = self._static_int_value(node.args[-1])
                if last_arg is not None and last_arg > self._policy.max_range_argument:
                    return False, (
                        f"blocked: range({last_arg}) 上界过大 "
                        f"(> {self._policy.max_range_argument})"
                    ), warnings

        return True, "", warnings

    # ── DoS 模式辅助 ────────────────────────────────────────
    @staticmethod
    def _is_constant_truthy(node: ast.AST) -> bool:
        """判断表达式是否为常量真值（True / 1 / 非零数字 / 非空字符串）"""
        if isinstance(node, ast.Constant):
            return bool(node.value)
        # Python <3.8 的 ast.NameConstant 兜底
        if isinstance(node, ast.Name) and node.id == "True":
            return True
        return False

    @staticmethod
    def _loop_has_exit(loop_node: ast.AST) -> bool:
        """判断循环体内是否有 break/return/raise/sys.exit 等显式出口"""
        for child in ast.walk(loop_node):
            if isinstance(child, (ast.Break, ast.Return, ast.Raise)):
                return True
        return False

    @staticmethod
    def _static_int_value(node: ast.AST) -> Optional[int]:
        """尝试在 AST 层面静态求值整数表达式（仅支持常量和 a**b 幂运算）。

        例如:
            ast.Constant(10**9)        → 1000000000
            ast.BinOp(10 ** 9)         → 1000000000
        若无法静态求值，返回 None。
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            base = ASTSecurityAnalyzer._static_int_value(node.left)
            exp = ASTSecurityAnalyzer._static_int_value(node.right)
            if base is not None and exp is not None and 0 <= exp <= 100:
                try:
                    return base ** exp
                except (OverflowError, ValueError):
                    return None
        return None


# ================================================================
# RestrictedPython 执行器 — Level 2
# ================================================================
class RestrictedPythonRunner:
    """RestrictedPython 安全执行

    使用 RestrictedPython 编译受限字节码:
    - 限制全局变量
    - 限制内置函数
    - 捕获 stdout
    """

    def __init__(self, policy: SandboxPolicy):
        self._policy = policy
        self._available = self._check_availability()

    @staticmethod
    def _check_availability() -> bool:
        try:
            from RestrictedPython import compile_restricted, safe_globals  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def available(self) -> bool:
        return self._available

    def execute(self, code: str, timeout: int = 5) -> SandboxResult:
        """在 RestrictedPython 环境中执行代码

        正确接入 RestrictedPython 的安全钩子:
            _print_       — print() 重写后的 PrintCollector 工厂（输出重定向到 buf）
            _getattr_     — safer_getattr, 阻止访问以 _ 开头的属性
            _write_       — full_write_guard, 限制属性赋值
            _getiter_     — 受限迭代器（for/推导式必需）
            _inplacevar_  — += / -= 等原地运算（增强赋值必需）
        """
        import io
        import sys

        if not self._available:
            return SandboxResult(
                passed=False,
                error="RestrictedPython 未安装",
                execution_level=2,
            )

        from RestrictedPython import compile_restricted, safe_builtins
        from RestrictedPython.Guards import (
            full_write_guard,
            guarded_iter_unpack_sequence,
            safer_getattr,
        )

        old_stdout = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf

        class _PrintCollector:
            """RestrictedPython print() 重写目标

            compile_restricted 把 ``print(x)`` 改写成
            ``_print_()._call_print(x)``；本类的实例负责
            把内容写入本地 buf，而非真实 stdout。
            """

            def __init__(self, _getattr: object = safer_getattr) -> None:
                self.txt: List[str] = []

            def write(self, data: str) -> None:
                self.txt.append(data)

            def _call_print(self, *objects: object, **kwargs: object) -> None:
                sep = kwargs.pop("sep", " ")  # type: ignore[arg-type]
                end = kwargs.pop("end", "\n")  # type: ignore[arg-type]
                buf.write(sep.join(str(o) for o in objects) + end)  # type: ignore[operator]

        try:
            bytecode = compile_restricted(code, "<sandbox>", "exec")

            # `_inplacevar_(op_string, var, val)`：RestrictedPython 把 `x += y`
            # 改写成 `x = _inplacevar_('+=', x, y)`，钩子必须按 op_string 分发。
            _INPLACE_OPS: Dict[str, Any] = {
                "+=": lambda a, b: a + b,
                "-=": lambda a, b: a - b,
                "*=": lambda a, b: a * b,
                "/=": lambda a, b: a / b,
                "//=": lambda a, b: a // b,
                "%=": lambda a, b: a % b,
                "**=": lambda a, b: a ** b,
                "&=": lambda a, b: a & b,
                "|=": lambda a, b: a | b,
                "^=": lambda a, b: a ^ b,
                "<<=": lambda a, b: a << b,
                ">>=": lambda a, b: a >> b,
                "@=": lambda a, b: a @ b,
            }

            def _inplacevar_(op: str, x: Any, y: Any) -> Any:
                fn = _INPLACE_OPS.get(op)
                if fn is None:
                    raise SyntaxError(f"unsupported augmented operator: {op}")
                return fn(x, y)

            globals_dict: Dict[str, Any] = {
                "__name__": "__sandbox__",
                "__builtins__": safe_builtins,
                # RestrictedPython 安全钩子
                "_print_": _PrintCollector,
                "_getattr_": safer_getattr,
                "_write_": full_write_guard,
                "_getiter_": iter,
                "_inplacevar_": _inplacevar_,
                "_unpack_sequence_": guarded_iter_unpack_sequence,
                # safe_builtins 默认不含 range/len/print 等常用函数，
                # 单独从 builtins 模块补回（已 AST 层禁用 open/exec/eval 等危险函数）
                "range": range,
                "len": len,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "sorted": sorted,
                "reversed": reversed,
            }

            exec(bytecode, globals_dict)  # noqa: S102 — 受限字节码，已通过 AST 分析

            return SandboxResult(
                stdout=buf.getvalue()[: self._policy.max_output_length],
                stderr="",
                passed=True,
                exit_code=0,
                execution_level=2,
            )
        except Exception as exc:
            return SandboxResult(
                stdout=buf.getvalue()[:1000],
                stderr=f"{type(exc).__name__}: {exc}",
                passed=False,
                error=str(exc),
                execution_level=2,
            )
        finally:
            sys.stdout = old_stdout


# ================================================================
# Subprocess 执行器 — Level 3（降级）
# ================================================================
class SubprocessRunner:
    """子进程隔离执行

    当 RestrictedPython 不可用时降级到此。
    安全: 独立的 Python 进程，OS 级隔离。
    """

    def __init__(self, policy: SandboxPolicy):
        self._policy = policy

    def execute(self, code: str, timeout: int = 5) -> SandboxResult:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False,
        )
        try:
            tmp.write(code)
            tmp.close()

            result = subprocess.run(
                ["python", tmp.name],
                capture_output=True,
                timeout=timeout,
                text=True,
            )

            return SandboxResult(
                stdout=(result.stdout or "")[:self._policy.max_output_length],
                stderr=(result.stderr or "")[:self._policy.max_output_length],
                passed=result.returncode == 0,
                exit_code=result.returncode,
                error=None if result.returncode == 0 else f"exit={result.returncode}",
                execution_level=3,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                stdout="",
                stderr=f"执行超时 (>{timeout}s)",
                passed=False,
                error="timeout",
                execution_level=3,
            )
        except Exception as exc:
            return SandboxResult(
                stdout="",
                stderr=str(exc),
                passed=False,
                error=str(exc),
                execution_level=3,
            )
        finally:
            try:
                Path(tmp.name).unlink()
            except OSError:
                pass


# ================================================================
# AI 代码审查器
# ================================================================
class CodeReviewer:
    """自动化代码审查建议生成

    规则版（Phase 1）:
    - 检查是否有 print / 变量命名 / 注释
    - 不调 LLM，毫秒级

    Phase 2: 接入 LLM 做深度代码审查
    """

    def review(self, code: str, result: SandboxResult) -> List[str]:
        """生成代码审查建议"""
        hints: List[str] = []

        if not code.strip():
            return hints

        # 检查是否有输出语句
        if "print" not in code:
            hints.append("建议添加 print() 输出结果，便于验证")

        # 检查变量命名
        lines = [l.strip() for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
        if lines:
            # 检查是否有单字母变量（非循环变量）
            for line in lines:
                if "=" in line:
                    var_part = line.split("=")[0].strip()
                    if len(var_part) == 1 and var_part.isalpha() and var_part not in ("i", "j", "k", "n", "x", "y", "z"):
                        hints.append(f"变量名 '{var_part}' 建议使用更具描述性的名称")
                        break

        # 检查是否有注释（超过 5 行无注释 → 建议）
        code_lines = code.split("\n")
        comment_lines = sum(1 for l in code_lines if l.strip().startswith("#"))
        total_lines = sum(1 for l in code_lines if l.strip())
        if total_lines > 5 and comment_lines == 0:
            hints.append("建议添加注释说明关键步骤")

        # 检查异常处理
        if result.passed is False and result.error:
            if "NameError" in (result.stderr + (result.error or "")):
                hints.append("代码中使用了未定义的变量，请检查拼写")
            if "SyntaxError" in (result.stderr + (result.error or "")):
                hints.append("语法错误，请检查缩进、括号匹配、冒号等")
            if "TypeError" in (result.stderr + (result.error or "")):
                hints.append("类型不匹配，请检查函数参数和运算符")

        return hints


# ================================================================
# CodeSandbox — 统一入口
# ================================================================
class CodeSandbox:
    """三级安全代码沙箱

    用法:
        sandbox = CodeSandbox()
        result = sandbox.execute("print(1+1)")
        assert result.passed
        print(result.stdout)  # "2"

    语言支持:
        - python: 完整三级安全执行
        - 其他: 返回不支持提示

    安全保证:
        - AST 静态分析: 阻止 import os/subprocess/socket 等
        - RestrictedPython: 字节码级限制（优先）
        - subprocess: OS 级隔离（降级）
    """

    def __init__(self, policy: Optional[SandboxPolicy] = None):
        self._policy = policy or SandboxPolicy()
        self._ast = ASTSecurityAnalyzer(self._policy)
        self._restricted = RestrictedPythonRunner(self._policy)
        self._subprocess = SubprocessRunner(self._policy)
        self._reviewer = CodeReviewer()

    @property
    def restricted_available(self) -> bool:
        return self._restricted.available

    def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 5,
        with_review: bool = True,
    ) -> SandboxResult:
        """执行代码

        Args:
            code: 源代码
            language: 编程语言（当前仅支持 python）
            timeout: 超时秒数
            with_review: 是否生成 AI 审查建议

        Returns:
            SandboxResult
        """
        if language != "python":
            return SandboxResult(
                stdout="",
                stderr=f"不支持的语言: {language}",
                passed=False,
                error=f"unsupported_language: {language}",
            )

        # ---- Level 1: AST 分析 ----
        safe, error, warnings = self._ast.analyze(code)
        if not safe:
            result = SandboxResult(
                stdout="",
                stderr=error,
                passed=False,
                error=error,
                execution_level=1,
                security_warnings=warnings,
            )
            if with_review:
                result.review_hints = self._reviewer.review(code, result)
            return result

        # ---- Level 2: RestrictedPython ----
        if self._restricted.available:
            result = self._restricted.execute(code, timeout)
        else:
            # ---- Level 3: subprocess ----
            logger.warning(
                "[CodeSandbox] RestrictedPython 不可用，降级到 subprocess"
            )
            result = self._subprocess.execute(code, timeout)

        result.security_warnings = warnings

        # AI 审查
        if with_review:
            result.review_hints = self._reviewer.review(code, result)

        return result

    def execute_with_ai_fix(
        self,
        code: str,
        language: str = "python",
        timeout: int = 5,
    ) -> SandboxResult:
        """执行代码，失败时尝试 AI 自动修复

        Phase 2: 接入 LLM 根据错误信息自动生成修复建议
        Phase 1: 仅提供 review_hints
        """
        result = self.execute(code, language, timeout, with_review=True)
        # Phase 2: if not result.passed: result = self._ai_fix(code, result)
        return result


# ================================================================
# 全局单例
# ================================================================
_sandbox: Optional[CodeSandbox] = None


def get_code_sandbox(policy: Optional[SandboxPolicy] = None) -> CodeSandbox:
    """获取 CodeSandbox 单例"""
    global _sandbox
    if _sandbox is None:
        _sandbox = CodeSandbox(policy=policy)
    return _sandbox


def reset_sandbox() -> None:
    """测试用：重置单例"""
    global _sandbox
    _sandbox = None
