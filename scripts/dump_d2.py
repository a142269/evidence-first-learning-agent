"""临时读 D2 编程题清单"""
import json
from pathlib import Path

p = Path(r"F:\比赛\中软杯\A3\data\question_bank_programming_extra_0704.json")
d = json.loads(p.read_text(encoding="utf-8"))
print(f"Total: {len(d['questions'])}")
print()
for i, q in enumerate(d["questions"], 1):
    print(f"--- {i}. {q['id']} ({q['kp_id']}/{q['bloom']}) ---")
    print(f"  stem:    {q['stem'][:200]}")
    print(f"  diff:    {q.get('difficulty', '?')}")
    print(f"  tags:    {q.get('tags', [])}")
    harness = q.get("test_harness", "")
    print(f"  harness: {harness[:300]}")
    print(f"  keywords: {q.get('expected_keywords', [])}")
    print()
