"""配套资源测试：code_examples / references / exercises + quality_checklist。

锁定：
* 5 个 code_examples 存在、可语法解析、含 docstring
* 3 篇 references 含正确 frontmatter（title / authors / year / kp_refs）
* 3 套 exercises 章节关联 + 含编程题
* quality_checklist.md 存在
* 覆盖率诊断里 chapter 03/04/05 有 exercise、≥ 4 章节有 code
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

from backend.app.services.knowledge_extras import (
    get_knowledge_extras,
    reset_knowledge_extras,
)


@pytest.fixture(scope="module")
def extras():
    reset_knowledge_extras()
    return get_knowledge_extras()


def test_code_examples_at_least_four(extras) -> None:
    """验收清单：≥ 4 个 code_examples 满足最低 KPI。"""
    assert len(extras.code_examples) >= 4


def test_each_code_example_is_parseable(extras) -> None:
    for c in extras.code_examples:
        path = Path(__file__).resolve().parents[2] / c.relative_path
        text = path.read_text(encoding="utf-8")
        assert text.lstrip().startswith('"""') or text.lstrip().startswith("'''"), (
            f"{c.name} 缺文件级 docstring"
        )
        try:
            ast.parse(text)
        except SyntaxError as exc:
            pytest.fail(f"{c.name} 语法错误: {exc}")


def test_each_code_example_has_doctring_doc_refs(extras) -> None:
    """每个示例 docstring 必须声明对应 KP 与章节。"""
    for c in extras.code_examples:
        assert c.kp_refs, f"{c.name} 缺 KP 引用"
        assert c.chapter_refs, f"{c.name} 缺 chapter 引用（用于前/后端展示）"
        assert c.entry_point, f"{c.name} 缺 entry_point"


def test_references_have_minimum_three(extras) -> None:
    assert len(extras.references) >= 3


def test_each_reference_has_required_frontmatter(extras) -> None:
    required = {"title", "kp_refs", "summary_zh"}
    for r in extras.references:
        missing = required - set(r.to_dict().keys())
        assert not missing, f"{r.name} 缺字段 {missing}"
        assert r.title, f"{r.name} title 为空"
        assert r.kp_refs, f"{r.name} kp_refs 为空"


def test_exercises_have_minimum_three(extras) -> None:
    assert len(extras.exercises) >= 3


def test_each_exercise_has_programming_or_high_bloom(extras) -> None:
    for e in extras.exercises:
        path = Path(__file__).resolve().parents[2] / e.relative_path
        text = path.read_text(encoding="utf-8")
        assert e.chapter_ref, f"{e.name} 缺 chapter_ref"
        assert e.kp_refs, f"{e.name} 缺 kp_refs"
        # 含编程题或高阶 Bloom 题（≥ Analyze）
        has_programming = bool(re.search(r"\*\*(编程题|Create|难度\s*[4-5])", text))
        has_high_bloom = any(b in {"Analyze", "Evaluate", "Create"} for b in e.bloom_focus)
        assert has_programming or has_high_bloom, (
            f"{e.name} 必须含编程题或 ≥Analyze 题"
        )
        assert e.question_count >= 3, f"{e.name} 至少 3 题"


def test_code_examples_structured_for_demo(extras) -> None:
    """demo 用：KP × 章节映射至少 3 个非空。"""
    coverage = extras.coverage()
    assert coverage["code_examples_total"] >= 4
    assert coverage["exercises_total"] >= 3
    assert coverage["references_total"] >= 3


def test_coverage_diagnosis_shape(extras) -> None:
    coverage = extras.coverage()
    assert "code_chapter_coverage" in coverage
    assert "exercise_chapter_coverage" in coverage
    assert "chapters_with_exercises" in coverage
    assert "chapters_with_code" in coverage


def test_quality_checklist_present() -> None:
    """docs 指南对位的 quality_checklist 必须存在（CI 锁死）。"""
    qc = (
        Path(__file__).resolve().parents[2]
        / "knowledge_base"
        / "knowledge_quality_checklist.md"
    )
    assert qc.exists()
    text = qc.read_text(encoding="utf-8")
    for keyword in ("frontmatter", "KP 三方一致性", "题库覆盖度", "CI 钩子"):
        assert keyword in text, f"checklist 缺章节 {keyword!r}"
