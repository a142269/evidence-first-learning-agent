"""Python 程序设计 · 配套实操示例 10 · 魔术方法与上下文管理器 demo

对应章节: 10 魔术方法与上下文管理器
对应 KP  : PY_014 (魔术方法), PY_015 (上下文管理器)
Bloom 关注: Apply / Analyze
运行方式 : python 10_magic_methods_demo.py
依赖     : 纯标准库
说明     : 7 个 demo 函数覆盖 __repr__/__str__/__eq__、运算符重载、可迭代对象、__call__、自定义 with、contextmanager 装饰器。
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from functools import total_ordering


# ---------------------------------------------------------------------------
# 1. Vector:运算符重载全套
# ---------------------------------------------------------------------------
def demo_vector_arithmetic() -> None:
    class Vector:
        def __init__(self, x, y):
            self.x, self.y = x, y

        def __repr__(self):
            return f"Vector({self.x}, {self.y})"

        def __str__(self):
            return f"({self.x}, {self.y})"

        def __add__(self, other):
            return Vector(self.x + other.x, self.y + other.y)

        def __sub__(self, other):
            return Vector(self.x - other.x, self.y - other.y)

        def __mul__(self, scalar):
            return Vector(self.x * scalar, self.y * scalar)

        def __rmul__(self, scalar):  # 右侧运算
            return self.__mul__(scalar)

        def __neg__(self):
            return Vector(-self.x, -self.y)

        def __abs__(self):
            return (self.x ** 2 + self.y ** 2) ** 0.5

        def __eq__(self, other):
            return self.x == other.x and self.y == other.y

        def __hash__(self):
            return hash((self.x, self.y))

        def __bool__(self):
            return self.x != 0 or self.y != 0

    v1 = Vector(1, 2)
    v2 = Vector(3, 4)
    assert v1 + v2 == Vector(4, 6)
    assert v2 - v1 == Vector(2, 2)
    assert v1 * 3 == Vector(3, 6)
    assert 3 * v1 == Vector(3, 6)  # __rmul__
    assert -v1 == Vector(-1, -2)
    assert abs(v1) == 5 ** 0.5
    assert bool(Vector(0, 0)) is False
    assert bool(v1) is True
    print(f"[OK] vector arithmetic (v1+v2={v1+v2}, 3*v1={3*v1})")


# ---------------------------------------------------------------------------
# 2. total_ordering 自动补齐比较
# ---------------------------------------------------------------------------
def demo_total_ordering() -> None:
    @total_ordering
    class Money:
        def __init__(self, amount, currency="CNY"):
            self.amount = amount
            self.currency = currency

        def __repr__(self):
            return f"Money({self.amount} {self.currency})"

        def __eq__(self, other):
            return self.amount == other.amount and self.currency == other.currency

        def __lt__(self, other):
            if self.currency != other.currency:
                raise ValueError("不同币种不可比较")
            return self.amount < other.amount

        def __hash__(self):
            return hash((self.amount, self.currency))

    m1 = Money(100)
    m2 = Money(200)
    assert m1 < m2
    assert m1 <= m2
    assert m2 > m1
    assert m2 >= m1
    print(f"[OK] total_ordering ({m1} < {m2} = {m1 < m2})")


# ---------------------------------------------------------------------------
# 3. Range-like:__getitem__ / __len__
# ---------------------------------------------------------------------------
def demo_sequence_protocol() -> None:
    class MyRange:
        def __init__(self, stop):
            self.stop = stop

        def __len__(self):
            return self.stop

        def __getitem__(self, i):
            if i < 0:
                i += self.stop
            if not 0 <= i < self.stop:
                raise IndexError(i)
            return i

    r = MyRange(5)
    assert len(r) == 5
    assert r[0] == 0 and r[4] == 4
    assert list(r) == [0, 1, 2, 3, 4]  # 自动支持迭代
    print(f"[OK] sequence protocol (list(MyRange(5)) = {list(r)})")


# ---------------------------------------------------------------------------
# 4. __iter__:可迭代对象
# ---------------------------------------------------------------------------
def demo_iterable() -> None:
    class Countdown:
        def __init__(self, start):
            self.start = start

        def __iter__(self):
            n = self.start
            while n > 0:
                yield n
                n -= 1

    c = Countdown(5)
    assert list(c) == [5, 4, 3, 2, 1]
    # 迭代器协议 + for 循环
    total = sum(c)
    assert total == 15
    print(f"[OK] __iter__ (Countdown(5) sum = {total})")


# ---------------------------------------------------------------------------
# 5. __call__:可调用对象
# ---------------------------------------------------------------------------
def demo_callable() -> None:
    class Multiplier:
        def __init__(self, factor):
            self.factor = factor

        def __call__(self, x):
            return x * self.factor

    double = Multiplier(2)
    triple = Multiplier(3)
    assert double(5) == 10
    assert triple(5) == 15
    assert callable(double) is True
    print(f"[OK] __call__ (double(5)={double(5)}, triple(5)={triple(5)})")


# ---------------------------------------------------------------------------
# 6. 自定义上下文管理器
# ---------------------------------------------------------------------------
def demo_context_manager_class() -> None:
    class Timer:
        def __enter__(self):
            self._start = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.elapsed = time.perf_counter() - self._start
            return False  # 不抑制异常

    with Timer() as t:
        total = sum(i ** 2 for i in range(100_000))
    assert total == 333328333350000
    assert t.elapsed >= 0
    print(f"[OK] context manager class (elapsed: {t.elapsed*1000:.1f}ms)")


# ---------------------------------------------------------------------------
# 7. @contextmanager 装饰器
# ---------------------------------------------------------------------------
def demo_contextmanager_decorator() -> None:
    @contextmanager
    def timer(label="block"):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            print(f"  [{label}] {elapsed*1000:.1f}ms")

    @contextmanager
    def temp_chdir(path):
        import os
        old = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(old)

    with timer("compute"):
        sum(i ** 2 for i in range(100_000))

    # 异常抑制
    from contextlib import suppress
    with suppress(ValueError, KeyError):
        int("abc")
    print("[OK] @contextmanager (timer + suppress)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_vector_arithmetic()
    demo_total_ordering()
    demo_sequence_protocol()
    demo_iterable()
    demo_callable()
    demo_context_manager_class()
    demo_contextmanager_decorator()
    print("\n✅ 所有测试通过!")
