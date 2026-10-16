"""Python 程序设计 · 配套实操示例 04 · 数据结构 demo

对应章节: 04 列表、字典、元组与集合
对应 KP  : PY_006 (列表与列表推导式), PY_007 (字典与哈希表), PY_008 (元组与集合)
Bloom 关注: Apply / Analyze
运行方式 : python 04_data_structures_demo.py
依赖     : 纯标准库
说明     : 8 个 demo 函数覆盖 list/dict/tuple/set 常用操作、推导式、命名元组、浅/深拷贝、时间复杂度。
"""
from __future__ import annotations

import copy
import time
from collections import namedtuple


# ---------------------------------------------------------------------------
# 1. 列表:增删改查 + 切片
# ---------------------------------------------------------------------------
def demo_list() -> None:
    lst = [3, 1, 4, 1, 5, 9, 2, 6]
    # 增
    lst.append(5)
    lst.insert(0, 0)
    lst.extend([5, 3])
    # 删
    lst.pop()           # 末尾
    lst.remove(1)        # 第一个 1
    # 查
    assert lst.index(4) >= 0
    assert lst.count(1) >= 1
    # 切片
    rev = lst[::-1]
    assert len(rev) == len(lst)
    # 排序
    s = sorted(lst)
    s_desc = sorted(lst, reverse=True)
    assert s == sorted(s)
    assert s_desc == sorted(lst, reverse=True)
    print(f"[OK] list (sorted={s[:3]}..., len={len(lst)})")


# ---------------------------------------------------------------------------
# 2. 列表推导式与陷阱
# ---------------------------------------------------------------------------
def demo_list_comprehension() -> None:
    """[[]]*3 陷阱 vs 正确写法"""
    # ❌ 错误:三个元素是同一对象
    bad = [[]] * 3
    bad[0].append(1)
    assert bad == [[1], [1], [1]]

    # ✅ 正确
    good = [[] for _ in range(3)]
    good[0].append(1)
    assert good == [[1], [], []]

    # 推导式 vs 循环
    squares_loop = []
    for i in range(10):
        squares_loop.append(i**2)
    squares_comp = [i**2 for i in range(10)]
    assert squares_loop == squares_comp
    print(f"[OK] list comprehension (squares[:5]={squares_comp[:5]})")


# ---------------------------------------------------------------------------
# 3. 字典:get / setdefault / defaultdict / Counter
# ---------------------------------------------------------------------------
def demo_dict() -> None:
    d = {"a": 1, "b": 2, "c": 3}
    # 安全访问
    assert d.get("a") == 1
    assert d.get("z", 0) == 0
    # 视图
    assert set(d.keys()) == {"a", "b", "c"}
    assert sum(d.values()) == 6
    # setdefault
    d.setdefault("fruits", []).extend(["apple", "banana"])
    assert "apple" in d["fruits"]
    # Counter
    from collections import Counter
    text = "abracadabra"
    counts = Counter(text)
    assert counts.most_common(2) == [("a", 5), ("b", 2)]
    print(f"[OK] dict (counts={dict(counts)})")


# ---------------------------------------------------------------------------
# 4. 字典推导式
# ---------------------------------------------------------------------------
def demo_dict_comprehension() -> None:
    # 翻转字典
    original = {"a": 1, "b": 2, "c": 3}
    inv = {v: k for k, v in original.items()}
    assert inv == {1: "a", 2: "b", 3: "c"}
    # 过滤
    big = {k: v for k, v in original.items() if v >= 2}
    assert big == {"b": 2, "c": 3}
    print(f"[OK] dict comprehension (inv={inv})")


# ---------------------------------------------------------------------------
# 5. 元组与命名元组
# ---------------------------------------------------------------------------
def demo_tuple() -> None:
    t = (1, 2, 3, 4, 5)
    a, b, *rest, last = t
    assert a == 1 and b == 2 and last == 5
    # 命名元组
    Point = namedtuple("Point", ["x", "y"])
    p = Point(3, 4)
    assert p.x == 3 and p.y == 4
    assert p._asdict() == {"x": 3, "y": 4}
    # 单元素元组
    single = (42,)
    assert isinstance(single, tuple)
    # 哈希化
    d = {(1, 2): "point A", (3, 4): "point B"}
    assert d[(1, 2)] == "point A"
    print(f"[OK] tuple + namedtuple (p={p})")


# ---------------------------------------------------------------------------
# 6. 集合运算
# ---------------------------------------------------------------------------
def demo_set() -> None:
    a = {1, 2, 3, 4, 5}
    b = {4, 5, 6, 7, 8}
    assert (a | b) == {1, 2, 3, 4, 5, 6, 7, 8}
    assert (a & b) == {4, 5}
    assert (a - b) == {1, 2, 3}
    assert (a ^ b) == {1, 2, 3, 6, 7, 8}
    assert a.issuperset({1, 2})
    assert {1, 2}.issubset(a)
    # 去重
    dup = [1, 2, 2, 3, 3, 3, 4]
    unique = list(set(dup))
    assert sorted(unique) == [1, 2, 3, 4]
    print(f"[OK] set (a^b={a ^ b})")


# ---------------------------------------------------------------------------
# 7. 浅拷贝 vs 深拷贝
# ---------------------------------------------------------------------------
def demo_copy() -> None:
    a = [[1, 2], [3, 4]]

    # 浅拷贝
    b = a.copy()
    b[0].append(99)
    assert a[0] == [1, 2, 99]  # 共享内层

    # 深拷贝
    a2 = [[1, 2], [3, 4]]
    c = copy.deepcopy(a2)
    c[0].append(99)
    assert a2[0] == [1, 2]  # 完全独立
    print("[OK] copy (shallow vs deep)")


# ---------------------------------------------------------------------------
# 8. 时间复杂度:O(n) vs O(1) 成员检测
# ---------------------------------------------------------------------------
def demo_complexity() -> None:
    """实测 list vs set 成员检测"""
    big_list = list(range(100_000))
    big_set = set(big_list)

    target = 99_999

    t0 = time.perf_counter()
    for _ in range(1000):
        _ = target in big_list
    list_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(1000):
        _ = target in big_set
    set_time = time.perf_counter() - t0

    assert list_time > set_time
    print(f"[OK] complexity (list={list_time*1000:.1f}ms, set={set_time*1000:.1f}ms)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_list()
    demo_list_comprehension()
    demo_dict()
    demo_dict_comprehension()
    demo_tuple()
    demo_set()
    demo_copy()
    demo_complexity()
    print("\n✅ 所有测试通过!")
