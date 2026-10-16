---
chapter_ref: "02"
chapter_title: "Python 数据结构"
kp_refs: [python_basics]
bloom_focus: [Apply, Analyze, Evaluate]
total_points: 20
deadline_hint: 本章配套学习时长 4 学时
---

# Python 数据结构 · 章节练习

> **配套**：A3 章节 §02 Python 数据结构  
> **配对代码**：`code_examples/02_data_structures_demo.py`

---

## 一、选择题（每题 2 分，共 10 分）

### Q1（Remember）
下列哪个数据结构是 **有序且不可变** 的？

- A. `list`
- B. `tuple`
- C. `set`
- D. `dict`

<details><summary>答案</summary>B。`tuple` 是有序且不可变；`list` 可变；`set` 无序；`dict` 是插入序映射（Python 3.7+）但本身是 mutable mapping。</details>

### Q2（Understand）
下面代码的时间复杂度是？
```python
s = set(range(1_000_000))
return 999_999 in s
```

- A. O(1)
- B. O(log n)
- C. O(n)
- D. O(n log n)

<details><summary>答案</summary>A。set 内部是哈希表，平均查找 O(1)。如果换成 `list`，则是 O(n)。</details>

### Q3（Apply）
用 `heapq` 找列表 `[3, 1, 4, 1, 5, 9, 2, 6]` 中最大的 3 个元素，下列写法最高效的是：

- A. `sorted(nums)[-3:]`
- B. `heapq.nlargest(3, nums)`
- C. `heapq.nlargest(3, sorted(nums))`
- D. `max(nums) for ...`

<details><summary>答案</summary>B。`heapq.nlargest(k, iterable)` 用 size-k 堆实现，复杂度 O(n log k)；A 是 O(n log n)；C 重复排序。</details>

### Q4（Analyze）
下面哪个场景**最不适合**用 `dict` 存储？

- A. 学生-成绩映射
- B. 词频统计
- C. 按插入顺序遍历的需求
- D. 需要 O(1) 范围查询（区间求和）

<details><summary>答案</summary>D。区间求和用前缀和数组 / 树状数组 / 线段树更合适；dict 适合点查询。</details>

### Q5（Evaluate）
判断：用 `deque` 实现一个 LRU 缓存（`OrderedDict` 也常用）。在 Python 3.9+ 哪个更推荐？

- A. `OrderedDict`，因为 O(1) 移动
- B. `dict` + 自维护双向链表（更直接）
- C. `list`，因为简单
- D. `set`，因为查找快

<details><summary>答案</summary>B。Python 3.7+ 普通 `dict` 已经保插入序；LRU 推荐 `functools.lru_cache` 或自维护 `dict + doubly linked list`。`OrderedDict` 在 3.7+ 不再必要。</details>

---

## 二、填空题（每题 2 分，共 6 分）

### Q6（Apply）
补全：用 `Counter` 找 top-3 高频词：
```python
from collections import Counter
words = ["a", "b", "a", "c", "a", "b"]
top3 = ____(words)[:3]
```

<details><summary>答案</summary>`Counter(words).most_common(3)`，结果 `[('a', 3), ('b', 2), ('c', 1)]`。</details>

### Q7（Apply）
补全：用 `deque` 实现 BFS 邻居扩展：
```python
from collections import deque
queue = ____([start_node])
while queue:
    node = queue.popleft()
    for nb in graph[node]:
        if not visited[nb]:
            visited[nb] = True
            queue.____(nb)
```

<details><summary>答案</summary>`deque` 和 `append`。`deque` 的 `popleft` 是 O(1)，比 `list.pop(0)` 快。</details>

### Q8（Apply）
补全：用 `defaultdict` 分组：
```python
from collections import defaultdict
groups = ____(list)
for name, team in pairs:
    groups[team].____(name)
```

<details><summary>答案</summary>`defaultdict(list)` 和 `append`。访问未存在的 key 时自动创建空 list。</details>

---

## 三、简答题（每题 3 分，共 6 分）

### Q9（Apply · 难度 3）
写一段代码：用 `heapq` 实现一个**最小堆**支持的 `MedianFinder` 类，支持 `add_num(num)` 添加元素与 `find_median()` 返回当前中位数。要求 O(log n) 插入、O(1) 查询。

<details><summary>参考答案</summary>

**双堆法**：
- `max_heap`（存较小一半，存负值实现 max-heap）
- `min_heap`（存较大一半）
- 保持 `len(max_heap) - len(min_heap) in {0, 1}`

```python
import heapq

class MedianFinder:
    def __init__(self):
        self.lo, self.hi = [], []   # max-heap, min-heap

    def add_num(self, num):
        heapq.heappush(self.lo, -num)
        heapq.heappush(self.hi, -heapq.heappop(self.lo))
        if len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))

    def find_median(self):
        if len(self.lo) > len(self.hi):
            return -self.lo[0]
        return (-self.lo[0] + self.hi[0]) / 2
```

复杂度：`add_num` O(log n)，`find_median` O(1)。</details>

### Q10（Evaluate）
比较 `list`、`tuple`、`set`、`dict` 在以下五个维度上的差异，并给出一个**实际应用场景**对应选择：

1. 索引访问 O(1)
2. 插入头部 O(1)
3. 去重
4. 哈希作为 dict key
5. 内存开销

<details><summary>参考答案</summary>

| 维度 | list | tuple | set | dict |
|------|------|-------|-----|------|
| 索引 O(1) | ✅ | ✅ | ❌ | ✅（按 key） |
| 头部插入 O(1) | ❌ | ❌ | ❌（但 add O(1)） | ❌ |
| 去重 | ❌（需手动） | ❌ | ✅（天然） | ❌（key 天然唯一） |
| 可哈希作 dict key | ❌（可哈希但可变） | ✅（元素都可哈希时） | ❌ | ❌ |
| 内存开销 | 中 | 低 | 高（哈希表） | 高 |

**场景**：  
- 排行榜实时更新：`list` + 排序（注意头部插入慢）  
- 单词去重 + 词频统计：`set` 去重 + `Counter` 计数  
- 坐标点作 dict key：`tuple`（保证所有元素可哈希）  
- 队列先进先出：`deque`（O(1) 头尾）</details>

---

## 四、编程题（5 分）

### Q11（Create · 难度 4）
实现一个 `TopKFrequent` 类：
- `__init__(self, k: int)` 构造时设定 k。
- `add(self, word: str) -> None` 添加一个词。
- `topk(self) -> list[str]` 返回当前出现频次最高的 k 个词（按频次降序；同频次按字母升序）。

**函数签名**：
```python
class TopKFrequent:
    def __init__(self, k: int): ...
    def add(self, word: str) -> None: ...
    def topk(self) -> list[str]: ...
```

**验收样例**：
```python
tf = TopKFrequent(2)
for w in ["a", "b", "a", "c", "a", "b"]:
    tf.add(w)
assert tf.topk() == ["a", "b"]
```

<details><summary>评分要点</summary>

- 用 `Counter` 维护词频（1 分）
- `topk` 用 `heapq.nlargest` 或 `sorted`（2 分）
- 处理同频次的字典序 tie-break（1 分）
- 通过 assert（1 分）</details>

---

> **配套自检**：完成本练习后请在 A3 `ResourcesView` 中查看 §02 章，下方应有"本章练习"入口。