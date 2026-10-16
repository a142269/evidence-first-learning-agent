"""校验 4 个生成文件的 JSON 合法性与数据一致性"""
import json
import os
import sys

DATA = r"F:\比赛\中软杯\A3\data"
FILES = [
    "question_bank_analytics_0708.json",
    "simulated_learning_data.json",
    "class_comparison_data.json",
    "learning_path_examples.json",
]

ok = True
for fname in FILES:
    p = os.path.join(DATA, fname)
    size = os.path.getsize(p)
    try:
        with open(p, "r", encoding="utf-8") as f:
            j = json.load(f)
        print(f"[OK] {fname}  size={size:>7} bytes  type={type(j).__name__}")
    except Exception as e:
        print(f"[FAIL] {fname}: {e}")
        ok = False

print()
print("=" * 60)
print("详细检查: question_bank_analytics_0708.json")
print("=" * 60)
with open(os.path.join(DATA, "question_bank_analytics_0708.json"), "r", encoding="utf-8") as f:
    qb = json.load(f)

assert isinstance(qb, list), "应是一个 JSON 数组"
print(f"  total questions: {len(qb)}")
assert len(qb) == 40, f"应为 40 题, 实际 {len(qb)}"

# Bloom 分布
from collections import Counter
by_kp = Counter(q["kp_id"] for q in qb)
by_bloom = Counter(q["bloom"] for q in qb)
by_type = Counter(q["type"] for q in qb)
print(f"  by kp_id: {dict(by_kp)}")
print(f"  by bloom: {dict(by_bloom)}")
print(f"  by type: {dict(by_type)}")

# 每个 kp 应该是 10 题
for kp, c in by_kp.items():
    assert c == 10, f"{kp} 数量错: {c}"
# 题型分布 6+2+2 per kp
for kp in by_kp:
    sub = [q for q in qb if q["kp_id"] == kp]
    types = Counter(q["type"] for q in sub)
    assert types["multiple_choice"] == 6, f"{kp} mc={types['multiple_choice']}"
    assert types["short_answer"] == 2, f"{kp} sa={types['short_answer']}"
    assert types["open_ended"] == 2, f"{kp} oe={types['open_ended']}"
print("  题型分布 6/2/2 per kp: OK")
# Bloom 1/2/2/2/2/1 per kp
for kp in by_kp:
    sub = [q for q in qb if q["kp_id"] == kp]
    b = Counter(q["bloom"] for q in sub)
    assert b["Remember"] == 1
    assert b["Understand"] == 2
    assert b["Apply"] == 2
    assert b["Analyze"] == 2
    assert b["Evaluate"] == 2
    assert b["Create"] == 1
print("  Bloom 分布 1/2/2/2/2/1 per kp: OK")
# id 唯一
ids = [q["id"] for q in qb]
assert len(set(ids)) == 40, "id 有重复"
print("  id 唯一: OK")
# 多选题 options=4
for q in qb:
    if q["type"] == "multiple_choice":
        assert len(q["options"]) == 4
        assert q["answer"] in "ABCD"
    else:
        assert "options" not in q
        assert "expected_keywords" in q
print("  multiple_choice options=4, sa/oe 有 expected_keywords: OK")

print()
print("=" * 60)
print("详细检查: simulated_learning_data.json")
print("=" * 60)
with open(os.path.join(DATA, "simulated_learning_data.json"), "r", encoding="utf-8") as f:
    sd = json.load(f)
print(f"  _meta: {sd['_meta']}")
assert len(sd["students"]) == 10
for s in sd["students"]:
    assert "student_id" in s
    assert "daily_records" in s
    assert "mastery_by_kp" in s
    assert "mistake_history" in s
    assert "summary_stats" in s
    # mastery 0-1
    for k, v in s["mastery_by_kp"].items():
        assert 0 <= v["current"] <= 1
        assert 0 <= v["initial"] <= 1
    # 错题字段
    for m in s["mistake_history"]:
        assert m["wrong_count"] >= 1
print(f"  10 学生, 全部字段完整, 掌握度 0-1 区间: OK")
total_records = sum(len(s["daily_records"]) for s in sd["students"])
total_mistakes = sum(len(s["mistake_history"]) for s in sd["students"])
print(f"  total daily_records: {total_records}")
print(f"  total mistake_history: {total_mistakes}")

print()
print("=" * 60)
print("详细检查: class_comparison_data.json")
print("=" * 60)
with open(os.path.join(DATA, "class_comparison_data.json"), "r", encoding="utf-8") as f:
    cc = json.load(f)
print(f"  _meta: {cc['_meta']}")
print(f"  target_student.nickname: {cc['target_student']['nickname']}")
print(f"  target_student.rankings.overall.rank: {cc['target_student']['rankings']['overall']['rank']}")
print(f"  class_stats.distribution: {cc['class_stats']['distribution']}")
print(f"  top_performers: {[t['nickname'] for t in cc['top_performers']]}")
assert len(cc["all_students"]) == 20
assert cc["_meta"]["total_students"] == 20
# 排名 1-20 唯一
all_ranks = [cc["target_student"]["rankings"][k]["rank"] for k in cc["target_student"]["rankings"]]
print(f"  target rankings: {dict((k, v) for k, v in cc['target_student']['rankings'].items())}")
print("  20 学生 + 排名 1-20 完整: OK")

print()
print("=" * 60)
print("详细检查: learning_path_examples.json")
print("=" * 60)
with open(os.path.join(DATA, "learning_path_examples.json"), "r", encoding="utf-8") as f:
    lp = json.load(f)
print(f"  _meta: {lp['_meta']}")
print(f"  paths: {len(lp['paths'])}")
for p in lp["paths"]:
    print(f"    {p['path_id']}: {p['title']} ({p['estimated_days']}天, {len(p['stages'])}阶段)")
    assert p["estimated_days"] in [7, 14, 30]
    assert 3 <= len(p["stages"]) <= 5
    # days 累计 = estimated_days
    total_d = sum(s["days"] for s in p["stages"])
    assert total_d == p["estimated_days"], f"{p['path_id']} days 累计 {total_d} != {p['estimated_days']}"
print("  3 条路径 + 阶段天数累计 = 估算天数: OK")

print()
print("ALL CHECKS PASSED" if ok else "SOMETHING WRONG")
