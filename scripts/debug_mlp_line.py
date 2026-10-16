"""看 MLP ref 字符串 line 300 实际内容"""
import re
from pathlib import Path

ref = Path(r"F:\比赛\中软杯\A3\scripts\reference_solutions.py").read_text(encoding="utf-8")

# 提取 REFERENCE_MLP
start = ref.find("REFERENCE_MLP = '''")
if start == -1:
    print("not found")
else:
    body_start = start + len("REFERENCE_MLP = '''")
    body_end = ref.find("'''", body_start)
    mlp = ref[body_start:body_end]
    print(f"MLP str length: {len(mlp)} chars")
    lines = mlp.split("\n")
    print(f"line count: {len(lines)}")
    print(f"line 298: {lines[297] if len(lines) > 297 else 'NA'!r}")
    print(f"line 299: {lines[298] if len(lines) > 298 else 'NA'!r}")
    print(f"line 300: {lines[299] if len(lines) > 299 else 'NA'!r}")
    print(f"line 301: {lines[300] if len(lines) > 300 else 'NA'!r}")
