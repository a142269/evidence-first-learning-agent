"""测 row_at + matmul + add_bias 单独"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCE_MLP

code = REFERENCE_MLP + """

# 简单测 — 写个 sandbox-friendly 验证
# 直接 matmul
A = [[1.0, 2.0], [3.0, 4.0]]
B = [[5.0, 6.0, 7.0], [8.0, 9.0, 10.0]]
try:
    C = mlp_forward_backward(A, [[0]], B, [[100, 200, 300]], [[1.0], [1.0], [1.0]], [[0]])
    print("FAIL: should have raised")
except IndexError as e:
    import traceback
    traceback.print_exc()
    print("IndexError at:", str(e)[:200])
"""
exec(code, globals())
