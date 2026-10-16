"""编译 sandbox 源码, 看哪个 global 引用 _getitem_"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCE_MLP

from RestrictedPython import compile_restricted
import dis

full_src = REFERENCE_MLP + """

X = [[1.0, 2.0], [3.0, 4.0]]
y = [[1], [0]]
W1 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
b1 = [[0.0, 0.0, 0.0]]
W2 = [[0.5], [0.5], [0.5]]
b2 = [[0.0]]
grads = mlp_forward_backward(X, y, W1, b1, W2, b2)
print("OK")
"""

bytecode = compile_restricted(full_src, "<t>", "exec")
# 扫所有 LOAD_GLOBAL / LOAD_NAME
import io
out = io.StringIO()
dis.dis(bytecode, file=out)
asm = out.getvalue()
# 找 _getitem_ 出现
lines = asm.split("\n")
hits = []
for i, line in enumerate(lines):
    if "_getitem_" in line or "GETITEM" in line.upper() or "SUBSCR" in line:
        hits.append((i, line))
        # 找上下文
print(f"_getitem_ hits: {len(hits)}")
for ln, txt in hits[:5]:
    print(f"  {txt}")
