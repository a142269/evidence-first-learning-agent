---
chapter_id: '16'
slug: decorators
title: 装饰器与闭包
kp_ids:
- PY_023
bloom_focus:
- Analyze
- Create
prerequisites:
- '15'
estimated_minutes: 240
---

# 16: 装饰器与闭包 · Python 元编程的入门钥匙

> **Bloom 层级**: Analyze → Create
> **建议学时**: 240 分钟(4 学时)
> **前置知识**: §15 迭代器与生成器

## 学习目标

1. 深入理解闭包与作用域链。
2. 掌握简单装饰器与 `@functools.wraps`。
3. 掌握带参数装饰器与类装饰器。
4. 理解装饰器堆叠的执行顺序。
5. 能用装饰器实现日志、计时、权限校验、重试等横切关注点。

## 16.1 装饰器是什么

装饰器(decorator)是**接收函数并返回函数**的可调用对象,用于在不修改原函数代码的情况下,给函数"加功能"。

```python
# 装饰器模式
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("调用前")
        result = func(*args, **kwargs)
        print("调用后")
        return result
    return wrapper

@my_decorator
def greet(name):
    print(f"Hello, {name}!")

greet("Alice")
# 调用前
# Hello, Alice!
# 调用后
```

`@my_decorator` 等价于 `greet = my_decorator(greet)`。

## 16.2 闭包:装饰器的基础

闭包 = 函数 + 其引用的外部变量(见 §03):

```python
def outer(x):
    def inner(y):
        return x + y  # 闭包捕获 x
    return inner

add_10 = outer(10)
print(add_10(5))  # 15
```

## 16.3 @functools.wraps

装饰器会"替换"原函数,导致 `__name__` / `__doc__` 丢失。用 `@wraps` 保留元信息:

```python
from functools import wraps

def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

## 16.4 实战:常用装饰器

### 16.4.1 计时器

```python
import time
from functools import wraps

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        print(f"{func.__name__} 耗时 {elapsed*1000:.1f}ms")
        return result
    return wrapper

@timer
def heavy():
    sum(i ** 2 for i in range(1_000_000))

heavy()
```

### 16.4.2 调用日志

```python
def logged(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"call {func.__name__}({args}, {kwargs})")
        result = func(*args, **kwargs)
        print(f"return {result!r}")
        return result
    return wrapper
```

### 16.4.3 缓存(Memoization)

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

# 第 100 项瞬间算完
print(fib(100))
```

### 16.4.4 重试

```python
import time
from functools import wraps

def retry(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        raise
                    print(f"第 {attempt} 次失败: {e},重试中...")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry(max_attempts=3, delay=0.1)
def flaky():
    import random
    if random.random() < 0.7:
        raise RuntimeError("flaky")
    return "ok"
```

## 16.5 带参数的装饰器

装饰器本身需要参数(像上面的 `retry(max_attempts=3)`),需要三层函数:

```python
def repeat(n):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(n):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@repeat(3)
def hello():
    print("hi")

hello()  # hi hi hi
```

## 16.6 类装饰器

用类实现装饰器,基于 `__call__`:

```python
class CountCalls:
    def __init__(self, func):
        wraps(func)(self)  # 复制元信息
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"{self.func.__name__} 被调用 {self.count} 次")
        return self.func(*args, **kwargs)

@CountCalls
def hello():
    print("hi")

hello()  # hi (1 次)
hello()  # hi (2 次)
print(hello.count)  # 2
```

## 16.7 装饰器堆叠

```python
@timer
@logged
def add(a, b):
    return a + b

# 等价:add = timer(logged(add))
# 调用顺序:timer → logged → add → logged → timer
add(1, 2)
```

**执行顺序**:从上到下装饰(从下到上调用)——离函数最近的装饰器是"最里层"。

## 16.8 实战:Flask 风格路由

```python
routes = {}

def route(path):
    def decorator(func):
        routes[path] = func
        return func
    return decorator

@route("/")
def index():
    return "home"

@route("/about")
def about():
    return "about"

print(routes)  # {'/': <function index>, '/about': <function about>}
```

## 16.9 实战:权限校验

```python
from functools import wraps

def require_role(role):
    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            if user.get("role") != role:
                raise PermissionError(f"需要 {role} 权限")
            return func(user, *args, **kwargs)
        return wrapper
    return decorator

@require_role("admin")
def delete_user(user, user_id):
    return f"已删除 {user_id}"

# 普通用户调用抛异常
try:
    delete_user({"role": "user"}, 42)
except PermissionError as e:
    print(f"权限不足: {e}")
```

## 16.10 常见误区

- **误区 1**:装饰器忘加 `@wraps(func)` —— `__name__` 等元信息丢失。
- **误区 2**:带参数装饰器写成两层函数 —— 必须是三层。
- **误区 3**:装饰器返回 None —— 装饰器必须返回 callable。
- **误区 4**:装饰器堆叠顺序搞反 —— 装饰是从下到上,调用是从上到下。
- **误区 5**:装饰器里用 `functools.wraps(func)` 漏写 `()` —— `wraps` 是装饰器工厂,要调用。

## 16.11 本章小结

1. 装饰器 = 接收函数返回函数的可调用对象,基于闭包。
2. `@functools.wraps` 保留原函数元信息(`__name__` / `__doc__`)。
3. 带参数装饰器需三层结构:工厂 + 装饰器 + 包装函数。
4. 类装饰器基于 `__call__`,可维护状态(调用计数等)。
5. 装饰器堆叠:`@A @B def f` 等价 `f = A(B(f))`,调用从外到内。
6. 实战:计时、日志、缓存、重试、权限校验、路由注册。
7. 装饰器是 Python 元编程的入口,理解它才能理解 Flask/Django 中间件。

## 16.12 练习思考

1. **动手实践**:实现一个 `cache(func)` 装饰器,用 dict 缓存函数结果(无限大小)。
2. **动手实践**:实现一个 `@rate_limit(calls_per_second)` 装饰器,限制函数调用频率。
3. **代码分析**:解释下面装饰器堆叠的调用顺序:
   ```python
   @timer
   @logged
   @retry(3)
   def f(): pass
   ```
4. **动手实践**:用类装饰器实现一个 `CountCalls` 类,统计函数调用次数,可通过 `f.count` 访问。
5. **拓展探索**:阅读 `functools.lru_cache` 源码,看它如何用装饰器实现缓存。

## 16.13 装饰器的实现原理

理解了装饰器的语法后,理解它的实现原理能帮助你写出更健壮的代码。

### 16.13.1 闭包陷阱:late binding

```python
# ❌ 经典陷阱
funcs = [lambda i=i: i**2 for i in range(5)]  # 用默认参数捕获
print([f() for f in funcs])  # [0, 1, 4, 9, 16]

# 错误写法
funcs = [lambda: i**2 for i in range(5)]
print([f() for f in funcs])  # [16, 16, 16, 16, 16] ← 全部 16!
```

原因:lambda 在调用时才查找 `i`,循环结束时 `i = 4`,所以全部平方得到 16。

### 16.13.2 装饰器在 Python 中的地位

装饰器是 Python 元编程的"基础工具",后续高级特性都基于它:

- **Flask 路由**:`@app.route("/")` 装饰器把函数注册到 URL 映射
- **Django 视图**:`@login_required` 装饰器实现权限校验
- **pytest**:`@pytest.fixture` 装饰器标记测试夹具
- **asyncio**:`@asyncio.coroutine`(旧)/`async def`(新)装饰器标记协程
- **dataclass**:`@dataclass` 装饰器自动生成 `__init__` 等魔术方法

### 16.13.3 性能考量

装饰器会带来轻微的性能开销(额外的函数调用),但通常可以忽略:
- 普通装饰器:每次调用增加 1-2 个 stack frame
- `lru_cache`:首次慢,后续接近 dict 查询
- 嵌套多层装饰器:栈深,profile 时可见

装饰器不应放在"性能热点路径"上,但大部分应用层代码可以放心用。

---

## 16.14 拓展阅读

- PEP 318 装饰器:https://peps.python.org/pep-0318/
- functools 模块:https://docs.python.org/3/library/functools.html
- 《流畅的 Python》第 7 章 函数装饰器和闭包、第 24 章 类元编程

---

*配套练习:`exercises/16_decorators_exercises.md`*
