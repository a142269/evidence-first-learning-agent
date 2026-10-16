---
chapter_ref: "01"
chapter_title: "变量与数据类型"
kp_refs: [PY_002, PY_003]
bloom_focus: [Remember, Understand, Apply, Analyze]
total_points: 50
deadline_hint: 本章配套学习时长 5 学时
---

# 变量与数据类型 · 章节练习

> **配套**:A3 章节 §01 变量与数据类型
> **配对代码**:`code_examples/01_variables_types_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 中 `bool` 类型的取值是?

- A. `0` 和 `1`
- B. `True` 和 `False`
- C. `"true"` 和 `"false"`
- D. `yes` 和 `no`

<details><summary>答案</summary>B。Python 用首字母大写的 `True` / `False`,注意不是 0/1(尽管是 int 子类)。</details>

### Q2(Understand)
以下哪个表达式会在 Python 中引发 `ValueError`?

- A. `int("42")`
- B. `int("42.5")`
- C. `int(42.9)`
- D. `int("0x10", 16)`

<details><summary>答案</summary>B。`int("42.5")` 不能直接转,因为字符串含小数点。</details>

### Q3(Apply)
`a = [1, 2, 3]; b = a; a.append(4); print(b)` 的输出是?

- A. `[1, 2, 3]`
- B. `[1, 2, 3, 4]`
- C. `4`
- D. 报错

<details><summary>答案</summary>B。`a` 与 `b` 指向同一 list 对象,`a.append(4)` 后 `b` 也被影响。</details>

### Q4(Analyze)
下列哪个是**不可变**类型?

- A. `list`
- B. `dict`
- C. `tuple`
- D. `set`

<details><summary>答案</summary>C。tuple 是不可变序列;list/dict/set 都可变。</details>

### Q5(Evaluate)
判断变量 `x` 是不是 `None`,以下哪种写法**最规范**?

- A. `x == None`
- B. `x is None`
- C. `not x`
- D. `x != None`

<details><summary>答案</summary>B。PEP 8 推荐用 `is` / `is not` 判断 `None`,不要用 `==`。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Remember)
Python 中"贴在对象上的标签"对应变量,但对象本身是 ______ (中文) 的。

<details><summary>答案</summary>不可变(对不可变对象而言;或回答"可哈希的"也对不可变类型有效)</details>

### Q7(Apply)
执行 `print(0.1 + 0.2)` 的输出是 `0.30000000000000004`,这是浮点数的 ______ 问题,推荐用 `decimal.Decimal` 处理。

<details><summary>答案</summary>精度</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 `is` 与 `==` 的区别,并各举一个典型用法。

<details><summary>参考答案</summary>`==` 比较**值**是否相等(调用 `__eq__`);`is` 比较**身份**(内存地址,`id()`)。典型用法:
- `x is None` ——判断 None 用 `is`
- `x == 0` ——比较数值用 `==`
- 判断单例(如 `True`,`False`,`None`)用 `is`</details>

### Q9(Analyze)
解释"Python 变量是标签,不是盒子"。用代码说明 `a = 10; b = a; a = 20` 的内存变化。

<details><summary>参考答案</summary>Python 变量不直接持有值,而是指向内存中的对象。执行过程:
1. `a = 10`:创建整数对象 10,把标签 a 贴上去
2. `b = a`:让标签 b 也指向 10(共享,不是复制)
3. `a = 20`:创建新对象 20,把 a 重新贴上去;b 仍指向 10
因此 `print(b)` 输出 10。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 `safe_divide(a, b)`,当 `b == 0` 时返回 `None`,否则返回 `a / b`,并保留 2 位小数。

<details><summary>参考实现</summary>

```python
def safe_divide(a, b):
    if b == 0:
        return None
    return round(a / b, 2)
```

</details>

### Q11(Create)
实现 `normalize_score(scores: list[int | float]) -> list[float]`,把列表里的分数按 (x - min) / (max - min) 归一化到 0-1,保留 3 位小数。处理空列表与所有分数相同的情况。

<details><summary>参考实现</summary>

```python
def normalize_score(scores):
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if lo == hi:
        return [0.0 for _ in scores]
    return [round((x - lo) / (hi - lo), 3) for x in scores]
```

</details>

---

*本章配套代码:`code_examples/01_variables_types_demo.py` 包含 8 个 demo 函数,涵盖变量赋值、可变性、`is` vs `==`、类型转换等。*
