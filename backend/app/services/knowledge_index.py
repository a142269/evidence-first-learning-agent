"""章节 ↔ 知识点 ↔ 题库 三方索引服务。

读取 knowledge_base/artificial_intelligence/chapters/*.md 的 YAML frontmatter
（由 scripts/build_chapter_frontmatter.py 写入），与 QuestionBank 联动暴露：

* 章节列表 / 元数据
* KP -> 章节
* 章节 -> 题（按 KP 串联）
* 覆盖率诊断

设计原则：
* 只读，进程内单例（lru_cache 缓存）
* 不依赖 chromadb / sklearn 等重型库，纯 stdlib + PyYAML
* 与 chat_pipeline / agents / artifacts 解耦，仅暴露纯函数接口
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.app.services.question_bank import QuestionBank, get_question_bank

logger = logging.getLogger(__name__)

_KB_ROOT = Path(__file__).resolve().parents[3] / "knowledge_base"
_DEFAULT_COURSE = "artificial_intelligence"
_CHAPTERS_DIR = _KB_ROOT / _DEFAULT_COURSE / "chapters"

# Frontmatter uses graph IDs after the 2026-07-03 knowledge-map repair, while
# data/question_bank.json still uses stable bank IDs. Keep the two namespaces
# separate so graph/path features and practice-question retrieval both work.
# 2026-07-16 平台化改造：这两张表仅作为 AI 课程的内置映射；其他课程可在
# knowledge_base/<slug>/course.yaml 里用 graph_to_bank_kp_ids /
# chapter_to_bank_kp_ids 提供各自的映射（缺省为空 = 直接用图谱 ID 查题库）。
_GRAPH_TO_BANK_KP_IDS: dict[str, list[str]] = {
    "AI_004": ["ml_basics"],
    "AI_005": ["supervised_learning"],
    "AI_005_02": ["decision_trees"],
    "AI_005_03": ["svm"],
    "AI_006": ["neural_networks", "mlp"],
    "AI_006_01": ["cnn"],
    "AI_006_02": ["rnn", "lstm"],
    "AI_006_03": ["transformer", "attention_mechanism"],
    "AI_007": ["nlp_basics"],
    "AI_009": ["reinforcement_learning"],
    "AI_011": ["rag"],
    "AI_012": ["multi_agent_systems"],
    "AI_013": ["ai_agent"],
    "AI_014": ["mcp_protocol"],
    "AI_015": ["multimodal_llm"],
    "AI_016": ["unsupervised_learning"],
    "MATH_001": ["linear_algebra"],
    "MATH_002": ["probability_statistics"],
    "CODE_001": ["python_basics"],
    "CODE_002": ["data_structures"],
}

_CHAPTER_TO_BANK_KP_IDS: dict[str, list[str]] = {
    "00": ["ml_basics"],
    "01": ["ml_basics"],
    "02": ["linear_algebra", "probability_statistics"],
    "03": ["neural_networks", "mlp"],
    "04": ["cnn"],
    "05": ["transformer", "attention_mechanism"],
    "06": ["multi_agent_systems"],
    "07": ["reinforcement_learning"],
    "08": ["multimodal_llm"],
    "09": ["rag"],
    "10": ["ai_agent"],
    "11": ["mcp_protocol"],
    "12": ["ai_project_practice"],
    "13": ["supervised_learning", "ml_basics"],
    "14": ["unsupervised_learning"],
    "15": ["decision_trees", "supervised_learning"],
    "16": ["svm", "supervised_learning"],
    "17": ["backpropagation"],
    "18": ["rnn", "lstm"],
    "19": ["nlp_basics"],
}

class KnowledgeIndexError(RuntimeError):
    """章节加载或索引失败时抛出。"""


@dataclass
class Chapter:
    """单个章节的元数据 + 正文。"""

    chapter_id: str
    slug: str
    title: str
    kp_ids: list[str]
    bloom_focus: list[str]
    prerequisites: list[str]
    estimated_minutes: int
    path: Path
    body: str = field(repr=False)
    question_kp_ids: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return self.path.name

    def to_summary(self) -> dict[str, Any]:
        """供 demo / API 序列化的轻量结构，不含正文。"""
        return {
            "chapter_id": self.chapter_id,
            "slug": self.slug,
            "title": self.title,
            "kp_ids": list(self.kp_ids),
            "question_kp_ids": list(self.question_kp_ids),
            "bloom_focus": list(self.bloom_focus),
            "prerequisites": list(self.prerequisites),
            "estimated_minutes": self.estimated_minutes,
            "filename": self.filename,
        }


_FRONTMATTER_DELIM = "---"


def _split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith(_FRONTMATTER_DELIM + "\n"):
        return None, text
    end = text.find("\n" + _FRONTMATTER_DELIM + "\n", len(_FRONTMATTER_DELIM) + 1)
    if end == -1:
        return None, text
    yaml_block = text[len(_FRONTMATTER_DELIM) + 1 : end]
    body = text[end + len("\n" + _FRONTMATTER_DELIM + "\n") :]
    try:
        meta = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        error_msg = f"frontmatter YAML 解析失败: {exc}"
        raise KnowledgeIndexError(error_msg) from exc
    return meta, body


class KnowledgeIndex:
    """章节 + KP + 题库的三方只读索引。"""

    def __init__(
        self,
        chapters_dir: Path | None = None,
        question_bank: QuestionBank | None = None,
        course: str = _DEFAULT_COURSE,
    ) -> None:
        self.course = str(course or _DEFAULT_COURSE).strip().lower()
        self.chapters_dir = chapters_dir or (_KB_ROOT / self.course / "chapters")
        self.bank = question_bank if question_bank is not None else get_question_bank()
        self._graph_to_bank, self._chapter_to_bank = self._load_kp_mappings()
        self._chapters: list[Chapter] = []
        self._by_id: dict[str, Chapter] = {}
        self._by_kp: dict[str, list[Chapter]] = defaultdict(list)
        self._by_question_kp: dict[str, list[Chapter]] = defaultdict(list)
        self._load()

    def _load(self) -> None:
        if not self.chapters_dir.exists():
            error_msg = f"章节目录不存在: {self.chapters_dir}"
            raise KnowledgeIndexError(error_msg)

        md_files = sorted(self.chapters_dir.glob("*.md"))
        for path in md_files:
            text = path.read_text(encoding="utf-8")
            meta, body = _split_frontmatter(text)
            if meta is None:
                logger.warning(f"[KnowledgeIndex] {path.name} 无 frontmatter，跳过")
                continue
            try:
                chapter = Chapter(
                    chapter_id=str(meta["chapter_id"]),
                    slug=str(meta["slug"]),
                    title=str(meta["title"]),
                    kp_ids=list(meta.get("kp_ids", []) or []),
                    bloom_focus=list(meta.get("bloom_focus", []) or []),
                    prerequisites=[str(p) for p in (meta.get("prerequisites", []) or [])],
                    estimated_minutes=int(meta.get("estimated_minutes", 30)),
                    path=path,
                    body=body,
                )
            except (KeyError, ValueError, TypeError) as exc:
                error_msg = f"{path.name} frontmatter 字段缺失或非法: {exc}"
                raise KnowledgeIndexError(error_msg) from exc

            if chapter.chapter_id in self._by_id:
                error_msg = f"chapter_id 重复: {chapter.chapter_id} ({path.name})"
                raise KnowledgeIndexError(error_msg)

            self._chapters.append(chapter)
            self._by_id[chapter.chapter_id] = chapter
            chapter.question_kp_ids = self._question_kp_ids_for(chapter)
            for kp in chapter.kp_ids:
                self._by_kp[kp].append(chapter)
            for kp in chapter.question_kp_ids:
                self._by_question_kp[kp].append(chapter)

        if not self._chapters:
            error_msg = f"没有章节被加载: {self.chapters_dir}"
            raise KnowledgeIndexError(error_msg)

        logger.info(
            f"[KnowledgeIndex] loaded {len(self._chapters)} chapters, "
            f"covering {len(self._by_kp)} KPs"
        )

    def _load_kp_mappings(self) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """课程级 KP 映射：AI 课用内置表，其余课程读 course.yaml（可缺省）。"""
        if self.course == _DEFAULT_COURSE:
            return dict(_GRAPH_TO_BANK_KP_IDS), dict(_CHAPTER_TO_BANK_KP_IDS)
        manifest_path = _KB_ROOT / self.course / "course.yaml"
        if not manifest_path.is_file():
            return {}, {}
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {}, {}

        def _as_mapping(value: Any) -> dict[str, list[str]]:
            if not isinstance(value, dict):
                return {}
            return {
                str(k): [str(x) for x in (v if isinstance(v, list) else [v])]
                for k, v in value.items()
            }

        return (
            _as_mapping(manifest.get("graph_to_bank_kp_ids")),
            _as_mapping(manifest.get("chapter_to_bank_kp_ids")),
        )

    def _question_kp_ids_for(self, chapter: Chapter) -> list[str]:
        """Return question-bank KP IDs for a chapter, derived from graph IDs."""
        mapped = self._chapter_to_bank.get(chapter.chapter_id)
        if mapped is None:
            mapped = []
            for kp in chapter.kp_ids:
                mapped.extend(self._graph_to_bank.get(kp, [kp]))

        seen: set[str] = set()
        deduped: list[str] = []
        for kp in mapped:
            if kp and kp not in seen:
                seen.add(kp)
                deduped.append(kp)
        return deduped

    # ============================================================
    # 查询接口
    # ============================================================
    @property
    def total(self) -> int:
        return len(self._chapters)

    @property
    def chapters(self) -> list[Chapter]:
        return list(self._chapters)

    @property
    def chapter_ids(self) -> list[str]:
        return [c.chapter_id for c in self._chapters]

    @property
    def kp_ids_covered(self) -> list[str]:
        return sorted(self._by_kp.keys())

    def get(self, chapter_id: str) -> Chapter | None:
        return self._by_id.get(str(chapter_id))

    def by_kp(self, kp_id: str) -> list[Chapter]:
        graph_matches = list(self._by_kp.get(kp_id, []))
        if graph_matches:
            return graph_matches
        return list(self._by_question_kp.get(kp_id, []))

    def practice_for(
        self,
        chapter_id: str,
        n: int = 5,
        bloom: str | None = None,
        seed: int | None = None,
    ) -> list[dict[str, Any]]:
        """根据章节的 kp_ids 从题库抽题；命中 0 KP 的章节走 broad fallback。"""
        chapter = self.get(chapter_id)
        if chapter is None:
            return []

        questions: list[dict[str, Any]] = []
        if chapter.question_kp_ids:
            for kp in chapter.question_kp_ids:
                questions.extend(self.bank.filter(kp_id=kp, bloom=bloom))

        if not questions:
            # 章节题库 KP 暂缺时，用 bloom_focus 兜底，保证演示仍能出题。
            for b in chapter.bloom_focus:
                questions.extend(self.bank.filter(bloom=b))

        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for q in questions:
            if q["id"] not in seen:
                seen.add(q["id"])
                deduped.append(q)

        if seed is not None:
            import random
            random.Random(seed).shuffle(deduped)

        return deduped[:n]

    def practice_for_kp(
        self,
        kp_id: str,
        n: int = 5,
        bloom: str | None = None,
        seed: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return real question-bank items mapped from a graph knowledge point."""
        question_kp_ids = self._graph_to_bank.get(str(kp_id), [str(kp_id)])
        questions: list[dict[str, Any]] = []
        for question_kp_id in question_kp_ids:
            questions.extend(self.bank.filter(kp_id=question_kp_id, bloom=bloom))

        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for question in questions:
            question_id = str(question.get("id") or "")
            if question_id and question_id not in seen:
                seen.add(question_id)
                deduped.append(question)

        if seed is not None:
            import random

            random.Random(seed).shuffle(deduped)
        return deduped[:n]

    def prerequisites_chain(self, chapter_id: str) -> list[Chapter]:
        """递归展开章节的全部先修，按拓扑顺序返回。"""
        seen: set[str] = set()
        order: list[Chapter] = []

        def visit(cid: str) -> None:
            chapter = self.get(cid)
            if chapter is None or cid in seen:
                return
            seen.add(cid)
            for pre in chapter.prerequisites:
                visit(pre)
            if cid != chapter_id:  # 不把自身放进来
                order.append(chapter)

        visit(chapter_id)
        return order

    # ============================================================
    # 覆盖率与诊断
    # ============================================================
    def coverage_report(self) -> dict[str, Any]:
        bank_kps = set(self.bank.kp_ids)
        kp_coverage = {kp: len(self._by_question_kp.get(kp, [])) for kp in bank_kps}
        orphan_kps = sorted(kp for kp, n in kp_coverage.items() if n == 0)
        missing_bank_question_kps = sorted(
            {
                kp
                for chapter in self._chapters
                for kp in chapter.question_kp_ids
                if kp not in bank_kps
            }
        )
        orphan_chapters = sorted(
            c.chapter_id
            for c in self._chapters
            if not c.question_kp_ids
            or all(kp not in bank_kps for kp in c.question_kp_ids)
        )
        return {
            "total_chapters": self.total,
            "total_kps_in_bank": len(bank_kps),
            "kps_with_chapter": len([n for n in kp_coverage.values() if n > 0]),
            "kp_coverage": kp_coverage,
            "orphan_kps": orphan_kps,
            "orphan_chapters": orphan_chapters,
            "missing_bank_question_kps": missing_bank_question_kps,
            "chapter_question_kps": {
                c.chapter_id: list(c.question_kp_ids) for c in self._chapters
            },
        }


@lru_cache(maxsize=8)
def get_knowledge_index(course: str = _DEFAULT_COURSE) -> KnowledgeIndex:
    """进程内按课程缓存的索引实例（无参调用保持旧行为 = AI 课）。"""
    return KnowledgeIndex(course=course)


def reset_knowledge_index() -> None:
    """测试钩子：清空 lru_cache。"""
    get_knowledge_index.cache_clear()
