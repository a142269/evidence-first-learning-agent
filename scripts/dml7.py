"""测 sigmoid 单独"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCE_MLP

code = REFERENCE_MLP + """

# 直接调 mlp_forward_backward
X = [[1.0, 2.0], [3.0, 4.0]]
y = [[1], [0]]
W1 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
b1 = [[0.0, 0.0, 0.0]]
W2 = [[0.5], [0.5], [0.5]]
b2 = [[0.0]]

# 跑前向: matmul + add_bias + sigmoid
from types import SimpleNamespace
# 我们不能调 helper, 只能调 mlp_forward_backward 看哪步炸
import traceback
try:
    grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
    print("OK")
    for k, v in grads.items():
        print(f"  {k}: {v}")
except Exception as e:
    traceback.print_exc()
    print("EXC:", str(e)[:200])
"""
try:
    exec(code, globals())
except Exception as e:
    print("Outer:", str(e)[:200])
