---
chapter_id: '08'
slug: inheritance_polymorphism
title: 继承与多态
kp_ids:
- PY_012
bloom_focus:
- Apply
- Analyze
prerequisites:
- '07'
estimated_minutes: 240
---

# 08: 继承与多态 · 代码复用的艺术

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 240 分钟(4 学时)
> **前置知识**: §07 类与对象

## 学习目标

1. 掌握单继承、方法重写、`super()` 的使用。
2. 理解多继承与 MRO(Method Resolution Order)算法。
3. 理解 C3 线性化与菱形继承问题。
4. 掌握抽象基类(ABC)与鸭子类型的多态实现。
5. 能用 `isinstance` / `issubclass` 设计可扩展的类层次。

## 8.1 继承基础

```python
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        raise NotImplementedError("子类必须实现 speak")

class Dog(Animal):
    def speak(self):
        return f"{self.name}: Woof!"

class Cat(Animal):
    def speak(self):
        return f"{self.name}: Meow!"

animals = [Dog("旺财"), Cat("小花")]
for a in animals:
    print(a.speak())  # 多态:同一接口,不同行为
```

## 8.2 方法重写(Override)

```python
class Bird(Animal):
    def __init__(self, name, wingspan):
        super().__init__(name)        # 调用父类构造
        self.wingspan = wingspan

    def speak(self):
        return f"{self.name}: Chirp!"

b = Bird("鹦鹉", 30)
print(b.name, b.wingspan)
```

**`super()` 的作用**:调用父类方法,支持方法链。

## 8.3 多继承与 MRO

```python
class A:
    def hello(self):
        return "A"

class B(A):
    def hello(self):
        return "B"

class C(A):
    def hello(self):
        return "C"

class D(B, C):
    pass

d = D()
print(d.hello())  # "B"(MRO: D → B → C → A)
print(D.__mro__)  # (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)
```

**MRO 解析顺序**:Python 用 **C3 线性化** 算法,保证:
1. 子类在父类之前
2. 父类按继承顺序
3. 每个类只出现一次

## 8.4 菱形继承问题

```python
class A:
    def m(self): return "A"

class B(A):
    def m(self): return f"B->A:{super().m()}"

class C(A):
    def m(self): return f"C->A:{super().m()}"

class D(B, C):
    def m(self): return f"D->BC:{super().m()}"

# 协同调用
print(D().m())
# D->BC:B->A:C->A:A
```

**Python 解决菱形继承**:通过 `super()` 协同链式调用,每个类只调用一次。

## 8.5 抽象基类(ABC)

强制子类实现特定方法:

```python
from abc import ABC, abstractmethod

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

# s = Shape()  # ❌ TypeError: Can't instantiate abstract class
c = Circle(5)  # ✅
print(c.area())
```

**作用**:明确接口契约,提前发现未实现的子类。

## 8.6 多态:鸭子类型

Python 推崇"鸭子类型":只要对象有 `speak` 方法,它就是"动物":

```python
def make_speak(animal):
    return animal.speak()

class Robot:
    def speak(self):
        return "Beep!"

# 不需要继承 Animal,只要有 speak 方法就能用
make_speak(Robot())  # "Beep!"
```

**优势**:不强制继承关系,更灵活。
**劣势**:运行时才检查类型错误,IDE 难以静态检查。

**最佳实践**:核心抽象用 ABC,工具/边缘场景用鸭子类型。

## 8.7 isinstance 与 issubclass

```python
print(isinstance(d, Dog))         # True
print(isinstance(d, Animal))      # True(继承)
print(isinstance(d, Cat))         # False

print(issubclass(Dog, Animal))    # True
print(issubclass(Cat, Dog))       # False
```

**应用**:类型检查、参数验证、`isinstance(x, (int, float))` 多类型检查。

## 8.8 组合 vs 继承

"优先用组合,少用继承":

```python
# 继承:"is-a" 关系
class ElectricCar(Car):
    def __init__(self, brand, battery):
        super().__init__(brand)
        self.battery = battery  # 电动汽车"是"汽车

# 组合:"has-a" 关系
class Car:
    def __init__(self, brand, engine):
        self.brand = brand
        self.engine = engine  # 汽车"有"一个引擎

# 引擎可独立替换
class Engine: ...
class ElectricEngine(Engine): ...
```

**LSP(里氏替换)**:子类对象应该能完全替换父类对象。

### 决策清单

判断"用继承还是组合"的 4 问:
1. 是否有清晰的"is-a"语义?如"学生 is-a 人",可以继承
2. 子类是否需要复用父类的实现?如 `super().__init__` 调用有意义
3. 父类的接口是否稳定?频繁变动的接口不该作为基类
4. 是否需要运行时切换实现?是 → 用组合(策略模式)

如果 4 个问题答案都是 YES,继承合适;否则用组合更安全。

## 8.9 实战:员工与部门

```python
from abc import ABC, abstractmethod

class Employee(ABC):
    def __init__(self, name, base_salary):
        self.name = name
        self.base_salary = base_salary

    @abstractmethod
    def calc_salary(self):
        pass

class FullTimeEmployee(Employee):
    def calc_salary(self):
        return self.base_salary

class PartTimeEmployee(Employee):
    def __init__(self, name, hourly_rate, hours):
        super().__init__(name, 0)
        self.hourly_rate = hourly_rate
        self.hours = hours

    def calc_salary(self):
        return self.hourly_rate * self.hours

class Intern(Employee):
    def calc_salary(self):
        return 0  # 实习无薪

staff = [
    FullTimeEmployee("Alice", 10000),
    PartTimeEmployee("Bob", 100, 80),
    Intern("Charlie"),
]
total = sum(e.calc_salary() for e in staff)
print(f"本月工资总额: {total}")  # 18000
```

## 8.10 常见误区

- **误区 1**:MRO 顺序记反——用 `cls.__mro__` 或 `cls.mro()` 查看。
- **误区 2**:多继承滥用——"钻石依赖"会让代码难以理解。
- **误区 3**:`super().__init__()` 忘写——父类初始化被跳过。
- **误区 4**:把"is-a"关系硬塞成继承——学生"是"人,但学生聚合课程更适合组合。
- **误区 5**:在 ABC 子类中"偷偷"调父类的抽象方法——应该报错或抛 `NotImplementedError`。

## 8.11 本章小结

1. 单继承复用父类,`super()` 调用父类方法。
2. 多继承用 C3 线性化确定 MRO,菱形继承靠 `super()` 协同解决。
3. ABC 强制接口契约,鸭子类型提供灵活多态。
4. `isinstance` / `issubclass` 做运行时类型检查。
5. 优先组合(Has-A),慎用继承(Is-A)。
6. LSP:子类对象应能完全替代父类对象。

## 8.12 练习思考

1. **动手实践**:实现 `Shape` 抽象基类,要求子类 `Circle` / `Rectangle` 实现 `area` / `perimeter`。
2. **代码分析**:用 `D.__mro__` 查看下面代码的 MRO 顺序。
   ```python
   class A: pass
   class B(A): pass
   class C(A): pass
   class D(B, C): pass
   ```
3. **动手实践**:用多继承实现"会飞的鱼":`Fish` + `Bird`,用 super() 协同调用 speak/fly/swim。
4. **动手实践**:用 `isinstance` 实现一个 `safe_add(a, b)`,只对数字类型做加法。
5. **拓展探索**:阅读 Django 的 `Model` 类,理解大型项目中的继承设计。

## 8.13 拓展阅读

- Python 继承官方文档:https://docs.python.org/3/tutorial/classes.html#inheritance
- 《流畅的 Python》第 12 章 继承的优缺点
- C3 线性化算法:https://en.wikipedia.org/wiki/C3_linearization

---

*配套代码示例:`code_examples/08_inheritance_demo.py`*
*配套练习:`exercises/08_inheritance_polymorphism_exercises.md`*
