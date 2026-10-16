"""sandbox 单独跑 MLP ref, 不带 harness"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.multimodal.code_sandbox import get_code_sandbox
from scripts.reference_solutions import REFERENCE_MLP

sb = get_code_sandbox()
# 不带 harness, 直接 def + 调用
code = REFERENCE_MLP + """

# 测试输入
X = [[0.5, 0.3], [0.1, 0.7], [0.8, 0.2], [0.4, 0.6]]
y = [[1], [0], [1], [0]]
W1 = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
b1 = [[0, 0, 0]]
W2 = [[0.1], [0.2], [0.3]]
b2 = [[0]]

grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
print("OK keys:", list(grads.keys()))
for k, v in grads.items():
    print(f"  {k}: {len(v)}x{len(v[0]) if v else 0}")
"""
r = sb.execute(code, language="python", timeout=30)
print("passed:", r.passed)
print("stdout:", r.stdout[:500])
print("err:", (r.error or r.stderr)[:500])
