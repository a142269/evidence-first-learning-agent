"""Final verification of 25-Python course补齐 task."""
import os
import re
import subprocess
from pathlib import Path

root = Path(r"F:\比赛\中软杯\A3")
kb = root / "knowledge_base" / "python_programming"
docs = root / "docs" / "voice_scripts"
data = root / "data"


def section(t):
    print(f"\n=== {t} ===")


# 1. 课程总纲
section("1. 课程总纲")
p = kb / "Python程序设计.md"
with open(p, "r", encoding="utf-8") as f:
    content = f.read()
end = content.find("---", 3) if content.startswith("---") else 0
body = content[end + 3:]
status = "OK" if len(body) >= 800 and "mermaid" in body else "FAIL"
print(f"  Python程序设计.md: {len(body)} chars, mermaid={'mermaid' in body} [{status}]")

# 2. 18 章节讲义
section("2. 18 章节讲义")
ch_dir = kb / "chapters"
ch_files = sorted([f for f in os.listdir(ch_dir) if f.endswith(".md")])
print(f"  章节数: {len(ch_files)} (target 18)")
all_ok = True
for f in ch_files:
    p = ch_dir / f
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    if content.startswith("---"):
        end = content.find("---", 3)
        body = content[end + 3:]
    else:
        body = content
    body_no_code = re.sub(r"```.*?```", "", body, flags=re.S)
    has_kp = "kp_ids:" in content
    target_met = len(body_no_code) >= 2000 and has_kp
    if not target_met:
        all_ok = False
        print(f"  [FAIL] {f}: {len(body_no_code)} chars, kp_ids={has_kp}")
print(f"  全部达标: {'YES' if all_ok else 'NO'}")

# 3. 18 练习
section("3. 18 章节练习")
ex_dir = kb / "exercises"
ex_files = sorted([f for f in os.listdir(ex_dir) if f.endswith("_exercises.md")])
print(f"  练习文件数: {len(ex_files)} (target 18)")
all_ok = True
for f in ex_files:
    p = ex_dir / f
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    q = len(re.findall(r"^### Q\d+", content, flags=re.M))
    if q < 10:
        all_ok = False
        print(f"  [FAIL] {f}: {q} 题")
print(f"  全部达标 (≥10 题): {'YES' if all_ok else 'NO'}")

# 4. 12 代码示例
section("4. 12 个代码示例(可运行)")
ce_dir = kb / "code_examples"
new_ce = [
    "01_variables_types_demo.py", "02_control_flow_demo.py",
    "03_functions_demo.py", "04_data_structures_demo.py",
    "05_strings_demo.py", "06_collections_demo.py",
    "07_oop_basics_demo.py", "08_inheritance_demo.py",
    "10_magic_methods_demo.py", "11_file_io_demo.py",
    "12_csv_json_demo.py", "13_exceptions_demo.py",
]
total_ok = 0
for f in new_ce:
    p = ce_dir / f
    if not p.exists():
        print(f"  [MISS] {f}")
        continue
    r = subprocess.run(["python", str(p)], capture_output=True, text=True, timeout=30)
    ok = "OK" if r.returncode == 0 else "FAIL"
    if r.returncode == 0:
        total_ok += 1
    print(f"  [{ok}] {f}")
print(f"  通过率: {total_ok}/12")

# 5. 6 参考文献
section("5. 6 篇参考文献")
ref_dir = kb / "references"
ref_files = sorted([f for f in os.listdir(ref_dir) if f.endswith(".md")])
print(f"  文献数: {len(ref_files)} (target 6)")
for f in ref_files:
    p = ref_dir / f
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    has_front = content.startswith("---")
    has_summary = "summary_zh" in content
    print(f"  {f}: frontmatter={has_front}, summary={has_summary}")

# 6. 实验指导
section("6. 实验指导.md")
p = kb / "实验指导.md"
if p.exists():
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    ex_count = content.count("实验 ") + content.count("## 实验")
    print(f"  实验指导.md: {ex_count} 实验 (target 5)")

# 7. 18 PPT 大纲
section("7. 18 个 PPT 大纲")
slides_dir = kb / "slides"
slide_files = sorted([f for f in os.listdir(slides_dir) if f.endswith(".md")])
print(f"  PPT 文件数: {len(slide_files)} (target 18)")

# 8. 题库 240 题
section("8. 题库 240 题")
qb = data / "question_bank_python.json"
if qb.exists():
    import json
    with open(qb, "r", encoding="utf-8") as f:
        bank = json.load(f)
    print(f"  题数: {len(bank['questions'])} (target 240)")
    print(f"  KP 数: {bank['_meta']['kp_count']}")
    print(f"  题型分布: {bank['_meta']['type_distribution']}")
    print(f"  Bloom 分布: {bank['_meta']['bloom_distribution']}")
    kps = set(q['kp_id'] for q in bank['questions'])
    print(f"  KP 覆盖: {len(kps)} (target 24)")

# 9. 6 语音脚本
section("9. 6 语音脚本")
vs_files = sorted([f for f in os.listdir(docs) if f.startswith("python_") and f.endswith(".md")])
print(f"  语音脚本数: {len(vs_files)} (target 6)")
for f in vs_files:
    p = docs / f
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    cn_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    print(f"  {f}: {cn_chars} 中文字符")

# 10. 旧文件清理
section("10. 旧文件清理验证")
old_md = ["01_python_basics.md", "02_data_structures.md", "03_oop.md", "04_file_io_exceptions.md"]
all_cleaned = True
for f in old_md:
    p = kb / f
    if p.exists():
        all_cleaned = False
        print(f"  [STILL EXISTS] {f}")
print(f"  旧 md 清理: {'OK' if all_cleaned else 'FAIL'}")

print()
print("=" * 60)
print("完成情况:25-Python 课程全量补齐任务")
print("=" * 60)
