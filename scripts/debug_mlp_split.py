"""分块 sandbox 测, 找到具体 fail 行"""
from backend.app.services.multimodal.code_sandbox import get_code_sandbox
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCES

sb = get_code_sandbox()

# 拆 MLP 真实现, 一段段跑
ref = REFERENCES["prog-mlp-gradient-0704"]
# 拆 "    def" 为分隔符
parts = ref.split("    def ")
print(f"parts count: {len(parts)}")
for i, p in enumerate(parts):
    title = p.split("(", 1)[0] if "(" in p else p.split("\n", 1)[0]
    if i == 0:
        # 第一段: 函数签名 + helper
        body = p
    else:
        body = "    def " + p
    # 跑: 把前 i+1 段拼起来
    full = "    def ".join(parts[:i+1])
    # 加上入口调用 (用第一个 def 之前的)
    pre = parts[0].split("def mlp_forward_backward")[0]
    if "def mlp_forward_backward" in parts[0]:
        pre = "def mlp_forward_backward(X, y, W1, b1, W2, b2):\n"
    full = pre + "    def ".join(parts[1:i+1])
    # 结尾必须有 forward + backward 调用
    full = full + """
    n = 0
    for r in X:
        n = n + 1
    return n
"""
    r = sb.execute(full, language="python", timeout=10)
    print(f"  Part {i} ({title[:25]:<25})  passed={r.passed}  err={(r.error or r.stderr)[:80]}")
