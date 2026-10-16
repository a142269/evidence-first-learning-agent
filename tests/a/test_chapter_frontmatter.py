"""锁住 20 章 frontmatter schema 一致性。"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CHAPTERS_DIR = (
    Path(__file__).resolve().parents[2]
    / "knowledge_base"
    / "artificial_intelligence"
    / "chapters"
)


REQUIRED_FIELDS = {
    "chapter_id",
    "slug",
    "title",
    "kp_ids",
    "bloom_focus",
    "prerequisites",
    "estimated_minutes",
}

VALID_BLOOM_LEVELS = {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}


def _parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} 未以 YAML frontmatter 起始"
    end = text.find("\n---\n", 4)
    assert end > 0, f"{path.name} frontmatter 未闭合"
    return yaml.safe_load(text[4:end])


@pytest.fixture(scope="module")
def chapter_files() -> list[Path]:
    files = sorted(CHAPTERS_DIR.glob("*.md"))
    assert len(files) == 20, f"期望 20 章，实际 {len(files)}"
    return files


def test_every_chapter_has_complete_frontmatter(chapter_files: list[Path]) -> None:
    for path in chapter_files:
        meta = _parse(path)
        missing = REQUIRED_FIELDS - set(meta.keys())
        assert not missing, f"{path.name} 缺字段 {missing}"


def test_chapter_id_matches_filename(chapter_files: list[Path]) -> None:
    for path in chapter_files:
        meta = _parse(path)
        cid = str(meta["chapter_id"])
        expected = path.name[:2]
        assert cid == expected, f"{path.name} chapter_id={cid} 与文件名前缀不符"


def test_bloom_focus_levels_are_valid(chapter_files: list[Path]) -> None:
    for path in chapter_files:
        meta = _parse(path)
        bloom_focus = meta.get("bloom_focus") or []
        assert bloom_focus, f"{path.name} bloom_focus 不能为空"
        for b in bloom_focus:
            assert b in VALID_BLOOM_LEVELS, f"{path.name} 含非法 Bloom 等级 {b!r}"


def test_prerequisites_reference_existing_chapters(chapter_files: list[Path]) -> None:
    chapter_ids = {p.name[:2] for p in chapter_files}
    for path in chapter_files:
        meta = _parse(path)
        for pre in meta.get("prerequisites") or []:
            assert str(pre) in chapter_ids, f"{path.name} 先修 {pre} 不存在"


def test_kp_ids_match_question_bank(chapter_files: list[Path]) -> None:
    from backend.app.services.knowledge_index import get_knowledge_index, reset_knowledge_index
    from backend.app.services.question_bank import get_question_bank, reset_question_bank

    reset_question_bank()
    reset_knowledge_index()
    index = get_knowledge_index()
    bank_kps = set(get_question_bank().kp_ids)
    for path in chapter_files:
        meta = _parse(path)
        chapter_id = str(meta["chapter_id"])
        chapter = index.get(chapter_id)
        assert chapter is not None, f"{path.name} 未被 KnowledgeIndex 加载"
        assert chapter.question_kp_ids, f"{path.name} 未映射到题库 KP"
        for kp in chapter.question_kp_ids:
            assert kp in bank_kps, f"{path.name} 映射到题库未定义的 KP: {kp}"
    assert index.coverage_report()["missing_bank_question_kps"] == []


def test_estimated_minutes_in_reasonable_range(chapter_files: list[Path]) -> None:
    for path in chapter_files:
        meta = _parse(path)
        mins = int(meta["estimated_minutes"])
        assert 20 <= mins <= 120, f"{path.name} estimated_minutes={mins} 超出 20-120"


def test_slug_matches_filename(chapter_files: list[Path]) -> None:
    for path in chapter_files:
        meta = _parse(path)
        expected_slug = path.stem.split("_", 1)[1]
        assert meta["slug"] == expected_slug, (
            f"{path.name} slug={meta['slug']!r} 与文件名不符"
        )
