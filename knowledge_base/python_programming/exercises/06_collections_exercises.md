---
chapter_ref: "06"
chapter_title: "collections 高级容器"
kp_refs: [PY_010]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 3 学时
---

# collections 高级容器 · 章节练习

> **配套**:A3 章节 §06 collections 高级容器
> **配对代码**:`code_examples/06_collections_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
`deque` 的最大优势是?

- A. 支持随机访问
- B. O(1) 双端操作
- C. 自动排序
- D. 唯一性

<details><summary>答案</summary>B。deque 在两端 append/pop 都是 O(1);list 头部操作是 O(n)。</details>

### Q2(Apply)
以下代码的输出是?
```python
from collections import Counter
c = Counter("banana")
print(c.most_common(1))
```

- A. `[('a', 3)]`
- B. `[('b', 1)]`
- C. `[('n', 2)]`
- D. `3`

<details><summary>答案</summary>A。most_common(1) 返回出现最多的 1 个,banana 中 a 出现 3 次。</details>

### Q3(Apply)
`defaultdict(int)` 在访问不存在的 key 时返回?

- A. 抛 KeyError
- B. 返回 None
- C. 返回 0(调用 int())
- D. 返回空 list

<details><summary>答案</summary>C。defaultdict 会在访问缺失 key 时调用 default_factory,这里是 int() → 0。</details>

### Q4(Analyze)
`OrderedDict` 在 Python 3.7+ 之后的独特价值是?

- A. 维护插入顺序(普通 dict 也行)
- B. 提供 `move_to_end` 等操作
- C. 性能更好
- D. 不可变

<details><summary>答案</summary>B。3.7+ 普通 dict 已保证插入顺序,OrderedDict 主要价值是 `move_to_end` / `popitem(last=False)` 等。</details>

### Q5(Evaluate)
需要支持"两端插入都很快"的消息队列,选?

- A. `list`
- B. `tuple`
- C. `deque`
- D. `set`

<details><summary>答案</summary>C。deque 是 O(1) 双端,list 头部是 O(n)。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`from collections import namedtuple; P = namedtuple("P", "x y")` 后,`P(3, 4)._asdict()` 的结果是 `{"x": 3, "y": ______}`。

<details><summary>答案</summary>4</details>

### Q7(Apply)
`deque(maxlen=3)` 连续 append 5 个元素后,内部只保留最后 ______ 个。

<details><summary>答案</summary>3</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 `Counter` 与 `defaultdict(int)` 都能计数,有什么本质区别?什么时候必须用 `Counter`?

<details><summary>参考答案</summary>本质区别:
- `defaultdict(int)`:值就是计数,需要手动 `cnt[k] += 1`
- `Counter`:继承自 dict,提供 most_common、算术运算、elements 等方法
必须用 Counter 的场景:
1. 需要 `most_common(k)` 找 Top-K
2. 需要 `(c1 & c2)` / `(c1 | c2)` 等集合运算
3. 访问不存在的 key 时 Counter 返回 0(defaultdict 也会创建)
4. 文本/词频统计的"标准答案"</details>

### Q9(Analyze)
什么是 ChainMap 的"层叠查找"?写一个 CLI > ENV > 配置文件 > 默认值的配置层叠示例。

<details><summary>参考答案</summary>ChainMap 把多个 dict 串成一个"层叠"结构,查找时按顺序回退,首个找到的胜出。
```python
from collections import ChainMap
import os

defaults = {"theme": "light", "lang": "en"}
file_config = {"lang": "zh"}
env = os.environ  # {"THEME": "dark"}

# ChainMap 顺序:先查 env,再 file_config,再 defaults
config = ChainMap(env, file_config, defaults)
print(config["theme"])  # "dark"(env 优先)
print(config["lang"])   # "zh"(file_config)
```
应用:配置层叠、模板引擎作用域链、Flask/Django 的 settings。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 `top_k_words(text: str, k: int) -> list[tuple[str, int]]`,用 `Counter` 找文本中出现次数最多的 k 个单词(忽略大小写与标点)。

<details><summary>参考实现</summary>

```python
import re
from collections import Counter

def top_k_words(text, k):
    words = re.findall(r"\w+", text.lower())
    return Counter(words).most_common(k)
```

</details>

### Q11(Create)
用 `deque(maxlen=N)` 实现 `running_average(iterable, window)` 生成器,返回最近 N 个元素的移动平均。

<details><summary>参考实现</summary>

```python
from collections import deque

def running_average(iterable, window):
    dq = deque(maxlen=window)
    for x in iterable:
        dq.append(x)
        yield sum(dq) / len(dq)

print(list(running_average([1, 2, 3, 4, 5], 3)))
# [1.0, 1.5, 2.0, 3.0, 4.0]
```

</details>

---

*本章配套代码:`code_examples/06_collections_demo.py` 包含 7 个 demo 函数,涵盖 namedtuple、deque、Counter、defaultdict、OrderedDict、ChainMap、性能对比。*
