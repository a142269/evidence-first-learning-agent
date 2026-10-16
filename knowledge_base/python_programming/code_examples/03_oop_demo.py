"""P0-2 配套实操示例 03 · Python 面向对象编程 demo

对应章节：03 面向对象
对应 KP   ：python_basics
Bloom 关注：Apply / Analyze
运行方式 ：python 03_oop_demo.py
依赖     ：纯标准库
说明     ：演示 class / inheritance / polymorphism / dunder methods /
           dataclass / property / 抽象基类 / mixin；每段 assert 自检。
           建议 200-300 行（本文件 ~250 行）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable


# ---------------------------------------------------------------------------
# 1. 最简 class + dunder
# ---------------------------------------------------------------------------
class Vector:
    """二维向量：演示 __init__ / __repr__ / __eq__ / __add__ / __mul__"""

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Vector({self.x}, {self.y})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vector) and self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __add__(self, other: "Vector") -> "Vector":
        return Vector(self.x + other.x, self.y + other.y)

    def __mul__(self, k: float) -> "Vector":
        return Vector(self.x * k, self.y * k)

    def __len__(self) -> int:
        # 约定：2D 向量长度 = 2
        return 2

    def __iter__(self):
        yield self.x
        yield self.y


def demo_basic_class() -> None:
    v1 = Vector(1, 2)
    v2 = Vector(3, 4)
    assert v1 + v2 == Vector(4, 6)
    assert v1 * 3 == Vector(3, 6)
    assert len(v1) == 2
    assert list(v1) == [1, 2]
    # 作为 dict key
    d = {v1: "origin-ish"}
    assert d[v1] == "origin-ish"


# ---------------------------------------------------------------------------
# 2. 继承 + 多态
# ---------------------------------------------------------------------------
class Shape(ABC):
    """抽象基类：演示 @abstractmethod + ABCMeta"""

    @abstractmethod
    def area(self) -> float: ...

    @abstractmethod
    def perimeter(self) -> float: ...

    def describe(self) -> str:
        return f"{type(self).__name__}(area={self.area():.2f}, peri={self.perimeter():.2f})"


class Circle(Shape):
    def __init__(self, r: float) -> None:
        self.r = r

    def area(self) -> float:
        return 3.14159 * self.r ** 2

    def perimeter(self) -> float:
        return 2 * 3.14159 * self.r


class Rectangle(Shape):
    def __init__(self, w: float, h: float) -> None:
        self.w, self.h = w, h

    def area(self) -> float:
        return self.w * self.h

    def perimeter(self) -> float:
        return 2 * (self.w + self.h)


def demo_inheritance_polymorphism() -> None:
    shapes: list[Shape] = [Circle(2), Rectangle(3, 4), Circle(1.5)]
    total_area = sum(s.area() for s in shapes)
    assert abs(total_area - (12.56636 + 12 + 7.06858)) < 1e-3

    # 多态调用 describe
    descriptions = [s.describe() for s in shapes]
    assert descriptions[0].startswith("Circle")
    assert descriptions[1].startswith("Rectangle")


# ---------------------------------------------------------------------------
# 3. property + 私有属性（name mangling）
# ---------------------------------------------------------------------------
class Temperature:
    """演示 @property 校验：摄氏度 ↔ 华氏度"""

    def __init__(self, celsius: float) -> None:
        self.celsius = celsius  # 走 setter

    @property
    def celsius(self) -> float:
        return self._celsius

    @celsius.setter
    def celsius(self, value: float) -> None:
        if value < -273.15:
            raise ValueError(f"below absolute zero: {value}")
        self._celsius = value

    @property
    def fahrenheit(self) -> float:
        return self._celsius * 9 / 5 + 32


def demo_property() -> None:
    t = Temperature(100)
    assert t.celsius == 100
    assert abs(t.fahrenheit - 212) < 1e-6

    # 触发 setter 校验
    raised = False
    try:
        Temperature(-300)
    except ValueError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# 4. dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Point:
    x: float
    y: float
    label: str = "origin"


@dataclass
class Student:
    name: str
    grades: list[int] = field(default_factory=list)

    def average(self) -> float:
        return sum(self.grades) / len(self.grades) if self.grades else 0.0


def demo_dataclass() -> None:
    p1 = Point(0, 0)
    p2 = Point(0, 0, label="A")
    assert p1.label == "origin"
    assert p2.label == "A"
    # frozen -> 不可变
    raised = False
    try:
        p1.x = 1  # type: ignore[misc]
    except Exception:
        raised = True
    assert raised

    s = Student("Alice", [90, 80, 100])
    assert s.average() == 90.0
    s.grades.append(70)
    assert s.average() == 85.0  # default_factory list 可变


# ---------------------------------------------------------------------------
# 5. Mixin + 多继承
# ---------------------------------------------------------------------------
class JsonMixin:
    """为子类提供 to_json / from_json"""

    def to_json(self) -> str:
        import json
        return json.dumps(self.__dict__, ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str):
        import json
        obj = cls.__new__(cls)
        obj.__dict__.update(json.loads(payload))
        return obj


class JsonPoint(Point, JsonMixin):  # type: ignore[misc]
    pass


def demo_mixin() -> None:
    p = JsonPoint(3, 4, label="demo")
    js = p.to_json()
    restored = JsonPoint.from_json(js)
    assert restored.x == 3 and restored.y == 4 and restored.label == "demo"


# ---------------------------------------------------------------------------
# 6. 上下文管理（__enter__ / __exit__）
# ---------------------------------------------------------------------------
class Timer:
    """演示 __enter__ / __exit__ + with 语句"""

    def __enter__(self) -> "Timer":
        import time
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        import time
        self.elapsed = time.perf_counter() - self._t0


def demo_context_manager() -> None:
    with Timer() as t:
        _ = sum(range(1000))
    assert t.elapsed >= 0


# ---------------------------------------------------------------------------
# 7. 类方法 / 静态方法 / __str__
# ---------------------------------------------------------------------------
class Course:
    COURSE_LIST: list["Course"] = []

    def __init__(self, name: str, code: str) -> None:
        self.name = name
        self.code = code
        Course.COURSE_LIST.append(self)

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    @classmethod
    def all(cls) -> list["Course"]:
        return list(cls.COURSE_LIST)

    @staticmethod
    def is_valid_code(code: str) -> bool:
        return code.startswith("A3-") and len(code) >= 4


def demo_classmethod_staticmethod() -> None:
    c1 = Course("AI 通识", "A3-AI")
    c2 = Course("Python 入门", "A3-PY")
    assert Course.is_valid_code(c1.code)
    assert not Course.is_valid_code("CS101")
    assert {c.code for c in Course.all()} == {"A3-AI", "A3-PY"}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    demo_basic_class()
    demo_inheritance_polymorphism()
    demo_property()
    demo_dataclass()
    demo_mixin()
    demo_context_manager()
    demo_classmethod_staticmethod()

    print("[Python-OOP] 7 demos all asserted OK")
    print("[OK] oop demo passed")


if __name__ == "__main__":
    main()