"""看 MLP 字符串 line 270 附近"""
from pathlib import Path
ref = Path(r"F:\比赛\中软杯\A3\scripts\reference_solutions.py").read_text(encoding="utf-8")
start = ref.find("REFERENCE_MLP = '''") + len("REFERENCE_MLP = '''")
end = ref.find("'''", start)
mlp = ref[start:end]
lines = mlp.split("\n")
# sandbox line 300 = MLP line 270 (因为前面有 harness 30 行)
for ln in [260, 265, 270, 275, 280, 285, 290, 295, 300]:
    if ln <= len(lines):
        print(f"  line {ln}: {lines[ln-1]!r}")
