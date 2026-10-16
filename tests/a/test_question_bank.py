"""题库测试：锁住 280 题容量 / 28 KP 覆盖 / Bloom 分布 / 检索接口正确性。

> 这些用例**强绑** ``data/question_bank.json`` 单文件路径，用于锁定主库基线
> 不被增量覆盖；合并行为由 `test_question_bank_merged.py` 验收。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.question_bank import (
    QuestionBank,
    QuestionBankError,
    get_question_bank,
    reset_question_bank,
)


_BANK_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def bank() -> QuestionBank:
    """强绑主库路径，保持当前 280 题基线契约。"""
    return QuestionBank(bank_path=_BANK_DIR / "question_bank.json")


@pytest.fixture
def merged_bank() -> QuestionBank:
    """合并视图（基于 _discover_bank_files 扫描），由 test_question_bank_merged.py 使用。"""
    reset_question_bank()
    return get_question_bank()


def test_total_is_280(bank: QuestionBank) -> None:
    assert bank.total == 280


def test_covers_28_kps(bank: QuestionBank) -> None:
    kps = bank.kp_ids
    assert len(kps) == 28
    expected_subset = {
        "python_basics", "ml_basics", "neural_networks", "transformer", "rag",
        "multi_agent_systems", "multimodal_llm", "ai_agent", "mcp_protocol",
    }
    assert expected_subset.issubset(set(kps))


def test_every_kp_has_10_questions(bank: QuestionBank) -> None:
    for kp in bank.kp_ids:
        assert len(bank.by_kp(kp)) == 10, f"{kp} 题数应为 10"


def test_bloom_distribution(bank: QuestionBank) -> None:
    summary = bank.coverage_summary()["by_bloom"]
    assert summary["Remember"] == 48
    assert summary["Understand"] == 56
    assert summary["Apply"] == 56
    assert summary["Analyze"] == 56
    assert summary["Evaluate"] == 36
    assert summary["Create"] == 28


def test_difficulty_spans_1_to_5(bank: QuestionBank) -> None:
    difficulties = bank.coverage_summary()["by_difficulty"]
    assert set(difficulties.keys()) == {1, 2, 3, 4, 5}


def test_each_multiple_choice_has_4_options_and_valid_answer(bank: QuestionBank) -> None:
    for q in bank.filter(question_type="multiple_choice"):
        assert "options" in q
        assert len(q["options"]) == 4, f"题 {q['id']} 选项数不是 4"
        assert q["answer"] in {"A", "B", "C", "D"}, f"题 {q['id']} 答案非法"


def test_short_answer_and_open_have_keywords(bank: QuestionBank) -> None:
    for qtype in ("short_answer", "open_ended"):
        for q in bank.filter(question_type=qtype):
            assert "expected_keywords" in q
            assert len(q["expected_keywords"]) >= 2
            assert q["answer"], f"题 {q['id']} 缺参考答案"


def test_question_ids_are_unique(bank: QuestionBank) -> None:
    ids = [q["id"] for q in bank.filter()]
    assert len(ids) == len(set(ids))


def test_filter_chained(bank: QuestionBank) -> None:
    hits = bank.filter(kp_id="transformer", bloom="Apply")
    assert all(q["kp_id"] == "transformer" and q["bloom"] == "Apply" for q in hits)
    assert len(hits) == 2  # Apply 每 KP 2 题


def test_sample_is_reproducible_with_seed(bank: QuestionBank) -> None:
    a = bank.sample(5, kp_id="cnn", seed=42)
    b = bank.sample(5, kp_id="cnn", seed=42)
    c = bank.sample(5, kp_id="cnn", seed=43)
    assert [q["id"] for q in a] == [q["id"] for q in b]
    assert [q["id"] for q in a] != [q["id"] for q in c]


def test_meta_content_hash_present(bank: QuestionBank) -> None:
    meta = bank.meta
    assert meta["total"] == 280
    assert meta["kp_count"] == 28
    assert "content_hash" in meta
    assert len(meta["content_hash"]) == 12


def test_missing_bank_raises(tmp_path: Path) -> None:
    with pytest.raises(QuestionBankError):
        QuestionBank(bank_path=tmp_path / "nope.json")


def test_get_question_bank_is_singleton() -> None:
    reset_question_bank()
    a = get_question_bank()
    b = get_question_bank()
    assert a is b
