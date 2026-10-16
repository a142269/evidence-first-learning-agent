---
chapter_id: '10'
slug: magic_methods
title: 魔术方法与上下文管理器
kp_ids:
- PY_014
- PY_015
bloom_focus:
- Apply
- Analyze
prerequisites:
- '09'
estimated_minutes: 420
---

# 10: 魔术方法与上下文管理器 · 让对象"活"起来

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 420 分钟(7 学时)
> **前置知识**: §09 封装与 property

## 学习目标

1. 掌握常用魔术方法(`__repr__` / `__str__` / `__eq__` / `__hash__` / `__len__` / `__getitem__` 等)的触发时机。
2. 通过运算符重载(`__add__` / `__mul__` / `__lt__` 等)让自定义类支持内置操作。
3. 实现可迭代对象(`__iter__` / `__next__`)。
4. 掌握 `with` 语句与 `__enter__` / `__exit__`。
5. 用 `@contextmanager` 装饰器简化上下文管理器。

## 10.1 什么是魔术方法

魔术方法(dunder methods)是 Python 数据模型的一部分,用 `__xxx__` 命名,会在特定操作时自动调用。

```python
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):       # repr(v)  / v 在列表中
        return f"Vector({self.x}, {self.y})"

    def __str__(self):        # str(v)  / print(v)
        return f"({self.x}, {self.y})"

    def __add__(self, other): # v1 + v2
        return Vector(self.x + other.x, self.y + other.y)

    def __eq__(self, other):  # v1 == v2
        return self.x == other.x and self.y == other.y

    def __hash__(self):       # 允许放入 set/dict
        return hash((self.x, self.y))

    def __abs__(self):        # abs(v)
        return (self.x ** 2 + self.y ** 2) ** 0.5

    def __len__(self):        # len(v)
        return 2

    def __getitem__(self, i): # v[0]
        return (self.x, self.y)[i]
```

## 10.2 常用魔术方法速查

| 魔术方法 | 触发 | 用途 |
|----------|------|------|
| `__init__` | 实例化 | 构造 |
| `__del__` | 销毁 | 析构(慎用) |
| `__repr__` | `repr()` / REPL | 明确表示 |
| `__str__` | `str()` / `print()` | 友好展示 |
| `__bytes__` | `bytes()` | 字节串 |
| `__format__` | `format()` | 自定义格式 |
| `__eq__` | `==` | 等值 |
| `__ne__` | `!=` | 不等 |
| `__lt__` | `<` | 小于 |
| `__le__` | `<=` | 小于等于 |
| `__gt__` | `>` | 大于 |
| `__ge__` | `>=` | 大于等于 |
| `__add__` | `+` | 加 |
| `__sub__` | `-` | 减 |
| `__mul__` | `*` | 乘 |
| `__matmul__` | `@` | 矩阵乘 |
| `__truediv__` | `/` | 真除 |
| `__floordiv__` | `//` | 整除 |
| `__mod__` | `%` | 取模 |
| `__pow__` | `**` | 幂 |
| `__and__` | `&` | 位与/集合交集 |
| `__or__` | `\|` | 位或/集合并集 |
| `__xor__` | `^` | 位异或/集合对称差 |
| `__neg__` | `-v` | 一元负 |
| `__pos__` | `+v` | 一元正 |
| `__abs__` | `abs()` | 绝对值 |
| `__invert__` | `~v` | 位反 |
| `__len__` | `len()` | 长度 |
| `__getitem__` | `v[i]` | 索引 |
| `__setitem__` | `v[i] = x` | 索引赋值 |
| `__delitem__` | `del v[i]` | 索引删除 |
| `__contains__` | `x in v` | 成员检测 |
| `__iter__` | `iter()` | 迭代 |
| `__next__` | `next()` | 下一个 |
| `__call__` | `v()` | 像函数一样调用 |
| `__enter__` | `with` | 进入 |
| `__exit__` | `with` | 退出 |
| `__bool__` | `bool()` | 真值 |

## 10.3 运算符重载实战

```python
from functools import total_ordering

@total_ordering
class Version:
    def __init__(self, major, minor, patch):
        self.major = major
        self.minor = minor
        self.patch = patch

    def __repr__(self):
        return f"Version({self.major}.{self.minor}.{self.patch})"

    def __eq__(self, other):
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other):
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __hash__(self):
        return hash((self.major, self.minor, self.patch))

v1 = Version(1, 2, 3)
v2 = Version(1, 2, 4)
print(v1 < v2)       # True
print(v1 == Version(1, 2, 3))  # True
print(sorted([v2, v1, Version(1, 1, 0)]))  # 按版本号排序
```

`@total_ordering` 装饰器让你只写 `__eq__` + `__lt__`,自动补齐其他比较。

## 10.4 可迭代对象

任何实现了 `__iter__` 的对象都是可迭代的;`__iter__` 返回一个迭代器(有 `__next__` 方法):

```python
class Countdown:
    def __init__(self, start):
        self.start = start

    def __iter__(self):
        n = self.start
        while n > 0:
            yield n     # 生成器,自动实现 __iter__ / __next__
            n -= 1

for i in Countdown(5):
    print(i)  # 5 4 3 2 1
```

**生成器 vs 类实现迭代器**:多数场景用生成器(见 §15)更简洁。

## 10.5 __call__:让对象像函数

```python
class Multiplier:
    def __init__(self, factor):
        self.factor = factor

    def __call__(self, x):
        return x * self.factor

double = Multiplier(2)
print(double(10))  # 20(像函数一样调用)

# 用途:函数工厂、参数化函数、装饰器实现
```

## 10.6 上下文管理器与 with

`with` 语句保证资源总是被清理:

```python
# 文件操作:标准库示例
with open("data.txt") as f:
    content = f.read()
# f 自动关闭,即使中间抛异常
```

### 10.6.1 自定义上下文管理器

```python
class Timer:
    """测量代码块执行时间"""
    def __enter__(self):
        import time
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.elapsed = time.perf_counter() - self._start
        # 返回 True 抑制异常,False/None 传播异常
        return False

with Timer() as t:
    total = sum(i ** 2 for i in range(1_000_000))
print(f"耗时: {t.elapsed*1000:.1f}ms")
```

### 10.6.2 contextmanager 装饰器

`@contextmanager` 把生成器函数变成上下文管理器:

```python
from contextlib import contextmanager

@contextmanager
def timer(label="block"):
    import time
    t0 = time.perf_counter()
    try:
        yield   # with 体在这里执行
    finally:
        elapsed = time.perf_counter() - t0
        print(f"{label}: {elapsed*1000:.1f}ms")

with timer("compute"):
    sum(range(1_000_000))
# compute: 24.5ms
```

### 10.6.3 异常抑制

```python
@contextmanager
def ignore(*exceptions):
    try:
        yield
    except exceptions:
        pass

with ignore(ValueError, KeyError):
    int("abc")  # 不报错
```

**标准库常用上下文管理器**:`open()`、`closing()`、`redirect_stdout()`、`suppress()`。

## 10.7 实战:可累加计时器

```python
import time
from contextlib import contextmanager

class AccumulatingTimer:
    def __init__(self):
        self.total = 0.0

    @contextmanager
    def measure(self):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.total += time.perf_counter() - t0

timer = AccumulatingTimer()
with timer.measure():
    sum(range(1_000_000))
with timer.measure():
    sum(range(2_000_000))
print(f"累计: {timer.total*1000:.1f}ms")
```

## 10.8 常见误区

- **误区 1**:`__del__` 不可靠——CPython 立刻回收,但 PyPy/Jython 不一定。推荐用 `with`。
- **误区 2**:`__eq__` 写了但忘写 `__hash__`——类变成 unhashable,无法放入 set/dict。
- **误区 3**:`__enter__` / `__exit__` 抛异常时返回 True——这会"吞掉"异常,慎用。
- **误区 4**:运算符重载做不相关的事(如 `__add__` 实现减法)——严重违反最小惊讶原则。
- **误区 5**:`__len__` 返回负数——违反 Python 数据模型约定,可能让 `bool(v)` 抛 ValueError。

## 10.9 本章小结

1. 魔术方法是 Python 数据模型的核心,定义对象在特定操作下的行为。
2. `__repr__` / `__str__` / `__eq__` / `__hash__` 是最常用的一组。
3. 运算符重载(`__add__` / `__lt__` 等)让自定义类支持内置语法,`@total_ordering` 可自动补齐。
4. `__iter__` / `__next__` 让对象可迭代;`__call__` 让对象可调用。
5. `with` 语句通过 `__enter__` / `__exit__` 保证资源清理;`@contextmanager` 简化实现。
6. `__del__` 不可靠,推荐用上下文管理器。

## 10.10 练习思考

1. **动手实践**:为 `Vector` 类实现 `__sub__` / `__mul__` / `__neg__`,让向量支持加减乘与取负。
2. **动手实践**:用 `@total_ordering` 让一个 `Money` 类支持 `<` / `>` / `<=` / `>=`(只写 `__eq__` + `__lt__`)。
3. **动手实践**:实现一个 `Range` 类(简化版 range),用 `__getitem__` / `__len__` 让它支持索引与长度。
4. **动手实践**:用 `@contextmanager` 实现 `temporary_chdir(path)`,进入时切到指定目录,退出时还原。
5. **拓展探索**:阅读 `pathlib.Path` 源码,看它实现了哪些魔术方法。

## 10.11 拓展阅读

- Python 数据模型:https://docs.python.org/3/reference/datamodel.html
- contextlib 模块:https://docs.python.org/3/library/contextlib.html
- 《流畅的 Python》第 13 章 接口:从协议到抽象基类

---

*配套代码示例:`code_examples/10_magic_methods_demo.py`*
*配套练习:`exercises/10_magic_methods_exercises.md`*
