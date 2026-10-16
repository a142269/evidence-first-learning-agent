from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _safe_read_features(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _safe_percentile(series: pd.Series, q: float) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0.0
    return float(np.percentile(values, q))


def _norm(series: pd.Series, reverse: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    min_v = values.min(skipna=True)
    max_v = values.max(skipna=True)
    if pd.isna(min_v) or pd.isna(max_v) or max_v == min_v:
        output = pd.Series(0.0, index=values.index)
    else:
        output = (values - min_v) / (max_v - min_v)
    if reverse:
        output = 1 - output
    return output.fillna(0.0)


@dataclass
class CourseExplorationRuleEngine:
    project_root: Path

    def _config_path(self) -> Path:
        return self.project_root / "configs" / "features" / "mode_features.yaml"

    def _feature_path(self) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "modes" / "course_exploration_features.parquet"
        if parquet_path.exists():
            return parquet_path
        return self.project_root / "data" / "feature_store" / "modes" / "course_exploration_features.csv"

    def _load_rule_meta(self) -> dict:
        cfg = yaml.safe_load(self._config_path().read_text(encoding="utf-8"))
        mode = next(item for item in cfg["modes"] if item.get("mode_key") == "course_exploration")
        return mode.get("subtype_rules_v1", {})

    def _build_thresholds(self, df: pd.DataFrame) -> dict[str, float]:
        return {
            "P30_total": _safe_percentile(df["course_exploration_total_score"], 30),
            "P40_total": _safe_percentile(df["course_exploration_total_score"], 40),
            "P60_total": _safe_percentile(df["course_exploration_total_score"], 60),
            "P70_total": _safe_percentile(df["course_exploration_total_score"], 70),
            "P75_total": _safe_percentile(df["course_exploration_total_score"], 75),
            "P30_cross": _safe_percentile(df["cross_discipline_course_ratio"], 30),
            "P60_cross": _safe_percentile(df["cross_discipline_course_ratio"], 60),
            "P70_cross": _safe_percentile(df["cross_discipline_course_ratio"], 70),
            "P40_plan": _safe_percentile(df["course_planning_proactivity"], 40),
            "P60_plan": _safe_percentile(df["course_planning_proactivity"], 60),
            "P70_plan": _safe_percentile(df["course_planning_proactivity"], 70),
            "P60_retake": _safe_percentile(df["retake_dependency_ratio"], 60),
            "P70_retake": _safe_percentile(df["retake_dependency_ratio"], 70),
            "P40_assessment": _safe_percentile(df["assessment_preference_index"], 40),
            "P70_assessment": _safe_percentile(df["assessment_preference_index"], 70),
            "P40_risk": _safe_percentile(df["high_risk_course_ratio"], 40),
            "P60_risk": _safe_percentile(df["high_risk_course_ratio"], 60),
            "P70_breadth": _safe_percentile(df["course_exploration_breadth"], 70),
            "P40_breadth": _safe_percentile(df["course_exploration_breadth"], 40),
            "P60_drift": _safe_percentile(df["major_drift_trajectory"], 60),
            "P70_drift": _safe_percentile(df["major_drift_trajectory"], 70),
            "P75_drift": _safe_percentile(df["major_drift_trajectory"], 75),
            "P60_gpa_return": _safe_percentile(df["gpa_return_rate"], 60),
            "P70_challenge": _safe_percentile(df["challenge_depth_index"], 70),
            "P60_challenge": _safe_percentile(df["challenge_depth_index"], 60),
            "P40_challenge": _safe_percentile(df["challenge_depth_index"], 40),
            "P60_prereq": _safe_percentile(df["prerequisite_challenge_rate"], 60),
            "P60_extension": _safe_percentile(df["extension_improvement_ratio"], 60),
            "P70_loyalty": _safe_percentile(df["professional_loyalty_index"], 70),
            "P60_loyalty": _safe_percentile(df["professional_loyalty_index"], 60),
            "P70_late": _safe_percentile(df["late_selection_ratio"], 70),
        }

    def _classify_with_profile(self, current: pd.DataFrame, t: dict[str, float], profile_name: str) -> pd.Series:
        if profile_name == "strict":
            target_oriented = (
                (current["cross_discipline_course_ratio"] >= t["P60_cross"])
                & (current["challenge_depth_index"] >= t["P70_challenge"])
                & (current["prerequisite_challenge_rate"] >= t["P60_prereq"])
                & (current["extension_improvement_ratio"] >= t["P60_extension"])
                & (current["course_planning_proactivity"] >= t["P60_plan"])
                & (current["major_drift_trajectory"] <= t["P60_drift"])
            )
            stable_deep = (
                (current["professional_loyalty_index"] >= t["P70_loyalty"])
                & (current["major_drift_trajectory"] <= t["P60_drift"])
                & (current["retake_dependency_ratio"] <= t["P60_retake"])
                & (current["challenge_depth_index"] >= t["P40_challenge"])
                & (current["challenge_depth_index"] <= t["P70_challenge"])
                & (current["cross_discipline_course_ratio"] >= t["P30_cross"])
                & (current["cross_discipline_course_ratio"] <= t["P70_cross"])
            )
            gpa_conservative = (
                (current["assessment_preference_index"] >= t["P70_assessment"])
                & (current["high_risk_course_ratio"] <= t["P40_risk"])
                & (current["gpa_return_rate"] >= t["P60_gpa_return"])
                & (current["course_planning_proactivity"] >= t["P40_plan"])
                & (current["challenge_depth_index"] <= t["P60_challenge"])
            )
            drifting_probe = (
                (current["major_drift_trajectory"] >= t["P70_drift"])
                & (current["late_selection_ratio"] >= t["P70_late"])
                & (current["cross_discipline_course_ratio"] >= t["P60_cross"])
                & (
                    (current["retake_dependency_ratio"] >= t["P60_retake"])
                    | (current["course_planning_proactivity"] <= t["P40_plan"])
                )
            )
        else:
            target_oriented = (
                (current["course_exploration_total_score"] >= t["P60_total"])
                & (current["cross_discipline_course_ratio"] >= t["P60_cross"])
                & (current["challenge_depth_index"] >= t["P60_challenge"])
                & (current["course_exploration_breadth"] >= t["P40_breadth"])
            )
            stable_deep = (
                (current["professional_loyalty_index"] >= t["P60_loyalty"])
                & (current["major_drift_trajectory"] <= t["P70_drift"])
                & (current["retake_dependency_ratio"] <= t["P70_retake"])
            )
            gpa_conservative = (
                (current["assessment_preference_index"] >= t["P70_assessment"])
                & (current["high_risk_course_ratio"] <= t["P60_risk"])
                & (current["gpa_return_rate"] >= t["P60_gpa_return"])
            )
            drifting_probe = (
                (current["major_drift_trajectory"] >= t["P60_drift"])
                & (current["late_selection_ratio"] >= t["P70_late"])
            )
        result = np.select(
            [drifting_probe, target_oriented, gpa_conservative, stable_deep],
            ["drifting_probe", "target_oriented_explorer", "gpa_conservative", "stable_deepening"],
            default="stable_deepening",
        )
        return pd.Series(result, index=current.index, dtype="object")

    def _enforce_all_labels(self, current: pd.DataFrame, labels: pd.Series) -> pd.Series:
        if len(current) < 4:
            return labels
        adjusted = labels.copy()
        required = [
            "target_oriented_explorer",
            "stable_deepening",
            "gpa_conservative",
            "drifting_probe",
        ]
        ranking_map = {
            "target_oriented_explorer": (
                _norm(current["cross_discipline_course_ratio"])
                + _norm(current["challenge_depth_index"])
                + _norm(current["prerequisite_challenge_rate"])
            ),
            "stable_deepening": (
                _norm(current["professional_loyalty_index"])
                + _norm(current["gpa_return_rate"])
                + _norm(current["major_drift_trajectory"], reverse=True)
            ),
            "gpa_conservative": (
                _norm(current["assessment_preference_index"])
                + _norm(current["high_risk_course_ratio"], reverse=True)
                + _norm(current["gpa_return_rate"])
            ),
            "drifting_probe": (
                _norm(current["major_drift_trajectory"])
                + _norm(current["late_selection_ratio"])
                + _norm(current["retake_dependency_ratio"])
            ),
        }
        for label in required:
            if (adjusted == label).sum() > 0:
                continue
            candidate_idx = ranking_map[label].sort_values(ascending=False).index
            for idx in candidate_idx:
                if adjusted.iloc[idx] != label:
                    adjusted.iloc[idx] = label
                    break
        return adjusted

    def _rule_confidence(self, current: pd.DataFrame) -> pd.Series:
        return np.select(
            [
                current["subtype_key"] == "target_oriented_explorer",
                current["subtype_key"] == "stable_deepening",
                current["subtype_key"] == "gpa_conservative",
                current["subtype_key"] == "drifting_probe",
            ],
            [
                (
                    0.25 * _norm(current["cross_discipline_course_ratio"])
                    + 0.25 * _norm(current["challenge_depth_index"])
                    + 0.20 * _norm(current["prerequisite_challenge_rate"])
                    + 0.15 * _norm(current["extension_improvement_ratio"])
                    + 0.15 * _norm(current["course_planning_proactivity"])
                ),
                (
                    0.35 * _norm(current["professional_loyalty_index"])
                    + 0.25 * _norm(current["gpa_return_rate"])
                    + 0.20 * _norm(current["major_drift_trajectory"], reverse=True)
                    + 0.20 * _norm(current["retake_dependency_ratio"], reverse=True)
                ),
                (
                    0.35 * _norm(current["assessment_preference_index"])
                    + 0.30 * _norm(current["high_risk_course_ratio"], reverse=True)
                    + 0.20 * _norm(current["gpa_return_rate"])
                    + 0.15 * _norm(current["challenge_depth_index"], reverse=True)
                ),
                (
                    0.35 * _norm(current["major_drift_trajectory"])
                    + 0.25 * _norm(current["late_selection_ratio"])
                    + 0.20 * _norm(current["retake_dependency_ratio"])
                    + 0.20 * _norm(current["cross_discipline_course_ratio"])
                ),
            ],
            default=_norm(current["course_exploration_total_score"]),
        )

    def _rebalance_distribution(self, current: pd.DataFrame, labels: pd.Series) -> pd.Series:
        if len(current) < 20:
            return labels
        adjusted = labels.copy()
        ratio = adjusted.value_counts(normalize=True)
        if ratio.max() <= 0.68:
            return adjusted
        target_min = max(8, int(len(current) * 0.08))
        score_map = {
            "target_oriented_explorer": (
                _norm(current["cross_discipline_course_ratio"])
                + _norm(current["challenge_depth_index"])
                + _norm(current["prerequisite_challenge_rate"])
                + _norm(current["extension_improvement_ratio"])
            ),
            "stable_deepening": (
                _norm(current["professional_loyalty_index"])
                + _norm(current["gpa_return_rate"])
                + _norm(current["major_drift_trajectory"], reverse=True)
            ),
            "gpa_conservative": (
                _norm(current["assessment_preference_index"])
                + _norm(current["high_risk_course_ratio"], reverse=True)
                + _norm(current["gpa_return_rate"])
            ),
            "drifting_probe": (
                _norm(current["major_drift_trajectory"])
                + _norm(current["late_selection_ratio"])
                + _norm(current["retake_dependency_ratio"])
            ),
        }
        for key in ["target_oriented_explorer", "gpa_conservative", "drifting_probe", "stable_deepening"]:
            current_count = int((adjusted == key).sum())
            if current_count >= target_min:
                continue
            need = target_min - current_count
            candidates = score_map[key].sort_values(ascending=False).index
            changed = 0
            for idx in candidates:
                if adjusted.loc[idx] == key:
                    continue
                adjusted.loc[idx] = key
                changed += 1
                if changed >= need:
                    break
        return adjusted

    def _build_summary(self, frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {"shape": [0, 0], "distribution": {}, "sample": []}
        distribution = frame["subtype_label"].value_counts(dropna=False).to_dict()
        return {
            "shape": [int(frame.shape[0]), int(frame.shape[1])],
            "distribution": distribution,
            "sample": frame.head(3).replace({np.nan: None}).to_dict(orient="records"),
        }

    def classify(self) -> pd.DataFrame:
        current = _safe_read_features(self._feature_path())
        if current.empty:
            return pd.DataFrame()
        current["XH"] = current["XH"].astype(str)

        thresholds = self._build_thresholds(current)
        rule_meta = self._load_rule_meta()

        labels = self._classify_with_profile(current, thresholds, profile_name="strict")
        counts = labels.value_counts(normalize=True)
        required_labels = {"target_oriented_explorer", "stable_deepening", "gpa_conservative", "drifting_probe"}
        if (not required_labels.issubset(set(counts.index))) or (counts.max() > 0.68):
            labels = self._classify_with_profile(current, thresholds, profile_name="relaxed")
        labels = self._enforce_all_labels(current, labels)
        counts = labels.value_counts(normalize=True)
        if counts.max() > 0.72:
            drift_boost = (
                _norm(current["major_drift_trajectory"])
                + _norm(current["late_selection_ratio"])
                + _norm(current["retake_dependency_ratio"])
            )
            boost_idx = drift_boost.sort_values(ascending=False).index[: max(1, int(len(current) * 0.08))]
            labels.loc[boost_idx] = "drifting_probe"
        labels = self._enforce_all_labels(current, labels)
        labels = self._rebalance_distribution(current, labels)
        labels = self._enforce_all_labels(current, labels)
        current["subtype_key"] = labels

        current["rule_name"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("rule_name", ""))
        current["subtype_label"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("label_cn", ""))
        current["rule_label"] = current["subtype_label"]
        current["explanation"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("explanation_template", ""))
        current["warning_level"] = np.where(current["subtype_key"] == "drifting_probe", "high", "normal")
        current["rule_confidence"] = np.clip(self._rule_confidence(current), 0.0, 1.0)
        current["mode_key"] = "course_exploration"
        current["mode_name"] = "选课探索模式"
        current["rule_version"] = "v1"
        current["created_at"] = pd.Timestamp.now()

        cols = [
            "XH",
            "mode_key",
            "mode_name",
            "subtype_key",
            "subtype_label",
            "rule_label",
            "rule_name",
            "warning_level",
            "rule_confidence",
            "course_exploration_total_score",
            "cross_discipline_course_ratio",
            "course_planning_proactivity",
            "retake_dependency_ratio",
            "assessment_preference_index",
            "high_risk_course_ratio",
            "course_exploration_breadth",
            "major_drift_trajectory",
            "gpa_return_rate",
            "challenge_depth_index",
            "prerequisite_challenge_rate",
            "extension_improvement_ratio",
            "professional_loyalty_index",
            "late_selection_ratio",
            "explanation",
            "created_at",
        ]
        existing = [col for col in cols if col in current.columns]
        return current[existing].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path) -> Path:
        result = self.classify()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        summary = self._build_summary(result)
        try:
            result.to_parquet(output_path, index=False)
            output_path.with_suffix(".json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            return output_path
        except Exception:
            csv_path = output_path.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            csv_path.with_suffix(".json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            return csv_path
