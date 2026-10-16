"""Round 1 verification: run code examples + check word counts + question counts."""
import os
import re
import subprocess

root = r"F:\比赛\中软杯\A3\knowledge_base\python_programming"


def section(title):
    print()
    print(f"=== {title} ===")


# 1. 运行代码示例
section("代码示例运行测试")
ce_dir = os.path.join(root, "code_examples")
for f in sorted(os.listdir(ce_dir)):
    if f.endswith(".py") and re.match(r"^\d", f):
        p = os.path.join(ce_dir, f)
        try:
            r = subprocess.run(["python", p], capture_output=True, text=True, timeout=30)
            ok = "OK" if r.returncode == 0 else "FAIL"
            print(f"  [{ok}] {f}")
            if r.returncode != 0:
                print(f"    stderr: {r.stderr[:300]}")
            else:
                last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
                print(f"    last line: {last}")
        except Exception as e:
            print(f"  [ERR] {f}: {e}")


# 2. 章节文件字数统计
section("章节讲义字数(不含 frontmatter)")
ch_dir = os.path.join(root, "chapters")
for f in sorted(os.listdir(ch_dir)):
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


# 3. 练习题数统计
section("练习题数")
ex_dir = os.path.join(root, "exercises")
for f in sorted(os.listdir(ex_dir)):
    if not f.endswith(".md"):
        continue
    p = os.path.join(ex_dir, f)
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    q = len(re.findall(r"^### Q\d+", content, flags=re.M))
    print(f"  {f}: {q} 题")


# 4. 总纲字数
section("课程总纲")
with open(os.path.join(root, "Python程序设计.md"), "r", encoding="utf-8") as fh:
    content = fh.read()
if content.startswith("---"):
    end = content.find("---", 3)
    body = content[end + 3:]
else:
    body = content
print(f"  Python程序设计.md: {len(body)} chars (target ≥800)")
print(f"  含 mermaid: {'mermaid' in body}")


# 5. KP 覆盖检查
section("章节 KP 映射(对照 knowledge_map.yaml)")
import yaml
with open(r"F:\比赛\中软杯\A3\knowledge_base\knowledge_map.yaml", "r", encoding="utf-8") as fh:
    km = yaml.safe_load(fh)
# 兼容多种 yaml 结构
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
for f in sorted(os.listdir(ch_dir)):
    p = os.path.join(ch_dir, f)
    with open(p, "r", encoding="utf-8") as fh:
        content = fh.read()
    kps = re.findall(r"^kp_ids:\s*\n((?:\s*-\s*\w+\s*\n)+)", content, flags=re.M)
    for kp_block in kps:
        ch_kps.update(re.findall(r"-\s*(\w+)", kp_block))
print(f"  knowledge_map 中定义: {len(py_kps)} 个 PY KP")
print(f"  章节已覆盖: {len(ch_kps)} 个 → {sorted(ch_kps)}")
print(f"  缺失: {sorted(py_kps - ch_kps) if py_kps - ch_kps else '无'}")
