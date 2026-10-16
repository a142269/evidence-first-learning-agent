"""读 3 道 import_blocked 题完整内容"""
import json
from pathlib import Path

p = Path(r"F:\比赛\中软杯\A3\data\question_bank_programming_extra_0704.json")
d = json.loads(p.read_text(encoding="utf-8"))
targets = {"prog-mlp-gradient-0704", "prog-rnn-bptt-0704", "prog-svm-kernel-0704"}
for q in d["questions"]:
    if q["id"] in targets:
        print(f"=== {q['id']} ===")
        print(f"stem ({len(q['stem'])} chars):")
        print(q["stem"])
        print()
        print(f"test_harness ({len(q.get('test_harness',''))} chars):")
        print(q.get("test_harness", ""))
        print(f"--- end ---\n")
