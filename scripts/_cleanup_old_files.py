import os
from pathlib import Path
root = Path(r"F:\比赛\中软杯\A3\knowledge_base\python_programming")

to_delete = [
    "01_python_basics.md",
    "02_data_structures.md",
    "03_oop.md",
    "04_file_io_exceptions.md",
]

for f in to_delete:
    p = root / f
    if p.exists():
        p.unlink()
        print(f"deleted: {p.name}")
    else:
        print(f"not found: {p.name}")

keep = [
    "code_examples/01_python_basics_demo.py",
    "code_examples/02_data_structures_demo.py",
    "code_examples/03_oop_demo.py",
    "exercises/01_python_basics_exercises.md",
    "exercises/02_data_structures_exercises.md",
]
print()
print("=== 保留的旧文件 ===")
for f in keep:
    p = root / f
    status = "EXISTS" if p.exists() else "MISSING"
    print(f"  {f}: {status}")
