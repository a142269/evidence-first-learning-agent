---
chapter_id: '09'
slug: encapsulation
title: 封装、property 与 dataclass
kp_ids:
- PY_013
bloom_focus:
- Apply
- Analyze
prerequisites:
- '07'
estimated_minutes: 180
---

# 09: 封装、property 与 dataclass · 数据类的现代写法

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 180 分钟(3 学时)
> **前置知识**: §07 类与对象

## 学习目标

1. 深入理解 Python 封装的"约定式"实现。
2. 掌握 `__getattr__` / `__setattr__` 等属性拦截机制。
3. 熟练使用 `@property` 实现数据校验、计算属性与延迟加载。
4. 掌握 `@dataclass` 装饰器简化数据类的编写。
5. 理解 `__slots__` 对内存的优化作用。

## 9.1 Python 封装哲学

"我们都是自愿遵守约定的成年人"——Python 核心开发者 Tim Peters。

| 语言 | 私有实现 | 表现 |
|------|----------|------|
| Java / C++ | 编译器强制 | 真的不能访问 |
| Python | 约定+改写 | "请不要访问" |

```python
class Secret:
    def __init__(self):
        self._hint = "看一眼也没事"  # 单下划线:约定
        self.__hidden = "真的不要看"  # 双下划线:名称改写

s = Secret()
print(s._hint)              # "看一眼也没事"
# print(s.__hidden)         # ❌ AttributeError
print(s._Secret__hidden)    # "真的不要看"(可强行访问)
```

**实战建议**:用单下划线 `_attr` 表达"内部用",足以应对 99% 场景;双下划线 `__attr` 只在明确需要"避免子类意外覆盖"时使用。

## 9.2 属性访问拦截

```python
class TrackedAttribute:
    def __init__(self):
        self._data = {}

    def __getattr__(self, name):
        """仅当属性 NOT FOUND 时调用"""
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"no attribute {name}")

    def __setattr__(self, name, value):
        """所有属性赋值都会经过"""
        print(f"  set: {name}={value}")
        super().__setattr__(name, value)

t = TrackedAttribute()
t.x = 10       # set: x=10
print(t.x)     # 10
```

**注意**:`__setattr__` 会拦截 `__init__` 内的赋值,要用 `super().__setattr__` 避免无限递归。

## 9.3 property 进阶

### 9.3.1 计算属性

```python
class Circle:
    def __init__(self, r):
        self.r = r

    @property
    def area(self):
        return 3.14159 * self.r ** 2

    @property
    def diameter(self):
        return 2 * self.r
```

### 9.3.2 数据校验

```python
class User:
    def __init__(self, name, age):
        self.name = name
        self.age = age   # 走 setter 校验

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        if not 0 <= value <= 150:
            raise ValueError(f"非法年龄: {value}")
        self._age = value

u = User("Alice", 25)
# u.age = 200  # ValueError
```

### 9.3.3 延迟加载

```python
class Image:
    def __init__(self, path):
        self.path = path
        self._data = None

    @property
    def data(self):
        if self._data is None:
            print("  loading image...")
            with open(self.path, "rb") as f:
                self._data = f.read()
        return self._data

img = Image("photo.jpg")
print(img.data)   # 第一次:加载
print(img.data)   # 第二次:缓存
```

## 9.4 @dataclass(Python 3.7+)

数据类的样板代码很多(`__init__` / `__repr__` / `__eq__`),`@dataclass` 自动生成:

```python
from dataclasses import dataclass, field

@dataclass
class Point:
    x: float
    y: float

p = Point(3, 4)
print(p)            # Point(x=3, y=4)  ← __repr__ 自动
print(p == Point(3, 4))  # True        ← __eq__ 自动

# 默认值
@dataclass
class User:
    name: str
    age: int = 0
    tags: list = field(default_factory=list)  # 可变默认值用 field

u = User("Alice")
u.tags.append("vip")
```

**field 高级参数**:

```python
@dataclass
class Item:
    name: str
    price: float = field(default=0.0)
    internal_id: int = field(default=0, repr=False)  # 不在 repr 中显示
    quantity: int = field(default=1, compare=False)  # 不参与比较
```

## 9.5 frozen=True:不可变数据类

```python
@dataclass(frozen=True)
class Coordinate:
    x: float
    y: float

c = Coordinate(3, 4)
# c.x = 5  # FrozenInstanceError
# c = Coordinate(3, 5)  # OK
```

**应用**:配置常量、字典 key、hashable 数据。

## 9.6 __slots__ 优化内存

默认每个实例有 `__dict__`,占用较大;`__slots__` 锁定属性,内存大幅减少:

```python
import sys

class WithDict:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class WithSlots:
    __slots__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x
        self.y = y

d1 = WithDict(1, 2)
d2 = WithSlots(1, 2)
print(sys.getsizeof(d1.__dict__), sys.getsizeof(d2))  # 104 vs 48
```

**限制**:不能再添加新属性;不会自动 weakref。

## 9.7 实战:数据类 + property

```python
from dataclasses import dataclass, field
from datetime import date

@dataclass
class Student:
    name: str
    birth_year: int

    @property
    def age(self):
        return date.today().year - self.birth_year

    @property
    def is_adult(self):
        return self.age >= 18

s = Student("Alice", 2005)
print(f"{s.name} {s.age}岁, 成年: {s.is_adult}")
```

## 9.8 描述符(Descriptor)简介

描述符是 property 的底层机制:`__get__` / `__set__` / `__delete__` 三个魔术方法实现。

```python
class Positive:
    """让属性自动保持正数的描述符"""
    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        return obj.__dict__[self.name]

    def __set__(self, obj, value):
        if value <= 0:
            raise ValueError(f"{self.name} 必须为正")
        obj.__dict__[self.name] = value

class Product:
    price = Positive()
    quantity = Positive()

p = Product()
p.price = 100
# p.price = -1  # ValueError
```

**Django ORM 的字段、SQLAlchemy 的 column** 都是描述符的实际应用。

## 9.9 常见误区

- **误区 1**:把 `__getattr__` 和 `__getattribute__` 混淆——前者只在属性找不到时调用,后者总是先调用。
- **误区 2**:`@property` 滥用——所有方法都加 property 会让"属性 vs 方法"边界模糊。
- **误区 3**:`@dataclass` 当万能——它只适合"数据类",业务逻辑多的类还是手写。
- **误区 4**:`__slots__` 与多继承冲突——子类与父类都需声明 slots。

## 9.10 本章小结

1. Python 封装靠"约定 + 名称改写",不靠强制。
2. `__getattr__` / `__setattr__` / `__getattribute__` 是属性访问的钩子。
3. `@property` 用于计算属性、校验、延迟加载。
4. `@dataclass` 自动生成 `__init__` / `__repr__` / `__eq__`;`frozen=True` 不可变。
5. `__slots__` 节省内存,代价是不能加新属性。
6. 描述符是 property 的底层,ORM 大量使用。

## 9.11 练习思考

1. **动手实践**:实现一个 `Temperature` 类,内部存摄氏度,property 提供 `celsius` 和 `fahrenheit`。
2. **动手实践**:用 `@dataclass` 写一个 `Address` 类,字段含 city/street/zip_code,实现 `__str__` 输出格式化地址。
3. **代码分析**:解释 `__getattr__` 与 `__getattribute__` 的区别,各举一个使用场景。
4. **动手实践**:实现一个 `Positive` 描述符(用 `__set__`),验证 `p.value = -1` 抛 ValueError。
5. **拓展探索**:阅读 `attrs` 库源码,对比 `@dataclass` 的扩展能力。

## 9.12 拓展阅读

- Python 数据类官方文档:https://docs.python.org/3/library/dataclasses.html
- 《流畅的 Python》第 19 章 动态属性与特性
- Descriptor HowTo:https://docs.python.org/3/howto/descriptor.html

---

*配套代码示例:`code_examples/09_encapsulation_demo.py`*
*配套练习:`exercises/09_encapsulation_exercises.md`*
