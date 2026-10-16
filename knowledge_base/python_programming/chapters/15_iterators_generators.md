---
chapter_id: '15'
slug: iterators_generators
title: 迭代器与生成器
kp_ids:
- PY_022
bloom_focus:
- Analyze
- Evaluate
prerequisites:
- '10'
estimated_minutes: 240
---

# 15: 迭代器与生成器 · Python 惰性计算的精髓

> **Bloom 层级**: Analyze → Evaluate
> **建议学时**: 240 分钟(4 学时)
> **前置知识**: §10 魔术方法

## 学习目标

1. 深入理解迭代器协议(`__iter__` / `__next__`)。
2. 掌握 `yield` 与生成器函数的工作原理。
3. 理解惰性计算在大数据流处理中的优势。
4. 掌握 `send` / `throw` / `close` 三个生成器方法。
5. 能用生成器改写"读全部"的循环为惰性版本。

## 15.1 迭代器协议

Python 中"可迭代"与"迭代器"是两个概念:

- **可迭代对象(iterable)**:有 `__iter__` 方法,返回迭代器
- **迭代器(iterator)**:有 `__iter__` 和 `__next__` 方法,`__next__` 返回下一个值或抛 StopIteration

```python
# 列表是可迭代对象
nums = [1, 2, 3]
it = iter(nums)       # iter() 调用 __iter__
print(next(it))       # 1(next() 调用 __next__)
print(next(it))       # 2
print(next(it))       # 3
# print(next(it))     # StopIteration

# 字符串、字典、集合都是可迭代对象
for c in "abc":       # 实际:iter("abc") → 逐字符
    pass
```

## 15.2 自定义迭代器

实现 `__iter__` 和 `__next__`:

```python
class Countdown:
    def __init__(self, start):
        self.start = start
        self.current = start

    def __iter__(self):
        return self

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1

for i in Countdown(3):
    print(i)  # 3 2 1
```

## 15.3 生成器:更优雅的迭代器

用 `yield` 关键字定义的函数,自动实现迭代器协议:

```python
def countdown(start):
    n = start
    while n > 0:
        yield n
        n -= 1

for i in countdown(3):
    print(i)  # 3 2 1
```

**生成器 vs 迭代器类**:生成器省去手动维护状态,代码更简洁。

## 15.4 yield 的工作原理

```python
def gen():
    print("start")
    yield 1
    print("middle")
    yield 2
    print("end")

g = gen()      # 创建生成器对象(不执行函数体)
print(next(g)) # start \n 1
print(next(g)) # middle \n 2
print(next(g)) # end \n StopIteration
```

`yield` 暂停函数,保存局部状态;`next()` 恢复执行。

## 15.5 生成器表达式

类似列表推导式,但用圆括号,惰性求值:

```python
# 列表推导式:立即计算
sum_list = sum([i ** 2 for i in range(1_000_000)])

# 生成器表达式:惰性计算
sum_gen = sum(i ** 2 for i in range(1_000_000))
assert sum_list == sum_gen  # 结果相同
```

**优势**:节省内存——1M 元素列表占 8MB+,生成器只占几 KB。

## 15.6 惰性计算的应用

### 15.6.1 大文件处理

```python
# ❌ 一次性读入,内存爆
lines = open("huge.log").readlines()

# ✅ 逐行迭代
with open("huge.log") as f:
    for line in f:
        process(line)
```

### 15.6.2 无限序列

```python
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

# 取前 10 个
from itertools import islice
fib = fibonacci()
print(list(islice(fib, 10)))  # [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
```

### 15.6.3 数据管道

```python
def read_lines(path):
    with open(path) as f:
        for line in f:
            yield line.strip()

def filter_non_empty(lines):
    for line in lines:
        if line:
            yield line

def parse_numbers(lines):
    for line in lines:
        yield int(line)

# 管道式处理(每个阶段都是惰性的)
pipeline = parse_numbers(filter_non_empty(read_lines("data.txt")))
total = sum(pipeline)
```

## 15.7 生成器的高级方法

### 15.7.1 send()

向生成器发送值,在 `yield` 处接收:

```python
def echo():
    while True:
        value = yield
        print(f"received: {value}")

g = echo()
next(g)            # 启动生成器
g.send("hello")    # received: hello
g.send("world")    # received: world
```

### 15.7.2 throw()

在 yield 处抛异常:

```python
def gen():
    try:
        yield 1
        yield 2
    except ValueError:
        yield "caught"

g = gen()
next(g)            # 1
g.throw(ValueError)  # "caught"
```

### 15.7.3 close()

关闭生成器,在 yield 处抛 `GeneratorExit`:

```python
def gen():
    try:
        yield 1
        yield 2
    finally:
        print("cleaned up")

g = gen()
next(g)            # 1
g.close()          # cleaned up
# next(g)         # StopIteration
```

## 15.8 yield from:委派生成器

将一个生成器"委派"给另一个:

```python
def sub_gen():
    yield 1
    yield 2

def main_gen():
    yield "a"
    yield from sub_gen()  # 等价于 for x in sub_gen(): yield x
    yield "b"

print(list(main_gen()))  # ['a', 1, 2, 'b']
```

**应用**:`asyncio` 早期版本(`async`/`await`)前身就是 `yield from`。

## 15.9 itertools 模块

Python 内置迭代器工具箱:

| 函数 | 用途 |
|------|------|
| `count(start, step)` | 无限计数器 |
| `cycle(iter)` | 无限循环 |
| `chain(a, b, ...)` | 拼接多个迭代器 |
| `islice(iter, stop)` | 切片 |
| `takewhile(pred, iter)` | 满足条件则取 |
| `dropwhile(pred, iter)` | 跳过满足条件的部分 |
| `groupby(iter, key)` | 分组 |
| `product(a, b)` | 笛卡尔积 |
| `permutations(iter, r)` | 排列 |
| `combinations(iter, r)` | 组合 |
| `starmap(func, iter)` | 类似 map,iter 元素是 tuple |
| `accumulate(iter, func)` | 累积 |

## 15.10 常见误区

- **误区 1**:生成器只能迭代一次——耗尽后要重新创建。
- **误区 2**:用 `return value` 在生成器中——`return` 立即终止,等同 `raise StopIteration`,但 `return value` 会变成 `StopIteration.value`。
- **误区 3**:在生成器中用 `for i in generator` 嵌套另一个生成器——忘记 `yield from` 会降低可读性。
- **误区 4**:对生成器使用 `len()` 或索引——不支持,必须先 `list()` 或用 `islice`。

## 15.11 本章小结

1. 迭代器协议:`__iter__` + `__next__`;`iter()` 与 `next()` 是工厂函数。
2. 生成器是"用 yield 定义的函数",自动实现迭代器协议。
3. `yield` 暂停函数,保存状态;`next()` 恢复。
4. 生成器表达式:惰性的列表推导式,内存友好。
5. `send` / `throw` / `close` 让生成器可与外部双向通信。
6. `yield from` 委派给子生成器,代码更简洁。
7. `itertools` 提供了大量迭代器组合工具。

## 15.12 练习思考

1. **动手实践**:实现一个生成器 `my_range(start, stop, step=1)`,与内置 `range` 行为一致。
2. **动手实践**:写一个生成器管道:读文件 → 过滤空行 → 提取数字 → 求平方和。
3. **代码分析**:下面代码输出什么?为什么?
   ```python
   def gen():
       yield 1
       yield 2
       yield 3
   g = gen()
   list(g)
   list(g)
   ```
4. **动手实践**:用 `itertools.islice` 写一个 `take(n, iterable)`,取可迭代对象前 n 个元素。
5. **拓展探索**:阅读 `asyncio` 早期文档,理解 `yield from` 如何演化为 `await`。

## 15.13 拓展阅读

- 迭代器协议官方文档:https://docs.python.org/3/tutorial/classes.html#iterators
- itertools:https://docs.python.org/3/library/itertools.html
- 《流畅的 Python》第 17 章 迭代器、生成器与经典协程

---

*配套练习:`exercises/15_iterators_generators_exercises.md`*
