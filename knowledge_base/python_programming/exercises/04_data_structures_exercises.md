---
chapter_ref: "04"
chapter_title: "列表、字典、元组与集合"
kp_refs: [PY_006, PY_007, PY_008]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 10 学时
---

# 数据结构 · 章节练习

> **配套**:A3 章节 §04 列表、字典、元组与集合
> **配对代码**:`code_examples/04_data_structures_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Understand)
以下哪个是**不可变**类型?

- A. `list`
- B. `dict`
- C. `tuple`
- D. `set`

<details><summary>答案</summary>C。tuple 是不可变序列。</details>

### Q2(Apply)
`lst = [1, 2, 3, 4, 5]; print(lst[::-2])` 的输出是?

- A. `[5, 4, 3, 2, 1]`
- B. `[1, 3, 5]`
- C. `[5, 3, 1]`
- D. `[1, 2, 3]`

<details><summary>答案</summary>C。`[::-2]` 是从尾到头步长 2,即 [5, 3, 1]。</details>

### Q3(Apply)
`d = {"a": 1, "b": 2}; d.get("c", 0)` 的返回值是?

- A. `None`
- B. `0`
- C. `KeyError`
- D. `"c"`

<details><summary>答案</summary>B。`get` 在 key 不存在时返回默认值 0,不抛 KeyError。</details>

### Q4(Analyze)
以下代码的输出是?
```python
nested = [[]] * 3
nested[0].append(1)
print(nested)
```

- A. `[[1], [], []]`
- B. `[[1], [1], [1]]`
- C. `[[], [], []]`
- D. 报错

<details><summary>答案</summary>B。`[[]] * 3` 三个元素指向同一对象,改一个全改。</details>

### Q5(Evaluate)
要在 O(1) 时间判断元素是否在集合中,应该用?

- A. `list`
- B. `tuple`
- C. `set`
- D. `dict`(只比较 key)

<details><summary>答案</summary>C/D。set 和 dict 的成员检测是 O(1),list/tuple 是 O(n)。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Remember)
命名元组 `from collections import namedtuple; Point = namedtuple("Point", ["x", "y"])` 创建的对象 `p = Point(3, 4)`,访问 `p.x` 的值是 ______ 。

<details><summary>答案</summary>3</details>

### Q7(Apply)
对列表 `[3, 1, 4, 1, 5]` 调用 `set()` 后得到 `{1, 3, 4, 5}`,这是 set 的 ______ 性质。

<details><summary>答案</summary>无序不重复(或回答"去重")</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 list 的 `append` 与 `extend` 有什么区别?

<details><summary>参考答案</summary>- `append(x)`:把 x 作为一个整体追加到列表末尾。`lst.append([4, 5])` 后 `lst = [1, 2, 3, [4, 5]]`
- `extend(iter)`:把可迭代对象中的元素逐个追加。`lst.extend([4, 5])` 后 `lst = [1, 2, 3, 4, 5]`
`+` 运算符等价于 `extend`,而 `+=` 在某些情况下也类似(对 list 是 extend,语义取决于实现)。</details>

### Q9(Analyze)
解释浅拷贝与深拷贝的区别,写代码说明什么情况下浅拷贝"不够用"。

<details><summary>参考答案</summary>浅拷贝只复制对象本身,嵌套的可变元素仍共享引用;深拷贝递归复制所有层级。
不够用的情况:
```python
import copy
a = [[1, 2], [3, 4]]
b = a.copy()         # 浅拷贝
b[0].append(99)      # 改内层
print(a)             # [[1, 2, 99], [3, 4]] ← 受影响
# 必须用深拷贝
c = copy.deepcopy(a)
c[0].append(88)
print(a)             # 不受影响
```
应用场景:快照、undo/redo 栈、并发任务间传数据。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 `group_by(items, key)`,根据 key 函数对 items 分组,返回 `dict[key, list]`。

<details><summary>参考实现</summary>

```python
def group_by(items, key):
    result = {}
    for item in items:
        k = key(item)
        result.setdefault(k, []).append(item)
    return result

# 或用 defaultdict
from collections import defaultdict
def group_by(items, key):
    result = defaultdict(list)
    for item in items:
        result[key(item)].append(item)
    return dict(result)
```

</details>

### Q11(Create)
实现 `find_top_n(scores: dict[str, int], n: int) -> list[tuple[str, int]]`,返回分数最高的 n 个(姓名, 分数),按分数降序;同分按姓名升序。

<details><summary>参考实现</summary>

```python
def find_top_n(scores, n):
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:n]

scores = {"Alice": 90, "Bob": 85, "Carol": 95, "Dave": 85}
print(find_top_n(scores, 3))
# [('Carol', 95), ('Alice', 90), ('Bob', 85)]
```

</details>

---

*本章配套代码:`code_examples/04_data_structures_demo.py` 包含 8 个 demo 函数,涵盖 list/dict/tuple/set 的常用操作、时间复杂度、浅/深拷贝。*
