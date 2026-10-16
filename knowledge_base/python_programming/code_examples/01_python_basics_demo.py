"""P0-2 配套实操示例 01 · Python 8 大基础语法 demo

对应章节：01 Python 基础语法
对应 KP   ：python_basics
Bloom 关注：Remember / Understand
运行方式 ：python 01_python_basics_demo.py
依赖     ：纯标准库
说明     ：8 大语法点（变量 / 类型 / 控制流 / 函数 / 列表 / 字典 / 字符串 /
           文件 IO）每个一个 demo 函数 + assert 自检；最后 [OK] 退出。
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from typing import Any, Callable


# ---------------------------------------------------------------------------
# 1. 变量 / 类型
# ---------------------------------------------------------------------------
def demo_variables() -> None:
    x = 42                       # int
    pi = 3.14159                 # float
    name = "A3"                  # str
    items = [1, 2, 3]            # list
    info = {"course": "Python"}  # dict
    is_ok = True                 # bool
    nothing = None               # NoneType

    assert isinstance(x, int)
    assert isinstance(pi, float)
    assert isinstance(name, str)
    assert isinstance(items, list)
    assert isinstance(info, dict)
    assert isinstance(is_ok, bool)
    assert nothing is None

    # 类型推导：sum 自动转为 int / float
    total: int | float = sum([1, 2, 3.5])
    assert isinstance(total, (int, float))


# ---------------------------------------------------------------------------
# 2. 控制流
# ---------------------------------------------------------------------------
def demo_control_flow() -> None:
    # if / elif / else
    n = 7
    parity = "even" if n % 2 == 0 else "odd"
    assert parity == "odd"

    # for / range
    acc = 0
    for i in range(1, 6):
        acc += i
    assert acc == 15

    # while + break / continue
    cnt = 0
    while True:
        cnt += 1
        if cnt == 3:
            continue   # 跳过本轮
        if cnt == 5:
            break      # 跳出循环
    assert cnt == 5


# ---------------------------------------------------------------------------
# 3. 函数
# ---------------------------------------------------------------------------
def demo_functions() -> None:
    def add(a: int, b: int) -> int:
        """两数相加"""
        return a + b

    def greet(name: str, *, excited: bool = False) -> str:
        """* 之后为 keyword-only 参数"""
        suffix = "!" if excited else "."
        return f"Hello, {name}{suffix}"

    assert add(2, 3) == 5
    assert greet("A3") == "Hello, A3."
    assert greet("A3", excited=True) == "Hello, A3!"

    # lambda + sorted key
    pairs = [(1, "b"), (3, "a"), (2, "c")]
    by_second = sorted(pairs, key=lambda p: p[1])
    assert by_second == [(3, "a"), (1, "b"), (2, "c")]


# ---------------------------------------------------------------------------
# 4. 列表 / 元组 / 推导式
# ---------------------------------------------------------------------------
def demo_list_and_comprehension() -> None:
    nums = [1, 2, 3, 4, 5]
    squares = [n * n for n in nums if n % 2 == 1]
    assert squares == [1, 9, 25]

    # 切片：start:stop:step
    assert nums[1:4] == [2, 3, 4]
    assert nums[::-1] == [5, 4, 3, 2, 1]

    # 解构
    a, b, *rest = nums
    assert (a, b, rest) == (1, 2, [3, 4, 5])


# ---------------------------------------------------------------------------
# 5. 字典
# ---------------------------------------------------------------------------
def demo_dict() -> None:
    scores: dict[str, int] = {"Alice": 90, "Bob": 85, "Cara": 92}

    # 取值与默认值
    assert scores.get("Dan", 0) == 0

    # 遍历
    total = sum(scores.values())
    assert total == 267

    # dict 推导式
    squared = {k: v // 10 for k, v in scores.items()}
    assert squared == {"Alice": 9, "Bob": 8, "Cara": 9}

    # 合并（Python 3.9+）
    extra = {"Dan": 88}
    merged = scores | extra
    assert merged["Dan"] == 88


# ---------------------------------------------------------------------------
# 6. 字符串
# ---------------------------------------------------------------------------
def demo_string() -> None:
    s = "Hello, A3 Learning!"

    # 切片 / 大小写
    assert s[:5] == "Hello"
    assert s.upper() == "HELLO, A3 LEARNING!"

    # 拆分 / 拼接
    words = s.split(", ")
    assert words == ["Hello", "A3 Learning!"]
    joined = " | ".join(words)
    assert joined == "Hello | A3 Learning!"

    # 格式化
    name = "Alice"
    score = 95.5
    fmt = f"{name} 得了 {score:.1f} 分"
    assert fmt == "Alice 得了 95.5 分"


# ---------------------------------------------------------------------------
# 7. 文件 IO
# ---------------------------------------------------------------------------
def demo_file_io() -> None:
    # 用 io.StringIO 模拟文件，避免依赖磁盘
    buf = io.StringIO()
    payload = {"course": "Python", "level": 1}
    json.dump(payload, buf)
    buf.seek(0)
    loaded = json.load(buf)
    assert loaded == payload


# ---------------------------------------------------------------------------
# 8. 异常处理
# ---------------------------------------------------------------------------
def demo_exception() -> None:
    try:
        _ = 1 / 0
    except ZeroDivisionError as exc:
        assert "division by zero" in str(exc)
    else:
        raise AssertionError("expected ZeroDivisionError")
    finally:
        pass

    # 自定义异常
    class TooSmallError(ValueError):
        pass

    def positive_only(x: int) -> int:
        if x <= 0:
            raise TooSmallError(f"x must be > 0, got {x}")
        return x

    assert positive_only(3) == 3
    raised = False
    try:
        positive_only(-1)
    except TooSmallError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    demos: list[Callable[[], None]] = [
        demo_variables,
        demo_control_flow,
        demo_functions,
        demo_list_and_comprehension,
        demo_dict,
        demo_string,
        demo_file_io,
        demo_exception,
    ]

    # 单独跑一遍，捕获每个 demo 的 stdout，避免输出互相干扰
    for d in demos:
        sink = io.StringIO()
        with redirect_stdout(sink):
            d()
        # 演示输出被收集（实际 demo 中并没有 print，便于安静通过）
        assert sink.getvalue() == ""

    # 顺便演示一次 print 不被吞的版本
    print("[Python-Basics] 8 demos all asserted OK")
    print("[OK] python basics demo passed")


if __name__ == "__main__":
    main()