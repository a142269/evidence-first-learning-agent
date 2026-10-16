"""测关键能力: list comp / zip / max / min / sum / enumerate / range / next / iter"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sb = get_code_sandbox()

cases = [
    ("list comp", "x = [i * i for i in range(5)]; assert x == [0, 1, 4, 9, 16]"),
    ("dict comp", "x = {i: i * i for i in range(3)}; assert x.get(0) == 0 and x.get(2) == 4"),
    ("sum", "x = [1, 2, 3, 4]; assert sum(x) == 10"),
    ("max", "x = [1, 5, 3]; assert max(x) == 5"),
    ("min", "x = [1, 5, 3]; assert min(x) == 1"),
    ("max key", "x = [[3, 'c'], [1, 'a'], [2, 'b']]; y = max(x); assert y[0] == 3"),  # tuple comp
    ("zip", "x = [1, 2, 3]; y = [10, 20, 30]; total = 0\nfor pair in zip(x, y):\n    pass\nassert total == 0"),
    ("zip with sum", "x = [1, 2, 3]; y = [10, 20, 30]; result = 0\nfor pair in zip(x, y):\n    pass\nassert result == 0"),
    ("zip + pop", "x = [1, 2, 3]; y = [10, 20, 30]\nfor pair in zip(x, y):\n    a = pair[0]\n    b = pair[1]"),
    ("iter", "x = iter([1, 2, 3]); assert next(x) == 1"),
    ("range + iter", "x = iter(range(5)); assert next(x) == 0"),
    ("set", "x = set(); x.add(1); x.add(2); x.add(1); assert len(x) == 2"),
    ("tuple literal", "x = (1, 2, 3); assert len(x) == 3"),
    ("str literal", "x = 'abc'; assert len(x) == 3"),
    ("bool", "x = True; y = False; assert x and not y"),
    ("class def", "class Foo:\n    def __init__(self, x):\n        self.x = x\nf = Foo(42); assert f.x == 42"),
    ("try except", "try:\n    x = 1 / 0\nexcept:\n    pass"),
    ("with pass", "with open('/dev/null') as f:\n    pass"),
    ("lambda no key", "sq = lambda x: x * x; assert sq(3) == 9"),
    ("map", "x = list(map(lambda v: v * 2, [1, 2, 3]))"),  # list() 失败
    ("filter", "result = []\nfor v in filter(lambda v: v > 1, [1, 2, 3]):\n    result.append(v)\nassert len(result) == 2"),
    ("reversed", "x = [3, 1, 2]; y = []\nfor v in reversed(x):\n    y.append(v)\nassert y == [2, 1, 3]"),
    ("slice iter", "x = [1, 2, 3, 4, 5]; y = x[1:4]\nfor v in y:\n    pass"),
    ("abs complex", "x = abs(-3.14); assert abs(x - 3.14) < 1e-9"),
    ("int from float", "x = int(3.7); assert x == 3"),
]

for name, code in cases:
    r = sb.execute(code, language="python", timeout=4)
    err = (r.error or r.stderr or "")[:140]
    mark = "PASS" if r.passed else "FAIL"
    print(f"  [{mark}] {name:<22}  {err}")
