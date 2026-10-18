"""Structured-output robustness: truncation-aware retries and tolerant JSON extraction.

These are synthetic contract tests; no provider is called.  They pin the
behaviour found by the 2026-10-18 diagnostic: the development-set failures were
length truncations at the per-call output cap (output tokens equal to the cap,
unbalanced JSON), not malformed-field or refusal responses.
"""
import json

import pytest
from pydantic import ValidationError

from backend.app.agent_runtime.learning_package import (
    Lesson, LearningPackageGraph, PackageFailure, _extract_json_object, _looks_truncated,
)
from backend.app.core.config import LLMConfig
from backend.app.core.llm_client import LLMClient
from backend.app.evaluation.ablation_runner import run_arm

LESSON = {"explanation": "检索增强生成先查找课程材料，再依据检索证据组织回答并标注引用来源。",
          "source_ids": ["c1"]}
PLAN = {"steps": [
    {"id": "tutor_explain", "role": "tutor", "goal": "讲解检索的作用", "depends_on": []},
    {"id": "practice_apply", "role": "practice", "goal": "设计三道递进练习", "depends_on": ["tutor_explain"]},
]}
PRACTICE = {"exercises": [
    {"question": f"第 {index} 题：为什么需要先检索？", "answer": "为了获得课程证据",
     "explanation": "检索先定位资料，回答再引用证据。", "source_ids": ["c1"]}
    for index in range(1, 4)
]}
EVIDENCE = [{"chunk_id": "c1", "source": "chapter.md", "content": "课程材料"}]
CASE = {"question": "讲解检索并设计三道练习", "course_id": "artificial_intelligence"}


class Runtime:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def complete_structured(self, messages, *, max_tokens):
        self.requests.append([dict(item) for item in messages])
        reply = self.replies.pop(0)
        if isinstance(reply, dict) and "text" in reply:
            return reply
        return {"text": reply, "usage": None}


def truncated_lesson():
    full = json.dumps(LESSON, ensure_ascii=False)
    return full[: max(24, len(full) - 40)]  # unbalanced JSON, like a length cut


def test_extract_json_object_tolerates_fences_and_prose():
    assert _extract_json_object('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _extract_json_object('```\n{"a": 1}\n```') == '{"a": 1}'
    assert _extract_json_object('前缀 {"a": {"b": "}"}} 后缀') == '{"a": {"b": "}"}}'
    assert _looks_truncated('{"a": "b', None) is True
    assert _looks_truncated('{"a": 1}', None) is False
    assert _looks_truncated('{"a": 1}', "length") is True


@pytest.mark.asyncio
async def test_lesson_accepts_fenced_json_without_retry():
    runtime = Runtime(['```json\n' + json.dumps(LESSON, ensure_ascii=False) + '\n```'])
    graph = LearningPackageGraph(runtime)
    result = await graph._ask({"message": "讲解", "budget": {}}, "Tutor", "生成讲解", {}, Lesson)
    assert result == LESSON
    assert len(runtime.requests) == 1


@pytest.mark.asyncio
async def test_truncated_lesson_retries_with_compact_guidance():
    runtime = Runtime([
        {"text": truncated_lesson(), "usage": None, "finish_reason": "length"},
        {"text": json.dumps(LESSON, ensure_ascii=False), "usage": None, "finish_reason": "stop"},
    ])
    graph = LearningPackageGraph(runtime)
    result = await graph._ask({"message": "讲解", "budget": {}}, "Tutor", "生成讲解", {}, Lesson)
    assert result == LESSON
    assert len(runtime.requests) == 2
    retry = runtime.requests[1][-1]["content"]
    assert "不是完整的 JSON" in retry and "长度" in retry
    assert "explanation" in retry and "350" in retry
    assert "source_ids" in retry


@pytest.mark.asyncio
async def test_unbalanced_json_without_finish_reason_is_treated_as_truncation():
    runtime = Runtime([
        {"text": truncated_lesson(), "usage": None},
        {"text": json.dumps(LESSON, ensure_ascii=False), "usage": None},
    ])
    graph = LearningPackageGraph(runtime)
    result = await graph._ask({"message": "讲解", "budget": {}}, "Tutor", "生成讲解", {}, Lesson)
    assert result == LESSON
    assert "长度" in runtime.requests[1][-1]["content"]


@pytest.mark.asyncio
async def test_repeated_truncation_fails_after_three_attempts():
    runtime = Runtime([
        {"text": truncated_lesson(), "usage": None, "finish_reason": "length"},
        {"text": truncated_lesson(), "usage": None, "finish_reason": "length"},
        {"text": truncated_lesson(), "usage": None, "finish_reason": "length"},
    ])
    graph = LearningPackageGraph(runtime)
    with pytest.raises(PackageFailure, match="learning_package_invalid_output"):
        await graph._ask({"message": "讲解", "budget": {}}, "Tutor", "生成讲解", {}, Lesson)
    assert len(runtime.requests) == 3


@pytest.mark.asyncio
async def test_balanced_schema_error_still_limited_to_two_attempts():
    invalid = json.dumps({"explanation": "过短", "source_ids": ["c1"]}, ensure_ascii=False)
    runtime = Runtime([invalid, invalid, json.dumps(LESSON, ensure_ascii=False)])
    graph = LearningPackageGraph(runtime)
    with pytest.raises(PackageFailure, match="learning_package_invalid_output"):
        await graph._ask({"message": "讲解", "budget": {}}, "Tutor", "生成讲解", {}, Lesson)
    assert len(runtime.requests) == 2
    assert "被截断" not in runtime.requests[1][-1]["content"]


@pytest.mark.asyncio
async def test_llm_client_exposes_finish_reason(monkeypatch):
    monkeypatch.delenv("V2_EVAL_BUDGET_CNY", raising=False)
    # The config provider property treats the offline-demo flag as "no provider".
    monkeypatch.delenv("A3_OFFLINE_DEMO", raising=False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"model": "deepseek-flash",
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    monkeypatch.setattr("requests.post", lambda *_args, **_kwargs: FakeResponse())
    config = LLMConfig(provider_override="openai_compatible", openai_api_key="test-key-not-real",
                       openai_base_url="https://example.invalid/v1", openai_model="deepseek-flash")
    client = LLMClient(config=config)
    result = await client.achat_strict_with_usage([{"role": "user", "content": "x"}], max_tokens=16)
    assert result["finish_reason"] == "length"
    assert result["usage"] == {"input_tokens": 3, "output_tokens": 2}


@pytest.mark.asyncio
async def test_ablation_without_reviewer_marks_lesson_only_as_incomplete():
    invalid_practice = json.dumps({"exercises": PRACTICE["exercises"][:1]}, ensure_ascii=False)
    runtime = Runtime([json.dumps(PLAN, ensure_ascii=False), json.dumps(LESSON, ensure_ascii=False),
                       invalid_practice, invalid_practice])
    result = await run_arm(runtime, CASE, EVIDENCE, "without_reviewer")
    assert result["completed"] is False
    assert result["error"] == "learning_package_incomplete_package"
    assert set(result["package"]) == {"lesson"}
    assert result["model_calls"] == 4


@pytest.mark.asyncio
async def test_ablation_full_arm_still_counts_complete_package():
    passed = {"approved": True, "issues": []}
    runtime = Runtime([json.dumps(PLAN, ensure_ascii=False), json.dumps(LESSON, ensure_ascii=False),
                       json.dumps(PRACTICE, ensure_ascii=False), json.dumps(passed)])
    result = await run_arm(runtime, CASE, EVIDENCE, "full")
    assert result["completed"] is True
    assert set(result["package"]) == {"lesson", "practice"}
