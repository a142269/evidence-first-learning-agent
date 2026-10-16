"""本地 Python 跑 MLP 真实现, 找 pop from empty 错"""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCE_MLP

# 测试输入
code = REFERENCE_MLP + """

X = [[0.5, 0.3], [0.1, 0.7], [0.8, 0.2], [0.4, 0.6]]
y = [[1], [0], [1], [0]]
W1 = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
b1 = [[0, 0, 0]]
W2 = [[0.1], [0.2], [0.3]]
b2 = [[0]]

try:
    grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
    print("OK keys:", list(grads.keys()))
    for k, v in grads.items():
        print(f"  {k}: {len(v)}x{len(v[0]) if v else 0}")
except Exception as e:
    print("EXC type:", type(e).__name__)
    print("EXC:", str(e)[:500])
    traceback.print_exc()
"""
try:
    exec(code, globals())
except Exception as e:
    print("Outer EXC:", str(e)[:200])
