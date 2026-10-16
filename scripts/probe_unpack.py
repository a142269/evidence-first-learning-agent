"""测 sandbox tuple 解包"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sb = get_code_sandbox()
cases = [
    ("a, b = (1, 2)", "a, b = (1, 2); assert a == 1 and b == 2"),
    ("a, b = func()", """
def f():
    return (10, 20)
a, b = f()
assert a == 10 and b == 20
"""),
    ("result = func(); a = result[0]", """
def f():
    return (10, 20)
result = f()
a = result[0]
b = result[1]
assert a == 10 and b == 20
"""),
    ("pop 拆 tuple-style", """
def f():
    return [10, 20]
r = f()
a = r.pop(0)
b = r.pop(0)
assert a == 10 and b == 20
"""),
]

for name, code in cases:
    r = sb.execute(code, language="python", timeout=4)
    err = (r.error or r.stderr or "")[:140]
    mark = "PASS" if r.passed else "FAIL"
    print(f"  [{mark}] {name:<26}  {err}")
