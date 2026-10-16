"""Full verification: all 18 chapters + all 18 exercises + all 12 code examples + KP coverage."""
import os
import re
import subprocess

root = r"F:\比赛\中软杯\A3\knowledge_base\python_programming"


def section(title):
    print()
    print(f"=== {title} ===")


# 1. 18 个章节讲义
section("1. 18 章节讲义 + 课程总纲")
ch_dir = os.path.join(root, "chapters")
ch_files = sorted(os.listdir(ch_dir))
for f in ch_files:
    p = os.path.join(ch_dir, f)
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    if content.startswith("---"):
        end = content.find("---", 3)
        body = content[end + 3:]
    else:
        body = content
    body_no_code = re.sub(r"```.*?```", "", body, flags=re.S)
    has_kp = "kp_ids:" in content
    print(f"  {f}: {len(body_no_code)} chars, kp_ids={has_kp}")

# 课程总纲
with open(os.path.join(root, "Python程序设计.md"), "r", encoding="utf-8") as fh:
    content = fh.read()
end = content.find("---", 3) if content.startswith("---") else 0
body = content[end + 3:]
print(f"  Python程序设计.md (总纲): {len(body)} chars, mermaid={'mermaid' in body}")


# 2. 18 练习
section("2. 章节练习题数")
ex_dir = os.path.join(root, "exercises")
ex_files = sorted([f for f in os.listdir(ex_dir) if f.endswith(".md")])
for f in ex_files:
    p = os.path.join(ex_dir, f)
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    q = len(re.findall(r"^### Q\d+", content, flags=re.M))
    print(f"  {f}: {q} 题")


# 3. 12 代码示例
section("3. 12 个代码示例运行")
ce_dir = os.path.join(root, "code_examples")
# 只测新写的 12 个(数字编号 + 章节)
new_ce = [
    "01_variables_types_demo.py",
    "02_control_flow_demo.py",
    "03_functions_demo.py",
    "04_data_structures_demo.py",
    "05_strings_demo.py",
    "06_collections_demo.py",
    "07_oop_basics_demo.py",
    "08_inheritance_demo.py",
    "10_magic_methods_demo.py",
    "11_file_io_demo.py",
    "12_csv_json_demo.py",
    "13_exceptions_demo.py",
]
total_ok = 0
for f in new_ce:
    p = os.path.join(ce_dir, f)
    if not os.path.exists(p):
        print(f"  [MISS] {f}")
        continue
    r = subprocess.run(["python", p], capture_output=True, text=True, timeout=30)
    ok = "OK" if r.returncode == 0 else "FAIL"
    total_ok += 1 if ok == "OK" else 0
    print(f"  [{ok}] {f}")
    if r.returncode != 0:
        print(f"    stderr: {r.stderr[:200]}")
print(f"  通过率: {total_ok}/{len(new_ce)}")


# 4. KP 覆盖
section("4. KP 覆盖(对照 knowledge_map.yaml)")
import yaml
with open(r"F:\比赛\中软杯\A3\knowledge_base\knowledge_map.yaml", "r", encoding="utf-8") as fh:
    km = yaml.safe_load(fh)
py_kps = set()
for top_key, val in km.items():
    if isinstance(val, dict):
        for sub_key, sub_val in val.items():
            if isinstance(sub_val, dict) and sub_key.startswith("PY_"):
                py_kps.add(sub_key)
            if isinstance(sub_val, dict):
                for k in sub_val:
                    if k.startswith("PY_"):
                        py_kps.add(k)

ch_kps = set()
for f in ch_files:
    p = os.path.join(ch_dir, f)
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    kps = re.findall(r"^kp_ids:\s*\n((?:\s*-\s*\w+\s*\n)+)", content, flags=re.M)
    for kp_block in kps:
        ch_kps.update(re.findall(r"-\s*(\w+)", kp_block))

print(f"  knowledge_map 定义: {len(py_kps)} 个 PY KP")
print(f"  章节已覆盖: {len(ch_kps)} 个")
missing = sorted(py_kps - ch_kps)
print(f"  缺失: {missing if missing else '无'}")
