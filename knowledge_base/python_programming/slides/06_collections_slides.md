# 06: collections 高级容器 · 幻灯片大纲

> 总页数：10 页 | 建议讲解时长：30 分钟

---

## Slide 1：封面
- 标题：collections 高级容器
- 副标题：Python 程序设计 · 第 7 讲

## Slide 2：本讲大纲
- 为什么需要 collections
- namedtuple / NamedTuple
- deque 双向队列
- Counter 计数器
- defaultdict 默认字典
- OrderedDict / ChainMap
- 性能对比

## Slide 3：为什么需要 collections
- 80% 场景 list / dict / tuple / set 够用
- 20% 场景需要"专业"容器
- 6 个常用：namedtuple / deque / Counter / defaultdict / OrderedDict / ChainMap

## Slide 4：namedtuple
```python
from collections import namedtuple
Point = namedtuple("Point", ["x", "y"])
p = Point(3, 4)
p.x          # 3
p._asdict()  # {'x': 3, 'y': 4}
```
- Python 3.6+ typing.NamedTuple 更强大（类型注解）
- 比 class 轻量
- 应用：CSV 行表示、字典 value、返回值

## Slide 5：deque 双向队列
```python
from collections import deque
dq = deque(maxlen=3)
dq.append(1)
dq.appendleft(0)
```
- O(1) 双端操作
- list 头部 insert 是 O(n)
- 应用：滑动窗口、BFS、消息队列
- [配图：list vs deque 性能对比图]

## Slide 6：Counter
```python
from collections import Counter
c = Counter("abracadabra")
c.most_common(2)      # [('a', 5), ('b', 2)]
(c1 + c2)             # 并
(c1 & c2)             # 交
```
- 简化计数
- 集合运算支持
- 应用：词频统计、Top-K、Anagram

## Slide 7：defaultdict
```python
from collections import defaultdict
dd = defaultdict(list)
for k, v in pairs:
    dd[k].append(v)
```
- 缺失 key 自动调用 `default_factory`
- 替代繁琐 `setdefault`
- 任意 callable：int / list / set / str

## Slide 8：OrderedDict / ChainMap
- OrderedDict（3.7+ 普通 dict 已有序）:
  - `move_to_end(key)` 移到末尾
  - `popitem(last=False)` 弹最旧
  - LRU Cache 实现基础
- ChainMap: 多 dict 层叠查找
  - CLI > env > config > defaults

## Slide 9：性能对比实测
- list.insert(0, x) vs deque.appendleft(x)
- 100K 元素 × 1000 次操作
- list: ~1500ms
- deque: ~0.1ms
- 性能差距 10000+ 倍
- [代码示例：基准测试]

## Slide 10：本讲总结与作业
- 核心要点：
  1. namedtuple 替代简单类
  2. deque 是 O(1) 双端
  3. Counter 简化计数
  4. defaultdict 替代 setdefault
- 作业：
  1. 用 Counter 实现 top_k_words
  2. 用 deque 实现 running_average
  3. 用 OrderedDict 实现 LRU
