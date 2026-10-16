---
chapter_id: '03'
slug: functions
title: 函数定义与参数
kp_ids:
- PY_005
bloom_focus:
- Apply
- Analyze
prerequisites:
- '02'
estimated_minutes: 240
---

# 03: 函数定义与参数 · 代码复用的起点

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 240 分钟(4 学时)
> **前置知识**: §02 控制流

## 学习目标

1. 掌握 `def` 关键字定义函数,理解函数是一等对象(first-class)。
2. 熟练使用位置参数、关键字参数、默认参数、`*args` 与 `**kwargs`。
3. 理解参数解包(packing/unpacking)与作用域(LEGB 规则)。
4. 掌握 `return` 的多值返回、文档字符串与类型注解。
5. 理解闭包与 lambda 表达式的适用场景。
6. 掌握函数式编程工具:`map` / `filter` / `reduce` / `functools.partial`。

## 3.1 函数是第一类对象

在 Python 中,函数与整数、字符串一样是对象:

- 可以赋值给变量
- 可以作为参数传递
- 可以作为返回值
- 可以存入容器

```python
def greet(name):
    return f"Hello, {name}!"

# 1. 赋值
f = greet
print(f("Python"))  # Hello, Python!

# 2. 存入列表
funcs = [str.upper, str.lower, str.title]
for func in funcs:
    print(func("hello"))

# 3. 作为参数(map 高阶函数)
names = ["alice", "bob", "charlie"]
greeted = list(map(greet, names))
# ['Hello, alice!', 'Hello, bob!', 'Hello, charlie!']
```

## 3.2 函数定义

```python
def 函数名(参数1: 类型, 参数2: 类型 = 默认值) -> 返回类型:
    """文档字符串(docstring)"""
    函数体
    return 返回值
```

```python
def add(a: int, b: int) -> int:
    """返回两个整数的和。

    Args:
        a: 第一个加数
        b: 第二个加数

    Returns:
        a + b 的结果
    """
    return a + b
```

## 3.3 参数类型

### 3.3.1 位置参数 vs 关键字参数

```python
def describe(name, age, city):
    print(f"{name}, {age}岁, 来自 {city}")

# 位置参数
describe("Alice", 25, "Beijing")

# 关键字参数(顺序无关)
describe(city="Shanghai", name="Bob", age=30)

# 混用:位置参数必须在关键字参数之前
describe("Charlie", city="Guangzhou", age=28)
```

### 3.3.2 默认参数

```python
def greet(name, greeting="Hello", punctuation="!"):
    return f"{greeting}, {name}{punctuation}"

greet("Alice")                    # Hello, Alice!
greet("Bob", greeting="Hi")       # Hi, Bob!
greet("Carol", "Hey", "~~~")      # Hey, Carol~~~
```

**陷阱:可变默认参数**

```python
# ❌ 错误写法
def add_item(item, lst=[]):
    lst.append(item)
    return lst

print(add_item(1))  # [1]
print(add_item(2))  # [1, 2]  ← 残留!

# ✅ 正确写法
def add_item(item, lst=None):
    if lst is None:
        lst = []
    lst.append(item)
    return lst
```

**原因**:默认参数在函数定义时计算一次,后续调用共享同一个对象。

### 3.3.3 *args 与 **kwargs

```python
def func(*args, **kwargs):
    print("args:", args)      # 元组
    print("kwargs:", kwargs)  # 字典

func(1, 2, 3, name="Alice", age=25)
# args: (1, 2, 3)
# kwargs: {'name': 'Alice', 'age': 25}
```

**典型用途**:装饰器、参数透传、子类覆盖 `__init__`。

```python
class MyDict(dict):
    def __init__(self, *args, default=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.default = default
```

### 3.3.4 强制关键字参数(Python 3+)

```python
def divide(a, b, *, precision=2):
    """* 之后的参数必须用关键字传"""
    return round(a / b, precision)

divide(10, 3)              # 3.33
divide(10, 3, precision=4) # 3.3333
divide(10, 3, 4)           # ❌ TypeError
```

## 3.4 return 语句

```python
# 1. 无 return → 返回 None
def f1(): pass
print(f1())  # None

# 2. 单值返回
def square(x): return x ** 2

# 3. 多值返回(实际是元组)
def min_max(lst):
    return min(lst), max(lst)

a, b = min_max([3, 1, 4, 1, 5, 9])
# a=1, b=9

# 4. 提前返回(guard clause)
def process(data):
    if not data:
        return  # 提前退出
    # ... 复杂处理
```

## 3.5 作用域:LEGB 规则

Python 查找名字的顺序:**L**ocal → **E**nclosing → **G**lobal → **B**uilt-in

```python
x = "global"           # G

def outer():
    x = "enclosing"    # E
    def inner():
        x = "local"    # L
        print(x)       # local
    inner()

# global 与 nonlocal
counter = 0
def inc():
    global counter     # 声明使用全局变量
    counter += 1

def outer():
    n = 0
    def inner():
        nonlocal n     # 声明使用外层(非全局)变量
        n += 1
    inner()
    return n
```

**最佳实践**:尽量避免 `global`,优先用参数传入、返回值传出。

## 3.6 闭包(Closure)

闭包 = 函数 + 其引用的外部变量。闭包能"捕获"定义时的环境:

```python
def make_multiplier(factor):
    def multiplier(x):
        return x * factor  # factor 被闭包捕获
    return multiplier

double = make_multiplier(2)
triple = make_multiplier(3)
print(double(5))  # 10
print(triple(5))  # 15
```

**应用**:装饰器、回调函数、函数工厂。

## 3.7 lambda 表达式

匿名函数,只允许一个表达式:

```python
square = lambda x: x ** 2
print(square(5))  # 25

# 排序 key
students = [("Alice", 85), ("Bob", 92), ("Charlie", 78)]
students.sort(key=lambda s: s[1], reverse=True)
# [('Bob', 92), ('Alice', 85), ('Charlie', 78)]
```

**何时用 lambda**:
- 简单的、一次性的函数(回调)
- 配合 `map` / `filter` / `sorted` 的 key

**何时不用**:复杂逻辑、有名字更好读、有文档价值——这时用 `def`。

## 3.8 函数式工具

### 3.8.1 map / filter

```python
nums = [1, 2, 3, 4, 5]
squared = list(map(lambda x: x**2, nums))
# [1, 4, 9, 16, 25]

evens = list(filter(lambda x: x % 2 == 0, nums))
# [2, 4]
```

### 3.8.2 functools.reduce

```python
from functools import reduce
total = reduce(lambda a, b: a + b, [1, 2, 3, 4, 5])
# 15
```

### 3.8.3 partial 偏函数

```python
from functools import partial
def power(base, exp):
    return base ** exp

square = partial(power, exp=2)
cube = partial(power, exp=3)
print(square(5))  # 25
print(cube(5))    # 125
```

## 3.9 文档字符串(Docstring)

PEP 257 规范:

```python
def fetch_user(user_id: int) -> dict:
    """从数据库获取用户信息。

    Args:
        user_id: 用户唯一标识

    Returns:
        包含用户字段的字典

    Raises:
        UserNotFoundError: 用户不存在
    """
    ...
```

**风格**:Google、NumPy、Sphinx 三种常见,选一种保持一致。

## 3.10 常见误区

- **误区 1**:可变默认参数(`def f(lst=[])`)——共享同一个 list 对象。
- **误区 2**:晚绑定闭包——循环里创建 lambda/函数时,变量值在调用时才解析。
  ```python
  funcs = [lambda i=i: i**2 for i in range(5)]  # ✅ 默认参数捕获
  funcs = [lambda: i**2 for i in range(5)]      # ❌ 全部返回 16
  ```
- **误区 3**:函数嵌套太深——超过 3 层应拆函数。
- **误区 4**:滥用 `global`——破坏封装,测试困难。
- **误区 5**:lambda 内部不能用 `if-else` 语句,只能用三元表达式。

## 3.11 本章小结

1. 函数是一等对象:可赋值、可传参、可返回、可入容器。
2. 参数:位置、关键字、默认、`*args` / `**kwargs`、强制关键字(`*,`)。
3. 默认参数必须是不可变对象(推荐 `None` 作为哨兵)。
4. 作用域 LEGB 规则;`global` 与 `nonlocal` 用于内层修改外层。
5. 闭包捕获定义时的环境;lambda 适合简单一次性函数。
6. `map` / `filter` / `reduce` / `partial` 是函数式编程工具。
7. 文档字符串(PEP 257)是函数的可读性保障。

## 3.12 练习思考

1. **代码分析**:下面代码输出什么?为什么?
   ```python
   def f(lst=[]):
       lst.append(1)
       return lst
   print(f())
   print(f())
   print(f())
   ```
2. **动手实践**:写一个 `make_counter()` 函数,返回的 counter 每次调用值加 1(用闭包,不用 global)。
3. **动手实践**:写 `*args` / `**kwargs` 版本的 `log(level, *messages, **fields)`,输出格式 `level | msg1 msg2 | field=value ...`。
4. **动手实践**:用 `functools.reduce` 计算列表最大值。
5. **代码优化**:把以下函数改写成无 `global` 的纯函数:
   ```python
   total = 0
   def add_to_total(x):
       global total
       total += x
   ```

## 3.13 拓展阅读

- Python 函数定义官方文档:https://docs.python.org/3/tutorial/controlflow.html#defining-functions
- PEP 257 — Docstring 约定:https://peps.python.org/pep-0257/
- 《流畅的 Python》第 5 章 一等函数

---

*配套代码示例:`code_examples/03_functions_demo.py`*
*配套练习:`exercises/03_functions_exercises.md`*
