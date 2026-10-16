"""看 MLP 字符串"""
from pathlib import Path
import sys
sys.path.insert(0, r"F:\比赛\中软杯\A3")
from scripts.reference_solutions import REFERENCE_MLP
lines = REFERENCE_MLP.split("\n")
out = [f"MLP str line count: {len(lines)}"]
from pathlib import Path
import json
import sys
sys.path.insert(0, r"F:\比赛\中软杯\A3")
from scripts.reference_solutions import REFERENCE_MLP

# 搜 MLP 字符串里的下标模式
import re
mlp = REFERENCE_MLP
out = [f"MLP lines: {len(mlp.split(chr(10)))}"]
for i, line in enumerate(mlp.split("\n"), 1):
    # 找可能的 obj[i] 模式
    if re.search(r'[a-zA-Z_]\w*\s*\[', line) and '[' in line and not line.lstrip().startswith('#'):
        # 过滤掉 docstring / 注释中的 [], 还有 reversed 等
        if 'reversed' in line or 'b\'\'' in line:
            continue
        out.append(f"  L{i}: {line}")
Path(r"F:\比赛\中软杯\A3\.tmp\dml3_out.log").write_text("\n".join(out), encoding="utf-8")
Path(r"F:\比赛\中软杯\A3\.tmp\dml3_out.log").write_text("\n".join(out), encoding="utf-8")
