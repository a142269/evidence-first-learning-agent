---
chapter_ref: "16"
chapter_title: "装饰器与闭包"
kp_refs: [PY_023]
bloom_focus: [Analyze, Create, Evaluate]
total_points: 50
deadline_hint: 本章配套学习时长 4 学时
---

# 装饰器与闭包 · 章节练习

> **配套**:A3 章节 §16 装饰器与闭包

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
装饰器本质上是什么?

- A. 一个类
- B. 接收函数并返回函数的可调用对象
- C. 一个语法
- D. Python 内置特性

<details><summary>答案</summary>B。装饰器是 callable,接受函数,返回(包装后的)函数。</details>

### Q2(Apply)
`@functools.wraps(func)` 的作用是?

- A. 加快装饰器执行
- B. 保留原函数的 `__name__` / `__doc__` 等元信息
- C. 自动缓存函数结果
- D. 让装饰器接受参数

<details><summary>答案</summary>B。@wraps 复制原函数元信息到 wrapper,避免被装饰函数"身份丢失"。</details>

### Q3(Apply)
带参数装饰器需要几层函数嵌套?

- A. 1 层
- B. 2 层
- C. 3 层
- D. 4 层

<details><summary>答案</summary>C。三层:参数工厂函数 + 装饰器 + 包装函数。</details>

### Q4(Analyze)
下面代码的调用顺序是?
```python
@A
@B
@C
def f(): pass
```

- A. A → B → C → f
- B. f → C → B → A
- C. C → B → A → f
- D. f → A → B → C

<details><summary>答案</summary>A。从外到内:A(B(C(f))),调用时先进入 A,再 B,再 C,最后 f。</details>

### Q5(Evaluate)
需要"调用前打日志,调用后打印耗时,失败重试 3 次",推荐用?

- A. 直接修改函数
- B. 三个装饰器堆叠
- C. 一个复杂装饰器
- D. 写在调用处

<details><summary>答案</summary>B。三个独立装饰器堆叠,符合单一职责,可灵活组合。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`@functools.lru_cache(maxsize=128)` 是 Python 内置的 ______ 装饰器。

<details><summary>答案</summary>缓存 / memoization</details>

### Q7(Apply)
类装饰器基于魔术方法 `______` 实现,把对象变成可调用。

<details><summary>答案</summary>__call__</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
为什么装饰器内部必须写 `@functools.wraps(func)`?如果不写会出什么问题?

<details><summary>参考答案</summary>`@wraps(func)` 复制原函数的 `__name__` / `__doc__` / `__module__` / `__qualname__` / `__dict__` 等元信息到 wrapper 函数。
不写的问题:
1. `func.__name__` 变成 `wrapper`,日志/调试看不出真实函数名
2. `help(func)` 显示 wrapper 的 docstring(可能是 None)
3. 反射/内省失效(如 `inspect.signature` / `__wrapped__`)
4. 装饰器堆叠时,内层装饰器看到的是外层 wrapper,链条断裂
5. IDE 跳转、覆盖率工具、单元测试报告都受影响</details>

### Q9(Analyze)
装饰器堆叠 `@A @B @C def f` 的执行顺序是什么?为什么?

<details><summary>参考答案</summary>执行顺序:从下到上装饰(A 包装 B 包装 C 包装 f),从上到下调用(A 包裹 B 包裹 C 包裹 f)。
原因:
1. 装饰阶段:Python 按从上到下读装饰器,先读 `@A`,但 `A` 拿到的是"被 B 和 C 装饰后的 f"
2. 等价于:`f = A(B(C(f)))`
3. 调用 `f()` 时,先进入 A 的 wrapper,执行 A 前置逻辑,然后调用 B(B 的前置 + 调用 C,C 的前置 + 调用原 f),再依次返回
4. 类比洋葱:从外到内,再从内到外</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现一个 `cache(func)` 装饰器,用 dict 缓存函数结果,支持任意参数。

<details><summary>参考实现</summary>

```python
from functools import wraps

def cache(func):
    cached = {}
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 用 args + sorted kwargs 做 key
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cached:
            cached[key] = func(*args, **kwargs)
        return cached[key]
    return wrapper

@cache
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

print(fib(100))  # 瞬间
```

</details>

### Q11(Create)
实现一个 `retry(max_attempts=3, delay=0, exceptions=(Exception,))` 装饰器:函数失败时重试,最多 max_attempts 次,每次间隔 delay 秒,只捕获 exceptions 指定的异常类型。

<details><summary>参考实现</summary>

```python
import time
from functools import wraps

def retry(max_attempts=3, delay=0, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        raise
                    print(f"  {func.__name__} 第 {attempt} 次失败: {e!r}")
                    if delay > 0:
                        time.sleep(delay)
        return wrapper
    return decorator

@retry(max_attempts=3, delay=0.1, exceptions=(ValueError,))
def parse(s):
    if not s:
        raise ValueError("empty")
    return int(s)
```

</details>

---

*本章配套练习覆盖简单装饰器、@wraps、带参数装饰器、类装饰器、堆叠顺序、实战。*
