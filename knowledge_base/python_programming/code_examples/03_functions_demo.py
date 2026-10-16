"""Python 程序设计 · 配套实操示例 03 · 函数 demo

对应章节: 03 函数定义与参数
对应 KP  : PY_005 (函数定义与参数)
Bloom 关注: Apply / Analyze
运行方式 : python 03_functions_demo.py
依赖     : 纯标准库
说明     : 7 个 demo 函数覆盖 *args/**kwargs、默认参数、闭包、lambda、函数式工具、partial、文档字符串。
"""
from __future__ import annotations

from functools import partial, reduce


# ---------------------------------------------------------------------------
# 1. 默认参数与关键字参数
# ---------------------------------------------------------------------------
def demo_default_kwargs() -> None:
    """演示默认参数陷阱与正确写法"""
    # ❌ 可变默认参数陷阱
    def bad(item, lst=[]):
        lst.append(item)
        return lst

    a = bad(1)
    b = bad(2)
    # 注意:a 和 b 都指向同一个共享 list,两次 append 后都变 [1, 2]
    assert a == [1, 2]  # a 也被污染
    assert b == [1, 2]  # 残留状态!
    assert a is b  # 返回的是同一个对象

    # ✅ 正确写法
    def good(item, lst=None):
        if lst is None:
            lst = []
        lst.append(item)
        return lst

    a = good(1)
    b = good(2)
    assert a == [1]
    assert b == [2]
    print("[OK] default args (mutable default trap)")


# ---------------------------------------------------------------------------
# 2. *args / **kwargs + 强制关键字
# ---------------------------------------------------------------------------
def demo_args_kwargs() -> None:
    def log(level, *messages, **fields):
        msg = " ".join(str(m) for m in messages)
        fld = " ".join(f"{k}={v}" for k, v in fields.items())
        return f"{level} | {msg} | {fld}"

    result = log("INFO", "user", "login", user="alice", ip="127.0.0.1")
    assert result == "INFO | user login | user=alice ip=127.0.0.1"

    # 强制关键字参数
    def divide(a, b, *, precision=2):
        return round(a / b, precision)

    assert divide(10, 3) == 3.33
    assert divide(10, 3, precision=4) == 3.3333
    print("[OK] *args/**kwargs + keyword-only")


# ---------------------------------------------------------------------------
# 3. 闭包:make_counter
# ---------------------------------------------------------------------------
def demo_closure() -> None:
    """闭包捕获定义时的环境"""
    def make_counter(start=0):
        n = start
        def counter():
            nonlocal n
            n += 1
            return n
        return counter

    c = make_counter(10)
    assert c() == 11
    assert c() == 12
    assert c() == 13

    # 独立闭包各自保持状态
    d = make_counter(100)
    assert d() == 101
    assert c() == 14  # c 仍是 13 → 14
    print("[OK] closure (counter)")


# ---------------------------------------------------------------------------
# 4. lambda + sorted/map/filter
# ---------------------------------------------------------------------------
def demo_lambda_higher_order() -> None:
    """lambda 配合 sorted / map / filter"""
    students = [("Alice", 85), ("Bob", 92), ("Charlie", 78), ("Dave", 92)]
    # 按分数降序,同分按姓名升序
    sorted_students = sorted(students, key=lambda s: (-s[1], s[0]))
    assert sorted_students[0] == ("Bob", 92)  # Bob 在 Dave 前(B<D)
    assert sorted_students[1] == ("Dave", 92)
    assert sorted_students[2] == ("Alice", 85)
    assert sorted_students[3] == ("Charlie", 78)

    nums = [1, 2, 3, 4, 5]
    squared = list(map(lambda x: x**2, nums))
    evens = list(filter(lambda x: x % 2 == 0, nums))
    assert squared == [1, 4, 9, 16, 25]
    assert evens == [2, 4]
    print("[OK] lambda + sorted/map/filter")


# ---------------------------------------------------------------------------
# 5. functools.reduce + partial
# ---------------------------------------------------------------------------
def demo_reduce_partial() -> None:
    """reduce 与 partial 偏函数"""
    total = reduce(lambda a, b: a + b, [1, 2, 3, 4, 5])
    assert total == 15

    my_max = reduce(lambda a, b: a if a > b else b, [3, 1, 4, 1, 5, 9, 2, 6])
    assert my_max == 9

    # partial
    def power(base, exp):
        return base ** exp

    square = partial(power, exp=2)
    cube = partial(power, exp=3)
    assert square(5) == 25
    assert cube(5) == 125
    print("[OK] reduce + partial")


# ---------------------------------------------------------------------------
# 6. 作用域:LEGB
# ---------------------------------------------------------------------------
def demo_scope_legb() -> None:
    """Local → Enclosing → Global → Built-in"""
    g_var = "global"

    def outer():
        e_var = "enclosing"
        def inner():
            l_var = "local"
            return l_var, e_var, g_var, len  # 全四层都能访问
        return inner()

    result = outer()
    assert result == ("local", "enclosing", "global", len)
    print(f"[OK] LEGB scope: {result[:3]}")


# ---------------------------------------------------------------------------
# 7. 文档字符串与类型注解
# ---------------------------------------------------------------------------
def demo_docstring_typehint() -> None:
    """良好的函数签名 + 文档"""

    def fetch_user(user_id: int, *, include_profile: bool = False) -> dict:
        """从数据库获取用户信息(模拟)。

        Args:
            user_id: 用户唯一标识
            include_profile: 是否包含详细 profile

        Returns:
            包含用户字段的字典
        """
        user = {"id": user_id, "name": f"user_{user_id}"}
        if include_profile:
            user["profile"] = {"level": 1, "xp": 100}
        return user

    u = fetch_user(42, include_profile=True)
    assert u["id"] == 42
    assert "profile" in u
    assert fetch_user.__doc__ is not None
    print("[OK] docstring + type hints")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_default_kwargs()
    demo_args_kwargs()
    demo_closure()
    demo_lambda_higher_order()
    demo_reduce_partial()
    demo_scope_legb()
    demo_docstring_typehint()
    print("\n✅ 所有测试通过!")
