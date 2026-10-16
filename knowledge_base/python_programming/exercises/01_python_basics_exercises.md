---
chapter_ref: "01"
chapter_title: "Python 基础语法"
kp_refs: [python_basics]
bloom_focus: [Remember, Understand, Apply]
total_points: 20
deadline_hint: 本章配套学习时长 4 学时
---

# Python 基础语法 · 章节练习

> **配套**：A3 章节 §01 Python 基础语法  
> **配对代码**：`code_examples/01_python_basics_demo.py`

---

## 一、选择题（每题 2 分，共 10 分）

### Q1（Remember）
下面哪个是 Python 中 **布尔类型** 的合法字面值？

- A. `TRUE`
- B. `True`
- C. `true`
- D. `1`

<details><summary>答案</summary>B。Python 布尔值首字母大写：`True` / `False`；`1` 是 int，不是 bool（虽然 `bool` 是 `int` 的子类，但字面值不属于 bool 类型）。</details>

### Q2（Understand）
执行 `print("a" + 3)` 的结果是：

- A. `a3`
- B. `a` + `3` → 报错 `TypeError`
- C. `a a a`
- D. `null`

<details><summary>答案</summary>B。Python 不会自动把 int 转成 str；必须显式 `"a" + str(3)` 或 f-string。</details>

### Q3（Apply）
下列哪个表达式会输出 `6`？

- A. `sum([1, 2, 3])`
- B. `[1, 2, 3].sum()`
- C. `(1, 2, 3).sum()`
- D. `{1, 2, 3}.sum()`

<details><summary>答案</summary>A。`sum()` 是内建函数，对任何 iterable 求和；list/tuple/set 都没有 `.sum()` 方法。</details>

### Q4（Understand）
下面代码的输出是：
```python
x = [1, 2, 3]
y = x
y.append(4)
print(x)
```

- A. `[1, 2, 3]`
- B. `[1, 2, 3, 4]`
- C. `[4, 2, 3]`
- D. 报错

<details><summary>答案</summary>B。`y = x` 是引用赋值，两者指向同一 list；`y.append` 也会改到 `x`。</details>

### Q5（Apply）
下面哪个 f-string 写法是**合法**的？

- A. `f"value: {x:}"`
- B. `f"value: {x:.2f}"`
- C. `f"value: {x}" `
- D. `F"value: {x:02d}"`

<details><summary>答案</summary>B、C、D。`{x:}` 在 Python 3.12 之前是非法格式说明符；其余都合法（f-string 同时支持 `f` 和 `F` 前缀）。</details>

---

## 二、填空题（每题 2 分，共 6 分）

### Q6（Apply）
补全代码：用 `range` 打印 0, 2, 4, 6, 8：
```python
for i in range(____):
    print(i)
```

<details><summary>答案</summary>`range(0, 10, 2)` 或 `range(10, step=2)`（Python 3.12+）或 `range(0, 10, 2)`。`step` 是步长，从 0 到 9（含）以 2 为步长，结果为 0, 2, 4, 6, 8。</details>

### Q7（Apply）
补全代码：把列表 `[3, 1, 4, 1, 5]` 去重并升序：
```python
nums = [3, 1, 4, 1, 5]
unique_sorted = sorted(____)
```

<details><summary>答案</summary>`sorted(set(nums))`。先 `set(nums)` 得到 `{1, 3, 4, 5}`，再 `sorted(...)` 排序为 `[1, 3, 4, 5]`。</details>

### Q8（Apply）
补全代码：写一个 `add(a, b)` 函数返回两数之和（用 type hint）：
```python
def add(a: int, b: int) -> ____:
    return a + b
```

<details><summary>答案</summary>`int`。函数签名形如 `def add(a: int, b: int) -> int`。</details>

---

## 三、简答题（每题 3 分，共 6 分）

### Q9（Understand）
请解释 Python 中 **可变（mutable）** 与 **不可变（immutable）** 类型的区别，并各举 3 个例子。

<details><summary>参考答案要点</summary>

- **可变**：对象创建后内容可原地修改（不改变身份 id）。例：`list`、`dict`、`set`。
- **不可变**：对象一旦创建内容不可变；任何"修改"都会创建新对象。例：`int`、`str`、`tuple`。
- 关键区分：函数传参时，可变对象可能在函数内被意外修改（side effect），不可变对象不会。</details>

### Q10（Apply）
阅读下列代码，说明 `print` 的输出与原因：
```python
def f(x, lst=[]):
    lst.append(x)
    return lst

print(f(1))
print(f(2))
print(f(3))
```

<details><summary>参考答案</summary>

输出：
```
[1]
[1, 2]
[1, 2, 3]
```

原因：默认参数 `lst=[]` 在函数**定义时**只创建一次（被绑定到函数对象的 `__defaults__`）。三次调用共享同一个 list。  
修正方法：`def f(x, lst=None): lst = lst if lst is not None else []`。</details>

---

## 四、编程题（5 分）

### Q11（Create · 难度 3）
写一个函数 `count_word_freq(text: str) -> dict[str, int]`，统计 `text` 中每个英文单词（忽略大小写、标点 `. , ! ?`）的出现次数，按频次降序返回字典。

**函数签名**：
```python
def count_word_freq(text: str) -> dict[str, int]:
    ...
```

**验收样例**：
```python
assert count_word_freq("Hello, hello! World.") == {"hello": 2, "world": 1}
```

<details><summary>评分要点</summary>

- 正确清洗标点 + lower（2 分）
- 使用 `Counter.most_common()` 或 sorted（2 分）
- 通过 assert（1 分）</details>

---

> **配套自检**：完成本练习后请在 A3 `ResourcesView` 中查看 §01 章，下方应有"本章练习"入口。