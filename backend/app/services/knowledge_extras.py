"""配套资源聚合服务 · 把 code_examples / references / exercises 暴露给前端与 Agent。

设计原则
========
* 只读 — 不修改源文件
* 纯 stdlib + PyYAML（与 knowledge_index 对齐）
* 章节 frontmatter 与 references / code_examples 的 `chapter_ref` 双向对齐
* 给前端 KnowledgeView / ResourcesView 当可选附件清单
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_AI_ROOT = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "artificial_intelligence"
)
_CODE_DIR = _AI_ROOT / "code_examples"
_REFS_DIR = _AI_ROOT / "references"
_EX_DIR = _AI_ROOT / "exercises"
_QUALITY_CHECKLIST = (
    Path(__file__).resolve().parents[3] / "knowledge_base" / "knowledge_quality_checklist.md"
)


class KnowledgeExtrasError(RuntimeError):
    """配套资源聚合失败时抛出。"""


@dataclass
class CodeExample:
    """一个可运行示例脚本。"""

    name: str  # 文件名
    relative_path: str  # 相对 knowledge_base/
    kp_refs: list[str]
    chapter_refs: list[str]
    summary: str  # 文件级 docstring 第一行
    entry_point: str | None  # "python xxx.py"
    estimated_minutes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.relative_path,
            "kp_refs": self.kp_refs,
            "chapter_refs": self.chapter_refs,
            "summary": self.summary,
            "entry_point": self.entry_point,
            "estimated_minutes": self.estimated_minutes,
        }


@dataclass
class ReferenceReading:
    """一篇扩展阅读材料。"""

    name: str
    relative_path: str
    title: str
    authors: list[str]
    year: int | None
    url: str | None
    kp_refs: list[str]
    summary_zh: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.relative_path,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "url": self.url,
            "kp_refs": self.kp_refs,
            "summary_zh": self.summary_zh,
        }


@dataclass
class ExerciseSheet:
    """一份章节配套练习 markdown。"""

    name: str
    relative_path: str
    chapter_ref: str
    chapter_title: str
    kp_refs: list[str]
    bloom_focus: list[str]
    total_points: int
    deadline_hint: str
    question_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.relative_path,
            "chapter_ref": self.chapter_ref,
            "chapter_title": self.chapter_title,
            "kp_refs": self.kp_refs,
            "bloom_focus": self.bloom_focus,
            "total_points": self.total_points,
            "deadline_hint": self.deadline_hint,
            "question_count": self.question_count,
        }


@dataclass
class KnowledgeExtras:
    """聚合视图：按章节 / KP 索引全部配套资源。"""

    code_examples: list[CodeExample] = field(default_factory=list)
    references: list[ReferenceReading] = field(default_factory=list)
    exercises: list[ExerciseSheet] = field(default_factory=list)

    def by_chapter(self, chapter_ref: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "code_examples": [
                c.to_dict() for c in self.code_examples if chapter_ref in c.chapter_refs
            ],
            "references": [
                r.to_dict() for r in self.references if chapter_ref in r.kp_refs
            ],
            "exercises": [
                e.to_dict() for e in self.exercises if e.chapter_ref == chapter_ref
            ],
        }

    def by_kp(self, kp_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "code_examples": [
                c.to_dict() for c in self.code_examples if kp_id in c.kp_refs
            ],
            "references": [
                r.to_dict() for r in self.references if kp_id in r.kp_refs
            ],
            "exercises": [
                e.to_dict() for e in self.exercises if kp_id in e.kp_refs
            ],
        }

    def coverage(self) -> dict[str, Any]:
        """返回覆盖率诊断，对接 check_kb_quality.py。"""
        chapters_with_exercises_set = {e.chapter_ref for e in self.exercises}
        chapters_with_code_set = {
            chap for c in self.code_examples for chap in c.chapter_refs
        }
        return {
            "code_examples_total": len(self.code_examples),
            "references_total": len(self.references),
            "exercises_total": len(self.exercises),
            "chapters_with_exercises": sorted(chapters_with_exercises_set),
            "chapters_with_code": sorted(chapters_with_code_set),
            "code_chapter_coverage": round(len(chapters_with_code_set) / 20, 3),
            "exercise_chapter_coverage": round(len(chapters_with_exercises_set) / 20, 3),
            "quality_checklist_present": _QUALITY_CHECKLIST.exists(),
        }


def _parse_md_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end <= 0:
        return {}
    try:
        return yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}


def _parse_python_docstring(path: Path) -> tuple[str, int]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r'"""(.+?)"""', text, re.DOTALL)
    if not m:
        return "", 0
    body = m.group(1).strip()
    first_line = body.splitlines()[0].strip() if body else ""
    # 估计耗时：从 "预估时长" 或 docstring 关键词推断
    minutes = 0
    search = re.search(r"(\d+)\s*(分钟|学时|minutes?)", body)
    if search:
        minutes = int(search.group(1))
    return first_line, minutes


def _load_code_examples() -> list[CodeExample]:
    if not _CODE_DIR.exists():
        return []
    examples: list[CodeExample] = []
    for path in sorted(_CODE_DIR.glob("*.py")):
        summary, minutes = _parse_python_docstring(path)
        # KP / Chapter 由 docstring 推断（标注块）
        text = path.read_text(encoding="utf-8")
        kp_refs = re.findall(r"对应 KP\s*[：:]\s*(.+)", text)
        chapter_refs = re.findall(r"对应章节\s*[：:]\s*([\w§\.0-9 ]+)", text)
        examples.append(
            CodeExample(
                name=path.name,
                relative_path=str(path.relative_to(_AI_ROOT.parents[1])),
                kp_refs=[kp.strip() for kp in kp_refs[0].split("、")] if kp_refs else [],
                chapter_refs=[c.strip().replace("§", "")[:2] for c in chapter_refs if c.strip()],
                summary=summary,
                entry_point=f"python {path.relative_to(_AI_ROOT.parents[1])}",
                estimated_minutes=minutes,
            )
        )
    return examples


def _load_references() -> list[ReferenceReading]:
    if not _REFS_DIR.exists():
        return []
    refs: list[ReferenceReading] = []
    for path in sorted(_REFS_DIR.glob("*.md")):
        meta = _parse_md_frontmatter(path)
        refs.append(
            ReferenceReading(
                name=path.name,
                relative_path=str(path.relative_to(_AI_ROOT.parents[1])),
                title=str(meta.get("title", path.stem)),
                authors=list(meta.get("authors", []) or []),
                year=int(meta["year"]) if meta.get("year") is not None else None,
                url=str(meta["url"]) if meta.get("url") else None,
                kp_refs=list(meta.get("kp_refs", []) or []),
                summary_zh=str(meta.get("summary_zh", "")),
            )
        )
    return refs


def _load_exercises() -> list[ExerciseSheet]:
    if not _EX_DIR.exists():
        return []
    sheets: list[ExerciseSheet] = []
    for path in sorted(_EX_DIR.glob("*.md")):
        meta = _parse_md_frontmatter(path)
        # 统计题数
        text = path.read_text(encoding="utf-8")
        q_count = len(re.findall(r"^###\s+Q\d+", text, re.MULTILINE))
        sheets.append(
            ExerciseSheet(
                name=path.name,
                relative_path=str(path.relative_to(_AI_ROOT.parents[1])),
                chapter_ref=str(meta.get("chapter_ref", "")),
                chapter_title=str(meta.get("chapter_title", "")),
                kp_refs=list(meta.get("kp_refs", []) or []),
                bloom_focus=list(meta.get("bloom_focus", []) or []),
                total_points=int(meta.get("total_points", 0) or 0),
                deadline_hint=str(meta.get("deadline_hint", "")),
                question_count=q_count,
            )
        )
    return sheets


@lru_cache(maxsize=1)
def _build_extras() -> KnowledgeExtras:
    return KnowledgeExtras(
        code_examples=_load_code_examples(),
        references=_load_references(),
        exercises=_load_exercises(),
    )


def get_knowledge_extras() -> KnowledgeExtras:
    """全局单例。"""
    return _build_extras()


def reset_knowledge_extras() -> None:
    """测试用：清掉 lru_cache 强制重读（新增配套资源后调用）。"""
    _build_extras.cache_clear()
