---
chapter_id: '07'
slug: oop_basics
title: 类与对象
kp_ids:
- PY_011
bloom_focus:
- Apply
- Analyze
prerequisites:
- '03'
estimated_minutes: 300
---

# 07: 类与对象 · Python 面向对象的核心

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 300 分钟(5 学时)
> **前置知识**: §03 函数

## 学习目标

1. 掌握 `class` 关键字定义类,理解实例化与方法调用。
2. 区分实例属性、类属性、实例方法、类方法、静态方法。
3. 理解 `self` 的作用与 `__init__` 构造方法。
4. 掌握 `@property` 装饰器实现受控属性访问。
5. 掌握 `@classmethod` / `@staticmethod` 的适用场景。
6. 理解封装、命名约定(单下划线、双下划线)的实际意义。

## 7.1 什么是面向对象

面向对象编程(OOP)三大特性:**封装**、**继承**、**多态**。Python 一切皆对象,类(class)是对象的"蓝图"或"模板"。

```python
class Dog:
    pass

d1 = Dog()       # 实例化
d2 = Dog()
print(type(d1))  # <class '__main__.Dog'>
print(d1 is d2)  # False(不同实例)
```

## 7.2 __init__ 与 self

```python
class Dog:
    def __init__(self, name, age):
        """构造方法:实例化时自动调用"""
        self.name = name      # 实例属性
        self.age = age

    def bark(self):
        """实例方法:第一个参数是 self"""
        return f"{self.name} says: Woof!"

d = Dog("旺财", 3)
print(d.bark())  # 旺财 says: Woof!
```

**`self` 的本质**:当前实例的引用。Python 把 `d.bark()` 解释为 `Dog.bark(d)`,`self` 就是 `d`。

## 7.3 实例属性 vs 类属性

```python
class Circle:
    pi = 3.14159  # 类属性(所有实例共享)

    def __init__(self, r):
        self.r = r  # 实例属性(每个实例独立)

c1 = Circle(1)
c2 = Circle(2)
print(c1.pi, c2.pi)        # 3.14159 3.14159(共享)
print(c1.r, c2.r)          # 1 2(独立)

# ⚠️ 通过实例修改类属性,只会创建实例属性"遮蔽"
c1.pi = 3.14               # 实例属性
print(c1.pi)               # 3.14
print(c2.pi)               # 3.14159(类属性未变)
print(Circle.pi)           # 3.14159
```

**最佳实践**:用类属性定义常量(如 `Circle.pi`),用实例属性存储每个实例的状态。

## 7.4 实例方法、类方法、静态方法

```python
class Date:
    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day

    def __str__(self):
        """实例方法:操作实例数据"""
        return f"{self.year}-{self.month:02d}-{self.day:02d}"

    @classmethod
    def from_string(cls, s):
        """类方法:第一个参数是 cls(类本身),常用于替代构造"""
        y, m, d = map(int, s.split("-"))
        return cls(y, m, d)

    @staticmethod
    def is_valid(s):
        """静态方法:不访问 self/cls,逻辑上属于类"""
        try:
            y, m, d = map(int, s.split("-"))
            return 1 <= m <= 12 and 1 <= d <= 31
        except (ValueError, AttributeError):
            return False

d = Date.from_string("2026-07-12")  # 用类方法构造
print(d)                            # 2026-07-12
print(Date.is_valid("2026-13-01"))  # False
```

| 方法类型 | 装饰器 | 第一参数 | 访问 | 适用 |
|----------|--------|----------|------|------|
| 实例方法 | 无 | self | 实例/类 | 操作实例数据 |
| 类方法 | `@classmethod` | cls | 类 | 替代构造、工厂方法 |
| 静态方法 | `@staticmethod` | 无 | 都可 | 工具函数、与类逻辑相关 |

## 7.5 封装与命名约定

Python 没有真正的"私有",靠**命名约定**:

| 形式 | 含义 | 例子 |
|------|------|------|
| `name` | 公有 | `self.name` |
| `_name` | 内部使用(约定,不强制) | `self._internal` |
| `__name` | 名称改写(name mangling) | `self.__private` |
| `__name__` | 魔术方法(特殊含义) | `__init__`、`__str__` |

```python
class Account:
    def __init__(self, balance):
        self.__balance = balance  # 名称改写为 _Account__balance

a = Account(100)
# a.__balance              # ❌ AttributeError
a._Account__balance        # 100(可访问,但请勿)
print(a.__dict__)          # {'_Account__balance': 100}
```

## 7.6 @property:把方法变成属性

```python
class Circle:
    def __init__(self, r):
        self._r = r

    @property
    def radius(self):
        """getter"""
        return self._r

    @radius.setter
    def radius(self, value):
        """setter:可加入校验"""
        if value < 0:
            raise ValueError("半径不能为负")
        self._r = value

    @property
    def area(self):
        """只读计算属性"""
        return 3.14159 * self._r ** 2

c = Circle(5)
print(c.radius)        # 5(像属性一样访问)
print(c.area)          # 78.53975
c.radius = 10          # 走 setter
# c.radius = -1        # ValueError
```

**优势**:保留"属性"语法的简洁,同时在背后执行校验/计算/通知。

## 7.7 魔术方法(dunder methods)

双下划线包围的方法是 Python 数据模型的一部分,__ 后续章节深入:

```python
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"

    def __str__(self):
        return f"({self.x}, {self.y})"

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

v1 = Vector(1, 2)
v2 = Vector(3, 4)
print(v1)            # (1, 2)  ← __str__
print(repr(v1))      # Vector(1, 2)  ← __repr__
print(v1 + v2)       # Vector(4, 6)  ← __add__
print(v1 == Vector(1, 2))  # True  ← __eq__
```

`__repr__` 是开发期用的"明确表示",`__str__` 是用户期用的"友好展示"。

## 7.8 实战:银行卡类

```python
class BankAccount:
    bank_name = "A3 银行"  # 类属性

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
            raise ValueError("存款金额必须为正")
        self._balance += amount
        return self

    def withdraw(self, amount):
        if amount <= self._balance:
            self._balance -= amount
            return self
        raise ValueError("余额不足")

    @classmethod
    def from_dict(cls, data):
        return cls(data["owner"], data.get("balance", 0))

    @staticmethod
    def is_valid_account_number(num):
        return isinstance(num, str) and len(num) == 16

    def __repr__(self):
        return f"BankAccount(owner={self.owner!r}, balance={self._balance})"

acc = BankAccount("Alice", 1000)
acc.deposit(500).withdraw(200)  # 方法链
print(acc)                       # BankAccount(owner='Alice', balance=1300)
```

## 7.9 常见误区

- **误区 1**:`self` 不是关键字,只是约定;但改名会导致代码不可读。
- **误区 2**:类属性被实例"遮蔽"——`c1.pi = 3.14` 不会改类属性,只创建实例属性。
- **误区 3**:混淆 `@staticmethod` 与 `@classmethod`——前者不需要 cls,后者需要。
- **误区 4**:每个方法都加 `@property`——只对需要校验/计算/通知的属性用。
- **误区 5**:类里写"业务逻辑 + 数据访问 + UI"全混在一起——违反单一职责。

## 7.10 本章小结

1. 类是对象的蓝图;`__init__` 是构造方法;`self` 是当前实例引用。
2. 类属性被所有实例共享,实例属性每个实例独立。
3. 实例方法操作 self,类方法(cls)用于替代构造,静态方法与类逻辑相关但无 self/cls。
4. 命名约定:`_x` 内部,`__x` 名称改写,`__x__` 魔术方法。
5. `@property` 把方法变属性,可在 getter/setter 中加校验。
6. `__repr__` / `__str__` / `__eq__` / `__add__` 等魔术方法定义对象行为。
7. 实战:银行卡类展示封装、property、classmethod 链式调用。

## 7.11 练习思考

1. **动手实践**:定义 `Rectangle` 类,含 `width` / `height` 属性,提供 `area` / `perimeter` 只读 property。
2. **动手实践**:为 `Rectangle` 加 `@classmethod from_string(s)`(解析 "10x20")和 `@staticmethod is_square(w, h)`。
3. **代码分析**:下面代码输出什么?为什么?
   ```python
   class C:
       x = 1
   a = C()
   b = C()
   a.x = 99
   print(b.x)
   print(C.x)
   ```
4. **动手实践**:用 `@property` 实现一个 `Temperature` 类,内部存摄氏度,提供 `celsius` 与 `fahrenheit` 两个 property。
5. **拓展探索**:阅读 Python 数据模型文档,了解 `__len__` / `__iter__` / `__getitem__` 的作用。

## 7.12 拓展阅读

- Python 类官方文档:https://docs.python.org/3/tutorial/classes.html
- 《流畅的 Python》第 9 章 符合 Python 风格的对象
- Python 数据模型:https://docs.python.org/3/reference/datamodel.html

---

*配套代码示例:`code_examples/07_oop_basics_demo.py`*
*配套练习:`exercises/07_oop_basics_exercises.md`*
