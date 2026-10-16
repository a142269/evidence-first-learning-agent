"""分前向/后向, 找 _getitem_ 错位置"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCE_MLP

from backend.app.services.multimodal.code_sandbox import get_code_sandbox
sb = get_code_sandbox()

# 找到 "    # ---- forward ----" 这行位置
mlp = REFERENCE_MLP
lines = mlp.split("\n")
fwd_start = None
for i, l in enumerate(lines):
    if "# ---- forward ----" in l:
        fwd_start = i
        break
print(f"forward start at line {fwd_start}")

# 测试 1: 只 helper
src1 = "\n".join(lines[:fwd_start])
r = sb.execute(src1 + "\n# stub", language="python", timeout=4)
print(f"[test1 helpers]  passed={r.passed}  err={(r.error or r.stderr)[:100]}")

# 测试 2: helpers + forward
src2 = "\n".join(lines[:fwd_start + 10])
r = sb.execute(src2 + "\n# stub", language="python", timeout=4)
print(f"[test2 forward partial]  passed={r.passed}  err={(r.error or r.stderr)[:100]}")
print(f"  last line: {lines[fwd_start + 9]!r}")

# 测试 3: 全 MLP + 调用
r = sb.execute(mlp + """

X = [[1.0, 2.0], [3.0, 4.0]]
y = [[1], [0]]
W1 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
b1 = [[0.0, 0.0, 0.0]]
W2 = [[0.5], [0.5], [0.5]]
b2 = [[0.0]]
try:
    grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
    print("OK")
except Exception as e:
    print("EXC:", str(e)[:200])
""", language="python", timeout=10)
print(f"[test3 full]  passed={r.passed}")
print(f"  err: {(r.error or r.stderr)!r}")
print(f"  stdout: {r.stdout[:200]}")
