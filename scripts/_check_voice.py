"""Check voice script length."""
from pathlib import Path

docs = Path(r"F:\比赛\中软杯\A3\docs\voice_scripts")
files = sorted([f for f in docs.iterdir() if f.name.startswith("python_") and f.suffix == ".md"])
for f in files:
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
    cn = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    print(f"  {f.name}: {cn} 中文字符")
