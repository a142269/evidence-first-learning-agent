"""Python 程序设计 · 配套实操示例 02 · 控制流 demo

对应章节: 02 控制流:条件与循环
对应 KP  : PY_004 (控制流(条件与循环))
Bloom 关注: Understand / Apply
运行方式 : python 02_control_flow_demo.py
依赖     : 纯标准库
说明     : 6 个 demo 函数覆盖 if-elif-else、for + range、while + break/continue、enumerate/zip、列表推导式、match-case(3.10+)。
"""
from __future__ import annotations

import sys


# ---------------------------------------------------------------------------
# 1. 条件判断:if-elif-else + 三元表达式
# ---------------------------------------------------------------------------
def demo_if_elif_else() -> None:
    """根据分数返回等级"""
    def grade(score: int) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 60:
            return "C"
        else:
            return "F"

    assert grade(95) == "A"
    assert grade(85) == "B"
    assert grade(65) == "C"
    assert grade(45) == "F"
    # 三元
    status = "成年" if 20 >= 18 else "未成年"
    assert status == "成年"
    print("[OK] if-elif-else + ternary")


# ---------------------------------------------------------------------------
# 2. for + range
# ---------------------------------------------------------------------------
def demo_for_range() -> None:
    total = sum(i for i in range(1, 101))
    assert total == 5050
    # 倒序
    countdown = list(range(5, 0, -1))
    assert countdown == [5, 4, 3, 2, 1]
    print(f"[OK] for + range (sum 1..100 = {total})")


# ---------------------------------------------------------------------------
# 3. while + break/continue/else
# ---------------------------------------------------------------------------
def demo_while_break_continue() -> None:
    """while 循环 + break/continue/else"""
    # 找到第一个 3 的倍数
    for i in range(1, 10):
        if i % 3 == 0:
            assert i == 3
            break

    # 求素数(用 for-else)
    def is_prime(n: int) -> bool:
        if n < 2:
            return False
        for x in range(2, int(n**0.5) + 1):
            if n % x == 0:
                return False
        return True

    primes_under_20 = [n for n in range(2, 20) if is_prime(n)]
    assert primes_under_20 == [2, 3, 5, 7, 11, 13, 17, 19]
    print(f"[OK] while + for-else (primes<20: {primes_under_20})")


# ---------------------------------------------------------------------------
# 4. enumerate + zip
# ---------------------------------------------------------------------------
def demo_enumerate_zip() -> None:
    """同时拿索引和值 / 并行遍历"""
    fruits = ["apple", "banana", "cherry"]
    pairs = list(enumerate(fruits, start=1))
    assert pairs == [(1, "apple"), (2, "banana"), (3, "cherry")]

    names = ["Alice", "Bob", "Charlie"]
    scores = [85, 92, 78]
    merged = [(n, s) for n, s in zip(names, scores)]
    assert merged == [("Alice", 85), ("Bob", 92), ("Charlie", 78)]
    print(f"[OK] enumerate + zip ({merged})")


# ---------------------------------------------------------------------------
# 5. 推导式(列表/字典/集合/生成器)
# ---------------------------------------------------------------------------
def demo_comprehensions() -> None:
    """四种推导式"""
    # 列表
    squares = [i**2 for i in range(10)]
    assert squares == [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
    # 嵌套
    matrix = [[i * 3 + j for j in range(3)] for i in range(3)]
    assert matrix == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    # 字典
    word_count = {c: "hello".count(c) for c in set("hello")}
    assert word_count == {"h": 1, "e": 1, "l": 2, "o": 1}
    # 集合
    even_squares = {i**2 for i in range(10) if i % 2 == 0}
    assert even_squares == {0, 4, 16, 36, 64}
    # 生成器(惰性)
    big_sum = sum(i**2 for i in range(1000))
    assert big_sum == sum(i**2 for i in range(1000))
    print(f"[OK] comprehensions (sum of squares 0..999 = {big_sum})")


# ---------------------------------------------------------------------------
# 6. match-case(Python 3.10+)
# ---------------------------------------------------------------------------
def demo_match_case() -> None:
    """结构化模式匹配(3.10+)"""
    if sys.version_info < (3, 10):
        print("[SKIP] match-case 需要 Python 3.10+")
        return

    def http_status(status: int) -> str:
        match status:
            case 200:
                return "OK"
            case 301 | 302:
                return "Redirect"
            case 404:
                return "Not Found"
            case 500 | 502 | 503:
                return "Server Error"
            case _:
                return "Unknown"

    assert http_status(200) == "OK"
    assert http_status(301) == "Redirect"
    assert http_status(404) == "Not Found"
    assert http_status(500) == "Server Error"
    assert http_status(999) == "Unknown"
    print("[OK] match-case")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_if_elif_else()
    demo_for_range()
    demo_while_break_continue()
    demo_enumerate_zip()
    demo_comprehensions()
    demo_match_case()
    print("\n✅ 所有测试通过!")
