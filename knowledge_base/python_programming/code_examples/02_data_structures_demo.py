"""P0-2 配套实操示例 02 · Python 常用数据结构 demo

对应章节：02 数据结构
对应 KP   ：python_basics
Bloom 关注：Apply / Analyze
运行方式 ：python 02_data_structures_demo.py
依赖     ：纯标准库
说明     ：覆盖 list / tuple / dict / set / deque / heapq / Counter 至少 6 种
           数据结构，每种一个 demo 函数 + assert 自检；最后 [OK] 退出。
"""
from __future__ import annotations

import heapq
from collections import Counter, deque, defaultdict


# ---------------------------------------------------------------------------
# 1. list 进阶：排序、压缩、二维
# ---------------------------------------------------------------------------
def demo_list() -> None:
    nums = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]

    # 排序 + key
    by_abs = sorted(nums, key=lambda x: -x)[:3]
    assert by_abs == [9, 6, 5]

    # zip 同时遍历多列表
    names = ["Alice", "Bob", "Cara"]
    scores = [90, 85, 92]
    table = list(zip(names, scores))
    assert table == [("Alice", 90), ("Bob", 85), ("Cara", 92)]

    # 嵌套列表生成（矩阵）
    matrix = [[i * j for j in range(1, 4)] for i in range(1, 4)]
    assert matrix == [[1, 2, 3], [2, 4, 6], [3, 6, 9]]


# ---------------------------------------------------------------------------
# 2. tuple：不可变 + 解构 + 命名元组
# ---------------------------------------------------------------------------
def demo_tuple() -> None:
    from collections import namedtuple

    Point = namedtuple("Point", ["x", "y"])
    p = Point(3, 4)

    assert p.x == 3 and p.y == 4
    assert p[0] == 3
    # namedtuple 自带 _asdict / _replace
    p2 = p._replace(x=10)
    assert p2 == Point(10, 4)

    # tuple 作为 dict 的 key（hashable）
    grid = {(0, 0): "origin", (1, 0): "right"}
    assert grid[(0, 0)] == "origin"


# ---------------------------------------------------------------------------
# 3. dict 进阶：defaultdict、Counter、OrderedDict
# ---------------------------------------------------------------------------
def demo_dict_advanced() -> None:
    # defaultdict：分组
    fruits = ["apple", "banana", "apple", "cherry", "banana", "apple"]
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for f in fruits:
        grouped[f[0]].append(f)
    assert grouped["a"] == ["apple", "apple", "apple"]
    assert grouped["b"] == ["banana", "banana"]

    # Counter：词频
    c = Counter(fruits)
    assert c.most_common(1) == [("apple", 3)]
    assert c["banana"] == 2

    # Counter 算术
    c2 = Counter(["apple", "cherry", "cherry"])  # 多减 1 次才能得到负值
    c.subtract(c2)
    assert c["apple"] == 2        # 3 - 1
    assert c["cherry"] == -1      # 1 - 2


# ---------------------------------------------------------------------------
# 4. set：去重 + 集合运算
# ---------------------------------------------------------------------------
def demo_set() -> None:
    a = {1, 2, 3, 4}
    b = {3, 4, 5, 6}

    assert a | b == {1, 2, 3, 4, 5, 6}      # union
    assert a & b == {3, 4}                   # intersection
    assert a - b == {1, 2}                   # difference
    assert a ^ b == {1, 2, 5, 6}             # symmetric difference
    assert a.issubset({1, 2, 3, 4, 5})

    # 列表去重且保序（Python 3.7+ dict 保序）
    raw = [3, 1, 2, 1, 3, 4]
    uniq = list(dict.fromkeys(raw))
    assert uniq == [3, 1, 2, 4]


# ---------------------------------------------------------------------------
# 5. deque：双端队列（O(1) 头尾操作）
# ---------------------------------------------------------------------------
def demo_deque() -> None:
    q: deque[int] = deque([1, 2, 3])
    q.appendleft(0)
    q.append(4)
    assert list(q) == [0, 1, 2, 3, 4]

    q.pop()                  # 队尾
    q.popleft()              # 队头
    assert list(q) == [1, 2, 3]

    # 滑动窗口最大值（用 deque 维护单调队列）
    nums = [1, 3, -1, -3, 5, 3, 6, 7]
    k = 3
    window: deque[int] = deque()
    result: list[int] = []
    for i, x in enumerate(nums):
        while window and window[0] <= i - k:
            window.popleft()
        while window and nums[window[-1]] < x:
            window.pop()
        window.append(i)
        if i >= k - 1:
            result.append(nums[window[0]])
    assert result == [3, 3, 5, 5, 6, 7]


# ---------------------------------------------------------------------------
# 6. heapq：堆 / 优先队列 / top-k
# ---------------------------------------------------------------------------
def demo_heapq() -> None:
    # 默认 min-heap
    heap = [5, 3, 8, 1, 9, 2]
    heapq.heapify(heap)
    assert heap[0] == 1

    sorted_list = [heapq.heappop(heap) for _ in range(len(heap))]
    assert sorted_list == [1, 2, 3, 5, 8, 9]

    # top-k 最大：用 min-heap 维护 k 个候选
    nums = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    k = 3
    top_k: list[int] = heapq.nlargest(k, nums)
    assert sorted(top_k) == [5, 6, 9]

    # 合并有序流
    merged = list(heapq.merge([1, 3, 5], [2, 4, 6], [0, 7]))
    assert merged == [0, 1, 2, 3, 4, 5, 6, 7]


# ---------------------------------------------------------------------------
# 7. Counter 进阶：top-k 词频 + 元素运算
# ---------------------------------------------------------------------------
def demo_counter_extra() -> None:
    text = "the quick brown fox jumps over the lazy dog".split()
    cnt = Counter(text)

    assert cnt.most_common(2) == [("the", 2), ("quick", 1)]
    # elements() 按计数展开
    assert sorted(cnt.elements()) == sorted(text)

    # 多 Counter 相加 / 交
    a = Counter({"x": 3, "y": 1})
    b = Counter({"x": 1, "z": 2})
    assert (a + b)["x"] == 4
    assert (a & b)["x"] == 1     # 交集取 min


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    demo_list()
    demo_tuple()
    demo_dict_advanced()
    demo_set()
    demo_deque()
    demo_heapq()
    demo_counter_extra()

    print("[Python-DataStructures] 7 demos all asserted OK")
    print("[OK] data structures demo passed")


if __name__ == "__main__":
    main()