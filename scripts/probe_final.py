"""最终验证: 3 道题改写后的 harness 都能跑通 (mock 实现)"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sandbox = get_code_sandbox()

# === 题 4 改写 (LCG 拆分 + list 迭代 + 不下标) ===
HARNESS_Q4 = """
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

grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
assert len(grads) == 4
total = 0
ok = True
for v in grads.values():
    for row in v:
        for x in row:
            total = total + 1
            if not (-1e308 < x < 1e308):
                ok = False
assert ok
assert total == 13
"""
MOCK_Q4 = """
def mlp_forward_backward(X, y, W1, b1, W2, b2):
    dW1 = []
    for i in range(2):
        row = []
        for j in range(3):
            row.append(0.1)
        dW1.append(row)
    db1 = [[0.01, 0.02, 0.03]]
    dW2 = []
    for i in range(3):
        row = []
        for j in range(1):
            row.append(0.1)
        dW2.append(row)
    db2 = [[0.05]]
    return {'dW1': dW1, 'db1': db1, 'dW2': dW2, 'db2': db2}
"""
r = sandbox.execute(MOCK_Q4 + "\n" + HARNESS_Q4, language="python", timeout=4)
print(f"[题 4 mock 跑通]      {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")

# === 题 6 改写 (删 import math, 替换 isfinite) ===
HARNESS_Q6 = """
dW = bptt_dw([1.0, 2.0, 3.0], 0.5, 1.0)
assert isinstance(dW, float)
assert -1e308 < dW < 1e308
"""
MOCK_Q6 = """
def bptt_dw(xs, W, U):
    return 1.5
"""
r = sandbox.execute(MOCK_Q6 + "\n" + HARNESS_Q6, language="python", timeout=4)
print(f"[题 6 mock 跑通]      {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")

# === 题 8 改写 (只删 import math) ===
HARNESS_Q8 = """
assert abs(rbf_kernel([1,2], [1,2]) - 1.0) < 1e-6
assert abs(rbf_kernel([0,0], [10,10], gamma=0.5)) < 1e-3
"""
MOCK_Q8 = """
def rbf_kernel(x, y, gamma=0.5):
    # 用 .pop(0) 绕开下标
    xx = list(x)
    yy = list(y)
    s = 0.0
    n = len(xx)
    for i in range(n):
        a = xx.pop(0)
        b = yy.pop(0)
        d = a - b
        s = s + d * d
    return 2.718281828459045 ** (-gamma * s)
"""
r = sandbox.execute(MOCK_Q8 + "\n" + HARNESS_Q8, language="python", timeout=4)
print(f"[题 8 mock 跑通]      {'PASS' if r.passed else 'FAIL'} err={(r.error or r.stderr)[:200]}")

# === 不带 mock 跑 harness (验证 harness 本身可执行, 分类 = NEEDS_STARTER) ===
r = sandbox.execute(HARNESS_Q4, language="python", timeout=4)
err = (r.error or r.stderr)[:200]
cat = "NEEDS_STARTER" if "is not defined" in err else "OTHER"
print(f"[题 4 harness 单独]   {cat}  err={err[:100]}")

r = sandbox.execute(HARNESS_Q6, language="python", timeout=4)
err = (r.error or r.stderr)[:200]
cat = "NEEDS_STARTER" if "is not defined" in err else "OTHER"
print(f"[题 6 harness 单独]   {cat}  err={err[:100]}")

r = sandbox.execute(HARNESS_Q8, language="python", timeout=4)
err = (r.error or r.stderr)[:200]
cat = "NEEDS_STARTER" if "is not defined" in err else "OTHER"
print(f"[题 8 harness 单独]   {cat}  err={err[:100]}")
