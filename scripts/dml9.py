"""sandbox 跑完整简化版 MLP"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCE_MLP

from backend.app.services.multimodal.code_sandbox import get_code_sandbox
sb = get_code_sandbox()
code = REFERENCE_MLP + """

X = [[1.0, 2.0], [3.0, 4.0]]
y = [[1], [0]]
W1 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
b1 = [[0.0, 0.0, 0.0]]
W2 = [[0.5], [0.5], [0.5]]
b2 = [[0.0]]
try:
    grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
    print("OK keys:", list(grads.keys()))
except Exception as e:
    print("EXC:", str(e)[:300])
"""
r = sb.execute(code, language="python", timeout=30)
print("passed:", r.passed)
print("stdout:", r.stdout)
print("err:", (r.error or r.stderr)[:500])
