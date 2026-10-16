"""Python 程序设计 · 配套实操示例 06 · collections 高级容器 demo

对应章节: 06 collections 高级容器
对应 KP  : PY_010 (collections 高级容器)
Bloom 关注: Apply / Analyze
运行方式 : python 06_collections_demo.py
依赖     : 纯标准库
说明     : 7 个 demo 函数覆盖 namedtuple、deque、Counter、defaultdict、OrderedDict、ChainMap、性能对比。
"""
from __future__ import annotations

import time
from collections import ChainMap, Counter, OrderedDict, defaultdict, deque, namedtuple
from typing import NamedTuple


# ---------------------------------------------------------------------------
# 1. namedtuple
# ---------------------------------------------------------------------------
def demo_namedtuple() -> None:
    Point = namedtuple("Point", ["x", "y"])
    p = Point(3, 4)
    assert p.x == 3 and p.y == 4
    assert p._asdict() == {"x": 3, "y": 4}
    assert p._fields == ("x", "y")

    p2 = p._replace(x=10)
    assert p2 == Point(10, 4)
    assert p == Point(3, 4)  # 原对象未变

    # 命名元组可哈希
    d = {Point(0, 0): "原点", Point(1, 0): "X 轴"}
    assert d[Point(0, 0)] == "原点"

    # Python 3.6+ typing.NamedTuple 支持类型注解
    class User(NamedTuple):
        name: str
        age: int
        email: str = ""

    u = User("Alice", 25)
    assert u.name == "Alice" and u.age == 25
    print(f"[OK] namedtuple (p={p}, user={u})")


# ---------------------------------------------------------------------------
# 2. deque 双向队列 + 滑动窗口
# ---------------------------------------------------------------------------
def demo_deque() -> None:
    dq = deque([1, 2, 3])
    dq.append(4)
    dq.appendleft(0)
    assert list(dq) == [0, 1, 2, 3, 4]
    assert dq.popleft() == 0
    assert dq.pop() == 4
    assert list(dq) == [1, 2, 3]

    # 限制长度的滑动窗口
    window = deque(maxlen=3)
    for i in range(5):
        window.append(i)
    assert list(window) == [2, 3, 4]
    print(f"[OK] deque (window={list(window)})")


# ---------------------------------------------------------------------------
# 3. Counter 计数器
# ---------------------------------------------------------------------------
def demo_counter() -> None:
    text = "the quick brown fox jumps over the lazy dog the"
    words = Counter(text.split())
    top3 = words.most_common(3)
    assert top3[0] == ("the", 3)
    assert Counter("abracadabra").most_common(1) == [("a", 5)]

    # 不存在的 key 返回 0
    c = Counter(a=3, b=1)
    assert c["z"] == 0

    # 集合运算
    c1 = Counter(a=3, b=1)
    c2 = Counter(a=1, b=2)
    assert (c1 + c2) == Counter(a=4, b=3)
    assert (c1 & c2) == Counter(a=1, b=1)
    print(f"[OK] counter (top3={top3})")


# ---------------------------------------------------------------------------
# 4. defaultdict
# ---------------------------------------------------------------------------
def demo_defaultdict() -> None:
    pairs = [("fruit", "apple"), ("fruit", "banana"), ("veg", "carrot")]
    # 旧写法
    d_old = {}
    for k, v in pairs:
        d_old.setdefault(k, []).append(v)
    # 新写法
    dd = defaultdict(list)
    for k, v in pairs:
        dd[k].append(v)
    assert d_old == dict(dd)

    # 计数
    cnt = defaultdict(int)
    for c in "abracadabra":
        cnt[c] += 1
    assert dict(cnt) == {"a": 5, "b": 2, "r": 2, "c": 1, "d": 1}
    print(f"[OK] defaultdict (groups={dict(dd)})")


# ---------------------------------------------------------------------------
# 5. OrderedDict / LRU
# ---------------------------------------------------------------------------
def demo_ordered_dict() -> None:
    od = OrderedDict()
    od["a"] = 1
    od["b"] = 2
    od["c"] = 3
    od.move_to_end("a")
    assert list(od.keys()) == ["b", "c", "a"]
    assert od.popitem(last=False) == ("b", 2)

    # LRU 简化实现
    class LRUCache:
        def __init__(self, capacity):
            self.cache = OrderedDict()
            self.cap = capacity

        def get(self, key):
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

        def put(self, key, value):
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.cap:
                self.cache.popitem(last=False)

    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")      # a 变最新
    cache.put("c", 3)   # b 被淘汰
    assert cache.get("b") is None
    assert cache.get("a") == 1
    print("[OK] OrderedDict (LRU cache)")


# ---------------------------------------------------------------------------
# 6. ChainMap 配置层叠
# ---------------------------------------------------------------------------
def demo_chainmap() -> None:
    defaults = {"theme": "light", "lang": "en", "debug": False}
    user_prefs = {"theme": "dark", "lang": "zh"}
    env = {"debug": True}

    config = ChainMap(env, user_prefs, defaults)
    assert config["theme"] == "dark"       # user_prefs
    assert config["lang"] == "zh"          # user_prefs
    assert config["debug"] is True         # env 优先

    # 写入只到第一层
    config["new_key"] = "value"
    assert "new_key" in env
    assert "new_key" not in user_prefs
    print(f"[OK] ChainMap (theme={config['theme']}, lang={config['lang']})")


# ---------------------------------------------------------------------------
# 7. 性能对比:list.insert(0) vs deque.appendleft
# ---------------------------------------------------------------------------
def demo_performance() -> None:
    N = 50_000
    lst = list(range(N))
    dq = deque(range(N))

    t0 = time.perf_counter()
    for _ in range(1000):
        lst.insert(0, 0)
    list_t = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(1000):
        dq.appendleft(0)
    deque_t = time.perf_counter() - t0

    # deque 应快得多(数量级)
    assert deque_t * 100 < list_t, f"deque 慢于 list: {deque_t*1000:.1f}ms vs {list_t*1000:.1f}ms"
    print(f"[OK] perf (list.insert(0)={list_t*1000:.1f}ms, deque.appendleft={deque_t*1000:.1f}ms)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_namedtuple()
    demo_deque()
    demo_counter()
    demo_defaultdict()
    demo_ordered_dict()
    demo_chainmap()
    demo_performance()
    print("\n✅ 所有测试通过!")
