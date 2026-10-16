---
chapter_id: '02'
slug: control_flow
title: 控制流:条件与循环
kp_ids:
- PY_004
bloom_focus:
- Understand
- Apply
prerequisites:
- '01'
estimated_minutes: 240
---

# 02: 控制流:条件与循环 · 程序的三种基本结构

> **Bloom 层级**: Understand → Apply
> **建议学时**: 240 分钟(4 学时)
> **前置知识**: §01 变量与数据类型

## 学习目标

1. 掌握 `if-elif-else` 条件分支结构,理解 Python 的"真值测试"机制。
2. 掌握 `for` / `while` 循环的语法与适用场景。
3. 理解 `break` / `continue` / `else` 子句的控制流细节。
4. 熟练使用 `range()`、`enumerate()`、`zip()` 等迭代工具。
5. 能用列表推导式、字典推导式编写简洁高效的"数据处理流水线"。
6. 避免循环常见反模式(死循环、修改迭代对象等)。

## 2.1 结构化程序设计三大结构

1966 年,Böhm 与 Jacopini 在数学上证明:**任何可计算的程序都可以用顺序、选择、循环三种基本结构组合而成**。Python 通过缩进语法把这三种结构表达得极为清晰。

```
顺序       →  代码按书写顺序逐行执行
选择(条件) →  if-elif-else
循环       →  for / while
```

## 2.2 条件分支:if-elif-else

### 2.2.1 基本语法

```python
if 条件1:
    语句块1
elif 条件2:
    语句块2
else:
    语句块3
```

注意:
- 条件后必须有冒号 `:`
- 缩进(4 空格)代表代码块,不能用大括号
- `elif` 而不是 `else if`(减少缩进层级)

```python
def grade(score: int) -> str:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"
```

### 2.2.2 真值测试(Truthiness)

Python 中所有对象都可以用在 if 条件中,根据"真值"判断:

| 对象 | 真值 |
|------|------|
| `False` | ❌ |
| `None` | ❌ |
| `0`、`0.0` | ❌ |
| `""`、`b""` | ❌ |
| `[]`、`()`、`{}`、`set()` | ❌ |
| 其他 | ✅ |

```python
# 推荐用真值,不要写 == 0 / == ""
if not users:           # ✅ 简洁
    print("没有用户")
if len(users) == 0:     # ❌ 啰嗦
    print("没有用户")
```

### 2.2.3 条件表达式(三元)

```python
# C 风格
result = x if condition else y

# 示例
status = "成年" if age >= 18 else "未成年"
max_val = a if a > b else b
```

## 2.3 for 循环

### 2.3.1 遍历序列

```python
fruits = ["apple", "banana", "cherry"]
for fruit in fruits:
    print(fruit)

# 字符串
for char in "Python":
    print(char)

# 字典
d = {"a": 1, "b": 2, "c": 3}
for key in d:                # 默认遍历 key
    print(key, d[key])
for key, val in d.items():   # 解包
    print(key, val)
```

### 2.3.2 range()

`range(stop)` 或 `range(start, stop, step)`,返回惰性序列:

```python
for i in range(5):           # 0, 1, 2, 3, 4
    pass
for i in range(1, 10, 2):    # 1, 3, 5, 7, 9
    pass
for i in range(10, 0, -1):   # 10, 9, ..., 1
    pass
```

`range` 不创建 list,内存效率高——遍历 1 亿次只占 48 字节。

### 2.3.3 enumerate()

同时获取索引与值:

```python
fruits = ["apple", "banana", "cherry"]
for idx, fruit in enumerate(fruits):
    print(f"{idx}: {fruit}")
# 0: apple
# 1: banana
# 2: cherry

# 起始索引
for idx, fruit in enumerate(fruits, start=1):
    print(f"{idx}: {fruit}")
```

### 2.3.4 zip()

并行遍历多个序列:

```python
names = ["Alice", "Bob", "Charlie"]
scores = [85, 92, 78]
for name, score in zip(names, scores):
    print(f"{name}: {score}")

# 长度不同时,以最短为准
zip_longest(names, scores, fillvalue=0)  # 需 import itertools
```

## 2.4 while 循环

```python
count = 0
while count < 5:
    print(count)
    count += 1

# 无限循环 + break
while True:
    user_input = input("请输入 q 退出: ")
    if user_input == "q":
        break
    print(f"你输入了: {user_input}")
```

**适用场景**:
- 不知道要循环多少次(如用户交互、网络重试)
- 等待某个状态变化

**不适用**:有明确序列时,用 for 比 while 简洁

## 2.5 循环控制:break / continue / else

### 2.5.1 break 跳出

```python
for i in range(10):
    if i == 5:
        break
    print(i)  # 0,1,2,3,4
```

### 2.5.2 continue 跳过

```python
for i in range(10):
    if i % 2 == 0:
        continue
    print(i)  # 1,3,5,7,9
```

### 2.5.3 else 子句(Python 特色)

循环正常结束(没被 break 中断)时,执行 else:

```python
# 搜索素数
for n in range(2, 10):
    for x in range(2, n):
        if n % x == 0:
            break
    else:
        print(f"{n} 是素数")
```

**应用**:搜索失败时给出默认行为,比标志位更优雅。

## 2.6 推导式(Comprehension)

### 2.6.1 列表推导式

```python
# 传统
squares = []
for i in range(10):
    squares.append(i ** 2)

# 推导式
squares = [i ** 2 for i in range(10)]

# 带条件
evens = [i for i in range(10) if i % 2 == 0]

# 嵌套(等价于双重 for)
pairs = [(x, y) for x in range(3) for y in range(3)]
# [(0,0), (0,1), (0,2), (1,0), (1,1), (1,2), (2,0), (2,1), (2,2)]
```

### 2.6.2 字典推导式

```python
# 字符计数
text = "hello"
counts = {c: text.count(c) for c in set(text)}
# {'h': 1, 'e': 1, 'l': 2, 'o': 1}

# 翻转字典
inv = {v: k for k, v in original.items()}
```

### 2.6.3 集合推导式

```python
squared = {i ** 2 for i in range(10)}
# {0, 1, 64, 4, 36, 9, 16, 49, 81, 25}
```

### 2.6.4 生成器表达式(节省内存)

```python
# 列表推导式:立即计算,占用内存
sum_list = sum([i ** 2 for i in range(10**6)])

# 生成器表达式:惰性计算
sum_gen = sum(i ** 2 for i in range(10**6))
```

**何时不用推导式**:逻辑复杂、有副作用、嵌套超过 2 层——这时拆成显式循环更清晰。

## 2.7 match-case(Python 3.10+)

类似 switch-case,但支持模式匹配:

```python
def http_status(status):
    match status:
        case 200:
            return "OK"
        case 301 | 302:
            return "Redirect"
        case 404:
            return "Not Found"
        case 500..=599:
            return "Server Error"
        case _:
            return "Unknown"

# 结构模式匹配
def process(point):
    match point:
        case (0, 0):
            return "Origin"
        case (x, 0):
            return f"On X axis at {x}"
        case (0, y):
            return f"On Y axis at {y}"
        case (x, y):
            return f"At ({x}, {y})"
```

## 2.8 常见误区

- **误区 1**:`for i in range(len(lst))` — Python 风格是直接 `for item in lst`,只在你真的需要索引时才用 `enumerate`。
- **误区 2**:在循环中修改列表 — `for item in lst: lst.remove(item)` 会跳过元素。应该用列表推导式创建新列表,或用切片。
- **误区 3**:`while True: ...` 忘记 break 或条件更新 — 死循环。
- **误区 4**:推导式嵌套三层以上 — 牺牲可读性,不如显式循环。
- **误区 5**:`else` 子句理解反 — "如果循环正常结束就执行 else,被 break 中断就不执行",不是"出错才执行"。

## 2.9 本章小结

1. 三大结构:顺序、选择(if)、循环(for/while)。
2. 真值测试:`0`、`""`、`[]`、`{}`、`None`、`False` 为 False,其他为 True。
3. `for` 遍历可迭代对象,`range`/`enumerate`/`zip` 是常用工具。
4. `while` 适用于不确定次数的循环,常与 `break` 配合。
5. `break` 跳出、`continue` 跳过、`else` 在循环正常结束时执行。
6. 列表/字典/集合推导式是 Python 风格,生成器表达式节省内存。
7. `match-case`(3.10+)提供结构化模式匹配。

## 2.10 练习思考

1. **代码分析**:下面代码输出什么?为什么?
   ```python
   for i in range(5):
       if i == 3:
           continue
       print(i)
   else:
       print("done")
   ```
2. **动手实践**:实现 FizzBuzz 函数 `fizzbuzz(n) -> list[str]`,1-15 中能被 3 整除替换为 "Fizz",能被 5 整除替换为 "Buzz",能被 15 整除替换为 "FizzBuzz",其他返回数字字符串。
3. **动手实践**:用字典推导式统计一段文本中每个单词出现的次数(忽略大小写与标点)。
4. **代码优化**:把下面代码改写成列表推导式:
   ```python
   result = []
   for x in range(10):
       if x % 2 == 0:
           result.append(x ** 2)
   ```
5. **拓展探索**:用 `dis` 模块反汇编一个简单 for 循环,看看 Python 底层是怎么实现的。

## 2.11 拓展阅读

- Python 控制流官方文档:https://docs.python.org/3/tutorial/controlflow.html
- PEP 634 — 结构化模式匹配:https://peps.python.org/pep-0634/
- 《流畅的 Python》第 2 章 数据结构与算法(列表推导式部分)

---

*配套代码示例:`code_examples/02_control_flow_demo.py`*
*配套练习:`exercises/02_control_flow_exercises.md`*
