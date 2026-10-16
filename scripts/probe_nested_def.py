"""sandbox 测嵌套 def 是否被 __name__ 拦"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox

sb = get_code_sandbox()
test = """
def outer():
    def inner():
        return 1
    return inner()
print(outer())
"""
r = sb.execute(test, language="python", timeout=4)
print("passed:", r.passed)
print("err:", (r.error or r.stderr)[:200])
