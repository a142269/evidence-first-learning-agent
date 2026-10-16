"""确认下标访问到底能不能用"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sandbox = get_code_sandbox()

cases = [
    ("list 下标", "x = [1,2,3]; y = x[0]; assert y == 1"),
    ("tuple 下标", "x = (1,2,3); y = x[0]; assert y == 1"),
    ("dict 字符串下标", "x = {'a':1}; y = x['a']; assert y == 1"),
    ("str 下标", "x = 'abc'; y = x[0]; assert y == 'a'"),
    ("dict.values", "x = {'a':1, 'b':2}; total = 0\nfor v in x.values():\n    total = total + v\nassert total == 3"),
    ("dict.items", "x = {'a':1, 'b':2}; total = 0\nfor k, v in x.items():\n    total = total + v\nassert total == 3"),
    ("list 切片", "x = [1,2,3,4]; y = x[1:3]; assert y == [2, 3]"),
    ("isinstance dict", "x = {'a':1}; assert isinstance(x, dict)"),
    ("type(dict)", "x = type({}); assert x == dict"),
    ("dict 构造", "x = dict(a=1, b=2); assert x['a'] == 1"),
    ("zip iter", "total = 0\nfor v in zip([1,2], [3,4]):\n    total = total + v[0]\nassert total == 4"),
    ("tuple 解包", "a, b = (1, 2); assert a == 1 and b == 2"),
]

for name, code in cases:
    r = sandbox.execute(code, language="python", timeout=4)
    err = (r.error or r.stderr or "")[:120]
    mark = "PASS" if r.passed else "FAIL"
    print(f"  [{mark}] {name:<22}  {err}")
