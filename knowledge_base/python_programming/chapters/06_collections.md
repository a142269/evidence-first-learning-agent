---
chapter_id: '06'
slug: collections
title: collections 高级容器
kp_ids:
- PY_010
bloom_focus:
- Apply
- Analyze
prerequisites:
- '04'
estimated_minutes: 180
---

# 06: collections 高级容器 · 让内置容器"开外挂"

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 180 分钟(3 学时)
> **前置知识**: §04 数据结构

## 学习目标

1. 掌握 `namedtuple` / `deque` / `Counter` / `defaultdict` / `OrderedDict` / `ChainMap` 的使用场景。
2. 能用 `Counter` 简化计数逻辑、用 `defaultdict` 避免繁琐的 `setdefault`。
3. 理解 `deque` 双向队列的性能优势(O(1) 两端操作)。
4. 理解 `ChainMap` 在配置层叠、命名空间隔离中的高级应用。
5. 能根据场景选择合适的高级容器替代内置 list/dict。

## 6.1 为什么需要 collections

内置的 list/dict/tuple/set 在 80% 场景下够用,但有 20% 场景需要更专业的容器——`collections` 模块提供了这些"开外挂"的工具。

| 容器 | 解决的问题 |
|------|------------|
| `namedtuple` | 给元组字段命名,提高可读性 |
| `deque` | 双向队列,O(1) 两端操作 |
| `Counter` | 哈希计数器,自动统计 |
| `defaultdict` | 缺失 key 自动建默认值 |
| `OrderedDict` | 显式表达"有序字典" |
| `ChainMap` | 多个 dict 链式查找 |

## 6.2 namedtuple(命名元组)

```python
from collections import namedtuple

Point = namedtuple("Point", ["x", "y"])
p = Point(3, 4)
print(p.x, p.y)        # 3 4(替代 p[0] p[1])
print(p._asdict())     # {'x': 3, 'y': 4}
print(p._fields)       # ('x', 'y')

# 默认值
Status = namedtuple("Status", ["code", "msg"], defaults=["OK"])
s = Status(200)
assert s.code == 200 and s.msg == "OK"

# 替换
p2 = p._replace(x=10)
assert p2 == Point(10, 4)
```

**Python 3.6+ typing.NamedTuple 更强大**:

```python
from typing import NamedTuple

class User(NamedTuple):
    name: str
    age: int
    email: str = ""

u = User("Alice", 25)
# 自动有 __repr__ / __eq__ / 解包支持
```

**应用**:替代简单类,作为函数返回值、字典 value、CSV 行表示。

## 6.3 deque(双向队列)

`list` 末尾 append/pop 是 O(1),但**头部**操作是 O(n)。`deque` 两端都是 O(1):

```python
from collections import deque

q = deque([1, 2, 3])
q.append(4)        # 队尾 [1, 2, 3, 4]
q.appendleft(0)    # 队首 [0, 1, 2, 3, 4]
q.pop()            # 4
q.popleft()        # 0
print(q)           # deque([1, 2, 3])

# 限制长度的滑动窗口
window = deque(maxlen=3)
for i in range(5):
    window.append(i)
    print(i, list(window))
# 0 [0]
# 1 [0, 1]
# 2 [0, 1, 2]
# 3 [1, 2, 3]  ← 旧元素自动弹出
# 4 [2, 3, 4]
```

**应用**:广度优先搜索(BFS)、滑动窗口、消息队列、撤销栈。

```python
# 性能对比
import time
N = 100_000

# list 头部插入
lst = list(range(N))
t0 = time.perf_counter()
for _ in range(1000):
    lst.insert(0, 0)
list_time = time.perf_counter() - t0

# deque 头部插入
dq = deque(range(N))
t0 = time.perf_counter()
for _ in range(1000):
    dq.appendleft(0)
deque_time = time.perf_counter() - t0

print(f"list insert(0): {list_time*1000:.1f}ms, deque appendleft: {deque_time*1000:.1f}ms")
# 典型结果:list ~1500ms, deque ~0.1ms(数万倍差距)
```

## 6.4 Counter(计数器)

```python
from collections import Counter

# 统计字符
c = Counter("abracadabra")
print(c.most_common(2))  # [('a', 5), ('b', 2)]
print(c["z"])            # 0(不存在的 key 返回 0)

# 统计单词
text = "the quick brown fox jumps over the lazy dog the"
words = Counter(text.split())
print(words.most_common(3))  # [('the', 3), ('quick', 1), ('brown', 1)]

# 集合运算
c1 = Counter(a=3, b=1)
c2 = Counter(a=1, b=2)
print(c1 + c2)  # Counter({'a': 4, 'b': 3})
print(c1 - c2)  # Counter({'a': 2})  # 负数被丢弃
print(c1 & c2)  # Counter({'a': 1, 'b': 1})  # min
print(c1 | c2)  # Counter({'a': 3, 'b': 2})  # max
```

**应用**:词频统计、Top-K 排行、找出出现最多的元素、Anagram 检测。

## 6.5 defaultdict(默认字典)

```python
from collections import defaultdict

# ❌ 普通 dict:繁琐的 setdefault
d = {}
for k, v in pairs:
    d.setdefault(k, []).append(v)

# ✅ defaultdict:自动初始化
dd = defaultdict(list)
for k, v in pairs:
    dd[k].append(v)

# 任何可调用对象都可作为 default_factory
dd_int = defaultdict(int)        # 缺失时为 0
dd_set = defaultdict(set)        # 缺失时为 set()
dd_str = defaultdict(str)        # 缺失时为 ""
```

**与 dict 的关键区别**:访问不存在的 key 会自动创建并调用 `default_factory`,而不是抛 `KeyError`。

**应用**:分组(groupby)、图邻接表、累积计数。

## 6.6 OrderedDict(有序字典)

Python 3.7+ 普通 dict 已保证插入顺序,`OrderedDict` 主要用于:

1. **显式表达意图**(代码可读性)
2. **`move_to_end`**:把 key 移到末尾(LRU Cache 实现的关键)
3. **`popitem(last=False)`**:弹出最旧的 key

```python
from collections import OrderedDict

od = OrderedDict()
od["a"] = 1
od["b"] = 2
od["c"] = 3
od.move_to_end("a")  # {'b': 2, 'c': 3, 'a': 1}
print(od.popitem(last=False))  # ('b', 2) 弹出最旧

# LRU Cache 简化实现
class LRUCache:
    def __init__(self, capacity):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
```

**现代替代**:Python 3.9+ 的 `functools.lru_cache` 已经足够好。

## 6.7 ChainMap(链式映射)

把多个 dict 串成一个"层叠"结构,查找时按顺序回退:

```python
from collections import ChainMap

defaults = {"color": "red", "user": "guest"}
user_prefs = {"color": "blue"}

config = ChainMap(user_prefs, defaults)
print(config["color"])  # "blue"(用户偏好优先)
print(config["user"])   # "guest"(回退到默认值)

# 新增会写到第一个 dict
config["new_key"] = "value"
print(user_prefs)       # {'color': 'blue', 'new_key': 'value'}
```

**应用**:配置层叠(CLI args > 环境变量 > 配置文件 > 默认值)、模板引擎作用域链。

## 6.8 其他容器

- `UserDict` / `UserList` / `UserString` —— 包装 dict/list/str,方便子类化
- `OrderedSet` —— Python 没有内置,用 `dict.fromkeys()` 实现
- `SortedDict` / `SortedList` —— 第三方 `sortedcontainers` 库提供

## 6.9 常见误区

- **误区 1**:`Counter` 计数时只对可哈希对象计数,不能用 list 作为 key。
- **误区 2**:`defaultdict` 在迭代时会"自动创建"key,可能产生意外副作用:
  ```python
  dd = defaultdict(int)
  for k in ["a", "b", "c"]:
      print(dd[k])  # 自动创建 0 0 0
  print(dd)  # defaultdict(int, {'a': 0, 'b': 0, 'c': 0})
  ```
- **误区 3**:`deque` 不支持切片,只支持两端操作。
- **误区 4**:`OrderedDict` 在 3.7+ 之后失去"排序保证"以外的独特价值。

## 6.10 本章小结

1. `namedtuple` / `typing.NamedTuple` 给元组字段命名,提升可读性。
2. `deque` 提供 O(1) 双端操作,适合队列、滑动窗口。
3. `Counter` 简化计数,提供 most_common 与集合运算。
4. `defaultdict` 自动初始化缺失 key,避免繁琐 setdefault。
5. `OrderedDict` 主要用于显式有序语义和 `move_to_end`(LRU)。
6. `ChainMap` 用于配置层叠,多 dict 链式查找。
7. 选择标准:用合适的容器表达意图,而不是把 list/dict 写到所有地方。

## 6.11 练习思考

1. **动手实践**:用 `Counter` 找出一段文本中出现次数最多的前 5 个单词。
2. **动手实践**:用 `defaultdict(list)` 实现 `group_by(items, key)`。
3. **代码分析**:下面 `deque(maxlen=3)` 循环 5 次后的状态是什么?为什么?
   ```python
   dq = deque(maxlen=3)
   for i in range(5):
       dq.append(i)
   ```
4. **动手实践**:用 `OrderedDict` 实现一个简单的 LRU Cache(简化版)。
5. **拓展探索**:阅读 `sortedcontainers` 库源码,理解 SortedList 的实现。

## 6.12 拓展阅读

- collections 官方文档:https://docs.python.org/3/library/collections.html
- 《流畅的 Python》第 3 章 字典与集合(扩展部分)
- sortedcontainers:https://github.com/grantjenks/python-sortedcontainers

---

*配套代码示例:`code_examples/06_collections_demo.py`*
*配套练习:`exercises/06_collections_exercises.md`*
