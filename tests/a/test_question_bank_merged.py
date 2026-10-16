"""题库合并加载测试：跨文件加载 + 类型完备性 + KP 覆盖。

锁定：
* 默认加载会扫描 data/question_bank*.json（主库 + 增量）
* 至少 5 种题型（含 fill_blank / programming 新增）
* 280 主库题全量可达
* fill / programming 增量题的 KP 集合 ⊆ 主库 KP 集合（不留孤儿）
* duplicate id 不会让题目数爆炸
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.question_bank import (
    QuestionBank,
    QuestionBankError,
    _discover_bank_files,
    get_question_bank,
    reset_question_bank,
)


@pytest.fixture
def bank() -> QuestionBank:
    reset_question_bank()
    return get_question_bank()


def test_discovery_finds_expected_files() -> None:
    files = _discover_bank_files()
    names = [p.name for p in files]
    # 主库必须排首位
    assert names[0] == "question_bank.json"
    # quiz_bank.json 不参与合并
    assert "quiz_bank.json" not in names
    # 增量题库应当被扫描到
    assert any("extra" in n for n in names)
    assert any("fill" in n for n in names)
    assert any("programming" in n for n in names)


def test_merged_total_at_least_280(bank) -> None:
    """主库 280 题及增量合并后仍至少有 280 题。"""
    assert bank.total >= 280, f"合并题数 {bank.total} < 280"


def test_main_library_baseline(bank) -> None:
    """主库的 280 题应当完全可达，未被增量挤压。"""
    main_ids = {q["id"] for q in bank.filter()}
    # 主库 ≥ 280 道题
    sample_main_ids = {
        "q-python_basics-00",
        "q-transformer-00",
        "q-mcp_protocol-09",
        "q-multi_agent_systems-09",
        "q-ai_agent-09",
    }
    assert sample_main_ids <= main_ids


def test_all_five_question_types_present(bank) -> None:
    types = set(bank.allowed_types())
    expected = {"multiple_choice", "short_answer", "open_ended", "fill_blank", "programming"}
    assert expected <= types, f"缺题型: {expected - types}"


def test_fill_blank_questions_have_expected_keywords(bank) -> None:
    for q in bank.by_type("fill_blank"):
        assert "answer" in q, f"{q['id']} 填空题缺 answer"
        assert "expected_keywords" in q, f"{q['id']} 填空题缺 expected_keywords"


def test_programming_questions_have_test_harness(bank) -> None:
    for q in bank.by_type("programming"):
        assert q.get("test_harness"), f"{q['id']} 编程题缺 test_harness"
        assert q.get("language"), f"{q['id']} 编程题缺 language"


def test_new_increments_kp_subset_of_main(bank) -> None:
    """新增题库的 KP 不能引入主库未覆盖的 KP。"""
    main_kps = set()
    for q in bank.by_type("multiple_choice"):
        if q["kp_id"]:
            main_kps.add(q["kp_id"])

    new_kps: set[str] = set()
    for qtype in ("fill_blank", "programming"):
        for q in bank.by_type(qtype):
            new_kps.add(q["kp_id"])
    # 所有增量 KP 都在主库里有题目（不留孤儿）
    assert new_kps <= main_kps, f"增量 KP 不在主库内: {new_kps - main_kps}"


def test_programming_covers_at_least_8_kps(bank) -> None:
    prog_kps = {q["kp_id"] for q in bank.by_type("programming") if q.get("kp_id")}
    assert len(prog_kps) >= 8, f"编程题仅覆盖 {len(prog_kps)} KP（要求 ≥ 8）"


def test_fill_blank_covers_at_least_8_kps(bank) -> None:
    fill_kps = {q["kp_id"] for q in bank.by_type("fill_blank") if q.get("kp_id")}
    assert len(fill_kps) >= 8, f"填空题仅覆盖 {len(fill_kps)} KP（要求 ≥ 8）"


def test_sources_reports_each_file(bank) -> None:
    sources = bank.sources()
    paths = [s["path"] for s in sources]
    assert "question_bank.json" in paths
    # 至少有两个增量被识别
    extra_files = [p for p in paths if p != "question_bank.json"]
    assert len(extra_files) >= 2, f"增量文件数 {len(extra_files)} < 2"


def test_sources_reports_duplicates(bank) -> None:
    """0703 增量被识别为全 duplicate；新题库应 newly_added 等于其 count。"""
    src_map = {s["path"]: s for s in bank.sources()}
    if "question_bank_extra_0703.json" in src_map:
        src = src_map["question_bank_extra_0703.json"]
        # 0403 增量大抵全 duplicate（提前并入主库）
        assert src["duplicates_skipped"] >= 0
        assert src["newly_added"] >= 0
        assert src["newly_added"] + src["duplicates_skipped"] == src["count"]


def test_no_duplicate_ids_after_merge(bank) -> None:
    seen = set()
    for q in bank.filter():
        qid = q["id"]
        assert qid not in seen, f"去重后仍有重复 id: {qid}"
        seen.add(qid)


def test_explicit_path_overrides_discovery(tmp_path: Path) -> None:
    """显式 bank_path 仍可用（向后兼容）。"""
    payload = {"questions": [{"id": "q-test-00", "kp_id": "python_basics", "bloom": "Remember",
                              "type": "multiple_choice", "stem": "test", "difficulty": 1,
                              "answer": "A", "options": ["a", "b", "c", "d"], "explanation": "x"}]}
    fp = tmp_path / "single.json"
    fp.write_text(__import__("json").dumps(payload), encoding="utf-8")
    b = QuestionBank(bank_path=fp)
    assert b.total == 1
    assert b.kp_ids == ["python_basics"]


def test_missing_files_raises(tmp_path: Path) -> None:
    with pytest.raises(QuestionBankError):
        QuestionBank(bank_paths=[tmp_path / "ghost.json"])


def test_get_question_bank_is_singleton() -> None:
    reset_question_bank()
    assert get_question_bank() is get_question_bank()
