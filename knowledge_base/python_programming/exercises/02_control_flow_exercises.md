---
chapter_ref: "02"
chapter_title: "控制流:条件与循环"
kp_refs: [PY_004]
bloom_focus: [Understand, Apply, Analyze]
total_points: 50
deadline_hint: 本章配套学习时长 4 学时
---

# 控制流 · 章节练习

> **配套**:A3 章节 §02 控制流
> **配对代码**:`code_examples/02_control_flow_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 中表示"否则"的保留字是?

- A. `else if`
- B. `elseif`
- C. `elif`
- D. `elsif`

<details><summary>答案</summary>C。Python 用 `elif` 减少缩进层级。</details>

### Q2(Understand)
下列代码的输出是?
```python
for i in range(5):
    if i == 3:
        break
    print(i, end=" ")
```

- A. `0 1 2 3 4`
- B. `0 1 2 3`
- C. `0 1 2`
- D. `0 1 2 3 4`(无空格)

<details><summary>答案</summary>C。`break` 在 i==3 时跳出,只输出 0, 1, 2。</details>

### Q3(Apply)
下列关于 `for-else` 的说法正确的是?

- A. 循环抛出异常时执行 else
- B. 循环正常结束(无 break)时执行 else
- C. 循环被 break 中断时执行 else
- D. else 永远不执行

<details><summary>答案</summary>B。`for-else` 是 Python 特色:else 在循环正常结束时执行,被 break 中断则不执行。</details>

### Q4(Analyze)
下面推导式的结果是?
```python
[x for x in range(10) if x % 2 == 0]
```

- A. `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]`
- B. `[0, 2, 4, 6, 8]`
- C. `[1, 3, 5, 7, 9]`
- D. `[0, 2, 4, 6, 8, 10]`

<details><summary>答案</summary>B。条件 `x % 2 == 0` 过滤偶数。</details>

### Q5(Evaluate)
遍历索引和值,推荐用?

- A. `for i in range(len(lst)): print(i, lst[i])`
- B. `for i, v in enumerate(lst): print(i, v)`
- C. `for i in lst: print(i)`
- D. `while i < len(lst): print(i, lst[i])`

<details><summary>答案</summary>B。`enumerate` 是 Python 风格,简洁且高效。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
用 zip 并行遍历两个等长列表的语法是 `for a, b in ______ (list1, list2):`。

<details><summary>答案</summary>zip</details>

### Q7(Apply)
`range(1, 10, 2)` 生成的序列是 `[1, 3, 5, 7, ______]`。

<details><summary>答案</summary>9</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请解释 Python 中"真值测试"(Truthiness)规则,列出至少 5 个真值为 False 的对象。

<details><summary>参考答案</summary>Python 中所有对象都可以在 if/for/while 等条件语境下转换为 bool,转换规则:
- `False` / `None` —— 假
- 数值零:`0`、`0.0`、`0j` —— 假
- 空序列/容器:`""`、`b""`、`[]`、`()`、`{}`、`set()` —— 假
- 自定义类的 `__bool__` 返回 False 或 `__len__` 返回 0 —— 假
其他对象都为真(包括负数与非空对象)。</details>

### Q9(Analyze)
"在循环中修改列表"会有什么问题?请举例说明并给出正确做法。

<details><summary>参考答案</summary>问题:在 for 循环中 `lst.remove(item)` 会导致跳过元素,因为迭代器位置与列表索引错位。
```python
lst = [1, 2, 3, 4, 5]
for x in lst:
    if x % 2 == 0:
        lst.remove(x)
# 结果 [1, 3, 5](只删除了部分偶数)
```
正确做法:用列表推导式创建新列表,或用切片复制。
```python
lst = [x for x in lst if x % 2 != 0]
# 或
for x in lst[:]:
    if x % 2 == 0:
        lst.remove(x)
```</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 FizzBuzz:函数 `fizzbuzz(n: int) -> list[str]`,1 到 n 之间,能被 3 整除返回 "Fizz",能被 5 整除返回 "Buzz",能被 15 整除返回 "FizzBuzz",其他返回数字字符串。

<details><summary>参考实现</summary>

```python
def fizzbuzz(n):
    result = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            result.append("FizzBuzz")
        elif i % 3 == 0:
            result.append("Fizz")
        elif i % 5 == 0:
            result.append("Buzz")
        else:
            result.append(str(i))
    return result
```

</details>

### Q11(Create)
实现 `word_frequency(text: str) -> dict[str, int]`,统计一段文本中每个单词出现的次数(忽略大小写、标点符号、空格)。

<details><summary>参考实现</summary>

```python
import re
from collections import Counter

def word_frequency(text):
    words = re.findall(r"\w+", text.lower())
    return dict(Counter(words))
```

</details>

---

*本章配套代码:`code_examples/02_control_flow_demo.py` 包含 6 个 demo 函数,涵盖 if/elif/else、for、while、break/continue、列表推导式等。*
