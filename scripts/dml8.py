"""sandbox 测 matmul 单独 (把 matmul 提升到全局)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import importlib

# 把 REFERENCE_MLP 替换为: matmul 提到全局, 简化
mlp_str = '''
def cp(L):
    out = []
    for v in L:
        out.append(v)
    return out
def row_at(M, idx):
    c = cp(M)
    r = None
    for _ in range(idx + 1):
        r = c.pop(0)
    return r
def get_at(M, i, j):
    r = row_at(M, i)
    rc = cp(r)
    v = None
    for _ in range(j + 1):
        v = rc.pop(0)
    return v
def matmul(A, B):
    m = 0
    for r in A:
        m = m + 1
    nb = 0
    for r in B:
        nb = nb + 1
    if m == 0 or nb == 0:
        return []
    b_first = row_at(B, 0)
    p = 0
    for v in b_first:
        p = p + 1
    result = []
    for i in range(m):
        a_row = row_at(A, i)
        new_row = []
        for j in range(p):
            s = 0.0
            for k in range(nb):
                arc = cp(a_row)
                a_k = None
                for _ in range(k + 1):
                    a_k = arc.pop(0)
                b_kj = get_at(B, k, j)
                s = s + a_k * b_kj
            new_row.append(s)
        result.append(new_row)
    return result

A = [[1.0, 2.0], [3.0, 4.0]]
B = [[5.0, 6.0, 7.0], [8.0, 9.0, 10.0]]
try:
    C = matmul(A, B)
    print("OK", C)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("EXC:", str(e)[:200])
'''

from backend.app.services.multimodal.code_sandbox import get_code_sandbox
sb = get_code_sandbox()
r = sb.execute(mlp_str, language="python", timeout=4)
print("passed:", r.passed)
print("stdout:", r.stdout)
print("err:", (r.error or r.stderr)[:300])
