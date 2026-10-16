"""快速探查 sandbox 对 import / 内置函数的实际行为"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sandbox = get_code_sandbox()
tests = [
    ("纯算术", "x = 2 ** 0.5; assert abs(x - 1.41421356) < 1e-6"),
    ("abs 内置", "x = abs(-3.14); assert x == 3.14"),
    ("len 内置", "x = len([1,2,3]); assert x == 3"),
    ("sum 内置", "x = sum([1,2,3]); assert x == 6"),
    ("def + list", """
def add(a, b):
    return a + b
assert add(1, 2) == 3
"""),
    ("list 推导", """
squares = [x * x for x in range(5)]
assert squares == [0, 1, 4, 9, 16]
"""),
    ("lambda", """
sq = lambda x: x * x
assert sq(3) == 9
"""),
    ("闭包 nonlocal", """
def make_counter():
    n = [0]
    def inc():
        n[0] += 1
        return n[0]
    return inc
c = make_counter()
assert c() == 1
assert c() == 2
"""),
    ("import 试 — 1", "import math; x = math.sqrt(4); assert x == 2.0"),
    ("import 试 — 2", "from math import sqrt; x = sqrt(4); assert x == 2.0"),
    ("import 试 — random", "import random; x = random.random(); assert 0 <= x <= 1"),
    ("import 试 — 列表推导带 math", "import math; vals = [math.sqrt(x) for x in [1,4,9]]; assert vals[1] == 2.0"),
]

for name, code in tests:
    r = sandbox.execute(code, language="python", timeout=4)
    err = (r.error or r.stderr or "")[:100]
    cat = "PASS" if r.passed else "FAIL"
    print(f"  [{cat}] {name:<25}  err={err}")
