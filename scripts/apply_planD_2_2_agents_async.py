"""Plan D 2.2 — 批量把 Agent 的 self._call_llm(...) 改 await self._acall_llm(...)。

覆盖:
* profile_agent / course_expert / quiz_generator / path_planner
* multimodal_agent / tutor_agent / evaluator_agent
* textbook_qa_agent / reviewer_agent
* safe_decline_agent 不调 _call_llm 跳过
"""
import re
from pathlib import Path

ROOT = Path(r"F:\比赛\中软杯\A3\backend\app\agents")

TARGETS = [
    "profile_agent.py",
    "course_expert.py",
    "quiz_generator.py",
    "path_planner.py",
    "multimodal_agent.py",
    "tutor_agent.py",
    "evaluator_agent.py",
    "textbook_qa_agent.py",
    "reviewer_agent.py",
]

# 匹配 `result = self._call_llm(` 改成 `result = await self._acall_llm(`
# 同时兼容可能的缩进（4 / 8 空格）
PATTERN = re.compile(
    r"^(\s*)([A-Za-z_][A-Za-z0-9_]*\s*=\s*)self\._call_llm\(",
    re.MULTILINE,
)
REPLACEMENT = r"\1\2await self._acall_llm("

updated = 0
for name in TARGETS:
    fp = ROOT / name
    if not fp.exists():
        print(f"[SKIP] {name} not found")
        continue
    text = fp.read_text(encoding="utf-8")
    if "await self._acall_llm" in text:
        print(f"[SKIP] {name} already has _acall_llm")
        continue
    new_text, count = PATTERN.subn(REPLACEMENT, text)
    if count == 0:
        print(f"[SKIP] {name} no _call_llm usage")
        continue
    fp.write_text(new_text, encoding="utf-8")
    print(f"[OK] {name}: {count} replacements")
    updated += count

print(f"[DONE] {updated} replacements total")
