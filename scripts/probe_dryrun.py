"""Round 4 探查: 完全无下标 + 无 all/any"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sandbox = get_code_sandbox()

# 1) dict.values() 迭代 (不下标)
test_dict = """
d = {'a': 1, 'b': 2, 'c': 3}
total = 0
for v in d.values():
    total = total + v
assert total == 6
assert len(d) == 3
"""
r = sandbox.execute(test_dict, language="python", timeout=4)
print(f"[dict.values 迭代]    {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")

# 2) dict.get 方法
test_get = """
d = {'a': 1, 'b': 2}
v = d.get('a')
assert v == 1
v2 = d.get('z', 99)
assert v2 == 99
"""
r = sandbox.execute(test_get, language="python", timeout=4)
print(f"[dict.get 方法]        {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")

# 3) 题 4 完整 mock 跑通
test_q4 = """
def lcgstate(s):
    return (s * 1664525 + 1013904223) & 0xFFFFFFFF

def lcgvalue(s):
    return s / 0xFFFFFFFF * 2 - 1

def rgen(rows, cols, s):
    out = []
    for i in range(rows):
        row = []
        for j in range(cols):
            v = lcgvalue(s)
            s = lcgstate(s)
            row.append(v)
        out.append(row)
    return out

def zmat(rows, cols):
    out = []
    for i in range(rows):
        row = []
        for j in range(cols):
            row.append(0.0)
        out.append(row)
    return out

state = 0
state = lcgstate(state)
X = rgen(4, 2, state)
y = [[1], [0], [1], [0]]
W1 = rgen(2, 3, state)
b1 = zmat(1, 3)
W2 = rgen(3, 1, state)
b2 = zmat(1, 1)

def mlp_forward_backward(X, y, W1, b1, W2, b2):
    dW1 = zmat(2, 3)
    db1 = zmat(1, 3)
    dW2 = zmat(3, 1)
    db2 = zmat(1, 1)
    return {'dW1': dW1, 'db1': db1, 'dW2': dW2, 'db2': db2}

grads = mlp_forward_backward(X, y, W1, b1, W2, b2)

# 校验: dict 大小 + 4 个 value 都是 2D 列表 + 数字有限
assert isinstance(grads, dict)
assert len(grads) == 4

# 验证总元素数 (4 个 list: 2*3 + 1*3 + 3*1 + 1*1 = 13)
total = 0
ok = True
for v in grads.values():
    if not isinstance(v, list):
        ok = False
        break
    for row in v:
        for x in row:
            total = total + 1
            if not (-1e308 < x < 1e308):
                ok = False
assert ok
assert total == 13
"""
r = sandbox.execute(test_q4, language="python", timeout=4)
print(f"[题 4 mock 完整]       {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")

# 4) 题 8 改写 (用 range + 索引但有 _getitem_ 问题, 改用 zip-enumerate)
test_q8 = """
def rbf_kernel(x, y, gamma=0.5):
    s = 0.0
    n = len(x)
    i = 0
    while i < n:
        d = x[i] - y[i]  # ← 下标
        s = s + d * d
        i = i + 1
    return 2.718281828459045 ** (-gamma * s)
"""
r = sandbox.execute(test_q8, language="python", timeout=4)
print(f"[题 8 (用 while+索引)] {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")

# 5) 题 8 改写 v2: 不用下标, 用 zip 两个 list 然后 sum((a-b)^2)
#    但 zip((a,b), (c,d)) 返回 list of tuple, for (a,b) in zip(...): 是解包, 不行
#    只能 sum 单值: 用 enumerate? 但 enumerate 需要 _getiter_, 应该 OK
test_q8_v2 = """
def rbf_kernel(x, y, gamma=0.5):
    # 用 list 模拟 (xi - yi)^2 之和
    diffs = []
    for pair in zip(x, y):
        diffs.append(pair[0] - pair[1])  # ← 还是下标
    s = 0.0
    for d in diffs:
        s = s + d * d
    return 2.718281828459045 ** (-gamma * s)
"""
r = sandbox.execute(test_q8_v2, language="python", timeout=4)
print(f"[题 8 v2 (zip+下标)]  {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")
