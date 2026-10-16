"""sandbox 跑 add_bias 看哪行出 pop from empty"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sb = get_code_sandbox()

# 简化测试 add_bias
test = """
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

def add_bias(M, b):
    b_row = row_at(b, 0)
    out = []
    for r in M:
        rc = cp(r)
        bc = cp(b_row)
        new_row = []
        i = 0
        while len(rc) > 0:
            a = rc.pop(0)
            bb = bc.pop(0)
            new_row.append(a + bb)
            i = i + 1
        out.append(new_row)
    return out

M = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]]
b = [[0, 0, 0]]
out = add_bias(M, b)
print(out)
"""

r = sb.execute(test, language="python", timeout=4)
print("passed:", r.passed)
print("stdout:", r.stdout)
print("err:", (r.error or r.stderr)[:200])
