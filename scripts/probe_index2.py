"""逐上下文探查 pair[i] 何时能/不能"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sandbox = get_code_sandbox()

cases = [
    ("赋值-单独", "pair = (1, 2); a = pair[0]"),
    ("赋值-多", "pair = (1, 2); a = pair[0]; b = pair[1]"),
    ("比较-单独", "pair = (1, 2); assert pair[0] == 1"),
    ("算术-单独", "pair = (1, 2); x = pair[0] - pair[1]; assert x == -1"),
    ("算术-连用", "pair = (1, 2); x = pair[0] + pair[1] * 2; assert x == 5"),
    ("for迭代-单独", "for v in [(1,2), (3,4)]:\n    x = v[0]"),
    ("zip迭代", "for v in zip([1,2], [3,4]):\n    x = v[0]"),
    ("for解包+下标", "for v in [(1,2), (3,4)]:\n    x = v[0]\n    y = v[1]"),
    ("for解包zip", "for v in zip([1,2], [3,4]):\n    x = v[0]\n    y = v[1]"),
]

for name, code in cases:
    r = sandbox.execute(code, language="python", timeout=4)
    err = (r.error or r.stderr or "")[:120]
    mark = "PASS" if r.passed else "FAIL"
    print(f"  [{mark}] {name:<22}  {err}")
