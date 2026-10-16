"""Python 程序设计 · 配套实操示例 08 · 继承与多态 demo

对应章节: 08 继承与多态
对应 KP  : PY_012 (继承与多态)
Bloom 关注: Apply / Analyze
运行方式 : python 08_inheritance_demo.py
依赖     : 纯标准库
说明     : 6 个 demo 函数覆盖单继承、super()、MRO、菱形继承、ABC、鸭子类型。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


# 共享的基类(模块级)
class _BaseAnimal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. 单继承 + 方法重写
# ---------------------------------------------------------------------------
def demo_single_inheritance() -> None:
    class Dog(_BaseAnimal):
        def speak(self):
            return f"{self.name}: Woof!"

    class Cat(_BaseAnimal):
        def speak(self):
            return f"{self.name}: Meow!"

    d = Dog("旺财")
    c = Cat("小花")
    assert d.speak() == "旺财: Woof!"
    assert c.speak() == "小花: Meow!"

    # 多态:同一接口不同行为
    for a in [d, c]:
        print(f"  {a.speak()}")
    print("[OK] single inheritance + polymorphism")


# ---------------------------------------------------------------------------
# 2. super() 调用父类
# ---------------------------------------------------------------------------
def demo_super() -> None:
    class Bird(_BaseAnimal):
        def __init__(self, name, wingspan):
            super().__init__(name)  # 调父类构造
            self.wingspan = wingspan

        def speak(self):
            return f"{self.name}: Chirp! (wingspan={self.wingspan}cm)"

    b = Bird("鹦鹉", 30)
    assert b.name == "鹦鹉"
    assert b.wingspan == 30
    print(f"[OK] super() (b={b.speak()})")


# ---------------------------------------------------------------------------
# 3. MRO 解析顺序
# ---------------------------------------------------------------------------
def demo_mro() -> None:
    class A:
        def hello(self): return "A"

    class B(A):
        def hello(self): return "B"

    class C(A):
        def hello(self): return "C"

    class D(B, C):
        pass

    d = D()
    assert d.hello() == "B"  # MRO: D -> B -> C -> A
    mro_names = [cls.__name__ for cls in D.__mro__]
    assert mro_names == ["D", "B", "C", "A", "object"]
    print(f"[OK] MRO ({' -> '.join(mro_names)})")


# ---------------------------------------------------------------------------
# 4. 菱形继承 + super() 协同
# ---------------------------------------------------------------------------
def demo_diamond() -> None:
    class A:
        def m(self): return "A"

    class B(A):
        def m(self): return f"B({super().m()})"

    class C(A):
        def m(self): return f"C({super().m()})"

    class D(B, C):
        def m(self): return f"D({super().m()})"

    # 协同调用,每个类只执行一次
    assert D().m() == "D(B(C(A)))"
    print(f"[OK] diamond inheritance ({D().m()})")


# ---------------------------------------------------------------------------
# 5. 抽象基类(ABC)
# ---------------------------------------------------------------------------
def demo_abc() -> None:
    class Shape(ABC):
        @abstractmethod
        def area(self):
            pass

        @abstractmethod
        def perimeter(self):
            pass

    class Circle(Shape):
        def __init__(self, r):
            self.r = r

        def area(self):
            return 3.14159 * self.r ** 2

        def perimeter(self):
            return 2 * 3.14159 * self.r

    try:
        s = Shape()  # ❌ 不能实例化抽象类
        assert False
    except TypeError as e:
        print(f"  caught expected TypeError: {e}")

    c = Circle(5)
    assert abs(c.area() - 78.5398) < 0.001
    assert abs(c.perimeter() - 31.4159) < 0.001
    print(f"[OK] ABC (circle area={c.area():.2f})")


# ---------------------------------------------------------------------------
# 6. 鸭子类型 + 实战:员工薪资
# ---------------------------------------------------------------------------
def demo_duck_typing() -> None:
    class Employee(ABC):
        def __init__(self, name, base):
            self.name = name
            self.base = base

        @abstractmethod
        def calc_salary(self):
            pass

    class FullTime(Employee):
        def calc_salary(self):
            return self.base

    class PartTime(Employee):
        def __init__(self, name, rate, hours):
            super().__init__(name, 0)
            self.rate = rate
            self.hours = hours

        def calc_salary(self):
            return self.rate * self.hours

    class Intern(Employee):
        def __init__(self, name):
            super().__init__(name, 0)

        def calc_salary(self):
            return 0

    # 鸭子类型:Robot 只要有 calc_salary 就能用
    class Robot:
        def __init__(self, name):
            self.name = name

        def calc_salary(self):
            return -1  # 机器人不需要工资,但接口兼容

    def total_payroll(staff):
        return sum(s.calc_salary() for s in staff if s.calc_salary() > 0)

    staff = [FullTime("Alice", 10000), PartTime("Bob", 100, 80), Intern("Charlie"), Robot("R2D2")]
    assert total_payroll(staff) == 18000
    print(f"[OK] duck typing (total payroll: {total_payroll(staff)})")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_single_inheritance()
    demo_super()
    demo_mro()
    demo_diamond()
    demo_abc()
    demo_duck_typing()
    print("\n✅ 所有测试通过!")
