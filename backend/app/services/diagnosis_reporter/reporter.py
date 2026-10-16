"""High-level orchestrator that turns A's services + B's algorithms into
both a Markdown and a JSON learning diagnosis report.

All optional B-owned integrations (BKT forecaster, active-learning
uncertainty sampler, Bloom 6×3 classifier) are wrapped in try/except so
that the reporter degrades to friendly fallbacks instead of crashing when
B services are not wired up.
"""
# ruff: noqa: RUF001
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.cognitive_diagnosis.bkt_forecaster import (
    BKTForecaster,
    ForecastPoint,
)
from backend.app.services.knowledge_index import KnowledgeIndex, get_knowledge_index
from backend.app.services.question_bank import QuestionBank, get_question_bank
from backend.app.services.realdina_service import RealDINAService, get_realdina_service

from ._helpers import (
    archetype_from_nickname,
    bounded,
    dict_at,
    keyword_score,
    label_score,
    mean,
    slugify,
    stable_seed,
)
from ._json_payload import build_json_payload
from ._markdown import render_markdown
from ._models import (
    BloomBundle,
    BloomCell,
    DiagnosisReport,
    ForecastBundle,
    IntegrationStatus,
    MasteryRow,
    RecommendationBundle,
    ReportQuestion,
    ReportWriteResult,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SEED_PATH = _PROJECT_ROOT / "data" / "seed.json"
_SEED_EXTENDED_PATH = _PROJECT_ROOT / "data" / "seed_extended.json"
_DEFAULT_REPORT_DIR = _PROJECT_ROOT / "reports" / "diagnosis"
_DEFAULT_FORECAST_HORIZON = 30

_FORMAT_MARKDOWN = "md"
_FORMAT_JSON = "json"
_VALID_FORMATS: frozenset[str] = frozenset({_FORMAT_MARKDOWN, _FORMAT_JSON})


class DiagnosisReporter:
    """Build and persist judge-facing learning diagnosis reports."""

    def __init__(
        self,
        realdina_service: RealDINAService | None = None,
        question_bank: QuestionBank | None = None,
        knowledge_index: KnowledgeIndex | None = None,
        bkt_model: Any | None = None,
        seed_path: Path = _SEED_PATH,
        seed_extended_path: Path = _SEED_EXTENDED_PATH,
    ) -> None:
        self.realdina = realdina_service or get_realdina_service()
        self.question_bank = question_bank or get_question_bank()
        self.knowledge_index = knowledge_index or self._safe_knowledge_index()
        self.bkt_model = bkt_model if bkt_model is not None else self._safe_bkt_model()
        self.seed_path = seed_path
        self.seed_extended_path = seed_extended_path
        self.seed = self._read_json(seed_path)
        self.seed_extended = self._read_json(seed_extended_path)
        self.students = self._load_students()
        self.kp_meta = self._load_kp_meta()
        self.relations = list(self.seed_extended.get("knowledge_relations", []))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build_report(
        self,
        user_id: str,
        generated_at: datetime | None = None,
        focus_kp_id: str | None = None,
    ) -> DiagnosisReport:
        timestamp = generated_at or datetime.now(timezone.utc)
        student = self.students.get(user_id, self._fallback_student(user_id))
        profile = self._profile_for(student)
        nickname = str(student.get("nickname", user_id))
        archetype = self._archetype_for(student, nickname, profile)
        profile_scores = self._profile_scores(profile)
        mastery_rows = self._mastery_rows(user_id)
        strengths = sorted(mastery_rows, key=lambda row: row.combined, reverse=True)[:3]
        weaknesses = sorted(mastery_rows, key=lambda row: row.combined)[:3]

        focus = focus_kp_id or (weaknesses[0].kp_id if weaknesses else "aggregate")
        focus_mastery = self._combined_mastery_for(mastery_rows, focus)
        forecast_bundle = self._build_forecast(focus, focus_mastery)
        recommendations = self._build_recommendations(user_id, mastery_rows, weaknesses)
        bloom_bundle = self._build_bloom(recommendations.questions)

        learning_path_entries = self._learning_path_entries(weaknesses)
        learning_path_lines = self._learning_path_lines(learning_path_entries, weaknesses)
        mistake_payload, mistake_lines = self._mistake_section(profile, weaknesses)
        profile_summary_text = self._profile_summary_text(profile, archetype, mastery_rows)

        markdown = render_markdown(
            user_id=user_id,
            nickname=nickname,
            archetype=archetype,
            generated_at_label=timestamp.strftime("%Y-%m-%d %H:%M:%S %Z").strip(),
            profile=profile,
            profile_scores=profile_scores,
            mastery_rows=mastery_rows,
            strengths=strengths,
            weaknesses=weaknesses,
            forecast=forecast_bundle,
            recommendations=recommendations,
            bloom=bloom_bundle,
            learning_path_lines=learning_path_lines,
            mistake_lines=mistake_lines,
        )

        integrations = {
            "forecast": forecast_bundle.status,
            "recommendations": recommendations.status,
            "bloom_6x3": bloom_bundle.status,
        }

        json_payload = build_json_payload(
            user_id=user_id,
            nickname=nickname,
            archetype=archetype,
            generated_at_iso=timestamp.isoformat(),
            focus_kp_id=focus,
            profile_summary_text=profile_summary_text,
            profile_scores=profile_scores,
            mastery_rows=mastery_rows,
            strengths=strengths,
            weaknesses=weaknesses,
            learning_path_entries=learning_path_entries,
            mistake_payload=mistake_payload,
            forecast=forecast_bundle,
            recommendations=recommendations,
            bloom=bloom_bundle,
            integrations=integrations,
        )

        return DiagnosisReport(
            user_id=user_id,
            nickname=nickname,
            archetype=archetype,
            generated_at=timestamp,
            focus_kp_id=focus,
            markdown=markdown,
            json_payload=json_payload,
            profile_scores=profile_scores,
            mastery_rows=mastery_rows,
            strengths=strengths,
            weaknesses=weaknesses,
            forecast=forecast_bundle,
            recommendations=recommendations,
            bloom=bloom_bundle,
            integrations=integrations,
        )

    def write_report(
        self,
        user_id: str,
        output_dir: Path = _DEFAULT_REPORT_DIR,
        generated_at: datetime | None = None,
        focus_kp_id: str | None = None,
        formats: tuple[str, ...] = (_FORMAT_MARKDOWN, _FORMAT_JSON),
        export_pdf: bool = False,
    ) -> ReportWriteResult:
        """Persist the report under `{output_dir}/{slug}_{YYYYMMDD}.{ext}`."""
        normalized_formats = self._normalize_formats(formats)
        report = self.build_report(
            user_id=user_id,
            generated_at=generated_at,
            focus_kp_id=focus_kp_id,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{slugify(user_id)}_{report.generated_at.strftime('%Y%m%d')}"

        markdown_path: Path | None = None
        json_path: Path | None = None
        if _FORMAT_MARKDOWN in normalized_formats:
            markdown_path = output_dir / f"{stem}.md"
            markdown_path.write_text(report.markdown, encoding="utf-8")
        if _FORMAT_JSON in normalized_formats:
            json_path = output_dir / f"{stem}.json"
            json_path.write_text(
                json.dumps(report.json_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        pdf_path = (
            self._export_pdf(markdown_path)
            if export_pdf and markdown_path is not None
            else None
        )
        return ReportWriteResult(
            markdown_path=markdown_path,
            json_path=json_path,
            pdf_path=pdf_path,
            report=report,
        )

    # ------------------------------------------------------------------
    # Mastery + profile
    # ------------------------------------------------------------------
    def _mastery_rows(self, user_id: str) -> list[MasteryRow]:
        realdina_snapshot = self.realdina.snapshot_for(user_id)
        kp_ids = sorted(set(self.kp_meta) | set(realdina_snapshot))
        bkt_masteries = self._bkt_masteries(user_id)
        rows: list[MasteryRow] = []
        for kp_id in kp_ids:
            meta = self.kp_meta.get(kp_id, {})
            realdina_value = float(
                realdina_snapshot.get(kp_id, self.realdina.mastery(user_id, kp_id))
            )
            bkt_value = bkt_masteries.get(kp_id)
            combined = (
                (realdina_value + bkt_value) / 2.0
                if bkt_value is not None
                else realdina_value
            )
            rows.append(
                MasteryRow(
                    kp_id=kp_id,
                    name=str(meta.get("name", kp_id)),
                    course=str(meta.get("course", "AI 课程")),
                    bloom=str(meta.get("bloom", "Understand")),
                    difficulty=int(meta.get("difficulty", 3)),
                    realdina=bounded(realdina_value),
                    bkt=bounded(bkt_value) if bkt_value is not None else None,
                    combined=bounded(combined),
                )
            )
        return sorted(rows, key=lambda row: (row.course, row.difficulty, row.kp_id))

    def _profile_scores(self, profile: dict[str, Any]) -> list[tuple[str, float]]:
        knowledge = dict_at(profile, "knowledge_base")
        time_management = dict_at(profile, "time_management")
        preference = dict_at(profile, "learning_preference")
        efficacy = dict_at(profile, "self_efficacy")
        interaction = dict_at(profile, "interaction_pattern")
        style = dict_at(profile, "cognitive_style")

        weekly_hours = float(time_management.get("weekly_hours", 12) or 12)
        depth_text = str(preference.get("depth", "理解优先"))
        mode_text = str(preference.get("mode", "混合学习"))
        primary_style = str(style.get("primary", "综合型"))
        return [
            ("基础扎实度", bounded(float(knowledge.get("score", 0.5) or 0.5))),
            ("时间投入", bounded(weekly_hours / 35.0)),
            ("学习稳定性", label_score(str(time_management.get("consistency", "中")))),
            (
                "实践倾向",
                keyword_score(mode_text + primary_style, ["项目", "动手", "实践", "Kaggle"]),
            ),
            ("理论深度", keyword_score(depth_text, ["原理", "理论", "前沿", "深层"])),
            ("自我效能", bounded(float(efficacy.get("confidence", 0.5) or 0.5))),
            ("坚持度", label_score(str(efficacy.get("persistence", "中")))),
            (
                "交互主动性",
                keyword_score(
                    str(interaction.get("style", "")),
                    ["提问", "合作", "协商", "实战"],
                ),
            ),
        ]

    def _profile_summary_text(
        self,
        profile: dict[str, Any],
        archetype: str,
        mastery_rows: list[MasteryRow],
    ) -> str:
        goal = dict_at(profile, "learning_goal")
        preference = dict_at(profile, "learning_preference")
        style = dict_at(profile, "cognitive_style")
        target = str(goal.get("target", "个性化学习目标"))
        mode = str(preference.get("mode", "混合学习"))
        primary_style = str(style.get("primary", "综合型"))
        mean_mastery = mean([row.combined for row in mastery_rows])
        return (
            f"学习者画像：{archetype}；目标：{target}；偏好：{mode}；"
            f"主认知风格：{primary_style}；20 KP 综合掌握度均值：{mean_mastery:.0%}。"
        )

    def _combined_mastery_for(self, mastery_rows: list[MasteryRow], kp_id: str) -> float:
        for row in mastery_rows:
            if row.kp_id == kp_id:
                return row.combined
        return mean([row.combined for row in mastery_rows]) if mastery_rows else 0.5

    # ------------------------------------------------------------------
    # Forecast (B-owned BKTForecaster)
    # ------------------------------------------------------------------
    def _build_forecast(self, focus_kp_id: str, focus_mastery: float) -> ForecastBundle:
        focus_name = self._kp_name(focus_kp_id)
        try:
            forecaster = BKTForecaster()
            points = forecaster.forecast(focus_mastery, horizon_days=_DEFAULT_FORECAST_HORIZON)
            milestones = forecaster.find_milestones(points)
            return ForecastBundle(
                focus_kp_id=focus_kp_id,
                focus_kp_name=focus_name,
                horizon_days=_DEFAULT_FORECAST_HORIZON,
                points=points,
                milestones=milestones,
                status=IntegrationStatus(
                    available=True,
                    source="cognitive_diagnosis.bkt_forecaster.BKTForecaster",
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DiagnosisReporter] BKTForecaster unavailable: %s", exc)
            return ForecastBundle(
                focus_kp_id=focus_kp_id,
                focus_kp_name=focus_name,
                horizon_days=_DEFAULT_FORECAST_HORIZON,
                points=[],
                milestones=[],
                status=IntegrationStatus(
                    available=False,
                    source="bkt_forecaster_fallback",
                    fallback_reason=f"BKT forecaster crashed: {exc}",
                ),
            )

    # ------------------------------------------------------------------
    # Recommendations (B-owned UncertaintySampler + fallback)
    # ------------------------------------------------------------------
    def _build_recommendations(
        self,
        user_id: str,
        mastery_rows: list[MasteryRow],
        weaknesses: list[MasteryRow],
    ) -> RecommendationBundle:
        questions, status = self._try_uncertainty_sampler(user_id, mastery_rows)
        if questions:
            return RecommendationBundle(questions=questions[:5], status=status)
        return self._weakness_biased_recommendations(user_id, weaknesses)

    def _try_uncertainty_sampler(
        self, user_id: str, mastery_rows: list[MasteryRow]
    ) -> tuple[list[ReportQuestion], IntegrationStatus]:
        try:
            from backend.app.services.active_learning.uncertainty_sampler import (
                UncertaintySampler,
            )

            sampler = UncertaintySampler(bank=self.question_bank)
            mastery_map = {row.kp_id: row.combined for row in mastery_rows}
            param_map = {row.kp_id: {"slip": 0.1, "guess": 0.2} for row in mastery_rows}
            picks = sampler.recommend(
                user_id=user_id,
                mastery_map=mastery_map,
                param_map=param_map,
                top_k=5,
                strategy="entropy",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DiagnosisReporter] UncertaintySampler unavailable: %s", exc)
            return [], IntegrationStatus(
                available=False,
                source="active_learning_fallback",
                fallback_reason=f"UncertaintySampler crashed: {exc}",
            )

        questions: list[ReportQuestion] = []
        for entry in picks:
            question = entry.get("question") or entry
            if not isinstance(question, dict):
                continue
            questions.append(
                ReportQuestion(
                    question_id=str(question.get("id", "")),
                    kp_id=str(question.get("kp_id", "")),
                    kp_name=str(
                        question.get("kp_name", self._kp_name(str(question.get("kp_id", ""))))
                    ),
                    bloom=str(question.get("bloom", "")),
                    difficulty=int(question.get("difficulty", 3)),
                    stem=str(question.get("stem", "")),
                    selection_score=float(entry.get("score", 0.0)),
                    selection_reason=str(entry.get("reason", "uncertainty")),
                )
            )
        status = IntegrationStatus(
            available=True,
            source="active_learning.uncertainty_sampler.UncertaintySampler",
        )
        return questions, status

    def _weakness_biased_recommendations(
        self, user_id: str, weaknesses: list[MasteryRow]
    ) -> RecommendationBundle:
        seed = stable_seed(user_id)
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, row in enumerate(weaknesses):
            for question in self.question_bank.sample(2, kp_id=row.kp_id, seed=seed + index):
                qid = str(question.get("id", ""))
                if qid and qid not in seen:
                    selected.append(question)
                    seen.add(qid)
                if len(selected) >= 5:
                    break
            if len(selected) >= 5:
                break
        if len(selected) < 5:
            for question in self.question_bank.sample(10, seed=seed + 99):
                qid = str(question.get("id", ""))
                if qid and qid not in seen:
                    selected.append(question)
                    seen.add(qid)
                if len(selected) >= 5:
                    break

        questions = [
            ReportQuestion(
                question_id=str(question.get("id", "")),
                kp_id=str(question.get("kp_id", "")),
                kp_name=str(
                    question.get("kp_name", self._kp_name(str(question.get("kp_id", ""))))
                ),
                bloom=str(question.get("bloom", "")),
                difficulty=int(question.get("difficulty", 3)),
                stem=str(question.get("stem", "")),
                selection_score=None,
                selection_reason="weakness_biased_sample",
            )
            for question in selected[:5]
        ]
        return RecommendationBundle(
            questions=questions,
            status=IntegrationStatus(
                available=False,
                source="question_bank.sample",
                fallback_reason="UncertaintySampler unavailable",
            ),
        )

    # ------------------------------------------------------------------
    # Bloom 6×3 (B-owned bloom_6x3 + fallback)
    # ------------------------------------------------------------------
    def _build_bloom(self, questions: list[ReportQuestion]) -> BloomBundle:
        try:
            from backend.app.services.cognitive_diagnosis.bloom_6x3 import (
                get_bloom6x3_config,
            )

            config = get_bloom6x3_config()
            data = config.load()
            cognitive_dims = data.get("cognitive_dimensions", {})
            knowledge_dims = data.get("knowledge_dimensions", {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DiagnosisReporter] Bloom6x3 config unavailable: %s", exc)
            return self._bloom_fallback(questions, str(exc))

        cells: dict[tuple[str, str], dict[str, Any]] = {}
        cognitive_totals: dict[str, int] = {}
        for question in questions:
            classification = config.classify_text(question.stem)
            level = str(classification.get("level", "understand"))
            sub_level = str(classification.get("sub_level", ""))
            knowledge_dim = str(classification.get("knowledge_dim", "conceptual"))
            key = (level, knowledge_dim)
            cell = cells.setdefault(
                key,
                {
                    "cognitive": level,
                    "cognitive_label": str(cognitive_dims.get(level, {}).get("label", level)),
                    "knowledge_dim": knowledge_dim,
                    "knowledge_label": str(
                        knowledge_dims.get(knowledge_dim, {}).get("label", knowledge_dim)
                    ),
                    "count": 0,
                    "sub_levels": [],
                },
            )
            cell["count"] = int(cell["count"]) + 1
            if sub_level and sub_level not in cell["sub_levels"]:
                cell["sub_levels"].append(sub_level)
            cognitive_totals[level] = cognitive_totals.get(level, 0) + 1

        return BloomBundle(
            cells=[
                BloomCell(
                    cognitive=str(cell["cognitive"]),
                    cognitive_label=str(cell["cognitive_label"]),
                    knowledge_dim=str(cell["knowledge_dim"]),
                    knowledge_label=str(cell["knowledge_label"]),
                    count=int(cell["count"]),
                    sub_levels=list(cell["sub_levels"]),
                )
                for cell in cells.values()
            ],
            cognitive_totals=cognitive_totals,
            status=IntegrationStatus(
                available=True,
                source="cognitive_diagnosis.bloom_6x3.Bloom6x3Config",
            ),
        )

    def _bloom_fallback(
        self, questions: list[ReportQuestion], reason: str
    ) -> BloomBundle:
        cells: dict[str, dict[str, Any]] = {}
        cognitive_totals: dict[str, int] = {}
        for question in questions:
            level = (question.bloom or "Understand").lower()
            key = level
            cell = cells.setdefault(
                key,
                {
                    "cognitive": level,
                    "cognitive_label": question.bloom or "Understand",
                    "knowledge_dim": "conceptual",
                    "knowledge_label": "概念性",
                    "count": 0,
                    "sub_levels": [],
                },
            )
            cell["count"] = int(cell["count"]) + 1
            cognitive_totals[level] = cognitive_totals.get(level, 0) + 1
        return BloomBundle(
            cells=[
                BloomCell(
                    cognitive=str(cell["cognitive"]),
                    cognitive_label=str(cell["cognitive_label"]),
                    knowledge_dim=str(cell["knowledge_dim"]),
                    knowledge_label=str(cell["knowledge_label"]),
                    count=int(cell["count"]),
                    sub_levels=list(cell["sub_levels"]),
                )
                for cell in cells.values()
            ],
            cognitive_totals=cognitive_totals,
            status=IntegrationStatus(
                available=False,
                source="bloom_6x3_fallback",
                fallback_reason=f"Bloom6x3 unavailable: {reason}",
            ),
        )

    # ------------------------------------------------------------------
    # Learning path + mistakes
    # ------------------------------------------------------------------
    def _learning_path_entries(
        self, weaknesses: list[MasteryRow]
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for row in weaknesses:
            chapters = self.knowledge_index.by_kp(row.kp_id) if self.knowledge_index else []
            chapter = chapters[0] if chapters else None
            neighbors = self._relation_neighbors(row.kp_id)
            entry: dict[str, Any] = {
                "kp_id": row.kp_id,
                "kp_name": row.name,
                "current_mastery": round(row.combined, 4),
                "neighbors": neighbors[:3],
            }
            if chapter is not None and self.knowledge_index is not None:
                prereq = self.knowledge_index.prerequisites_chain(chapter.chapter_id)
                entry.update(
                    {
                        "chapter_id": chapter.chapter_id,
                        "chapter_title": chapter.title,
                        "estimated_minutes": chapter.estimated_minutes,
                        "prerequisites": [item.title for item in prereq][:3],
                    }
                )
            else:
                entry.update(
                    {
                        "chapter_id": None,
                        "chapter_title": None,
                        "estimated_minutes": 0,
                        "prerequisites": [],
                    }
                )
            entries.append(entry)
        return entries

    def _learning_path_lines(
        self,
        entries: list[dict[str, Any]],
        weaknesses: list[MasteryRow],
    ) -> list[str]:
        if not entries:
            return ["- 暂无可用掌握度数据，建议先完成一次入门测评。"]
        lines: list[str] = []
        for entry in entries:
            if not entry.get("chapter_title"):
                lines.append(
                    f"- **{entry['kp_name']}**：先做 2 道基础题，再根据错因补看对应章节。"
                )
                continue
            prereq_text = " → ".join(entry.get("prerequisites", [])) or "无需额外先修"
            neighbor_text = "、".join(entry.get("neighbors", [])) or "暂无相邻 KP"
            lines.append(
                f"- **{entry['kp_name']}**：先修 `{prereq_text}`；"
                f"精读《{entry['chapter_title']}》"
                f"（约 {entry['estimated_minutes']} 分钟）；随后拓展 {neighbor_text}。"
            )
        if len(lines) < len(weaknesses):
            lines.append("- 其它弱项暂无对应章节索引。")
        return lines

    def _mistake_section(
        self,
        profile: dict[str, Any],
        weaknesses: list[MasteryRow],
    ) -> tuple[dict[str, Any], list[str]]:
        weak_points = dict_at(profile, "weak_points")
        topics = [str(item) for item in weak_points.get("topics", [])]
        patterns = [str(item) for item in weak_points.get("patterns", [])]
        target_kps = [row.kp_id for row in weaknesses]
        payload = {
            "available": False,
            "source": "profile.weak_points",
            "summary": "尚未读取持久化错题明细，使用画像弱项 + 掌握度低点做风险预估。",
            "topics": topics,
            "patterns": patterns,
            "target_kps": target_kps,
        }
        lines = [
            "- 当前没有读取到持久化错题明细，报告使用画像弱项 + 掌握度低点做风险预估。"
        ]
        if topics:
            lines.append(f"- 画像弱项主题：{'、'.join(topics)}。")
        if patterns:
            lines.append(f"- 常见错误模式：{'、'.join(patterns)}。")
        if weaknesses:
            names = "、".join(row.name for row in weaknesses)
            lines.append(f"- 建议优先复盘：{names}，每个 KP 至少完成 2 道变式题。")
        return payload, lines

    # ------------------------------------------------------------------
    # Helpers / data loading
    # ------------------------------------------------------------------
    def _relation_neighbors(self, kp_id: str) -> list[str]:
        neighbors: list[tuple[float, str]] = []
        for relation in self.relations:
            source = str(relation.get("source", ""))
            target = str(relation.get("target", ""))
            weight = float(relation.get("weight", 0.5) or 0.5)
            if source == kp_id:
                neighbors.append((weight, self._kp_name(target)))
            elif target == kp_id:
                neighbors.append((weight * 0.9, self._kp_name(source)))
        neighbors.sort(key=lambda item: item[0], reverse=True)
        return [name for _, name in neighbors]

    def _kp_name(self, kp_id: str) -> str:
        meta = self.kp_meta.get(kp_id, {})
        return str(meta.get("name", kp_id))

    def _bkt_masteries(self, user_id: str) -> dict[str, float]:
        if self.bkt_model is None or not hasattr(self.bkt_model, "get_all_masteries"):
            return {}
        try:
            raw = self.bkt_model.get_all_masteries(user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DiagnosisReporter] BKT state unavailable: %s", exc)
            return {}
        return {str(kp): bounded(float(value)) for kp, value in dict(raw).items()}

    def _load_students(self) -> dict[str, dict[str, Any]]:
        students: dict[str, dict[str, Any]] = {}
        for student in self.seed.get("students", []):
            if isinstance(student, dict) and student.get("user_id"):
                students[str(student["user_id"])] = student
        for student in self.seed_extended.get("extra_students", []):
            if isinstance(student, dict) and student.get("user_id"):
                students[str(student["user_id"])] = student
        return students

    def _load_kp_meta(self) -> dict[str, dict[str, Any]]:
        meta: dict[str, dict[str, Any]] = {}
        for item in self.seed_extended.get("knowledge_points", []):
            if isinstance(item, dict) and item.get("id"):
                meta[str(item["id"])] = item
        return meta

    def _profile_for(self, student: dict[str, Any]) -> dict[str, Any]:
        profile = student.get("profile", {})
        return profile if isinstance(profile, dict) else {}

    def _archetype_for(
        self,
        student: dict[str, Any],
        nickname: str,
        profile: dict[str, Any],
    ) -> str:
        explicit = student.get("archetype")
        if explicit:
            return str(explicit)
        parsed = archetype_from_nickname(nickname)
        if parsed:
            return parsed
        style = dict_at(profile, "cognitive_style")
        primary = style.get("primary")
        if primary:
            return str(primary)
        return "未分类学习者"

    def _fallback_student(self, user_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "nickname": f"{user_id}（临时画像）",
            "profile": {
                "knowledge_base": {"score": 0.5, "level": "未知"},
                "learning_goal": {"target": "补全诊断数据"},
                "learning_preference": {"mode": "混合学习", "depth": "理解优先"},
                "cognitive_style": {"primary": "综合型"},
                "weak_points": {"topics": [], "patterns": []},
                "time_management": {"weekly_hours": 12, "consistency": "中"},
                "self_efficacy": {"confidence": 0.5, "persistence": "中"},
                "interaction_pattern": {"style": "提问型"},
            },
        }

    def _safe_knowledge_index(self) -> KnowledgeIndex | None:
        try:
            return get_knowledge_index()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DiagnosisReporter] KnowledgeIndex unavailable: %s", exc)
            return None

    def _safe_bkt_model(self) -> Any | None:
        try:
            from backend.app.services.cognitive_diagnosis.bkt import get_bkt

            return get_bkt()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DiagnosisReporter] BKT unavailable: %s", exc)
            return None

    def _export_pdf(self, markdown_path: Path) -> Path | None:
        tool = shutil.which("markdown-pdf")
        if tool is None:
            logger.info("[DiagnosisReporter] markdown-pdf not found; skipped PDF export")
            return None
        pdf_path = markdown_path.with_suffix(".pdf")
        try:
            subprocess.run(
                [tool, str(markdown_path), "-o", str(pdf_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("[DiagnosisReporter] PDF export failed: %s", exc)
            return None
        return pdf_path if pdf_path.exists() else None

    @staticmethod
    def _normalize_formats(formats: tuple[str, ...]) -> frozenset[str]:
        if not formats:
            raise ValueError("at least one output format must be requested")
        invalid = set(formats) - _VALID_FORMATS
        if invalid:
            raise ValueError(f"unsupported output formats: {sorted(invalid)}")
        return frozenset(formats)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[DiagnosisReporter] failed to read %s: %s", path, exc)
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def parse_format_arg(value: str) -> tuple[str, ...]:
        """Map CLI `--format md|json|both` to the internal tuple."""
        normalized = value.strip().lower()
        if normalized in {"both", "all"}:
            return (_FORMAT_MARKDOWN, _FORMAT_JSON)
        if normalized in {_FORMAT_MARKDOWN, "markdown"}:
            return (_FORMAT_MARKDOWN,)
        if normalized in {_FORMAT_JSON}:
            return (_FORMAT_JSON,)
        raise ValueError(f"invalid format: {value}")


__all__ = [
    "BloomBundle",
    "BloomCell",
    "DiagnosisReport",
    "DiagnosisReporter",
    "ForecastBundle",
    "ForecastPoint",
    "IntegrationStatus",
    "MasteryRow",
    "RecommendationBundle",
    "ReportQuestion",
    "ReportWriteResult",
]
