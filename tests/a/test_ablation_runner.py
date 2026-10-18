import json

import pytest

from backend.app.evaluation.ablation_runner import run_arm


PLAN = {"steps": [{"id": "tutor_explain", "role": "tutor", "goal": "讲解", "depends_on": []},
                  {"id": "practice_apply", "role": "practice", "goal": "练习", "depends_on": ["tutor_explain"]}]}
LESSON = {"explanation": "检索增强生成使用课程中的资料组织回答，并标记来源以便读者核对。", "source_ids": ["c1"]}
PRACTICE = {"exercises": [{"question": "检索的主要作用是什么？", "answer": "提供资料", "explanation": "检索提供有依据的课程资料。", "source_ids": ["c1"]} for _ in range(3)]}
EVIDENCE = [{"chunk_id": "c1", "source": "chapter.md", "content": "课程材料"}]
CASE = {"question": "讲解检索并设计练习", "course_id": "artificial_intelligence"}


class Runtime:
    def __init__(self, replies):
        self.replies = list(replies)
        self.token_limits = []

    async def complete_structured(self, messages, *, max_tokens):
        self.token_limits.append(max_tokens)
        return {"text": json.dumps(self.replies.pop(0), ensure_ascii=False), "usage": None}

    async def call_tool(self, *args, **kwargs):
        raise AssertionError("identity-dependent tools must not run")


@pytest.mark.asyncio
async def test_three_arms_have_distinct_real_call_sequences():
    passed = {"approved": True, "issues": []}
    for arm, replies, calls in [("single", [{"lesson": LESSON, "practice": PRACTICE}], 1),
                                ("without_reviewer", [PLAN, LESSON, PRACTICE], 3),
                                ("full", [PLAN, LESSON, PRACTICE, passed], 4)]:
        runtime = Runtime(replies)
        result = await run_arm(runtime, CASE, EVIDENCE, arm)
        assert result["completed"] and result["model_calls"] == calls
        assert set(runtime.token_limits) == ({8192} if arm == "single" else {1024})
        assert sum(runtime.token_limits) <= 8192
        assert result["package"]["lesson"] == LESSON


@pytest.mark.asyncio
async def test_full_arm_runs_one_targeted_practice_repair():
    rejected = {"approved": False, "issues": ["题目需改进"], "repair_target": "exercise"}
    passed = {"approved": True, "issues": []}
    result = await run_arm(Runtime([PLAN, LESSON, PRACTICE, rejected, PRACTICE, passed]), CASE, EVIDENCE, "full")
    assert result["completed"] and result["model_calls"] == 6
    assert result["reviewer_initially_rejected"] and result["reviewer_revision_succeeded"]


@pytest.mark.asyncio
async def test_fabricated_citations_fail_closed():
    result = await run_arm(Runtime([{"lesson": {**LESSON, "source_ids": ["fake"]}, "practice": PRACTICE}]), CASE, EVIDENCE, "single")
    assert not result["completed"] and result["error"] == "learning_package_invalid_citation"
