---
title: "dataclasses 官方文档解读"
authors: [Python Documentation Team]
year: 2024
url: https://docs.python.org/3/library/dataclasses.html
kp_refs: [PY_009, PY_011, PY_013]
summary_zh: Python 3.7+ 标准库 dataclasses 完整指南,简化数据类编写。
---

# dataclass 官方文档解读

> **面向读者**:已学完 §07-§09 章节,想用更现代方式写数据类的同学

## 摘要

`dataclasses` 是 Python 3.7 引入的标准库,通过装饰器自动生成 `__init__` / `__repr__` / `__eq__` 等方法,大幅简化数据类的样板代码。截至 2024 年,3.10+ 增加 `slots` / `kw_only` 等参数,功能更加完善。

## 核心 API

### @dataclass 装饰器参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `init` | True | 生成 `__init__` |
| `repr` | True | 生成 `__repr__` |
| `eq` | True | 生成 `__eq__` |
| `order` | False | 生成比较方法 |
| `unsafe_hash` | False | 强制 `__hash__` |
| `frozen` | False | 不可变(禁止赋值) |
| `match_args` | True | 生成 `__match_args__`(3.10+) |
| `kw_only` | False | 全部字段为 keyword-only(3.10+) |
| `slots` | False | 添加 `__slots__`(3.10+) |

### field() 函数

```python
from dataclasses import dataclass, field

@dataclass
class Article:
    title: str
    author: str
    tags: list = field(default_factory=list)  # 可变默认值
    views: int = field(default=0)
    _internal_id: int = field(default=None, repr=False)  # 不在 repr 中
    timestamp: datetime = field(default=None, compare=False)  # 不参与比较
```

## 实战示例

### 简单数据类

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

p = Point(3, 4)
print(p)            # Point(x=3, y=4)
print(p == Point(3, 4))  # True
```

### 不可变 + hashable

```python
@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float

c = Coordinate(39.9, 116.4)
# c.lat = 0  # FrozenInstanceError
cache = {c: "北京"}
```

### 继承

```python
@dataclass
class Person:
    name: str
    age: int

@dataclass
class Employee(Person):
    employee_id: str
    department: str = "Engineering"
```

### 继承 + 默认值(小心)

```python
# ❌ 父类有默认值,子类会出问题
@dataclass
class Parent:
    a: int = 0

@dataclass
class Child(Parent):
    b: int  # TypeError: non-default argument 'b' follows default argument 'a'
```

解决:用 `kw_only=True`(3.10+)或全字段给默认值。

### __post_init__ 验证

```python
@dataclass
class User:
    name: str
    age: int

    def __post_init__(self):
        if self.age < 0:
            raise ValueError("age 不能为负")
```

### slots 优化内存

```python
@dataclass(slots=True)  # 3.10+
class Point:
    x: float
    y: float

# 内存占用更小,属性访问略快
# 不能再加新属性
```

## 与 attrs / Pydantic 的对比

| 库 | 优势 | 劣势 |
|----|------|------|
| `dataclass` | 标准库,无依赖 | 字段类型需手动注解;无运行时校验 |
| `attrs` | 老牌,功能丰富 | 第三方依赖 |
| `Pydantic` | 运行时类型校验,FastAPI 集成 | 较重;v1/v2 API 不兼容 |
| `msgspec` | 极快,JSON 序列化首选 | 较新,生态小 |

## 对 Python 课程学习的启示

- **优先 dataclass**:数据类需求首选标准库,无依赖
- **frozen=True 不可变**:常量、缓存 key、配置项
- **post_init 校验**:复杂约束可在 `__post_init__` 中加
- **slots=True**(3.10+):大量实例时节省内存

## 链接

- 官方文档:https://docs.python.org/3/library/dataclasses.html
- PEP 557:https://peps.python.org/pep-0557/
- Real Python 教程:https://realpython.com/python-data-classes/
