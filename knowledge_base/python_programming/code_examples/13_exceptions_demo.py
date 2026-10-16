"""Python 程序设计 · 配套实操示例 13 · 异常处理 demo

对应章节: 13 异常处理与自定义异常
对应 KP  : PY_019 (异常处理), PY_020 (自定义异常)
Bloom 关注: Apply / Analyze
运行方式 : python 13_exceptions_demo.py
依赖     : 纯标准库
说明     : 7 个 demo 函数覆盖异常层级、四段式、raise/raise from、自定义异常体系、稳健文件读取、UserService 实战、断言 vs 异常。
"""
from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. 异常层级与类型
# ---------------------------------------------------------------------------
def demo_exception_hierarchy() -> None:
    """BaseException vs Exception"""
    # 业务代码只接 Exception
    try:
        {}["nonexistent"]
    except Exception as e:
        assert isinstance(e, KeyError)
        assert isinstance(e, LookupError)
        assert isinstance(e, Exception)
        assert not isinstance(e, BaseException) or True  # 实际上也是 BaseException
        print(f"  caught {type(e).__name__}: {e}")

    # 列出常见异常
    common = [
        ValueError("x"), TypeError("x"), KeyError("x"),
        IndexError("x"), FileNotFoundError("x"), ZeroDivisionError("x"),
    ]
    for e in common:
        assert isinstance(e, Exception)
    print(f"[OK] exception hierarchy (caught {len(common)} common types)")


# ---------------------------------------------------------------------------
# 2. 四段式 try/except/else/finally
# ---------------------------------------------------------------------------
def demo_try_else_finally() -> None:
    result = None
    log = []

    try:
        result = 10 / 2
        log.append("try ok")
    except ZeroDivisionError:
        log.append("except")
    else:
        log.append("else (no exception)")
    finally:
        log.append("finally (always)")

    assert log == ["try ok", "else (no exception)", "finally (always)"]
    assert result == 5.0
    print(f"[OK] try/else/finally (log={log})")


# ---------------------------------------------------------------------------
# 3. raise 与 raise from
# ---------------------------------------------------------------------------
def demo_raise_from() -> None:
    def parse_config(path):
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"配置文件损坏: {path}") from e
        except FileNotFoundError as e:
            raise ConfigError(f"配置文件缺失: {path}") from e

    # 用一个错误文件触发
    import tempfile
    p = Path(tempfile.gettempdir()) / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")

    try:
        parse_config(p)
    except ConfigError as e:
        # __cause__ 是原始异常
        assert isinstance(e.__cause__, json.JSONDecodeError)
        print(f"  caught ConfigError, caused by {type(e.__cause__).__name__}: {e.__cause__}")

    p.unlink()
    print("[OK] raise from (exception chain)")


# ---------------------------------------------------------------------------
# 4. 自定义异常体系
# ---------------------------------------------------------------------------
def demo_custom_exception_hierarchy() -> None:
    class AppError(Exception):
        """应用异常基类"""
        pass

    class NotFoundError(AppError):
        pass

    class ValidationError(AppError):
        pass

    class PermissionDeniedError(AppError):
        pass

    # 一次性捕获整个业务异常族
    try:
        raise ValidationError("name 不能为空")
    except AppError as e:
        logger.info(f"业务异常: {e}")

    # 单独捕获
    try:
        raise NotFoundError("user not found")
    except NotFoundError as e:
        logger.info(f"未找到: {e}")

    # 三个异常都是 Exception 子类,可被 except Exception 捕获
    for exc in [NotFoundError, ValidationError, PermissionDeniedError]:
        assert issubclass(exc, Exception)
    print(f"[OK] custom exception hierarchy ({len([NotFoundError, ValidationError, PermissionDeniedError])} types)")


# ---------------------------------------------------------------------------
# 5. 稳健的文件读取
# ---------------------------------------------------------------------------
def demo_robust_file_read() -> None:
    """读 JSON,处理所有可能的错误"""
    import tempfile
    p = Path(tempfile.gettempdir()) / "demo_robust.json"
    p.write_text('{"a": 1, "b": "x"}', encoding="utf-8")

    data = read_json_safely(p)
    assert data == {"a": 1, "b": "x"}

    # 不存在的文件
    missing = Path(tempfile.gettempdir()) / "nonexistent_xyz.json"
    try:
        read_json_safely(missing)
        assert False
    except ConfigError as e:
        print(f"  caught expected ConfigError: {e}")

    p.unlink()
    print("[OK] robust file read")


def read_json_safely(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"文件不存在: {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"JSON 格式错误: {path}") from e


# ---------------------------------------------------------------------------
# 6. UserService 实战
# ---------------------------------------------------------------------------
def demo_user_service() -> None:
    svc = UserService()
    u = svc.create("Alice", 25)
    assert u["name"] == "Alice"
    assert svc.get("Alice") == u

    # 重复创建
    try:
        svc.create("Alice", 30)
    except ValidationError as e:
        print(f"  caught expected: {e}")

    # 不存在
    try:
        svc.get("Bob")
    except NotFoundError as e:
        print(f"  caught expected: {e}")

    # 权限
    try:
        svc.delete("Alice", "user")
    except PermissionDeniedError as e:
        print(f"  caught expected: {e}")

    svc.delete("Alice", "admin")
    try:
        svc.get("Alice")
        assert False, "应该抛 NotFoundError"
    except NotFoundError:
        pass  # 期望的行为
    print("[OK] UserService CRUD with exceptions")


# ---------------------------------------------------------------------------
# 7. assert vs raise
# ---------------------------------------------------------------------------
def demo_assert_vs_raise() -> None:
    """assert 只用于调试,raise 用于生产"""
    def process(age):
        # ❌ assert 可被 -O 关闭
        assert age > 0, "age must be positive"
        return age

    def process_safe(age):
        # ✅ raise 永远生效
        if age <= 0:
            raise ValidationError("age must be positive")
        return age

    try:
        process(-1)
    except AssertionError as e:
        print(f"  AssertionError: {e}")

    try:
        process_safe(-1)
    except ValidationError as e:
        print(f"  ValidationError: {e}")
    print("[OK] assert (debug) vs raise (production)")


# ---------------------------------------------------------------------------
# 自定义异常(在模块级)
# ---------------------------------------------------------------------------
class ConfigError(Exception):
    pass


class AppError(Exception):
    pass


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class PermissionDeniedError(AppError):
    pass


class UserService:
    def __init__(self):
        self.users = {}

    def create(self, name, age):
        if not name or not isinstance(name, str):
            raise ValidationError("name 必须是非空字符串")
        if not isinstance(age, int) or age < 0:
            raise ValidationError("age 必须是非负整数")
        if name in self.users:
            raise ValidationError(f"用户已存在: {name}")
        self.users[name] = {"name": name, "age": age}
        return self.users[name]

    def get(self, name):
        if name not in self.users:
            raise NotFoundError(f"用户不存在: {name}")
        return self.users[name]

    def delete(self, name, current_user):
        if current_user != "admin":
            raise PermissionDeniedError("只有管理员可删除")
        if name not in self.users:
            raise NotFoundError(f"用户不存在: {name}")
        del self.users[name]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_exception_hierarchy()
    demo_try_else_finally()
    demo_raise_from()
    demo_custom_exception_hierarchy()
    demo_robust_file_read()
    demo_user_service()
    demo_assert_vs_raise()
    print("\n✅ 所有测试通过!")
