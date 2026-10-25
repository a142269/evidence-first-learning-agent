"""QWEN-312: prompt regression harness and fallback/override policy.

Fixed-sample behaviour assertions over the registry (version/hash/structure)
plus the Lead-decided fallback policy: runtime keeps the byte-identical
builtin fallback, every fallback logs a warning WITHOUT prompt text, and
verify_registry() is the CI hard gate.  All offline; no model calls.
"""
from __future__ import annotations

import logging

import pytest

from backend.app.agent_runtime import prompts
from backend.app.agent_runtime.learning_package import PROMPT_VERSION
from tests.a.test_learning_package import package, scripted as scripted
from tests.a.test_learning_runs_v2_lifecycle import api as api, events


def test_registry_aggregate_integrity():
    """Harness gate: every entry loads from its hash-verified file at v2.9."""
    assert prompts._OVERRIDES == {}, "production must start without A/B overrides"
    assert prompts.verify_registry() == {name: "ok" for name in prompts._BUILTIN}
    for entry in prompts.list_prompts():
        assert entry["version"] == PROMPT_VERSION == "learning-package-v2.9"
        prompt = prompts.render(entry["name"])
        assert prompt.source == "file"
        assert prompt.hash == prompts.sha256(prompt.text)
    prompts.clear_overrides()


def test_fixed_sample_learning_package_structure(scripted):
    """Fixed-sample regression: the deliverable keeps its documented shape."""
    client, _factory, replies, _calls = scripted
    replies.extend([
        {"steps": [
            {"id": "tutor_explain", "role": "tutor", "goal": "讲清检索增强生成", "depends_on": []},
            {"id": "practice_apply", "role": "practice", "goal": "三道递进练习", "depends_on": ["tutor_explain"]},
        ]},
        {"action": "search_course", "query": "检索增强生成 流程"},
        {"action": "finish", "query": ""},
        {"explanation": "固定样例讲解：先检索课程证据，再依据证据组织讲解并标注来源。",
         "source_ids": ["c1"]},
        {"exercises": [
            {"question": "固定样例问题一：检索增强生成的步骤是什么？", "answer": "先检索后生成。",
             "explanation": "固定样例解析一：先检索后生成。", "source_ids": ["c1"]},
            {"question": "固定样例问题二：引用元数据来自哪里？", "answer": "实际检索证据。",
             "explanation": "固定样例解析二：不接受模型编造。", "source_ids": ["c1"]},
            {"question": "固定样例问题三：预算超限会怎样？", "answer": "稳定错误失败。",
             "explanation": "固定样例解析三：上限不静默放宽。", "source_ids": ["c1"]},
        ]},
        {"approved": True, "issues": [], "lesson_approved": True, "practice_approved": True},
    ])
    output = events(package(client))
    final = output[-1][1]
    assert output[-1][0] == "run.completed", final
    plan = final["learning_package"]["plan"]
    assert [(step["id"], step["role"]) for step in plan["steps"]] == [
        ("tutor_explain", "tutor"), ("practice_apply", "practice")]
    assert plan["steps"][1]["depends_on"] == ["tutor_explain"]
    lesson = final["learning_package"]["lesson"]
    evidence_ids = {item["chunk_id"] for item in final["learning_package"]["evidence"]} \
        if "evidence" in final["learning_package"] else {"c1"}
    assert lesson["source_ids"] and set(lesson["source_ids"]) <= evidence_ids
    citation = lesson["citations"][0]
    assert set(citation) == {"chunk_id", "source", "label", "score"} and citation["score"] == 0
    exercises = final["learning_package"]["exercises"]
    assert len(exercises) == 3
    assert all(exercise["source_ids"] for exercise in exercises)
    assert all(set(exercise["citations"][0]) == {"chunk_id", "source", "label", "score"}
               for exercise in exercises)
    review = final["learning_package"]["review"]
    assert review["approved"] is True and review["lesson_approved"] is True
    assert final["learning_package"]["revisions"] == 0
    assert final["quality"]["claim_support"]["passed"] is True
    assert final["budget"]["model_calls"] == 6


def test_missing_file_falls_back_with_warning_and_no_text_leak(caplog, monkeypatch, tmp_path):
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    with caplog.at_level(logging.WARNING, logger="backend.app.agent_runtime.prompts"):
        prompt = prompts.render("planner_instruction")
    assert prompt.source == "builtin"
    assert prompt.text == prompts._BUILTIN["planner_instruction"]
    warnings = [record for record in caplog.records
                if record.name == "backend.app.agent_runtime.prompts"]
    assert len(warnings) == 1
    assert "planner_instruction" in warnings[0].getMessage()
    assert "missing" in warnings[0].getMessage()
    # No prompt text may leak into the log surface.
    assert "把学习需求拆成讲解" not in caplog.text
    assert "tutor_explain" not in caplog.text


def test_hash_mismatch_falls_back_with_warning_and_no_text_leak(caplog, monkeypatch, tmp_path):
    monkeypatch.setattr(prompts, "PROMPTS_DIR", tmp_path)
    (tmp_path / "tutor_instruction.txt").write_text("被篡改的候选文本", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="backend.app.agent_runtime.prompts"):
        prompt = prompts.render("tutor_instruction")
    assert prompt.source == "builtin"
    warnings = [record for record in caplog.records
                if record.name == "backend.app.agent_runtime.prompts"]
    assert len(warnings) == 1
    assert "tutor_instruction" in warnings[0].getMessage()
    assert "mismatch" in warnings[0].getMessage()
    assert "被篡改的候选文本" not in caplog.text
    assert prompts.verify_registry()["tutor_instruction"] == "mismatch"


def test_override_hook_roundtrip_for_ab():
    candidate = "候选讲解指令：仅用于 A/B harness。"
    prompts.apply_overrides({"tutor_instruction": candidate})
    try:
        prompt = prompts.render("tutor_instruction")
        assert prompt.source == "override" and prompt.text == candidate
        assert prompt.hash == prompts.sha256(candidate)
        assert prompt.version == PROMPT_VERSION
        with pytest.raises(prompts.PromptRegistryError) as err:
            prompts.apply_overrides({"no_such_prompt": "x"})
        assert err.value.code == "prompt_not_registered"
    finally:
        prompts.clear_overrides()
    restored = prompts.render("tutor_instruction")
    assert restored.source == "file" and prompts._OVERRIDES == {}
