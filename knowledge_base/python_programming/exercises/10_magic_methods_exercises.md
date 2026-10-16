---
chapter_ref: "10"
chapter_title: "魔术方法与上下文管理器"
kp_refs: [PY_014, PY_015]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 7 学时
---

# 魔术方法与上下文管理器 · 章节练习

> **配套**:A3 章节 §10 魔术方法与上下文管理器
> **配对代码**:`code_examples/10_magic_methods_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
`__str__` 与 `__repr__` 的区别是?

- A. 两者完全一样
- B. `__str__` 给用户看,`__repr__` 给开发者看
- C. `__str__` 是魔术方法,`__repr__` 不是
- D. `__str__` 返回字符串,`__repr__` 返回其他

<details><summary>答案</summary>B。`__repr__` 是"明确表示"(尽量可执行),`__str__` 是"友好展示"。</details>

### Q2(Apply)
让 `len(obj)` 工作,需要实现?

- A. `__str__`
- B. `__len__`
- C. `__size__`
- D. `__length__`

<details><summary>答案</summary>B。`__len__` 是被 len() 调用的魔术方法。</details>

### Q3(Apply)
`with` 语句结束时调用?

- A. `__init__`
- B. `__del__`
- C. `__exit__`
- D. `__close__`

<details><summary>答案</summary>C。with 体结束时调用 `__exit__(exc_type, exc_val, exc_tb)`。</details>

### Q4(Analyze)
`@contextmanager` 装饰器把什么变成上下文管理器?

- A. 普通函数
- B. 类
- C. 生成器函数
- D. lambda

<details><summary>答案</summary>C。@contextmanager 装饰的生成器函数,yield 处是 with 体的执行点。</details>

### Q5(Evaluate)
写自定义类 `Vector` 让 `v1 + v2` 生效,需要实现?

- A. `__add__`
- B. `__plus__`
- C. `operator.add`
- D. 重载 +

<details><summary>答案</summary>A。Python 没有"重载运算符",通过实现对应的魔术方法(`__add__`)让 + 工作。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`@functools.total_ordering` 让你只写 `__eq__` + `__lt__`,自动补齐其他 ______ 个比较方法。

<details><summary>答案</summary>4(__le__ / __gt__ / __ge__)</details>

### Q7(Apply)
`__exit__` 返回 `True` 表示 ______ 异常。

<details><summary>答案</summary>抑制</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
`__enter__` 与 `__exit__` 的参数分别是什么?`__exit__` 返回 True 与 False/None 有什么区别?

<details><summary>参考答案</summary>- `__enter__(self)`:进入 with 体时调用,返回值赋给 as 后的变量
- `__exit__(self, exc_type, exc_val, exc_tb)`:退出时调用,3 个异常参数(无异常时全 None)
- 返回 `True`:抑制异常(不向上传播)
- 返回 `False` / `None` / 不 return:异常正常传播</details>

### Q9(Analyze)
用 `@contextmanager` 装饰一个生成器函数实现"计时器"上下文管理器。说明 yield 处发生了什么。

<details><summary>参考答案</summary>```python
from contextlib import contextmanager
import time

@contextmanager
def timer(label="block"):
    t0 = time.perf_counter()
    try:
        yield  # with 体在这里执行
    finally:
        print(f"{label}: {time.perf_counter() - t0:.3f}s")

with timer("compute"):
    sum(i ** 2 for i in range(1_000_000))
```
yield 之前的代码相当于 `__enter__`,yield 之后的代码(在 finally 中)相当于 `__exit__`。contextmanager 把生成器自动包装成符合 with 协议的类。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
为 `Vector` 类实现 `__add__` / `__sub__` / `__mul__(scalar)` / `__rmul__(scalar)` / `__neg__` / `__abs__`,让向量支持加减乘与取负、取模长。

<details><summary>参考实现</summary>

```python
class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vector(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar):
        return self.__mul__(scalar)

    def __neg__(self):
        return Vector(-self.x, -self.y)

    def __abs__(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5
```

</details>

### Q11(Create)
用 `@contextmanager` 实现 `temporary_value(obj, attr, new_value)`,把 obj.attr 临时改为 new_value,with 体退出后还原(包括异常情况)。

<details><summary>参考实现</summary>

```python
from contextlib import contextmanager

@contextmanager
def temporary_value(obj, attr, new_value):
    old = getattr(obj, attr)
    setattr(obj, attr, new_value)
    try:
        yield
    finally:
        setattr(obj, attr, old)

class Config:
    debug = False

c = Config()
with temporary_value(c, "debug", True):
    print(c.debug)  # True
print(c.debug)  # False(已还原)
```

</details>

---

*本章配套代码:`code_examples/10_magic_methods_demo.py` 包含 7 个 demo 函数,涵盖运算符重载、比较、可迭代、`__call__`、with、contextmanager。*
