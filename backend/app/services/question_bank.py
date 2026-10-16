"""题库服务：加载 data/question_bank*.json 并提供按 KP / Bloom / 难度的检索接口。

合并加载规则
============
* ``question_bank.json``  — 主库（240 题 / 24 KP），必有
* ``question_bank_extra_*.json`` — 增量（如 0703 高质量选择题）
* ``question_bank_fill_*.json``     — 填空题增量
* ``question_bank_programming_*.json`` — 编程题增量

设计上把这些增量平铺进同一倒排索引，统一检索；去重以 ``id`` 为主键，遇到重复以先
加载者为准（主库最先；其他增量按文件名排序）。``quiz_bank.json`` 仍是另一套
schema（kp_id 用 ``kp_xxx`` 形式），**不参与合并**，避免破坏既有接口契约。

设计目标：
* O(1) 按 ID 查
* O(log N) 按 KP / Bloom / 难度 / 类型过滤（构建一次倒排索引）
* 与 chat_pipeline / quiz_generator agent 解耦：只暴露纯函数式接口
"""
from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
# 主库必须存在并最先加载；其余 glob 按文件名排序后接入（0703 增量会排在主库之后）。
_BANK_PATTERN = "question_bank*.json"
# 旧 schema 题库，不参与合并（保留 legacy 调用方）
_IGNORED_FILES = {"question_bank_legacy.json"}
_EXCLUDE_FILES = {"quiz_bank.json"}


class QuestionBankError(RuntimeError):
    """题库加载或检索失败时抛出。"""


def _discover_bank_files(data_dir: Path | None = None) -> list[Path]:
    """返回 sorted(glob(question_bank*.json))，去掉 legacy / quiz_bank.json。

    主库 ``question_bank.json`` 排第一位，其余按字典序；同名增量（如
    ``question_bank_extra_0703.json``）按文件名字符串自然排序。
    """
    base = data_dir or _DATA_DIR
    candidates = sorted(base.glob(_BANK_PATTERN))
    primary = base / "question_bank.json"
    rest = [
        p
        for p in candidates
        if p.name not in _EXCLUDE_FILES and p.name not in _IGNORED_FILES and p.name != "question_bank.json"
    ]
    ordered: list[Path] = []
    if primary.exists():
        ordered.append(primary)
    ordered.extend(rest)
    return ordered


def _infer_course(filename: str, kp_id: str) -> str:
    """存量题库无 course 字段，按文件名/KP 命名空间推断课程归属。"""
    name = filename.lower()
    if "python" in name or kp_id.startswith("PY_"):
        return "python_programming"
    return "artificial_intelligence"


class QuestionBank:
    """只读题库内存索引（合并多文件）。"""

    def __init__(
        self,
        bank_path: Path | None = None,
        bank_paths: list[Path] | None = None,
    ) -> None:
        self._explicit = bank_path is not None or bank_paths is not None
        if bank_path is not None:
            self.paths = [bank_path]
        elif bank_paths is not None:
            self.paths = list(bank_paths)
        else:
            self.paths = _discover_bank_files()

        if not self.paths:
            raise QuestionBankError("题库目录为空：data/question_bank*.json 都不存在")

        self._questions: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._by_kp: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._by_bloom: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._by_difficulty: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self._by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._by_course: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._meta: dict[str, Any] = {}
        self._sources: list[dict[str, Any]] = []  # [{path, count, types}]
        self._load()

    def _load(self) -> None:
        for path in self.paths:
            if not path.exists():
                raise QuestionBankError(f"题库文件不存在: {path}")
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                msg = f"题库 JSON 解析失败 ({path.name}): {exc}"
                raise QuestionBankError(msg) from exc

            # 兼容两种格式：(a) {"_meta":..., "questions":[...]}
            # (b) 顶层就是 list（0703 增量就是这种）
            if isinstance(payload, list):
                questions = payload
                payload_meta: dict[str, Any] = {}
            else:
                if not isinstance(payload, dict):
                    raise QuestionBankError(f"{path.name} 顶层必须是 dict 或 list")
                questions = list(payload.get("questions", []))
                payload_meta = payload.get("_meta", {}) or {}

            questions = list(questions) if not isinstance(questions, list) else questions
            source_types: dict[str, int] = defaultdict(int)
            replaced = 0
            for q in questions:
                qid = q.get("id")
                if not qid:
                    raise QuestionBankError(f"{path.name} 题目缺少 id: {q}")
                qtype = q.get("type", "multiple_choice")
                if qid in self._by_id:
                    # 去重（主库最先），跳过重复（保留双计 source_types 以反映快照完整度）
                    logger.debug("[QuestionBank] dup id %s from %s, skipped", qid, path.name)
                    source_types[qtype] += 1
                    replaced += 1
                    continue
                # 课程域标注（2026-07-16 平台化改造）：题目显式 course 字段
                # > 文件级 _meta.course > 文件名/KP 前缀约定 > 默认 AI 课
                q.setdefault(
                    "course",
                    str(payload_meta.get("course") or "")
                    or _infer_course(path.name, str(q.get("kp_id") or "")),
                )
                self._by_course[q["course"]].append(q)
                self._by_id[qid] = q
                self._questions.append(q)
                if "kp_id" in q:
                    self._by_kp[q["kp_id"]].append(q)
                if "bloom" in q:
                    self._by_bloom[q["bloom"]].append(q)
                self._by_difficulty[int(q.get("difficulty", 3))].append(q)
                self._by_type[qtype].append(q)
                source_types[qtype] += 1

            self._sources.append({
                "path": path.name,
                "count": len(questions),
                "newly_added": len(questions) - replaced,
                "duplicates_skipped": replaced,
                "types": dict(source_types),
            })

            # meta 取主库的，其余仅以合并 meta 形式记录 sources
            if payload_meta and not self._meta:
                self._meta = payload_meta
        if not self._questions:
            raise QuestionBankError("题库合并后为空")

        # 在合并 meta 上补一份 sources 信息，方便诊断
        self._meta["sources"] = self._sources
        self._meta["merged_total"] = len(self._questions)

        logger.info(
            f"[QuestionBank] merged {len(self._sources)} files: "
            f"{len(self._questions)} questions, {len(self._by_kp)} KPs, "
            f"{len(self._by_bloom)} Bloom levels, types={set(self._by_type.keys())}"
        )

    # ============================================================
    # 查询接口
    # ============================================================
    @property
    def meta(self) -> dict[str, Any]:
        return dict(self._meta)

    @property
    def total(self) -> int:
        return len(self._questions)

    @property
    def kp_ids(self) -> list[str]:
        return sorted(self._by_kp.keys())

    def get(self, question_id: str) -> dict[str, Any] | None:
        return self._by_id.get(question_id)

    def by_kp(self, kp_id: str) -> list[dict[str, Any]]:
        return list(self._by_kp.get(kp_id, []))

    def by_bloom(self, bloom: str) -> list[dict[str, Any]]:
        return list(self._by_bloom.get(bloom, []))

    def by_difficulty(self, level: int) -> list[dict[str, Any]]:
        return list(self._by_difficulty.get(level, []))

    def by_type(self, question_type: str) -> list[dict[str, Any]]:
        """按题型倒排索引查询。"""
        return list(self._by_type.get(question_type, []))

    def allowed_types(self) -> list[str]:
        """已加载的题型集合，按字母序。"""
        return sorted(self._by_type.keys())

    def sources(self) -> list[dict[str, Any]]:
        """每个源文件的题目数 + 类型分布 — 用于 demo / 文档展示。"""
        return [dict(src) for src in self._sources]

    def by_course(self, course: str) -> list[dict[str, Any]]:
        """按课程域倒排索引查询。"""
        return list(self._by_course.get(str(course).lower(), []))

    def courses(self) -> list[str]:
        """已加载题目覆盖的课程集合。"""
        return sorted(self._by_course.keys())

    def filter(
        self,
        kp_id: str | None = None,
        bloom: str | None = None,
        difficulty: int | None = None,
        question_type: str | None = None,
        course: str | None = None,
    ) -> list[dict[str, Any]]:
        """组合过滤，返回所有命中题。"""
        candidates: list[dict[str, Any]] = list(self._questions)
        if course:
            course = str(course).lower()
            candidates = [q for q in candidates if q.get("course") == course]
        if kp_id:
            candidates = [q for q in candidates if q["kp_id"] == kp_id]
        if bloom:
            candidates = [q for q in candidates if q["bloom"] == bloom]
        if difficulty is not None:
            candidates = [q for q in candidates if q.get("difficulty") == difficulty]
        if question_type:
            candidates = [q for q in candidates if q.get("type") == question_type]
        return candidates

    def sample(
        self,
        n: int,
        kp_id: str | None = None,
        bloom: str | None = None,
        difficulty: int | None = None,
        seed: int | None = None,
    ) -> list[dict[str, Any]]:
        """从过滤结果中随机抽 n 道。seed 为 None 时不可复现。"""
        pool = self.filter(kp_id=kp_id, bloom=bloom, difficulty=difficulty)
        if not pool:
            return []
        rng = random.Random(seed)
        return rng.sample(pool, k=min(n, len(pool)))

    def coverage_summary(self) -> dict[str, Any]:
        """每个 KP / Bloom 的题量统计，供 demo / 文档展示。"""
        return {
            "total": self.total,
            "by_kp": {kp: len(qs) for kp, qs in self._by_kp.items()},
            "by_bloom": {b: len(qs) for b, qs in self._by_bloom.items()},
            "by_difficulty": {d: len(qs) for d, qs in self._by_difficulty.items()},
            "by_type": {
                t: sum(1 for q in self._questions if q.get("type") == t)
                for t in {q.get("type", "multiple_choice") for q in self._questions}
            },
        }


@lru_cache(maxsize=1)
def get_question_bank() -> QuestionBank:
    """全局单例，进程内复用。"""
    return QuestionBank()


def reset_question_bank() -> None:
    """测试用：清空 lru_cache 让下次 get_question_bank() 重新加载。"""
    get_question_bank.cache_clear()
