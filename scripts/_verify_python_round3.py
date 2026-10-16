"""Round 3 verification."""
import os
import re
import subprocess

root = r"F:\比赛\中软杯\A3\knowledge_base\python_programming"

print("=== Round 3 代码示例运行 ===")
ce_dir = os.path.join(root, "code_examples")
for f in sorted(os.listdir(ce_dir)):
    if re.match(r"^(11|12|13)_", f) and f.endswith(".py"):
        p = os.path.join(ce_dir, f)
        r = subprocess.run(["python", p], capture_output=True, text=True, timeout=30)
        ok = "OK" if r.returncode == 0 else "FAIL"
        print(f"  [{ok}] {f}")
        if r.returncode != 0:
            print(f"    stderr: {r.stderr[:500]}")

print()
print("=== Round 3 章节字数(§11-§13) ===")
ch_dir = os.path.join(root, "chapters")
target = ["11_file_io.md", "12_csv_json.md", "13_exceptions.md"]
for f in sorted(os.listdir(ch_dir)):
    if f in target:
        p = os.path.join(ch_dir, f)
        with open(p, "r", encoding="utf-8") as fh:
            content = fh.read()
        if content.startswith("---"):
            end = content.find("---", 3)
            body = content[end + 3:]
        else:
            body = content
        body_no_code = re.sub(r"```.*?```", "", body, flags=re.S)
        print(f"  {f}: {len(body_no_code)} chars")

print()
print("=== Round 3 练习题数 ===")
ex_dir = os.path.join(root, "exercises")
for f in sorted(os.listdir(ex_dir)):
    if f in ["11_file_io_exercises.md", "12_csv_json_exercises.md", "13_exceptions_exercises.md"]:
        p = os.path.join(ex_dir, f)
        with open(p, "r", encoding="utf-8") as fh:
            content = fh.read()
        q = len(re.findall(r"^### Q\d+", content, flags=re.M))
        print(f"  {f}: {q} 题")
