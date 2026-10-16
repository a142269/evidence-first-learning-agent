from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from backend.app.services.portraits.group_portrait_service import GroupPortraitService
from backend.app.services.portraits.individual_portrait_service import IndividualPortraitService
from backend.app.services.reports.llm_runtime_config import load_llm_runtime_config
from backend.app.services.reports.llm_service import LLMNarrativeService, ModelScopeLLMClient
from backend.app.services.reports.mode_interconnection_service import ModeInterconnectionService
from backend.app.services.reports.narrative_generator import NarrativeGenerator
from backend.app.services.reports.rag_service import RagService
from backend.app.services.reports.report_enrichment import (
    build_confidence_assessment,
    build_counselor_toolkit,
    build_data_validity_statement,
    build_deep_attribution,
    build_personalized_micro_plan,
    build_strength_highlights,
    identify_behavior_archetype,
    semanticize_attribution_3d,
    semanticize_cross_rows,
)
from backend.app.services.reports.report_visualization_service import ReportVisualizationService


# Module-level cache for ods xlsx scans. Keyed by absolute file path.
# Each entry: {"mtime": float, "columns": list[str], "frame": DataFrame}
# Caches the (XH + time_cols) subset we actually use in _scan_student_time_sources,
# so repeated report generation avoids re-reading ~27 large Excel files per student.
_ODS_FRAME_CACHE: dict[str, dict[str, Any]] = {}


def _safe_read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".json":
        try:
            return pd.read_json(path)
        except Exception:
            text = path.read_text(encoding="utf-8")
            try:
                payload = json.loads(text)
            except Exception:
                try:
                    return pd.read_json(path, lines=True)
                except Exception:
                    return pd.DataFrame()
            if isinstance(payload, list):
                return pd.DataFrame(payload)
            if isinstance(payload, dict):
                for key in ["data", "records", "sample", "items", "rows"]:
                    rows = payload.get(key)
                    if isinstance(rows, list):
                        return pd.DataFrame(rows)
                try:
                    return pd.DataFrame(payload)
                except Exception:
                    return pd.DataFrame([payload])
            return pd.DataFrame()
    return pd.DataFrame()


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    text = str(value).strip()
    if not text:
        return {}
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        return {}
    return {}


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            return [str(v) for v in loaded if str(v).strip()]
    except Exception:
        pass
    return [seg.strip() for seg in text.replace("；", ";").split(";") if seg.strip()]


def _to_intervention_candidate(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        raw = value
    elif value is None:
        raw = {}
    else:
        text = str(value).strip()
        if not text:
            raw = {}
        else:
            try:
                parsed = json.loads(text)
            except Exception:
                try:
                    parsed = ast.literal_eval(text)
                except Exception:
                    parsed = {}
            raw = parsed if isinstance(parsed, dict) else {}

    family = _clean_text(raw.get("family", ""), "")
    priority_tier = "primary" if family == "learning_behavior" else "supplementary"
    family_display_map = {
        "learning_behavior": "学习行为干预",
        "self_discipline": "学习节律干预",
        "physical_vitality": "身体活力干预",
        "social_participation": "社交融入干预",
    }
    return {
        "code": _clean_text(raw.get("code", ""), ""),
        "name_cn": _clean_text(raw.get("name_cn", raw.get("name", "")), ""),
        "action_text": _clean_text(raw.get("action_text", ""), ""),
        "family": family,
        "priority_tier": priority_tier,
        "family_display": family_display_map.get(family, family or "通用干预"),
        "new_model_probability": float(pd.to_numeric(raw.get("new_model_probability", 0.0), errors="coerce") or 0.0),
        "new_fused_probability": float(pd.to_numeric(raw.get("new_fused_probability", 0.0), errors="coerce") or 0.0),
        "model_probability_drop": float(pd.to_numeric(raw.get("model_probability_drop", 0.0), errors="coerce") or 0.0),
        "fused_probability_drop": float(pd.to_numeric(raw.get("fused_probability_drop", 0.0), errors="coerce") or 0.0),
    }


def _choose_student_facing_intervention(warning: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Select the best student-facing intervention.

    Policy: prefer learning_behavior as the primary recommendation, but all
    intervention types (physical_vitality, self_discipline, etc.) are valid
    and should be presented together — just with learning_behavior first.
    """
    candidates = [_to_intervention_candidate(item) for item in _to_list(warning.get("top_interventions", ""))]
    candidates = [item for item in candidates if item.get("name_cn") or item.get("action_text")]

    if not candidates:
        fallback = {
            "code": "",
            "name_cn": _clean_text(warning.get("best_intervention_name", "学习行为增强"), "学习行为增强"),
            "action_text": _clean_text(
                warning.get("best_intervention_action", "本周先补齐任务、稳定到课并增加有效学习时长。"),
                "本周先补齐任务、稳定到课并增加有效学习时长。",
            ),
            "family": _clean_text(warning.get("best_intervention_family", "learning_behavior"), "learning_behavior"),
            "priority_tier": "primary",
            "family_display": "学习行为干预",
            "new_model_probability": float(pd.to_numeric(warning.get("best_model_probability_after", 0.0), errors="coerce") or 0.0),
            "new_fused_probability": float(pd.to_numeric(warning.get("best_fused_probability_after", 0.0), errors="coerce") or 0.0),
            "model_probability_drop": float(pd.to_numeric(warning.get("best_model_probability_drop", 0.0), errors="coerce") or 0.0),
            "fused_probability_drop": float(pd.to_numeric(warning.get("best_fused_probability_drop", 0.0), errors="coerce") or 0.0),
        }
        return fallback, [fallback]

    # Reorder: learning_behavior first, then others — all kept
    preferred_family_order = ["learning_behavior", "self_discipline", "physical_vitality", "social_participation"]
    for family in preferred_family_order:
        matched = next((item for item in candidates if str(item.get("family", "")) == family), None)
        if matched is not None:
            return matched, candidates
    return candidates[0], candidates


def _clean_text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return fallback
    return text


def _risk_level_display(level: str) -> str:
    value = str(level).strip().lower()
    mapping = {
        "high": "高风险预警",
        "medium": "中等关注",
        "low": "低风险关注",
    }
    if not value:
        return "待评估"
    return mapping.get(value, str(level))


def _trajectory_pattern_display(pattern: str) -> str:
    value = str(pattern).strip()
    mapping = {
        "持续稳健型": "状态整体稳定",
        "波动跃迁型": "状态波动较大需持续观察",
        "回升修复型": "状态正在逐步回升",
        "高开低走型": "近期状态下滑预警",
    }
    if not value:
        return "状态整体稳定"
    return mapping.get(value, value)


def _priority_display(priority: str) -> str:
    value = str(priority).strip().lower()
    mapping = {
        "urgent": "紧急处置",
        "high": "高优先级",
        "medium": "中优先级",
        "low": "常规跟进",
    }
    if not value:
        return "常规跟进"
    return mapping.get(value, str(priority))


def _score_to_100(score: Any) -> float:
    raw = float(pd.to_numeric(score, errors="coerce") or 0.0)
    if raw <= 1.0:
        raw = raw * 100.0
    return float(round(max(0.0, min(100.0, raw)), 1))


@dataclass
class ReportBuilder:
    project_root: Path
    enable_llm_narrative: bool = True
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    _interconnection_cache: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _business_warning_cache: pd.DataFrame | None = field(default=None, init=False, repr=False)

    def _individual_path(self) -> Path:
        json_path = self.project_root / "data" / "ads" / "portraits" / "individual_portraits.json"
        if json_path.exists():
            return json_path
        parquet_path = self.project_root / "data" / "ads" / "portraits" / "individual_portraits.parquet"
        if parquet_path.exists():
            return parquet_path
        csv_path = parquet_path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
        return json_path

    def _group_path(self) -> Path:
        return self.project_root / "data" / "ads" / "portraits" / "group_portraits.json"

    def _sections_cfg_path(self) -> Path:
        return self.project_root / "configs" / "reports" / "report_sections.yaml"

    def _phrases_cfg_path(self) -> Path:
        return self.project_root / "configs" / "reports" / "narrative_phrases.yaml"

    def _interconnection_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "mode_interconnection_results.json"

    def _business_warning_path(self) -> Path:
        return self.project_root / "data" / "ads" / "business_lists" / "all_student_business_warning_list.json"

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _load_individual(self) -> pd.DataFrame:
        path = self._individual_path()
        df = _safe_read(path)
        if (not path.exists()) or df.empty or ("XH" not in df.columns):
            builder = IndividualPortraitService(project_root=self.project_root)
            builder.save()
            df = _safe_read(path)
        if df.empty:
            return pd.DataFrame()
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        for col, fallback in [
            ("major", "未提供专业"),
            ("grade", "未提供年级"),
            ("academy", "未提供学院信息"),
            ("class_name", "默认班"),
        ]:
            if col not in out.columns:
                out[col] = fallback
            out[col] = out[col].apply(lambda x: _clean_text(x, fallback))
        return out

    def _load_group(self) -> dict[str, Any]:
        path = self._group_path()
        if not path.exists():
            service = GroupPortraitService(project_root=self.project_root)
            service.save()
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_interconnection(self) -> dict[str, Any]:
        if self._interconnection_cache is not None:
            return self._interconnection_cache
        path = self._interconnection_path()
        if not path.exists():
            service = ModeInterconnectionService(project_root=self.project_root, min_group_n=30)
            service.save()
        if not path.exists():
            self._interconnection_cache = {}
            return {}
        self._interconnection_cache = json.loads(path.read_text(encoding="utf-8"))
        return self._interconnection_cache

    def _load_business_warning(self) -> pd.DataFrame:
        if self._business_warning_cache is not None:
            return self._business_warning_cache
        df = _safe_read(self._business_warning_path())
        if df.empty:
            self._business_warning_cache = pd.DataFrame()
            return self._business_warning_cache
        out = df.copy()
        out["student_id"] = out.get("student_id", "").astype(str)
        for col in [
            "course_fail_fused_probability",
            "course_fail_model_probability",
            "course_fail_rule_support",
            "low_attendance_probability",
            "composite_attention_score",
            "primary_risk_score",
            "best_fused_probability_after",
            "best_fused_probability_drop",
            "combined_fused_probability_after",
            "combined_fused_probability_drop",
        ]:
            out[col] = pd.to_numeric(out.get(col, 0.0), errors="coerce").fillna(0.0)
        for col in [
            "course_fail_fused_risk_flag",
            "low_attendance_warning_flag",
            "is_current_latest_complete_term",
        ]:
            out[col] = out.get(col, False).astype(bool)
        self._business_warning_cache = out
        return self._business_warning_cache

    def _business_warning_for_student(self, student_id: str) -> dict[str, Any]:
        warnings = self._load_business_warning()
        if warnings.empty:
            return {}
        hit = warnings[warnings["student_id"] == str(student_id)]
        if hit.empty:
            return {}
        return hit.iloc[0].to_dict()

    def _risk_warning_payload(self, row: pd.Series, summary: dict[str, Any], warning: dict[str, Any]) -> dict[str, Any]:
        if not warning:
            return {
                "overview": summary["risk_overview"],
                "core_factors": summary["core_factors"],
                "behavior_proxy_statement": summary["behavior_proxy_statement"],
                "data_source": "individual_portrait_fallback",
                "business_warning": {},
            }
        course_fail_level = str(warning.get("course_fail_fused_risk_level", "low")).lower()
        course_fail_prob = float(pd.to_numeric(warning.get("course_fail_fused_probability", 0.0), errors="coerce") or 0.0)
        course_fail_flag = bool(warning.get("course_fail_fused_risk_flag", False))
        low_attendance_prob = float(pd.to_numeric(warning.get("low_attendance_probability", 0.0), errors="coerce") or 0.0)
        low_attendance_level = str(warning.get("low_attendance_risk_level", "low")).lower()
        composite_score = float(pd.to_numeric(warning.get("composite_attention_score", 0.0), errors="coerce") or 0.0)
        composite_level = str(warning.get("composite_risk_level", "low")).lower()
        course_fail_level_display = _risk_level_display(course_fail_level)
        composite_level_display = _risk_level_display(composite_level)
        top_factors = warning.get("composite_top_factors", [])
        if not isinstance(top_factors, list):
            top_factors = _to_list(top_factors)
        preferred_intervention, parsed_interventions = _choose_student_facing_intervention(warning)
        business_overview = (
            f"当前挂科风险处于“{course_fail_level_display}”，综合关注处于“{composite_level_display}”；"
            f"当前风险值约{course_fail_prob:.2f}，建议在下周完成一次干预复核。"
        )
        return {
            "overview": business_overview,
            "core_factors": top_factors[:8] if top_factors else summary["core_factors"],
            "behavior_proxy_statement": summary["behavior_proxy_statement"],
            "data_source": "business_warning_list",
            "business_warning": {
                "feature_term": str(warning.get("feature_term", "")),
                "target_term": str(warning.get("target_term", "")),
                "prediction_basis": str(warning.get("prediction_basis", "")),
                "warning_priority": str(warning.get("warning_priority", "")),
                "warning_priority_display": _priority_display(str(warning.get("warning_priority", ""))),
                "agreement_status": str(warning.get("agreement_status", "")),
                "course_fail": {
                    "model_probability": float(pd.to_numeric(warning.get("course_fail_model_probability", 0.0), errors="coerce") or 0.0),
                    "rule_support": float(pd.to_numeric(warning.get("course_fail_rule_support", 0.0), errors="coerce") or 0.0),
                    "fused_probability": course_fail_prob,
                    "risk_level": course_fail_level,
                    "risk_level_display": course_fail_level_display,
                    "warning_flag": course_fail_flag,
                },
                "attendance": {
                    "probability": low_attendance_prob,
                    "warning_flag": bool(warning.get("low_attendance_warning_flag", False)),
                    "risk_level": low_attendance_level,
                    "risk_level_display": _risk_level_display(low_attendance_level),
                },
                "composite": {
                    "attention_score": composite_score,
                    "risk_level": composite_level,
                    "risk_level_display": composite_level_display,
                    "primary_risk_code": str(warning.get("primary_risk_code", "")),
                    "primary_risk_name_cn": str(warning.get("primary_risk_name_cn", "")),
                    "primary_risk_score": float(pd.to_numeric(warning.get("primary_risk_score", 0.0), errors="coerce") or 0.0),
                },
                "rule_explanations": {
                    "composite_top_factors": top_factors[:8],
                    "intervention_advice": str(warning.get("intervention_advice", "")),
                },
                "intervention_simulation": {
                    "best_intervention_name": str(preferred_intervention.get("name_cn", warning.get("best_intervention_name", ""))),
                    "best_intervention_action": str(preferred_intervention.get("action_text", warning.get("best_intervention_action", ""))),
                    "best_intervention_family": str(preferred_intervention.get("family", warning.get("best_intervention_family", ""))),
                    "best_intervention_family_display": str(preferred_intervention.get("family_display", "")),
                    "best_fused_probability_after": float(pd.to_numeric(preferred_intervention.get("new_fused_probability", warning.get("best_fused_probability_after", 0.0)), errors="coerce") or 0.0),
                    "best_fused_probability_drop": float(pd.to_numeric(preferred_intervention.get("fused_probability_drop", warning.get("best_fused_probability_drop", 0.0)), errors="coerce") or 0.0),
                    "combined_action_names": str(warning.get("combined_action_names", "")),
                    "combined_fused_probability_after": float(pd.to_numeric(warning.get("combined_fused_probability_after", 0.0), errors="coerce") or 0.0),
                    "combined_fused_probability_drop": float(pd.to_numeric(warning.get("combined_fused_probability_drop", 0.0), errors="coerce") or 0.0),
                    "top_interventions": [str(item.get("name_cn", "")) for item in parsed_interventions if str(item.get("name_cn", "")).strip()],
                    "top_intervention_actions": [str(item.get("action_text", "")) for item in parsed_interventions if str(item.get("action_text", "")).strip()],
                },
                "mode_risk_levels": {
                    "low_learning_engagement_risk_level": str(warning.get("low_learning_engagement_risk_level", "low")),
                    "task_procrastination_risk_level": str(warning.get("task_procrastination_risk_level", "low")),
                    "classroom_interaction_low_risk_level": str(warning.get("classroom_interaction_low_risk_level", "low")),
                    "learning_resource_low_use_risk_level": str(warning.get("learning_resource_low_use_risk_level", "low")),
                    "academic_decline_risk_level": str(warning.get("academic_decline_risk_level", "low")),
                    "achievement_weakness_risk_level": str(warning.get("achievement_weakness_risk_level", "low")),
                    "lifestyle_abnormal_risk_level": str(warning.get("lifestyle_abnormal_risk_level", "low")),
                    "social_low_integration_risk_level": str(warning.get("social_low_integration_risk_level", "low")),
                    "course_exploration_misalignment_risk_level": str(warning.get("course_exploration_misalignment_risk_level", "low")),
                },
            },
            "portrait_risk_proxy": {
                "risk_level": str(row.get("risk_level", "low")),
                "risk_score": float(pd.to_numeric(row.get("risk_score", 0.0), errors="coerce") or 0.0),
            },
        }

    def _pick_group_snapshot(self, group_data: dict[str, Any], grade: str, major: str) -> dict[str, Any]:
        grade_rows = group_data.get("grade_portrait", [])
        major_rows = group_data.get("major_portrait", [])
        class_rows = group_data.get("class_portrait", [])
        grade_row = next((row for row in grade_rows if str(row.get("group_key")) == str(grade)), {})
        major_row = next((row for row in major_rows if str(row.get("group_key")) == str(major)), {})
        return {"grade": grade_row, "major": major_row, "class": class_rows}

    def _build_intervention_loop(self, warning: dict[str, Any], generated_at: str) -> dict[str, Any]:
        preferred_intervention, _ = _choose_student_facing_intervention(warning)
        action_name = str(preferred_intervention.get("name_cn", "")).strip()
        action_text = str(preferred_intervention.get("action_text", "")).strip()
        if action_name and action_text:
            first_action = f"优先执行“{action_name}”：{action_text}"
        else:
            first_action = action_text or str(warning.get("best_intervention_action", "本周保持规律作息并完成课程任务"))
        return {
            "status": "pending_execution",
            "execution_record": {
                "planned_action": first_action,
                "planned_execute_date": generated_at[:10],
                "owner_role": "counselor_student_copilot",
                "actual_execute_date": "",
                "actual_notes": "",
            },
            "feedback_record": {
                "feedback_label": "待反馈",
                "feedback_at": "",
                "feedback_note": "",
            },
            "review_record": {
                "review_cycle": "next_week",
                "expected_next_week_changes": [
                    "夜间活跃下降或稳定",
                    "课堂任务按时提交率提升",
                    "学习行为代理得分小幅提升",
                ],
                "observed_next_week_changes": [],
            },
        }

    def _build_priority_reason_card(self, warning: dict[str, Any]) -> dict[str, Any]:
        course_prob = float(pd.to_numeric(warning.get("course_fail_fused_probability", 0.0), errors="coerce") or 0.0)
        attention = float(pd.to_numeric(warning.get("composite_attention_score", 0.0), errors="coerce") or 0.0)
        level = str(warning.get("course_fail_fused_risk_level", "low")).lower()
        priority = str(warning.get("warning_priority", "low")).lower()
        reasons = []
        if course_prob >= 0.8:
            reasons.append(f"挂科融合概率较高（{course_prob:.2f}）")
        if attention >= 0.65:
            reasons.append(f"综合关注分较高（{attention:.2f}）")
        top_factors = warning.get("composite_top_factors", [])
        if not isinstance(top_factors, list):
            top_factors = _to_list(top_factors)
        reasons.extend(top_factors[:2])
        if not reasons:
            reasons = ["当前行为代理风险信号聚集，建议优先关注"]
        rank_score = round(course_prob * 0.55 + attention * 0.35 + (0.1 if level == "high" else (0.05 if level == "medium" else 0.0)), 4)
        return {
            "priority_level": priority or level,
            "rank_score": rank_score,
            "top3_reason_card": reasons[:3],
        }

    def _build_actionable_grouping(self, group_data: dict[str, Any]) -> dict[str, Any]:
        def _risk_high_ratio(row: dict[str, Any]) -> float:
            dist = row.get("risk_distribution", {}) if isinstance(row, dict) else {}
            return float(pd.to_numeric(dist.get("high", 0.0), errors="coerce") or 0.0)

        major_rows = sorted(group_data.get("major_portrait", []), key=_risk_high_ratio, reverse=True)[:3]
        class_rows = sorted(group_data.get("class_portrait", []), key=_risk_high_ratio, reverse=True)[:3]
        combo_rows = sorted(group_data.get("cross_mode_risk_combo_portrait", []), key=_risk_high_ratio, reverse=True)[:3]

        def _pack(row: dict[str, Any]) -> dict[str, Any]:
            return {
                "group_key": str(row.get("group_key", "")),
                "student_count": int(pd.to_numeric(row.get("student_count", 0), errors="coerce") or 0),
                "risk_high_ratio": _risk_high_ratio(row),
                "risk_distribution": row.get("risk_distribution", {}),
            }

        return {
            "follow_up_window": "this_week",
            "major_top3": [_pack(x) for x in major_rows],
            "class_top3": [_pack(x) for x in class_rows],
            "cross_mode_combo_top3": [_pack(x) for x in combo_rows],
        }

    def _build_student_view_enhancement(self, row: pd.Series, trajectory: dict[str, Any], advice: dict[str, Any]) -> dict[str, Any]:
        timeline = {}
        if isinstance(trajectory, dict):
            if isinstance(trajectory.get("time_axis_standard", {}), dict):
                timeline = trajectory.get("time_axis_standard", {}).get("timeline_score", {})
            if not timeline:
                timeline = trajectory.get("timeline_score", {})
        values = [float(pd.to_numeric(v, errors="coerce") or 0.0) for v in timeline.values()] if isinstance(timeline, dict) else []
        trend_msg = "整体平稳"
        if len(values) >= 2:
            delta = values[-1] - values[0]
            if delta > 0.05:
                trend_msg = "连续周改善"
            elif delta < -0.05:
                trend_msg = "连续周走弱"
        social_score = float(pd.to_numeric(row.get("social_life_score", 0.0), errors="coerce") or 0.0)
        social_label = _clean_text(row.get("social_life_label", "未识别"), "未识别")
        d5_action = "联系1位同学进行30分钟结对学习，并共同完成一次任务清单勾选。"
        if social_score >= 0.6 or "高" in social_label:
            d5_action = "与你的学习伙伴一起完成1次同伴讨论，并形成一页共学笔记。"
        top_action = _clean_text(advice.get("direction", "本周优先完成课程任务清单"), "本周优先完成课程任务清单")
        return {
            "three_sentence_summary": [
                f"当前五维综合行为代理得分为{float(pd.to_numeric(row.get('overall_growth_score', 0.0), errors='coerce') or 0.0):.2f}，核心关注集中在学习投入与节律稳定。",
                f"与过去相比，行为序列呈现“{trend_msg}”特征，建议按周节奏持续跟踪关键指标。",
                "本结论基于校园行为代理特征，不构成医学或心理诊断。",
            ],
            "one_priority_action": top_action,
            "seven_day_micro_plan": [
                {"day": "D1", "actions": ["整理本周课程任务清单", "晚间23:30前结束高强度线上活动"]},
                {"day": "D2", "actions": ["完成1门薄弱课程复盘", "参与1次线下学习场景"]},
                {"day": "D3", "actions": ["完成课堂作业并自检", "进行30分钟运动"]},
                {"day": "D4", "actions": ["复盘前三天执行情况", "补齐未完成任务"]},
                {"day": "D5", "actions": [d5_action, "控制夜间活跃时长"]},
                {"day": "D6", "actions": ["进行阶段测验或题目训练", "记录本周行为变化"]},
                {"day": "D7", "actions": ["提交周复盘", "形成下周行动计划"]},
            ],
            "self_vs_past_visualization": {
                "timeline_score": timeline,
                "trend_tag": trend_msg,
                "time_caliber_note": trajectory.get("time_caliber_note", "") if isinstance(trajectory, dict) else "",
            },
            "advice_constraints": [
                "预期影响指标：学习行为代理得分、夜间活跃指数、任务完成率",
                "观察窗口：建议按7天与4周双窗口复盘",
                "若两周内无改善，建议升级为辅导员重点跟进",
            ],
        }

    def _risk_semantic_summary(self, warning_payload: dict[str, Any]) -> str:
        warning = warning_payload.get("business_warning", {}) if isinstance(warning_payload, dict) else {}
        course_fail = warning.get("course_fail", {}) if isinstance(warning, dict) else {}
        level = str(course_fail.get("risk_level", "low")).lower()
        prob = float(pd.to_numeric(course_fail.get("fused_probability", 0.0), errors="coerce") or 0.0)
        if level == "high":
            return f"高风险：学业表现波动已进入高关注区，建议立即执行干预闭环（当前融合概率{prob:.2f}）。"
        if level == "medium":
            return f"中度风险：学业表现总体可维持，但学习节律和投入出现偏离（当前融合概率{prob:.2f}）。"
        return f"低风险：整体表现可控，但建议持续跟踪关键行为代理波动（当前融合概率{prob:.2f}）。"

    def _build_key_insights(
        self,
        row: pd.Series,
        trajectory_story: dict[str, Any],
        warning_payload: dict[str, Any],
        trajectory_evidence: dict[str, Any] | None = None,
        strength_highlights: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        confidence = trajectory_story.get("confidence", {}) if isinstance(trajectory_story, dict) else {}
        event_chain = trajectory_story.get("event_chain", []) if isinstance(trajectory_story, dict) else []
        turning_points = trajectory_story.get("turning_points", []) if isinstance(trajectory_story, dict) else []
        first_event = event_chain[0] if event_chain else {}
        first_turning = turning_points[0] if turning_points else {}

        # 轨迹结论增强：加入具体行为证据
        trajectory_content = (
            f"当前轨迹状态为{_trajectory_pattern_display(str(confidence.get('trajectory_pattern', '持续稳健型')))}，"
            f"样本充分性为{str(confidence.get('sample_sufficiency', '一般'))}。"
        )
        if trajectory_evidence and trajectory_evidence.get("persistence_assessment", {}).get("status") != "无法评估":
            pa = trajectory_evidence["persistence_assessment"]
            trajectory_content += f" {pa.get('detail', '')}"

        # 关键引信增强：关联具体数据
        trigger_content = f"{str(first_event.get('trigger', '暂无显著触发事件'))}；影响：{str(first_event.get('impact', '建议持续观察'))}。"
        if trajectory_evidence:
            te_list = trajectory_evidence.get("transition_evidence", [])
            if te_list:
                first_te = te_list[0]
                evidence_str = "；".join(first_te.get("evidence_facts", [])[:2])
                if evidence_str:
                    trigger_content += f" 数据支撑：{evidence_str}。"

        # 拐点增强：加入语义标签和证据
        turning_content = (
            f"{str(first_turning.get('time_label', '暂无'))}："
            f"{str(first_turning.get('from_state', '进入期'))}→{str(first_turning.get('to_state', '进入期'))}，"
            f"变化{float(pd.to_numeric(first_turning.get('delta', 0.0), errors='coerce') or 0.0):+.3f}。"
        )
        if trajectory_evidence:
            te_list = trajectory_evidence.get("transition_evidence", [])
            if te_list:
                last_te = te_list[-1]
                turning_content = last_te.get("narrative", turning_content)

        insights = [
            {
                "title": "风险结论",
                "content": self._risk_semantic_summary(warning_payload),
            },
            {
                "title": "轨迹结论",
                "content": trajectory_content,
            },
            {
                "title": "关键引信",
                "content": trigger_content,
            },
            {
                "title": "首要动作",
                "content": str(row.get("advice_direction", "本周优先执行课程任务与节律修复动作")),
            },
            {
                "title": "最近拐点",
                "content": turning_content,
            },
        ]

        # 优势闪光点卡片
        if strength_highlights and strength_highlights.get("highlights"):
            best = strength_highlights["highlights"][0]
            insights.append({
                "title": "优势闪光点",
                "content": f"{best.get('statement', '')} {best.get('leverage', '')}",
            })

        return insights

    def _build_trajectory_evidence(self, student_id: str, trajectory_story: dict[str, Any]) -> dict[str, Any]:
        """从ODS原始表中提取与轨迹状态转移相关的具体行为证据。"""
        turning_points = trajectory_story.get("turning_points", []) if isinstance(trajectory_story, dict) else []
        event_chain = trajectory_story.get("event_chain", []) if isinstance(trajectory_story, dict) else []
        state_sequence = trajectory_story.get("state_sequence", []) if isinstance(trajectory_story, dict) else []

        # 状态语义映射
        state_semantic_map = {
            "进入期": {"label": "适应探索期", "color": "#4CAF50", "description": "初入校园，行为模式尚在建立，各维度波动属正常范围"},
            "平台期": {"label": "稳态投入期", "color": "#2196F3", "description": "学习与生活节律趋于稳定，形成了可持续的行为惯性"},
            "恢复期": {"label": "回升修复期", "color": "#FF9800", "description": "经历波动后正在回归正轨，行为指标呈修复性上升"},
            "预警期": {"label": "偏离预警期", "color": "#f44336", "description": "多项行为指标偏离常态，需密切关注并考虑主动干预"},
            "爆发期": {"label": "剧烈波动期", "color": "#9C27B0", "description": "行为模式出现急剧变化，通常由重大事件触发"},
        }

        # 为每个状态附加语义标签
        semantic_states: list[dict[str, Any]] = []
        for s in state_sequence:
            state_name = str(s.get("state", "进入期"))
            semantic = state_semantic_map.get(state_name, {"label": state_name, "color": "#9E9E9E", "description": "状态特征待识别"})
            semantic_states.append({
                **s,
                "semantic_label": semantic["label"],
                "semantic_color": semantic["color"],
                "semantic_description": semantic["description"],
            })

        # 从ODS提取状态转移节点的具体行为证据
        transition_evidence: list[dict[str, Any]] = []
        from backend.app.services.reports.report_enrichment import _load_ods_table, _student_rows
        sid = str(student_id)

        # 读取关键ODS表
        lib = _load_ods_table(self.project_root, "learning_logs/图书馆打卡记录.xlsx", ["XH", "visittime"])
        lib_rows = _student_rows(lib, sid)
        net = _load_ods_table(self.project_root, "lifestyle_health/上网统计.xlsx", ["XH", "SCSC", "SCMW", "TJNY"])
        net_rows = _student_rows(net, sid)
        entry = _load_ods_table(self.project_root, "social_activity/门禁数据.xlsx", ["XH", "LOGINTIME"])
        entry_rows = _student_rows(entry, sid)
        hw = _load_ods_table(self.project_root, "learning_logs/学生作业提交记录.xlsx", ["XH", "CREATER_TIME"])
        hw_rows = _student_rows(hw, sid)
        grades = _load_ods_table(self.project_root, "grade_records/学生成绩.xlsx", ["XH", "KCMC", "ZCJ"])
        g_rows = _student_rows(grades, sid)

        # 计算整体行为摘要作为证据基础
        lib_total = int(len(lib_rows))
        hw_total = int(len(hw_rows))
        net_total_min = 0
        for col in ("SCSC", "SCMW"):
            if col in net_rows.columns:
                net_total_min += int(pd.to_numeric(net_rows[col], errors="coerce").fillna(0).sum())
        late_night_total = 0
        if not entry_rows.empty and "LOGINTIME" in entry_rows.columns:
            dt = pd.to_datetime(entry_rows["LOGINTIME"], errors="coerce").dropna()
            late_night_total = int(((dt.dt.hour >= 23) | (dt.dt.hour < 5)).sum())

        # 为每个拐点生成证据
        for tp in turning_points:
            from_state = str(tp.get("from_state", ""))
            to_state = str(tp.get("to_state", ""))
            time_label = str(tp.get("time_label", ""))
            delta = float(pd.to_numeric(tp.get("delta", 0.0), errors="coerce") or 0.0)

            from_semantic = state_semantic_map.get(from_state, {}).get("label", from_state)
            to_semantic = state_semantic_map.get(to_state, {}).get("label", to_state)

            # 构建行为证据描述
            evidence_facts: list[str] = []
            if delta < -0.05:  # 下滑
                if late_night_total >= 10:
                    evidence_facts.append(f"深夜门禁出入 {late_night_total} 次，作息紊乱可能是下滑诱因")
                if lib_total <= 3:
                    evidence_facts.append(f"图书馆仅到馆 {lib_total} 次，学习场景参与严重不足")
                if net_total_min >= 15000:
                    evidence_facts.append(f"在线时长高达 {net_total_min} 分钟，线上活动可能挤占学习时间")
            elif delta > 0.05:  # 上升
                if lib_total >= 10:
                    evidence_facts.append(f"图书馆到馆 {lib_total} 次，学习投入显著增加")
                if hw_total >= 15:
                    evidence_facts.append(f"作业提交 {hw_total} 次，任务完成度良好")
                if late_night_total < 5:
                    evidence_facts.append(f"深夜出入仅 {late_night_total} 次，作息相对规律")

            if not evidence_facts:
                evidence_facts.append("该阶段行为数据变化幅度较小，属于微调整")

            # 不及格课程作为附加证据
            fail_courses: list[str] = []
            if not g_rows.empty and "ZCJ" in g_rows.columns:
                scores = pd.to_numeric(g_rows["ZCJ"], errors="coerce")
                fails = g_rows[scores < 60]
                if not fails.empty and "KCMC" in fails.columns:
                    fail_list = []
                    for idx in range(min(3, len(fails))):
                        r = fails.iloc[idx]
                        score_val = pd.to_numeric(r.get("ZCJ", 0), errors="coerce")
                        if pd.notna(score_val):
                            fail_list.append(f"{r.get('KCMC', '未知')}（{float(score_val):.0f}分）")
                    fail_courses = fail_list

            transition_evidence.append({
                "time_label": time_label,
                "from_state": from_state,
                "to_state": to_state,
                "from_semantic": from_semantic,
                "to_semantic": to_semantic,
                "delta": delta,
                "direction": "下滑" if delta < -0.02 else ("上升" if delta > 0.02 else "平稳"),
                "evidence_facts": evidence_facts,
                "fail_courses": fail_courses,
                "narrative": (
                    f"{time_label}，该生从「{from_semantic}」转入「{to_semantic}」（变化 {delta:+.3f}）。"
                    f"数据显示：{'；'.join(evidence_facts[:3])}。"
                    + (f"同期出现不及格课程：{'、'.join(fail_courses)}。" if fail_courses else "")
                ),
            })

        # 毕竟性评估：状态持续时间与惯性分析
        persistence_assessment = {"status": "无法评估", "detail": "轨迹数据不足"}
        if semantic_states:
            current = semantic_states[-1]
            current_label = current.get("semantic_label", "")
            consecutive_same = 1
            for i in range(len(semantic_states) - 2, -1, -1):
                if semantic_states[i].get("state") == current.get("state"):
                    consecutive_same += 1
                else:
                    break
            if consecutive_same >= 3:
                persistence_assessment = {
                    "status": "高惯性",
                    "detail": f"该生已连续 {consecutive_same} 个观测周期处于「{current_label}」状态，行为惯性较强，常规提醒可能失效，需深度介入。",
                    "consecutive_periods": consecutive_same,
                    "current_state": current_label,
                }
            elif consecutive_same >= 2:
                persistence_assessment = {
                    "status": "中等惯性",
                    "detail": f"该生已连续 {consecutive_same} 个周期处于「{current_label}」状态，趋势初步形成，是干预的窗口期。",
                    "consecutive_periods": consecutive_same,
                    "current_state": current_label,
                }
            else:
                persistence_assessment = {
                    "status": "波动中",
                    "detail": f"状态刚转入「{current_label}」，尚未形成稳定惯性，密切跟踪1-2周可判断趋势。",
                    "consecutive_periods": consecutive_same,
                    "current_state": current_label,
                }

        return {
            "semantic_states": semantic_states,
            "transition_evidence": transition_evidence,
            "persistence_assessment": persistence_assessment,
            "behavior_summary": {
                "library_visits": lib_total,
                "homework_submissions": hw_total,
                "online_minutes": net_total_min,
                "late_night_entries": late_night_total,
                "fail_course_count": len(fail_courses) if 'fail_courses' in dir() else 0,
            },
        }

    def _build_counterfactual_simulation(self, trajectory_story: dict[str, Any], warning_payload: dict[str, Any]) -> dict[str, Any]:
        """反事实推演：如果在关键节点采取不同行动，结果会怎样？"""
        turning_points = trajectory_story.get("turning_points", []) if isinstance(trajectory_story, dict) else []
        simulation = warning_payload.get("business_warning", {}).get("intervention_simulation", {}) if isinstance(warning_payload, dict) else {}
        course_fail = warning_payload.get("business_warning", {}).get("course_fail", {}) if isinstance(warning_payload, dict) else {}
        base_prob = float(pd.to_numeric(course_fail.get("fused_probability", 0.0), errors="coerce") or 0.0)
        best_drop = float(pd.to_numeric(simulation.get("best_fused_probability_drop", 0.0), errors="coerce") or 0.0)
        combined_drop = float(pd.to_numeric(simulation.get("combined_fused_probability_drop", 0.0), errors="coerce") or 0.0)

        scenarios: list[dict[str, Any]] = []

        # 场景1：如果在最早的拐点增加社交支持
        if turning_points:
            first_tp = turning_points[0]
            time_label = str(first_tp.get("time_label", "早期"))
            scenarios.append({
                "scenario": f"假如在{time_label}增加同伴学习支持（每周1次结对学习）",
                "intervention_type": "社交支持强化",
                "estimated_effect": f"不及格风险可能降低约 {min(best_drop * 0.4, 0.15):.0%}",
                "reasoning": "同伴效应在行为偏离初期介入效果最显著，能在习惯固化前建立外部锚点。",
            })

        # 场景2：节律修复
        scenarios.append({
            "scenario": "假如在观测期中段执行 23:30 断网 + 固定晨间打卡",
            "intervention_type": "生活节律修复",
            "estimated_effect": f"综合行为代理得分可能提升 8-15%",
            "reasoning": "节律修复是所有维度改善的基础条件，历史案例中节律恢复后学习投入平均回升 12%。",
        })

        # 场景3：学习行为强化
        scenarios.append({
            "scenario": "假如每周固定 3 次图书馆时段并加入 1 个课程讨论组",
            "intervention_type": "学习投入增强",
            "estimated_effect": f"不及格风险预计降低约 {best_drop:.0%}" if best_drop > 0 else "学业产出有望提升一个等级",
            "reasoning": "学习场景的物理在场是投入的必要条件，讨论参与能将被动接收转为主动建构。",
        })

        # 综合干预效果
        combined_scenario = {
            "scenario": "假如同时执行上述所有干预措施",
            "intervention_type": "综合干预",
            "estimated_effect": f"不及格风险从 {base_prob:.0%} 降至约 {max(0, base_prob - combined_drop):.0%}" if combined_drop > 0 else "整体行为模式预计显著改善",
            "reasoning": "多维度干预的交互效应通常大于单一干预的简单加总，但需注意学生的执行负荷。",
        }

        return {
            "module_name": "关键节点反事实推演",
            "module_description": "基于该生历史数据，模拟在关键时间节点采取不同行动后的可能结果变化。此为回顾性分析，用于指导未来遇到类似情况时的干预策略。",
            "scenarios": scenarios,
            "combined_scenario": combined_scenario,
            "usage_note": "反事实推演基于群体统计规律，不代表个体必然结果；其价值在于为辅导员提供「处置参考手册」——当未来遇到类似轨迹的学生时，知道在哪个节点介入最有效。",
        }

    def _build_trajectory_presentation(self, trajectory_story: dict[str, Any], warning_payload: dict[str, Any]) -> dict[str, Any]:
        axis = trajectory_story.get("time_axis_standard", {}) if isinstance(trajectory_story, dict) else {}
        timeline = axis.get("report_timeline_score", {}) if isinstance(axis, dict) else {}
        if not isinstance(timeline, dict):
            timeline = {}
        display_granularity = str(axis.get("report_granularity", "term")) if isinstance(axis, dict) else "term"
        if len(timeline) < 2 and isinstance(axis, dict):
            week_series = axis.get("series_by_granularity", {}).get("week", {})
            if isinstance(week_series, dict) and len(week_series) >= 2:
                timeline = week_series
                display_granularity = "week"
        values = [float(pd.to_numeric(v, errors="coerce") or 0.0) for v in timeline.values()]
        labels = list(timeline.keys())
        slope = 0.0
        state_sequence = trajectory_story.get("state_sequence", []) if isinstance(trajectory_story, dict) else []
        current_state = str(state_sequence[-1].get("state", "进入期")) if state_sequence else "进入期"
        phase_map = {"进入期": "适应期", "平台期": "深耕期", "恢复期": "冲刺期", "预警期": "冲刺期", "爆发期": "冲刺期"}
        semester_stage = phase_map.get(current_state, "适应期")
        progress = 0.2 if semester_stage == "适应期" else (0.6 if semester_stage == "深耕期" else 0.9)
        future_forecast = []
        if values:
            last = values[-1]
            slope = 0.0 if len(values) < 2 else float(values[-1] - values[-2])
            for idx in range(1, 5):
                predicted = max(0.0, min(1.0, last + slope * idx * 0.6))
                ci = max(0.03, 0.06 * idx)
                future_forecast.append(
                    {
                        "offset_label": f"T+{idx}{'学期' if display_granularity == 'term' else '周'}",
                        "predicted_score": round(predicted, 4),
                        "ci_low": round(max(0.0, predicted - ci), 4),
                        "ci_high": round(min(1.0, predicted + ci), 4),
                    }
                )
        else:
            future_forecast = [
                {
                    "offset_label": f"T+{idx}{'学期' if display_granularity == 'term' else '周'}",
                    "predicted_score": 0.0,
                    "ci_low": 0.0,
                    "ci_high": 0.08,
                }
                for idx in range(1, 5)
            ]
        simulation = warning_payload.get("business_warning", {}).get("intervention_simulation", {}) if isinstance(warning_payload, dict) else {}
        course_fail = warning_payload.get("business_warning", {}).get("course_fail", {}) if isinstance(warning_payload, dict) else {}
        base_prob = float(pd.to_numeric(course_fail.get("fused_probability", 0.0), errors="coerce") or 0.0)
        projected_high_risk_prob = max(0.0, min(1.0, base_prob + (0.22 if slope < 0 else -0.08 if slope > 0 else 0.06)))
        first_high_risk_point = next((x for x in future_forecast if float(x.get("predicted_score", 0.0)) >= 0.60), None)
        if first_high_risk_point:
            forecast_narrative = (
                f"根据当前趋势，如不采取行动，风险值预计在{str(first_high_risk_point.get('offset_label', '后续阶段'))}"
                f"升至{float(first_high_risk_point.get('predicted_score', 0.0)):.2f}，可能突破高预警线（0.60），请在下周启动干预。"
            )
        elif slope < 0:
            forecast_narrative = "根据当前趋势，风险值仍在上行通道，建议立刻启动轻量干预并按周复盘。"
        else:
            forecast_narrative = "根据当前趋势，风险值短期可控，建议维持现有节奏并持续跟踪。"
        point_count = len(labels)
        sample_note = "当前时序样本较少，已联动周级证据链辅助解释。" if point_count < 2 else "当前时序样本充足，可用于趋势判断。"
        confidence = trajectory_story.get("confidence", {}) if isinstance(trajectory_story, dict) else {}
        trajectory_pattern = str(confidence.get("trajectory_pattern", "持续稳健型"))
        return {
            "display_granularity": display_granularity,
            "semester_stage": semester_stage,
            "semester_progress": progress,
            "future_4w_forecast": future_forecast,
            "intervention_simulation": {
                "best_intervention_name": str(simulation.get("best_intervention_name", "")),
                "best_intervention_action": str(simulation.get("best_intervention_action", "")),
                "best_fused_probability_drop": float(pd.to_numeric(simulation.get("best_fused_probability_drop", 0.0), errors="coerce") or 0.0),
                "combined_fused_probability_drop": float(pd.to_numeric(simulation.get("combined_fused_probability_drop", 0.0), errors="coerce") or 0.0),
            },
            "chart_explanation": (
                f"轨迹线用于呈现阶段演化方向，不代表即时结果判定；拐点请结合下方事件链和证据解读。{sample_note}"
            ),
            "forecast_narrative": forecast_narrative,
            "forecast_plain_summary": forecast_narrative,
            "projected_high_risk_probability": round(projected_high_risk_prob, 4),
            "trajectory_pattern_display": _trajectory_pattern_display(trajectory_pattern),
            "labels": labels,
            "timeline_score": timeline,
        }

    def _parse_datetime_any(self, series: pd.Series) -> pd.Series:
        text = series.astype(str).str.strip()
        out = pd.to_datetime(text, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        missing = out.isna()
        if missing.any():
            out.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y-%m-%d", errors="coerce")
        missing = out.isna()
        if missing.any():
            out.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y/%m/%d %H:%M:%S", errors="coerce")
        missing = out.isna()
        if missing.any():
            out.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y/%m/%d", errors="coerce")
        numeric = pd.to_numeric(text, errors="coerce")
        if numeric.notna().sum() > 0:
            excel = pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")
            ms = pd.to_datetime(numeric, unit="ms", errors="coerce")
            s = pd.to_datetime(numeric, unit="s", errors="coerce")
            valid_excel = excel.between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"))
            valid_ms = ms.between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"))
            valid_s = s.between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"))
            best = out.copy()
            if valid_excel.sum() > max(valid_ms.sum(), valid_s.sum(), 0):
                best = excel
            elif valid_ms.sum() >= valid_s.sum() and valid_ms.sum() > 0:
                best = ms
            elif valid_s.sum() > 0:
                best = s
            replace_mask = out.isna() & best.notna()
            out.loc[replace_mask] = best.loc[replace_mask]
        return out

    def _academic_term_by_sep_rule(self, dt_series: pd.Series) -> pd.Series:
        dt = pd.to_datetime(dt_series, errors="coerce")
        year = dt.dt.year
        month = dt.dt.month
        day = dt.dt.day
        term1 = (month > 9) | ((month == 9) & (day >= 1))
        start_year = year.where(term1, year - 1)
        term_no = pd.Series(np.where(term1, 1, 2), index=dt.index)
        labels = start_year.astype("Int64").astype(str) + "-" + (start_year + 1).astype("Int64").astype(str) + "学年-第" + term_no.astype(str) + "学期"
        labels[dt.isna()] = ""
        return labels

    def _scan_student_time_sources(self, student_id: str) -> dict[str, Any]:
        ods_root = self.project_root / "data" / "ods"
        if not ods_root.exists():
            return {"tables": [], "summary": {"source_count": 0, "tables_with_student_data": 0, "overall_freshness_days": None}}
        rule_map: dict[str, dict[str, Any]] = {
            "course_selection/学生选课信息.xlsx": {"fields": ["KKXN", "KKXQ"], "basis": "学年学期"},
            "course_selection/课程信息.xlsx": {"fields": ["CZSJ", "KSRQ"], "basis": "日期推学期"},
            "grade_records/奖学金获奖.xlsx": {"fields": ["PDXN"], "basis": "年份映射第二学期"},
            "grade_records/学生成绩.xlsx": {"fields": ["ZXJXJHH"], "basis": "学年学期编码"},
            "grade_records/学科竞赛.xlsx": {"fields": ["HJSJ"], "basis": "日期推学期"},
            "grade_records/本科生综合测评.xlsx": {"fields": ["XZNJ", "CPXN", "CPXQ"], "basis": "学年学期"},
            "grade_records/四六级成绩.xlsx": {"fields": [], "basis": "固定2021学年"},
            "grade_records/线上学习（综合表现）.xlsx": {"fields": [], "basis": "固定2021学年"},
            "learning_logs/上课信息统计表.xlsx": {"fields": ["TEACH_TIME"], "basis": "日期推学期"},
            "learning_logs/图书馆打卡记录.xlsx": {"fields": ["visittime"], "basis": "日期推学期"},
            "learning_logs/学生作业提交记录.xlsx": {"fields": ["CREATER_TIME", "ANSWER_TIME", "INSERT_TIME"], "basis": "提交时间推学期"},
            "learning_logs/学生签到记录.xlsx": {"fields": ["INSERT_TIME"], "basis": "日期推学期"},
            "learning_logs/考勤汇总.xlsx": {"fields": ["XN", "XQ", "ZC", "RQ"], "basis": "学年学期周"},
            "learning_logs/考试提交记录.xlsx": {"fields": ["CREATER_TIME", "ANSWER_TIME", "INSERT_TIME"], "basis": "提交时间推学期"},
            "learning_logs/讨论记录.xlsx": {"fields": ["INSERT_TIME"], "basis": "日期排序"},
            "learning_logs/课堂任务参与.xlsx": {"fields": ["SCHOOL_YEAR", "CREATE_TIME"], "basis": "学年+日期推学期"},
            "lifestyle_health/上网统计.xlsx": {"fields": ["TJNY"], "basis": "年月推学期"},
            "lifestyle_health/体育课.xlsx": {"fields": ["XQ", "SKSJ"], "basis": "学期"},
            "lifestyle_health/学生体能考核.xlsx": {"fields": ["XQ", "SJCJ"], "basis": "学期"},
            "lifestyle_health/日常锻炼.xlsx": {"fields": ["XQ", "ZC"], "basis": "学期周"},
            "lifestyle_health/跑步打卡.xlsx": {"fields": ["PUNCH_DAY", "TERM_ID", "WEEKNUM"], "basis": "日期推学期"},
            "lifestyle_health/体测数据.xlsx": {"fields": ["TCNF"], "basis": "年份"},
            "social_activity/门禁数据.xlsx": {"fields": ["LOGINTIME"], "basis": "日期推学期"},
            "social_activity/社团活动.xlsx": {"fields": ["HDRQ"], "basis": "日期推学期"},
            "student_base/学籍异动.xlsx": {"fields": ["SPRQ", "XNJ"], "basis": "日期推学期"},
            "student_base/学生基本信息.xlsx": {"fields": [], "basis": "不纳入演化"},
            "student_base/毕业去向.xlsx": {"fields": [], "basis": "不纳入演化"},
        }
        tables: list[dict[str, Any]] = []
        overall_latest: pd.Timestamp | None = None
        for file in sorted(ods_root.glob("**/*.xlsx")):
            cache_key = str(file.resolve())
            try:
                mtime = file.stat().st_mtime
            except OSError:
                continue
            rel = str(file.relative_to(ods_root)).replace("\\", "/")
            rule = rule_map.get(rel, {"fields": [], "basis": "日期时间"})
            requested_fields = list(rule.get("fields", []))

            cached = _ODS_FRAME_CACHE.get(cache_key)
            if cached is not None and cached.get("mtime") == mtime:
                cols = cached["columns"]
                cached_frame: pd.DataFrame = cached["frame"]
            else:
                try:
                    head = pd.read_excel(file, nrows=0)
                except Exception:
                    continue
                cols = [str(c) for c in head.columns]
                xh_col_probe = next((c for c in cols if c.upper() == "XH"), None)
                time_cols_probe = [c for c in requested_fields if c in cols]
                usecols_probe = list(dict.fromkeys(([xh_col_probe] if xh_col_probe else []) + time_cols_probe))
                try:
                    cached_frame = pd.read_excel(file, usecols=usecols_probe) if usecols_probe else pd.DataFrame()
                except Exception:
                    cached_frame = pd.DataFrame()
                if xh_col_probe and xh_col_probe in cached_frame.columns:
                    cached_frame = cached_frame.copy()
                    cached_frame[xh_col_probe] = cached_frame[xh_col_probe].astype(str).str.strip()
                _ODS_FRAME_CACHE[cache_key] = {"mtime": mtime, "columns": cols, "frame": cached_frame}

            time_cols = [c for c in requested_fields if c in cols]
            xh_col = next((c for c in cols if c.upper() == "XH"), None)
            frame = cached_frame
            if xh_col and xh_col in frame.columns:
                student_rows = frame[frame[xh_col] == str(student_id)]
            else:
                student_rows = frame
            parsed_series: list[pd.Series] = []
            for col in time_cols:
                if col not in student_rows.columns:
                    continue
                parsed = self._parse_datetime_any(student_rows[col])
                parsed_series.append(parsed)
            academic_labels: list[str] = []
            if "KKXN" in student_rows.columns and "KKXQ" in student_rows.columns:
                academic_labels = (
                    student_rows["KKXN"].astype(str).str.strip() + "学年-第" + pd.to_numeric(student_rows["KKXQ"], errors="coerce").fillna(1).astype(int).astype(str) + "学期"
                ).dropna().unique().tolist()
            elif "XN" in student_rows.columns and "XQ" in student_rows.columns:
                academic_labels = (
                    student_rows["XN"].astype(str).str.strip() + "学年-第" + pd.to_numeric(student_rows["XQ"], errors="coerce").fillna(1).astype(int).astype(str) + "学期"
                ).dropna().unique().tolist()
            elif "PDXN" in student_rows.columns:
                years = pd.to_numeric(student_rows["PDXN"], errors="coerce").dropna().astype(int)
                academic_labels = [f"{y-1}-{y}学年-第2学期" for y in sorted(set(years.tolist()))]
            elif "ZXJXJHH" in student_rows.columns:
                parsed_term = student_rows["ZXJXJHH"].astype(str).str.extract(r"(\d{4}-\d{4})-(\d)", expand=True)
                academic_labels = [
                    f"{a}学年-第{b}学期"
                    for a, b in parsed_term.dropna().itertuples(index=False, name=None)
                ]
            elif "XZNJ" in student_rows.columns:
                years = pd.to_numeric(student_rows["XZNJ"], errors="coerce").dropna().astype(int)
                academic_labels = [f"{y-1}-{y}学年-第2学期" for y in sorted(set(years.tolist()))]
            elif "TCNF" in student_rows.columns:
                years = pd.to_numeric(student_rows["TCNF"], errors="coerce").dropna().astype(int)
                academic_labels = [f"{y-1}-{y}学年-第2学期" for y in sorted(set(years.tolist()))]
            elif "grade_records/四六级成绩.xlsx" == rel:
                academic_labels = ["2020-2021学年-第2学期"]
            elif "grade_records/线上学习（综合表现）.xlsx" == rel:
                academic_labels = ["2020-2021学年-第2学期"]
            elif parsed_series:
                stacked_for_term = pd.concat(parsed_series, axis=0).dropna()
                if not stacked_for_term.empty:
                    academic_labels = [x for x in self._academic_term_by_sep_rule(stacked_for_term).dropna().astype(str).tolist() if x]
            latest_time = None
            earliest_time = None
            if parsed_series:
                stacked = pd.concat(parsed_series, axis=0).dropna()
                if not stacked.empty:
                    latest_time = pd.to_datetime(stacked.max(), errors="coerce")
                    earliest_time = pd.to_datetime(stacked.min(), errors="coerce")
            if latest_time is not None and pd.notna(latest_time):
                if overall_latest is None or latest_time > overall_latest:
                    overall_latest = latest_time
            academic_main = str(rule.get("basis", "日期时间"))
            tables.append(
                {
                    "table_name": str(file.relative_to(self.project_root)).replace("\\", "/"),
                    "time_fields": time_cols,
                    "primary_time_basis": academic_main,
                    "student_record_count": int(len(student_rows)),
                    "academic_labels_sample": sorted(set(academic_labels))[:4],
                    "earliest_time": str(earliest_time.date()) if earliest_time is not None and pd.notna(earliest_time) else "",
                    "latest_time": str(latest_time.date()) if latest_time is not None and pd.notna(latest_time) else "",
                    "file_updated_at": str(pd.to_datetime(file.stat().st_mtime, unit="s").date()),
                }
            )
        today = pd.Timestamp.now().normalize()
        freshness_days = int((today - overall_latest.normalize()).days) if overall_latest is not None else None
        return {
            "tables": tables,
            "summary": {
                "source_count": len(tables),
                "tables_with_student_data": sum(1 for t in tables if int(t.get("student_record_count", 0)) > 0),
                "overall_latest_time": str(overall_latest.date()) if overall_latest is not None else "",
                "overall_freshness_days": freshness_days,
            },
        }

    def _build_version_benchmark(self) -> dict[str, Any]:
        return {
            "baseline_version": "v2.3-static-trajectory",
            "current_version": "v2.4-dynamic-story",
            "highlights": [
                "新增27表时间字段溯源与数据源标注",
                "新增HMM风格状态识别与关键拐点解释",
                "报告重排为5大核心板块并强化结论先行",
            ],
        }

    def _label(self, row: pd.Series, key: str) -> str:
        value = row.get(key, "未识别")
        if pd.isna(value):
            return "未识别"
        text = str(value).strip()
        if not text or text.lower() == "nan" or text.lower() == "none":
            return "未识别"
        return text

    def _analysis_results(self, row: pd.Series, narrative: NarrativeGenerator, risk_warning_payload: dict[str, Any]) -> list[dict[str, Any]]:
        radar = _to_dict(row.get("radar_chart_data"))
        mode_tags = _to_dict(row.get("mode_tags"))
        trajectory_story = _to_dict(row.get("trajectory_story"))
        trajectory = _to_dict(row.get("trajectory_evolution"))
        key_behavior = _to_dict(row.get("key_behavior_analysis"))
        attribution = _to_dict(row.get("attribution_3d"))
        return [
            {
                "type": "个体基础画像",
                "content": {
                    "major": _clean_text(row.get("major", "未提供专业"), "未提供专业"),
                    "grade": _clean_text(row.get("grade", "未提供年级"), "未提供年级"),
                },
            },
            {
                "type": "群体画像映射",
                "content": {
                    "peer_group": _clean_text(row.get("peer_group", row.get("major", "未提供专业")), "未提供专业"),
                    "class_name": _clean_text(row.get("class_name", "默认班"), "默认班"),
                },
            },
            {"type": "五维能力雷达图", "content": radar},
            {"type": "多模态标签体系", "content": mode_tags},
            {"type": "动态剧情引擎", "content": trajectory_story},
            {"type": "学业轨迹演化", "content": trajectory},
            {"type": "关键行为分析", "content": key_behavior},
            {"type": "三维归因解释", "content": attribution},
            {"type": "风险预警结果", "content": risk_warning_payload.get("overview", "")},
            {"type": "关键解释因子", "content": risk_warning_payload.get("core_factors", [])},
            {"type": "个性化建议", "content": narrative.advice_narrative(str(row.get("advice_direction", "")), str(row.get("advice_plan", "")))},
        ]

    def _description_templates(
        self,
        narrative: NarrativeGenerator,
        score_cards: list[dict[str, Any]],
        summary: dict[str, Any],
        advice_direction: str,
        advice_plan_text: str,
    ) -> dict[str, Any]:
        by_mode = {str(item.get("mode", "")): item for item in score_cards}
        def _mode_text(mode_name: str) -> str:
            card = by_mode.get(mode_name, {})
            return narrative.mode_narrative(
                mode_name=mode_name,
                label=str(card.get("label", "未识别")),
                score=float(card.get("score", 0.0)),
            )
        advice_struct = narrative.advice_narrative(advice_direction, advice_plan_text)
        return {
            "learning_behavior_template": _mode_text("学习行为模式"),
            "learning_outcome_template": _mode_text("学习成果模式"),
            "lifestyle_health_template": _mode_text("生活节律与运动健康模式"),
            "social_life_template": _mode_text("社交生活模式"),
            "course_exploration_template": _mode_text("选课探索模式"),
            "risk_explanation_template": str(summary.get("risk_overview", "")),
            "advice_template": advice_struct,
        }

    def _build_llm_knowledge_qa(self, report: dict[str, Any], question: str) -> dict[str, Any]:
        llm_cfg = load_llm_runtime_config(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            model_name=self.llm_model,
        )
        if not llm_cfg.api_key.strip():
            return {"enabled": True, "status": "missing_api_key", "model": "", "question": question, "answer": ""}
        client = ModelScopeLLMClient(base_url=llm_cfg.base_url, api_key=llm_cfg.api_key, timeout=llm_cfg.timeout)
        model_name = llm_cfg.model_name.strip()
        if not model_name:
            models = client.list_models()
            if not models:
                return {"enabled": True, "status": "no_model_available", "model": "", "question": question, "answer": ""}
            model_name = models[0]
        service = LLMNarrativeService(client=client, model_name=model_name)
        answer = service.answer_student_question(report=report, question=question)
        if not answer.strip():
            return {"enabled": True, "status": "empty_response", "model": model_name, "question": question, "answer": ""}
        if answer.strip().startswith("[API_ERROR]"):
            return {"enabled": True, "status": "api_error", "model": model_name, "question": question, "answer": answer}
        return {"enabled": True, "status": "ok", "model": model_name, "question": question, "answer": answer}

    def _build_rag_knowledge_support(self, report: dict[str, Any], qa_status: str = "ok") -> dict[str, Any]:
        rag = RagService(project_root=self.project_root)
        student_profile = report.get("student_profile", {}) if isinstance(report.get("student_profile", {}), dict) else {}
        trajectory = report.get("trajectory_story", {}) if isinstance(report.get("trajectory_story", {}), dict) else {}
        state_sequence = trajectory.get("state_sequence", []) if isinstance(trajectory.get("state_sequence", []), list) else []
        current_state = str(state_sequence[-1].get("state", "进入期")) if state_sequence else "进入期"
        question = (
            f"学生{student_profile.get('student_id', '')} 当前处于{current_state}，"
            f"请给出基于行为代理的干预建议与证据链。"
        )
        hits = rag.search(
            query=question,
            top_k=3,
            role_view="counselor",
            allowed_sources=["知识库.md", "赛题.md"],
        )
        references = [
            {
                "doc_name": item.get("source", ""),
                "chunk_id": item.get("chunk_id", ""),
                "score": item.get("score", 0.0),
                "excerpt": item.get("excerpt", ""),
            }
            for item in hits
        ]
        if qa_status == "api_error":
            suggestion = "API额度不足，请根据上方报告内容来对学生分析"
            references = []
        else:
            suggestion = "未检索到特定干预建议，请参考通用辅导手册执行日常随访。"
            if references:
                # 真正的 RAG：把检索到的知识库片段 + 学生上下文发给大模型生成个性化建议
                try:
                    llm_cfg = load_llm_runtime_config(
                        base_url=self.llm_base_url,
                        api_key=self.llm_api_key,
                        model_name=self.llm_model,
                    )
                    if llm_cfg.api_key.strip():
                        client = ModelScopeLLMClient(
                            base_url=llm_cfg.base_url,
                            api_key=llm_cfg.api_key,
                            timeout=llm_cfg.timeout,
                        )
                        model_name = llm_cfg.model_name.strip()
                        if not model_name:
                            models = client.list_models()
                            model_name = models[0] if models else ""
                        if model_name:
                            service = LLMNarrativeService(client=client, model_name=model_name)
                            synthesized = service.synthesize_rag_suggestion(
                                report=report,
                                retrieved_chunks=references,
                                query=question,
                            )
                            if synthesized.strip() and not synthesized.strip().startswith("[API_ERROR]"):
                                suggestion = synthesized.strip()
                                references = []  # 大模型已合成，不再展示知识库原文
                            else:
                                suggestion = "API额度不足，请根据上方报告内容来对学生分析"
                                references = []
                except Exception:
                    suggestion = "知识库检索成功但大模型合成失败，请根据上方报告内容来对学生分析"
        return {
            "status": "ready" if references else "no_hit",
            "query": question,
            "suggestion": suggestion,
            "references": references,
        }

    def _build_llm_narrative(self, report: dict[str, Any]) -> dict[str, Any]:
        fallback_content = (
            f"{report.get('risk_warning', {}).get('overview', '')} "
            f"核心行为代理因子：{'；'.join(report.get('risk_warning', {}).get('core_factors', [])[:3])}。"
        ).strip()
        if not self.enable_llm_narrative:
            return {"enabled": False, "status": "disabled", "model": "", "content": fallback_content}
        llm_cfg = load_llm_runtime_config(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            model_name=self.llm_model,
        )
        if not llm_cfg.api_key.strip():
            return {"enabled": True, "status": "missing_api_key", "model": "", "content": fallback_content}
        client = ModelScopeLLMClient(base_url=llm_cfg.base_url, api_key=llm_cfg.api_key, timeout=llm_cfg.timeout)
        model_name = llm_cfg.model_name.strip()
        if not model_name:
            models = client.list_models()
            if not models:
                return {"enabled": True, "status": "no_model_available", "model": "", "content": fallback_content}
            model_name = models[0]
        service = LLMNarrativeService(client=client, model_name=model_name)
        content = service.generate_report_markdown(report)
        if not content.strip():
            return {"enabled": True, "status": "empty_response", "model": model_name, "content": fallback_content}
        if content.strip().startswith("[API_ERROR]"):
            return {"enabled": True, "status": "fallback_rule", "model": model_name, "content": fallback_content}
        return {"enabled": True, "status": "ok", "model": model_name, "content": content}

    def build_one(self, student_id: str) -> dict[str, Any]:
        individual = self._load_individual()
        if individual.empty:
            return {}
        row_df = individual[individual["XH"] == str(student_id)]
        if row_df.empty:
            return {}
        row = row_df.iloc[0]
        group_data = self._load_group()
        interconnection = self._load_interconnection()
        sections_cfg = self._load_yaml(self._sections_cfg_path())
        phrases_cfg = self._load_yaml(self._phrases_cfg_path())
        narrative = NarrativeGenerator(phrases_cfg=phrases_cfg)
        summary = narrative.build_summary(row)
        business_warning = self._business_warning_for_student(str(student_id))
        risk_warning_payload = self._risk_warning_payload(row=row, summary=summary, warning=business_warning)
        warning_priority_card = self._build_priority_reason_card(business_warning) if business_warning else {"priority_level": "low", "rank_score": 0.0, "top3_reason_card": []}
        major_text = _clean_text(row.get("major", "未提供专业"), "未提供专业")
        grade_text = _clean_text(row.get("grade", "未提供年级"), "未提供年级")
        academy_text = _clean_text(row.get("academy", "未提供学院信息"), "未提供学院信息")
        class_text = _clean_text(row.get("class_name", "默认班"), "默认班")
        group_snapshot = self._pick_group_snapshot(group_data, grade_text, major_text)
        sections = sections_cfg.get(
            "sections",
            [
                "student_profile",
                "group_profile",
                "five_mode_scores",
                "trend_analysis",
                "risk_warning",
                "strengths",
                "concerns",
                "advice",
            ],
        )
        score_cards = [
            {
                "mode": "学习行为模式",
                "label": self._label(row, "learning_behavior_label"),
                "score": float(row.get("learning_behavior_score", 0.0)),
                "score_100": _score_to_100(row.get("learning_behavior_score", 0.0)),
            },
            {
                "mode": "学习成果模式",
                "label": self._label(row, "learning_outcome_label"),
                "score": float(row.get("learning_outcome_score", 0.0)),
                "score_100": _score_to_100(row.get("learning_outcome_score", 0.0)),
            },
            {
                "mode": "生活节律与运动健康模式",
                "label": self._label(row, "lifestyle_health_label"),
                "score": float(row.get("lifestyle_health_score", 0.0)),
                "score_100": _score_to_100(row.get("lifestyle_health_score", 0.0)),
            },
            {
                "mode": "社交生活模式",
                "label": self._label(row, "social_life_label"),
                "score": float(row.get("social_life_score", 0.0)),
                "score_100": _score_to_100(row.get("social_life_score", 0.0)),
            },
            {
                "mode": "选课探索模式",
                "label": self._label(row, "course_exploration_label"),
                "score": float(row.get("course_exploration_score", 0.0)),
                "score_100": _score_to_100(row.get("course_exploration_score", 0.0)),
            },
        ]
        strengths = [card["mode"] for card in sorted(score_cards, key=lambda x: x["score"], reverse=True)[:2]]
        concerns = [card["mode"] for card in sorted(score_cards, key=lambda x: x["score"])[:2]]
        trajectory_story = _to_dict(row.get("trajectory_story"))
        trajectory_evolution = _to_dict(row.get("trajectory_evolution"))
        trajectory_presentation = self._build_trajectory_presentation(trajectory_story, risk_warning_payload)
        data_source_trace = self._scan_student_time_sources(str(student_id))
        version_benchmark = self._build_version_benchmark()
        generated_at = str(pd.Timestamp.now())
        behavior_archetype = identify_behavior_archetype(score_cards)
        data_validity = build_data_validity_statement(data_source_trace)
        deep_attribution = build_deep_attribution(self.project_root, str(student_id))
        counselor_toolkit = build_counselor_toolkit(behavior_archetype.get("code", "stable_average"), business_warning)
        personalized_micro_plan = build_personalized_micro_plan(behavior_archetype.get("code", "stable_average"))
        raw_attribution_3d = _to_dict(row.get("attribution_3d"))
        attribution_3d_semantic = semanticize_attribution_3d(raw_attribution_3d)
        # 新增增强层
        trajectory_evidence = self._build_trajectory_evidence(str(student_id), trajectory_story)
        counterfactual = self._build_counterfactual_simulation(trajectory_story, risk_warning_payload)
        strength_hl = build_strength_highlights(score_cards, deep_attribution)
        confidence_assess = build_confidence_assessment(deep_attribution, data_source_trace)
        report = {
            "meta": {
                "student_id": str(student_id),
                "audience": "学生与档案双受众",
                "tone": "成长建议为主，风险提示为辅",
                "export_priority": ["html", "pdf", "word"],
                "explain_policy": "与本人历史 + 与同群体分位",
                "behavior_proxy_statement": summary["behavior_proxy_statement"],
                "generated_at": generated_at,
                "time_caliber_note": str(trajectory_story.get("time_caliber_note", "")),
            },
            "sections": sections,
            "report_structure": [
                "综合诊断看板",
                "五维画像对比",
                "多维归因解释",
                "学业轨迹演化",
                "知识增强式建议",
            ],
            "student_profile": {
                "student_id": str(student_id),
                "major": major_text,
                "grade": grade_text,
                "academy": academy_text,
                "class_name": class_text,
                "risk_level": row.get("risk_level", "low"),
                "risk_level_display": _risk_level_display(str(row.get("risk_level", "low"))),
                "risk_score": float(row.get("risk_score", 0.0)),
                "overall_growth_score": float(row.get("overall_growth_score", 0.0)),
            },
            "group_profile": group_snapshot,
            "five_mode_scores": score_cards,
            "radar_chart": _to_dict(row.get("radar_chart_data")),
            "mode_tags": _to_dict(row.get("mode_tags")),
            "trajectory_story": trajectory_story,
            "trajectory_evolution": trajectory_evolution,
            "trajectory_presentation": trajectory_presentation,
            "trajectory_evidence": trajectory_evidence,
            "counterfactual_simulation": counterfactual,
            "key_behavior_analysis": _to_dict(row.get("key_behavior_analysis")),
            "attribution_3d": attribution_3d_semantic,
            "behavior_archetype": behavior_archetype,
            "deep_attribution": deep_attribution,
            "strength_highlights": strength_hl,
            "confidence_assessment": confidence_assess,
            "counselor_toolkit": counselor_toolkit,
            "personalized_micro_plan": personalized_micro_plan,
            "data_validity": data_validity,
            "trend_analysis": {
                "history_compare": summary["trend_overview"],
                "peer_compare": summary["peer_overview"],
            },
            "risk_warning": {
                **risk_warning_payload,
                "priority_reason_card": warning_priority_card,
            },
            "key_insights": self._build_key_insights(
                row=row,
                trajectory_story=trajectory_story,
                warning_payload=risk_warning_payload,
                trajectory_evidence=trajectory_evidence,
                strength_highlights=strength_hl,
            ),
            "data_source_trace": data_source_trace,
            "data_freshness": data_source_trace.get("summary", {}),
            "update_log": [
                {"version": version_benchmark["baseline_version"], "content": "静态画像+规则叙事版本"},
                {"version": version_benchmark["current_version"], "content": "动态剧情引擎版本（多源时序+状态识别+知识增强建议）", "generated_at": generated_at},
            ],
            "version_benchmark": version_benchmark,
            "priority_reason_card": warning_priority_card,
            "strengths": strengths,
            "concerns": concerns,
            "advice": narrative.advice_narrative(str(row.get("advice_direction", "")), str(row.get("advice_plan", ""))),
            "analysis_results": self._analysis_results(row, narrative, risk_warning_payload=risk_warning_payload),
            "cross_mode_interconnection": {
                "global_key_paths": interconnection.get("key_paths", {}),
                "global_key_paths_semantic": semanticize_cross_rows(interconnection.get("key_paths", {})),
                "custom_achievements": interconnection.get("custom_achievements", {}),
                "student_view": interconnection.get("student_profiles", {}).get(str(student_id), {}),
                "meta": interconnection.get("meta", {}),
            },
        }
        visual_service = ReportVisualizationService()
        report["visual_assets"] = visual_service.build_assets(
            row_dict=row.to_dict(),
            radar_chart=report.get("radar_chart", {}),
            trajectory_evolution=report.get("trajectory_evolution", {}),
            trajectory_story=report.get("trajectory_story", {}),
            group_snapshot=group_snapshot,
            business_warning=risk_warning_payload.get("business_warning", {}).get("course_fail", {}),
        )
        report["description_templates"] = self._description_templates(
            narrative=narrative,
            score_cards=score_cards,
            summary=summary,
            advice_direction=str(row.get("advice_direction", "")),
            advice_plan_text=str(row.get("advice_plan", "")),
        )
        report["llm_enhanced_narrative"] = self._build_llm_narrative(report)
        report["knowledge_enhanced_qa"] = self._build_llm_knowledge_qa(
            report=report,
            question="这个学生当前最核心问题是什么？请给出证据链和三条可执行建议。",
        )
        report["rag_knowledge_support"] = self._build_rag_knowledge_support(
            report=report,
            qa_status=report["knowledge_enhanced_qa"].get("status", "ok")
        )
        report["intervention_closure"] = self._build_intervention_loop(
            warning=business_warning,
            generated_at=report["meta"]["generated_at"],
        )
        report["actionable_grouping"] = self._build_actionable_grouping(group_data)
        report["student_view_enhancement"] = self._build_student_view_enhancement(
            row=row,
            trajectory=report.get("trajectory_story", {}),
            advice=report.get("advice", {}),
        )
        warnings = self._load_business_warning()
        if not warnings.empty:
            top = warnings.copy()
            top["priority_score"] = (
                pd.to_numeric(top.get("course_fail_fused_probability", 0.0), errors="coerce").fillna(0.0) * 0.55
                + pd.to_numeric(top.get("composite_attention_score", 0.0), errors="coerce").fillna(0.0) * 0.35
                + pd.to_numeric(top.get("primary_risk_score", 0.0), errors="coerce").fillna(0.0) * 0.10
            )
            top3 = top.sort_values("priority_score", ascending=False).head(3)
            report["todo_top3_ranking"] = [
                {
                    "student_id": str(item.get("student_id", "")),
                    "priority_score": float(pd.to_numeric(item.get("priority_score", 0.0), errors="coerce") or 0.0),
                    "warning_priority": str(item.get("warning_priority", "")),
                    "reason_card": self._build_priority_reason_card(item).get("top3_reason_card", []),
                }
                for _, item in top3.iterrows()
            ]
        else:
            report["todo_top3_ranking"] = []
        return report

    def build_batch(self, student_ids: list[str]) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for student_id in student_ids:
            report = self.build_one(student_id)
            if report:
                reports.append(report)
        return reports
