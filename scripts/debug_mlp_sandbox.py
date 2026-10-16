"""sandbox 跑完整 MLP 真实现, 详细 trace"""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCES

from backend.app.services.multimodal.code_sandbox import get_code_sandbox
sb = get_code_sandbox()

# 模拟 harness 输入
test_harness = """
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
try:
    grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
    print("grads ok, keys:", list(grads.keys()))
except Exception as e:
    print("EXC type:", type(e).__name__)
    print("EXC:", str(e)[:500])
    import traceback
    traceback.print_exc()

# 单独测 def 行 (看 __name__ 报错是 transform 失败还是其他)
print("---")
print("Test: standalone def with __name__")
try:
    r = exec(compile("def f():\n    pass\nprint(f.__name__)", "<t>", "exec"), {})
    print("passed")
except Exception as e:
    print("EXC:", str(e)[:200])
"""

r = sb.execute(REFERENCES["prog-mlp-gradient-0704"] + test_harness, language="python", timeout=30)
print("passed:", r.passed)
print("stdout:", r.stdout[:1000])
print("stderr:", (r.stderr or "")[:500])
print("error:", (r.error or "")[:200])
