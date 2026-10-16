"""Python 程序设计 · 配套实操示例 07 · 类与对象 demo

对应章节: 07 类与对象
对应 KP  : PY_011 (类与对象)
Bloom 关注: Apply / Analyze
运行方式 : python 07_oop_basics_demo.py
依赖     : 纯标准库
说明     : 8 个 demo 函数覆盖类定义、self、实例/类属性、三种方法、封装命名、property、魔术方法、实战。
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. 类定义 + __init__ + self
# ---------------------------------------------------------------------------
def demo_basic_class() -> None:
    class Dog:
        def __init__(self, name, age):
            self.name = name
            self.age = age

        def bark(self):
            return f"{self.name} says: Woof!"

    d = Dog("旺财", 3)
    assert d.name == "旺财"
    assert d.bark() == "旺财 says: Woof!"
    # 等价调用
    assert Dog.bark(d) == "旺财 says: Woof!"
    print(f"[OK] basic class (d={d.name}, age={d.age})")


# ---------------------------------------------------------------------------
# 2. 实例属性 vs 类属性
# ---------------------------------------------------------------------------
def demo_class_attr() -> None:
    class Circle:
        pi = 3.14159  # 类属性

        def __init__(self, r):
            self.r = r  # 实例属性

    c1 = Circle(1)
    c2 = Circle(2)
    assert c1.pi == c2.pi == 3.14159
    c1.pi = 3.14  # 创建实例属性(遮蔽类属性)
    assert c1.pi == 3.14
    assert c2.pi == 3.14159  # c2 仍用类属性
    assert Circle.pi == 3.14159
    print(f"[OK] class attribute (c1.pi={c1.pi}, c2.pi={c2.pi})")


# ---------------------------------------------------------------------------
# 3. 三种方法:实例/类/静态
# ---------------------------------------------------------------------------
def demo_method_types() -> None:
    class Date:
        def __init__(self, y, m, d):
            self.y, self.m, self.d = y, m, d

        def __str__(self):  # 实例方法
            return f"{self.y}-{self.m:02d}-{self.d:02d}"

        @classmethod
        def from_string(cls, s):  # 类方法:替代构造
            y, m, d = map(int, s.split("-"))
            return cls(y, m, d)

        @staticmethod
        def is_leap(year):  # 静态方法:工具函数
            return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    d = Date.from_string("2026-07-12")
    assert str(d) == "2026-07-12"
    assert Date.is_leap(2024) is True
    assert Date.is_leap(2025) is False
    print(f"[OK] method types (d={d}, 2024 leap={Date.is_leap(2024)})")


# ---------------------------------------------------------------------------
# 4. 封装:命名约定与名称改写
# ---------------------------------------------------------------------------
def demo_encapsulation() -> None:
    class Account:
        def __init__(self, balance):
            self._hint = "看一眼没事"
            self.__balance = balance  # 名称改写

    a = Account(100)
    assert a._hint == "看一眼没事"
    # a.__balance       # AttributeError
    assert a._Account__balance == 100  # 改写后的名字
    print(f"[OK] encapsulation (a._Account__balance={a._Account__balance})")


# ---------------------------------------------------------------------------
# 5. @property:校验 + 计算属性
# ---------------------------------------------------------------------------
def demo_property() -> None:
    class User:
        def __init__(self, age):
            self.age = age  # 走 setter 校验

        @property
        def age(self):
            return self._age

        @age.setter
        def age(self, value):
            if not 0 <= value <= 150:
                raise ValueError(f"非法年龄: {value}")
            self._age = value

    u = User(25)
    assert u.age == 25
    try:
        u.age = 200
        assert False, "should have raised"
    except ValueError as e:
        print(f"  caught expected ValueError: {e}")
    print(f"[OK] property validation (u.age={u.age})")


# ---------------------------------------------------------------------------
# 6. __str__ / __repr__ / __eq__
# ---------------------------------------------------------------------------
def demo_magic_basic() -> None:
    class Point:
        def __init__(self, x, y):
            self.x, self.y = x, y

        def __repr__(self):
            return f"Point({self.x}, {self.y})"

        def __eq__(self, other):
            return self.x == other.x and self.y == other.y

    p = Point(3, 4)
    assert repr(p) == "Point(3, 4)"
    assert p == Point(3, 4)
    assert p != Point(3, 5)
    print(f"[OK] __repr__/__eq__ ({p!r})")


# ---------------------------------------------------------------------------
# 7. 运算符重载:Vector
# ---------------------------------------------------------------------------
def demo_operator_overload() -> None:
    class Vector:
        def __init__(self, x, y):
            self.x, self.y = x, y

        def __repr__(self):
            return f"Vector({self.x}, {self.y})"

        def __add__(self, other):
            return Vector(self.x + other.x, self.y + other.y)

        def __sub__(self, other):
            return Vector(self.x - other.x, self.y - other.y)

        def __mul__(self, scalar):
            return Vector(self.x * scalar, self.y * scalar)

        def __abs__(self):
            return (self.x ** 2 + self.y ** 2) ** 0.5

        def __eq__(self, other):
            return isinstance(other, Vector) and self.x == other.x and self.y == other.y

        def __hash__(self):
            return hash((self.x, self.y))

    v1 = Vector(1, 2)
    v2 = Vector(3, 4)
    assert v1 + v2 == Vector(4, 6)
    assert v2 - v1 == Vector(2, 2)
    assert v1 * 3 == Vector(3, 6)
    assert abs(v1) == 5 ** 0.5
    print(f"[OK] operator overload (v1+v2={v1+v2}, |v1|={abs(v1):.2f})")


# ---------------------------------------------------------------------------
# 8. 综合实战:BankAccount
# ---------------------------------------------------------------------------
def demo_bank_account() -> None:
    class BankAccount:
        bank_name = "A3 银行"

        def __init__(self, owner, balance=0):
            if balance < 0:
                raise ValueError("初始余额不能为负")
            self.owner = owner
            self._balance = balance

        @property
        def balance(self):
            return self._balance

        def deposit(self, amount):
            if amount <= 0:
                raise ValueError("存款必须为正")
            self._balance += amount
            return self

        def withdraw(self, amount):
            if amount > self._balance:
                raise ValueError("余额不足")
            self._balance -= amount
            return self

        def __repr__(self):
            return f"BankAccount(owner={self.owner!r}, balance={self._balance})"

    acc = BankAccount("Alice", 1000)
    acc.deposit(500).withdraw(200)
    assert acc.balance == 1300
    print(f"[OK] BankAccount ({acc})")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_basic_class()
    demo_class_attr()
    demo_method_types()
    demo_encapsulation()
    demo_property()
    demo_magic_basic()
    demo_operator_overload()
    demo_bank_account()
    print("\n✅ 所有测试通过!")
