"""精确测 sandbox 下标: 是 transform 拦了, 还是某个其他原因"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sb = get_code_sandbox()

cases = [
    # 基础下标 (理论上 RestrictedPython 不改写)
    ("list[0]", "x = [10, 20, 30]; assert x[0] == 10"),
    ("tuple[0]", "x = (10, 20, 30); assert x[0] == 10"),
    ("dict['a']", "x = {'a': 10}; assert x['a'] == 10"),
    ("str[0]", "x = 'hello'; assert x[0] == 'h'"),
    # 不下标但访问
    ("list[0] pop", "x = [10, 20]; y = x.pop(0); assert y == 10"),
    ("list append", "x = []; x.append(1); x.append(2); assert len(x) == 2"),
    # 解包
    ("list 双赋值", "x = [1, 2]; a = x.pop(0); b = x.pop(0); assert a == 1 and b == 2"),
    # sorted with key
    ("sorted key 下标", "x = [[3, 'c'], [1, 'a'], [2, 'b']]; y = sorted(x, key=lambda p: p[0]); assert y[0][1] == 'a'"),
    # min
    ("min 默认", "x = [3, 1, 2]; y = min(x); assert y == 1"),
    ("min key", "x = [[3, 'c'], [1, 'a']]; y = min(x, key=lambda p: p[0]); assert y[1] == 'a'"),
    # 直接内置 list
    ("list() type", "x = list((1, 2, 3)); assert x[0] == 1"),
    # safe_builtins 检查
    ("isinstance int", "x = 1; assert isinstance(x, int)"),
    ("isinstance float", "x = 1.0; assert isinstance(x, float)"),
    ("isinstance list", "x = [1]; assert isinstance(x, list)"),
    ("isinstance str", "x = 'a'; assert isinstance(x, str)"),
    ("isinstance tuple", "x = (1,); assert isinstance(x, tuple)"),
    ("isinstance dict", "x = {'a': 1}; assert isinstance(x, dict)"),
    # min 不用 key
    ("min of tuples", "x = [(3, 'c'), (1, 'a')]; y = min(x); assert y == (1, 'a')"),
    # 反向 - 看看哪里 _getitem_ 实际能跑
    ("globals has _getitem_", "x = [1]; 'safe'"),  # 不能动态查 globals
]

for name, code in cases:
    r = sb.execute(code, language="python", timeout=4)
    err = (r.error or r.stderr or "")[:140]
    mark = "PASS" if r.passed else "FAIL"
    print(f"  [{mark}] {name:<22}  {err}")
