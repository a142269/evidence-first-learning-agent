"""读 8 道题完整 stem + harness"""
import json
from pathlib import Path

p = Path(r"F:\比赛\中软杯\A3\data\question_bank_programming_extra_0704.json")
d = json.loads(p.read_text(encoding="utf-8"))
for i, q in enumerate(d["questions"], 1):
    print(f"\n{'='*72}\n{i}. {q['id']} ({q['kp_id']}/{q['bloom']}/diff={q['difficulty']})\n{'='*72}")
    print(f"stem:\n{q['stem']}")
    print(f"\ntest_harness:\n{q.get('test_harness','')}")
    print(f"\nexpected_keywords: {q.get('expected_keywords',[])}")
