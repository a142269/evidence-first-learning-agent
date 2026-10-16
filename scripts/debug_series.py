from backend.app.services.multimodal.code_sandbox import get_code_sandbox
sb = get_code_sandbox()
harness = """
def test_series(p):
    k = 1
    term = p - 1.0
    s = 0.0
    while k < 200:
        s = s + term / k
        term = term * (p - 1.0)
        k = k + 1
    return s

v = test_series(0.5)
print("series value:", v)
print("h term p=0.5:", -0.5 * (v / 0.693147))
print("expected ln(0.5):", -0.6931471805599453)
print("expected h for p=0.5:", 0.5)
"""
r = sb.execute(harness, language="python", timeout=10)
print("passed:", r.passed)
print("stdout:", r.stdout)
print("error:", (r.error or r.stderr)[:200])
