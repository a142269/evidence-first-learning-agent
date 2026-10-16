"""sandbox 逐步跑, 找到 _getitem_ 错位置"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCE_MLP

from backend.app.services.multimodal.code_sandbox import get_code_sandbox
sb = get_code_sandbox()

# 拆 MLP 字符串为 def, 跑每段
parts = REFERENCE_MLP.split("\ndef ")
print(f"parts: {len(parts)}")
# 第一次: 只 def mlp_forward_backward
for i, p in enumerate(parts):
    title = p.split("(", 1)[0] if "(" in p else p[:30]
    # 重建 source: 第一段用原 "def " 开头, 后续段前面加 "def "
    if i == 0:
        src = p
    else:
        src = "\ndef ".join(parts[:i+1])
    # 加测试调用 — 返回 None 简化
    src = src + "\n# stub return None\n"
    # 跑
    r = sb.execute(src, language="python", timeout=4)
    status = "PASS" if r.passed else "FAIL"
    err = (r.error or r.stderr)[:80]
    print(f"  [{status}] part {i} ({title[:30]:<30})  err={err}")
