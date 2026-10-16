from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _safe_percentile(series: pd.Series, q: float) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0.0
    return float(np.percentile(values, q))


def _safe_read_features(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _calc_score_trend(history: pd.DataFrame) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)
    if "snapshot_date" not in history.columns or "lifestyle_health_total_score" not in history.columns:
        return pd.Series(dtype=float)
    history = history.copy()
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"], errors="coerce")
    history = history.dropna(subset=["snapshot_date"])
    if history.empty:
        return pd.Series(dtype=float)
    history = history.sort_values(["XH", "snapshot_date"])
    history["order"] = history.groupby("XH").cumcount()

    def _slope(group: pd.DataFrame) -> float:
        y = pd.to_numeric(group["lifestyle_health_total_score"], errors="coerce").values
        x = group["order"].values.astype(float)
        if len(group) < 2 or np.all(np.isnan(y)):
            return 0.0
        mask = ~np.isnan(y)
        if mask.sum() < 2:
            return 0.0
        x = x[mask]
        y = y[mask]
        x_centered = x - x.mean()
        denom = np.sum(x_centered ** 2)
        if denom == 0:
            return 0.0
        return float(np.sum(x_centered * (y - y.mean())) / denom)

    return history.groupby("XH", as_index=True).apply(_slope)


@dataclass
class LifestyleHealthRuleEngine:
    project_root: Path

    def _config_path(self) -> Path:
        return self.project_root / "configs" / "features" / "mode_features.yaml"

    def _feature_path(self) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "modes" / "lifestyle_health_features.parquet"
        if parquet_path.exists():
            return parquet_path
        return self.project_root / "data" / "feature_store" / "modes" / "lifestyle_health_features.csv"

    def _history_path(self) -> Path:
        return self.project_root / "data" / "feature_store" / "modes" / "lifestyle_health_features_history.parquet"

    def _load_rule_meta(self) -> dict:
        cfg = yaml.safe_load(self._config_path().read_text(encoding="utf-8"))
        mode = next(item for item in cfg["modes"] if item.get("mode_key") == "lifestyle_health")
        return mode.get("subtype_rules_v1", {})

    def _compute_thresholds(self, df: pd.DataFrame) -> dict[str, float]:
        return {
            "P30_score": _safe_percentile(df["lifestyle_health_total_score"], 30),
            "P40_score": _safe_percentile(df["lifestyle_health_total_score"], 40),
            "P40_night_activity": _safe_percentile(df["night_activity_index"], 40),
            "P40_day_night": _safe_percentile(df["day_night_activity_ratio"], 40),
            "P60_pe": _safe_percentile(df["pe_course_completion_rate"], 60),
            "P70_score": _safe_percentile(df["lifestyle_health_total_score"], 70),
            "P70_running_freq": _safe_percentile(df["running_frequency"], 30),
            "P70_miss_weeks": _safe_percentile(df["continuous_missed_exercise_weeks"], 70),
            "P70_dorm": _safe_percentile(df["dorm_stay_ratio"], 70),
            "P70_night_activity": _safe_percentile(df["night_activity_index"], 70),
            "P75_entropy": _safe_percentile(df["circadian_entropy"], 75),
            "P75_volatility": _safe_percentile(df["rhythm_volatility_index"], 75),
        }

    def classify(self) -> pd.DataFrame:
        current = _safe_read_features(self._feature_path())
        if current.empty:
            return pd.DataFrame()
        current["XH"] = current["XH"].astype(str)

        if self._history_path().exists():
            history = _safe_read_features(self._history_path())
        else:
            history = current.copy()
        trend = _calc_score_trend(history)
        current["score_trend"] = current["XH"].map(trend).fillna(0.0)

        t = self._compute_thresholds(current)
        rule_meta = self._load_rule_meta()
        history_days = 0
        if not history.empty and "snapshot_date" in history.columns:
            snapshot_dates = pd.to_datetime(history["snapshot_date"], errors="coerce").dropna().dt.normalize().unique()
            history_days = len(snapshot_dates)

        regular = (
            (current["lifestyle_health_total_score"] >= t["P70_score"])
            & (current["night_activity_index"] <= t["P40_night_activity"])
            & (current["continuous_missed_exercise_weeks"] <= 1)
            & (current["pe_course_completion_rate"] >= t["P60_pe"])
        )
        if history_days >= 2:
            warning = (
                (current["circadian_entropy"] >= t["P75_entropy"])
                & (current["rhythm_volatility_index"] >= t["P75_volatility"])
                & (current["score_trend"] < 0)
            )
        else:
            warning = (
                (current["circadian_entropy"] >= t["P75_entropy"])
                & (current["rhythm_volatility_index"] >= t["P75_volatility"])
                & (current["lifestyle_health_total_score"] <= t["P40_score"])
            )
        low_ex = (
            (current["running_frequency"] <= t["P70_running_freq"])
            & (current["continuous_missed_exercise_weeks"] >= t["P70_miss_weeks"])
            & (current["dorm_stay_ratio"] >= t["P70_dorm"])
        )
        night = (
            (current["night_activity_index"] >= t["P70_night_activity"])
            & (current["day_night_activity_ratio"] <= t["P40_day_night"])
            & (current["lifestyle_health_total_score"] >= t["P30_score"])
        )

        current["subtype_key"] = np.select(
            [warning, regular, low_ex, night],
            ["rhythm_disorder_warning", "regular_vitality", "low_exercise_static", "late_schedule_active"],
            default="late_schedule_active",
        )
        counts = current["subtype_key"].value_counts(dropna=False)
        if counts.get("rhythm_disorder_warning", 0) == 0:
            risk_score = (
                0.35 * (pd.to_numeric(current["circadian_entropy"], errors="coerce").fillna(0.0))
                + 0.35 * (pd.to_numeric(current["rhythm_volatility_index"], errors="coerce").fillna(0.0))
                + 0.20 * (pd.to_numeric(current["night_activity_index"], errors="coerce").fillna(0.0))
                - 0.25 * (pd.to_numeric(current["lifestyle_health_total_score"], errors="coerce").fillna(0.0))
            )
            top_n = max(1, int(len(current) * 0.03))
            idx = risk_score.sort_values(ascending=False).head(top_n).index
            current.loc[idx, "subtype_key"] = "rhythm_disorder_warning"

        current["rule_name"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("rule_name", ""))
        current["subtype_label"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("label_cn", ""))
        current["explanation"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("explanation_template", ""))
        current["warning_level"] = np.where(current["subtype_key"] == "rhythm_disorder_warning", "high", "normal")
        current["mode_key"] = "lifestyle_health"
        current["mode_name"] = "生活节律与运动健康模式"
        current["rule_version"] = "v1"
        current["created_at"] = pd.Timestamp.now()
        current["history_days"] = history_days

        cols = [
            "XH",
            "mode_key",
            "mode_name",
            "subtype_key",
            "subtype_label",
            "rule_name",
            "warning_level",
            "lifestyle_health_total_score",
            "continuous_missed_exercise_weeks",
            "pe_course_completion_rate",
            "day_night_activity_ratio",
            "dorm_stay_ratio",
            "score_trend",
            "night_activity_index",
            "circadian_entropy",
            "rhythm_volatility_index",
            "explanation",
            "history_days",
            "created_at",
        ]
        return current[cols].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path) -> Path:
        result = self.classify()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if result.empty:
            result.to_csv(output_path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
            return output_path.with_suffix(".csv")
        try:
            result.to_parquet(output_path, index=False)
            return output_path
        except Exception:
            csv_path = output_path.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            return csv_path
