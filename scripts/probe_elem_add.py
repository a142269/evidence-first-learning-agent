"""单独测 elem_add 函数"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sb = get_code_sandbox()
test = """
def cp(L):
    out = []
    for v in L:
        out.append(v)
    return out

def elem_add(A, B):
    ac = cp(A)
    bc = cp(B)
    out = []
    while len(ac) > 0:
        ra = ac.pop(0)
        rb = bc.pop(0)
        rac = cp(ra)
        rbc = cp(rb)
        new_row = []
        while len(rac) > 0:
            a = rac.pop(0)
            b = rbc.pop(0)
            new_row.append(a + b)
        out.append(new_row)
    return out

print(elem_add([[1, 2]], [[3, 4]]))
"""
r = sb.execute(test, language="python", timeout=4)
print("passed:", r.passed)
print("stdout:", r.stdout)
print("err:", (r.error or r.stderr)[:300])
