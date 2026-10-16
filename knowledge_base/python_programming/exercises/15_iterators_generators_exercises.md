---
chapter_ref: "15"
chapter_title: "迭代器与生成器"
kp_refs: [PY_022]
bloom_focus: [Analyze, Evaluate, Create]
total_points: 50
deadline_hint: 本章配套学习时长 4 学时
---

# 迭代器与生成器 · 章节练习

> **配套**:A3 章节 §15 迭代器与生成器

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 中"迭代器"必须实现的两个方法是?

- A. `__init__` / `__next__`
- B. `__iter__` / `__next__`
- C. `__iter__` / `__len__`
- D. `__iter__` / `__getitem__`

<details><summary>答案</summary>B。`__iter__` 返回自身,`__next__` 返回下一个值或抛 StopIteration。</details>

### Q2(Apply)
以下代码的输出是?
```python
def gen():
    yield 1
    yield 2
g = gen()
print(list(g))
print(list(g))
```

- A. `[1, 2]` 两次
- B. `[1, 2]` 和 `[]`
- C. `[1, 2, 1, 2]`
- D. 报错

<details><summary>答案</summary>B。生成器是一次性的,耗尽后第二次返回空 list。</details>

### Q3(Apply)
`sum(i ** 2 for i in range(1000000))` 与 `sum([i ** 2 for i in range(1000000)])` 的区别?

- A. 结果不同
- B. 前者用生成器表达式,惰性,内存更省
- C. 后者更快
- D. 前者会报错

<details><summary>答案</summary>B。圆括号是生成器表达式,惰性求值;方括号是列表推导式,立即求值。</details>

### Q4(Analyze)
`yield from sub_gen()` 等价于?

- A. `yield sub_gen()`
- B. `for x in sub_gen(): yield x`
- C. `return sub_gen()`
- D. `sub_gen()`

<details><summary>答案</summary>B。`yield from` 是语法糖,等价于 for 循环 + yield。</details>

### Q5(Evaluate)
处理一个 10GB 大文件,应该用?

- A. `content = f.read()`(一次读)
- B. `for line in f`(逐行迭代)
- C. `f.readlines()`(读所有行)
- D. `f.read(1024)`(读 1KB)

<details><summary>答案</summary>B。for line in f 是惰性迭代,内存友好;其它方式都会 OOM。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
用 `iter(list)` 创建的对象类型是 `<class '______'>`。

<details><summary>答案</summary>list_iterator</details>

### Q7(Apply)
生成器的 `g.send(value)` 在 yield 处接收 value,等效于 `g.__next__()` 但额外传入 ______ 。

<details><summary>答案</summary>value</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
"惰性计算"是什么?为什么生成器比列表更省内存?

<details><summary>参考答案</summary>惰性计算:只在需要时才计算下一个值,不预先计算所有值。
列表推导式 `[i**2 for i in range(1_000_000)]` 立即计算 100 万个值,占用 8MB+ 内存。
生成器表达式 `(i**2 for i in range(1_000_000))` 只保存"如何计算下一个值"的逻辑,逐次产出,内存占用几乎恒定。
应用场景:
1. 大文件/大数据流处理
2. 无限序列(Fibonacci)
3. 数据管道(多阶段转换)</details>

### Q9(Analyze)
"生成器是一次性"的含义是什么?如果需要多次迭代,应该怎么做?

<details><summary>参考答案</summary>含义:生成器只能向前迭代,一旦耗尽(`StopIteration`),再次迭代返回空。
多次迭代的方案:
1. **重新创建生成器**:每次需要时调用 `gen()` 创建新实例
2. **`itertools.tee`**:把一个可迭代对象拆成多个独立迭代器
```python
from itertools import tee
g = (i**2 for i in range(10))
a, b = tee(g)
print(list(a))  # [0, 1, 4, ..., 81]
print(list(b))  # [0, 1, 4, ..., 81]
```
3. **转为 list**(牺牲内存换多次迭代)
4. **用 `itertools.chain` 重复**:不推荐,会"重新跑"生成器</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现生成器 `my_range(start, stop, step=1)`,行为类似内置 `range`。

<details><summary>参考实现</summary>

```python
def my_range(start, stop=None, step=1):
    if stop is None:
        stop = start
        start = 0
    n = start
    while (step > 0 and n < stop) or (step < 0 and n > stop):
        yield n
        n += step

print(list(my_range(5)))           # [0, 1, 2, 3, 4]
print(list(my_range(1, 10, 2)))    # [1, 3, 5, 7, 9]
print(list(my_range(10, 0, -1)))   # [10, 9, ..., 1]
```

</details>

### Q11(Create)
用生成器实现 `read_large_csv(path, chunk_size=1000)`,每次 yield 1000 行(惰性,适合大文件)。

<details><summary>参考实现</summary>

```python
def read_large_csv(path, chunk_size=1000):
    chunk = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            chunk.append(line.rstrip())
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

# 用法
for batch in read_large_csv("huge.csv", chunk_size=500):
    process_batch(batch)
```

</details>

---

*本章配套练习覆盖迭代器协议、yield、生成器表达式、惰性计算、send/throw/close。*
