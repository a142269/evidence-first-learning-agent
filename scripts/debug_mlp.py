"""本地测 MLP 真实现 + 定位 pop from empty 错"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCES

# 模拟 harness 中的输入生成
code = REFERENCES["prog-mlp-gradient-0704"] + """

# 模拟 harness 输入
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
print("grads type:", type(grads))
print("keys:", list(grads.keys()))
for k, v in grads.items():
    print(f"  {k}: {len(v)}x{len(v[0]) if v else 0}")
"""

try:
    exec(code, globals())
except Exception as e:
    traceback.print_exc()
