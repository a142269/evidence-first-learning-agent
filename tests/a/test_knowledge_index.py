"""KnowledgeIndex 服务测试：章节加载、KP 索引、与题库联动、覆盖率诊断。"""
from __future__ import annotations

import pytest

from backend.app.services.knowledge_index import (
    Chapter,
    KnowledgeIndex,
    KnowledgeIndexError,
    get_knowledge_index,
    reset_knowledge_index,
)
from backend.app.services.question_bank import get_question_bank, reset_question_bank


@pytest.fixture
def idx() -> KnowledgeIndex:
    reset_question_bank()
    reset_knowledge_index()
    return get_knowledge_index()


def test_loads_20_chapters(idx: KnowledgeIndex) -> None:
    assert idx.total == 20


def test_chapter_ids_are_zero_padded_two_digits(idx: KnowledgeIndex) -> None:
    assert idx.chapter_ids == [f"{i:02d}" for i in range(20)]


def test_get_returns_chapter_dataclass(idx: KnowledgeIndex) -> None:
    chapter = idx.get("13")
    assert isinstance(chapter, Chapter)
    assert chapter.title == "监督学习"
    assert "AI_005" in chapter.kp_ids
    assert "supervised_learning" in chapter.question_kp_ids
    assert chapter.estimated_minutes == 55


def test_by_kp_returns_all_chapters_referencing_kp(idx: KnowledgeIndex) -> None:
    sup_chapters = idx.by_kp("supervised_learning")
    cids = {c.chapter_id for c in sup_chapters}
    assert {"13", "15", "16"}.issubset(cids)


def test_practice_for_returns_5_questions_by_default(idx: KnowledgeIndex) -> None:
    qs = idx.practice_for("13", n=5)
    assert len(qs) == 5
    assert all(q["kp_id"] in idx.get("13").question_kp_ids for q in qs)


def test_practice_for_filters_by_bloom(idx: KnowledgeIndex) -> None:
    qs = idx.practice_for("18", n=10, bloom="Apply")
    assert all(q["bloom"] == "Apply" for q in qs)
    assert all(q["kp_id"] in {"rnn", "lstm"} for q in qs)


def test_practice_for_orphan_chapter_falls_back_to_bloom(idx: KnowledgeIndex) -> None:
    # 章节 06 的题库 KP 暂缺，应通过 bloom_focus 兜底
    qs = idx.practice_for("06", n=5)
    assert qs, "orphan 章节也应返回题"


def test_practice_for_unknown_chapter_returns_empty(idx: KnowledgeIndex) -> None:
    assert idx.practice_for("99", n=5) == []


def test_practice_for_graph_kp_uses_question_bank_mapping(idx: KnowledgeIndex) -> None:
    questions = idx.practice_for_kp("AI_006_03", n=4)

    assert questions
    assert all(q["kp_id"] in {"transformer", "attention_mechanism"} for q in questions)


def test_practice_for_graph_kp_without_bank_coverage_is_empty(idx: KnowledgeIndex) -> None:
    assert idx.practice_for_kp("AI_001", n=4) == []


def test_practice_for_seed_is_reproducible(idx: KnowledgeIndex) -> None:
    a = idx.practice_for("17", n=4, seed=42)
    b = idx.practice_for("17", n=4, seed=42)
    c = idx.practice_for("17", n=4, seed=43)
    ids_a = [q["id"] for q in a]
    ids_b = [q["id"] for q in b]
    ids_c = [q["id"] for q in c]
    assert ids_a == ids_b
    assert ids_a != ids_c


def test_prerequisites_chain_walks_recursively(idx: KnowledgeIndex) -> None:
    # 章节 12 直接先修 01/04/05/09，间接覆盖更深
    chain = idx.prerequisites_chain("12")
    cids = {c.chapter_id for c in chain}
    assert {"01", "04", "05", "09"}.issubset(cids)
    # 01 的先修 00 也应被传递性命中
    assert "00" in cids


def test_prerequisites_chain_for_root_chapter_is_empty(idx: KnowledgeIndex) -> None:
    # 章节 00 没有先修
    assert idx.prerequisites_chain("00") == []


def test_coverage_report_shape(idx: KnowledgeIndex) -> None:
    report = idx.coverage_report()
    assert report["total_chapters"] == 20
    assert report["total_kps_in_bank"] == len(get_question_bank().kp_ids)
    assert report["kps_with_chapter"] == 23
    assert set(report["orphan_kps"]) == {
        *(f"PY_{number:03d}" for number in range(1, 25)),
        "python_basics", "data_structures", "cognitive_diagnosis",
        "data_visualization", "learning_analytics_ethics", "learning_science",
    }
    assert report["orphan_chapters"] == []
    assert report["missing_bank_question_kps"] == []


def test_get_knowledge_index_is_singleton() -> None:
    reset_knowledge_index()
    a = get_knowledge_index()
    b = get_knowledge_index()
    assert a is b


def test_missing_directory_raises(tmp_path) -> None:
    with pytest.raises(KnowledgeIndexError):
        KnowledgeIndex(chapters_dir=tmp_path / "does_not_exist")


def test_empty_directory_raises(tmp_path) -> None:
    with pytest.raises(KnowledgeIndexError):
        KnowledgeIndex(chapters_dir=tmp_path)
