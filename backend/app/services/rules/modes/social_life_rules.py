from __future__ import annotations

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
class SocialLifeRuleEngine:
    project_root: Path

    def _config_path(self) -> Path:
        return self.project_root / "configs" / "features" / "mode_features.yaml"

    def _feature_path(self) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "modes" / "social_life_features.parquet"
        if parquet_path.exists():
            return parquet_path
        return self.project_root / "data" / "feature_store" / "modes" / "social_life_features.csv"

    def _load_rule_meta(self) -> dict:
        cfg = yaml.safe_load(self._config_path().read_text(encoding="utf-8"))
        mode = next(item for item in cfg["modes"] if item.get("mode_key") == "social_life")
        return mode.get("subtype_rules_v1", {})

    def _build_base_thresholds(self, df: pd.DataFrame) -> dict[str, float]:
        return {
            "P30_total": _safe_percentile(df["social_life_total_score"], 30),
            "P40_total": _safe_percentile(df["social_life_total_score"], 40),
            "P60_total": _safe_percentile(df["social_life_total_score"], 60),
            "P70_total": _safe_percentile(df["social_life_total_score"], 70),
            "P40_formal": _safe_percentile(df["formal_activity_participation_count"], 40),
            "P60_formal": _safe_percentile(df["formal_activity_participation_count"], 60),
            "P70_formal": _safe_percentile(df["formal_activity_participation_count"], 70),
            "P60_formal_freq": _safe_percentile(df["formal_activity_frequency"], 60),
            "P40_signin": _safe_percentile(df["activity_signin_rate"], 40),
            "P60_signin": _safe_percentile(df["activity_signin_rate"], 60),
            "P40_consistency": _safe_percentile(df["checkin_consistency_index"], 40),
            "P60_consistency": _safe_percentile(df["checkin_consistency_index"], 60),
            "P40_online": _safe_percentile(df["online_interaction_count"], 40),
            "P60_online": _safe_percentile(df["online_interaction_count"], 60),
            "P70_online": _safe_percentile(df["online_interaction_count"], 70),
            "P70_post": _safe_percentile(df["post_reply_activity"], 70),
            "P40_quality": _safe_percentile(df["interaction_quality_index"], 40),
            "P60_quality": _safe_percentile(df["interaction_quality_index"], 60),
            "P60_online_ratio": _safe_percentile(df["online_expression_ratio"], 60),
            "P40_stable": _safe_percentile(df["stable_copresence_partner_count"], 40),
            "P60_stable": _safe_percentile(df["stable_copresence_partner_count"], 60),
            "P60_multi_scene": _safe_percentile(df["multi_scene_engagement_index"], 60),
            "P40_multi_scene": _safe_percentile(df["multi_scene_engagement_index"], 40),
            "P60_balance": _safe_percentile(df["offline_online_balance_index"], 60),
            "P70_isolation": _safe_percentile(df["social_isolation_index"], 70),
            "P75_isolation": _safe_percentile(df["social_isolation_index"], 75),
            "P60_isolation": _safe_percentile(df["social_isolation_index"], 60),
            "P60_offline": _safe_percentile(df["offline_activity_index"], 60),
            "P40_offline": _safe_percentile(df["offline_activity_index"], 40),
        }

    def _classify_with_profile(self, current: pd.DataFrame, t: dict[str, float], profile_name: str) -> pd.Series:
        if profile_name == "strict":
            high = (
                (current["social_life_total_score"] >= t["P70_total"])
                & (current["formal_activity_participation_count"] >= t["P60_formal"])
                & (current["formal_activity_frequency"] >= t["P60_formal_freq"])
                & (current["stable_copresence_partner_count"] >= t["P60_stable"])
                & (current["online_interaction_count"] >= t["P60_online"])
                & (current["multi_scene_engagement_index"] >= t["P60_multi_scene"])
                & (current["offline_online_balance_index"] >= t["P60_balance"])
            )
            formal = (
                (current["formal_activity_participation_count"] >= t["P70_formal"])
                & (current["activity_signin_rate"] >= t["P60_signin"])
                & (current["offline_activity_index"] >= t["P60_offline"])
                & (current["checkin_consistency_index"] >= t["P40_consistency"])
                & (current["social_isolation_index"] <= t["P60_isolation"])
            )
            online = (
                (current["online_interaction_count"] >= t["P70_online"])
                & (current["post_reply_activity"] >= t["P70_post"])
                & (current["interaction_quality_index"] >= t["P60_quality"])
                & (current["online_expression_ratio"] >= t["P60_online_ratio"])
                & (current["stable_copresence_partner_count"] <= t["P60_stable"])
            )
            low = (
                (
                    (current["social_life_total_score"] <= t["P30_total"])
                    & (current["formal_activity_participation_count"] <= t["P40_formal"])
                    & (current["online_interaction_count"] <= t["P40_online"])
                    & (current["multi_scene_engagement_index"] <= t["P40_multi_scene"])
                )
                | (
                    (current["social_isolation_index"] >= t["P75_isolation"])
                    & (
                        (
                            (current["stable_copresence_partner_count"] <= t["P40_stable"])
                            & (current["checkin_consistency_index"] <= t["P40_consistency"])
                        )
                        | (current["social_life_total_score"] <= t["P30_total"])
                    )
                )
            )
        else:
            high = (
                (current["social_life_total_score"] >= t["P60_total"])
                & (current["formal_activity_participation_count"] >= t["P60_formal"])
                & (current["online_interaction_count"] >= t["P60_online"])
                & (current["multi_scene_engagement_index"] >= t["P60_multi_scene"])
            )
            formal = (
                (current["formal_activity_participation_count"] >= t["P60_formal"])
                & (current["activity_signin_rate"] >= t["P40_signin"])
                & (current["offline_activity_index"] >= t["P40_offline"])
                & (current["checkin_consistency_index"] >= t["P40_consistency"])
            )
            online = (
                (current["online_interaction_count"] >= t["P60_online"])
                & (current["post_reply_activity"] >= t["P60_online"])
                & (current["interaction_quality_index"] >= t["P40_quality"])
                & (current["stable_copresence_partner_count"] <= t["P60_stable"])
            )
            low = (
                (
                    (current["social_isolation_index"] >= t["P70_isolation"])
                    & (current["multi_scene_engagement_index"] <= t["P40_multi_scene"])
                    & (current["social_life_total_score"] <= t["P40_total"])
                )
                | (
                    (current["social_life_total_score"] <= t["P30_total"])
                    & (current["formal_activity_participation_count"] <= t["P40_formal"])
                    & (current["online_interaction_count"] <= t["P40_online"])
                )
            )

        rule_result = np.select(
            [low, high, formal, online],
            ["low_integration_isolated", "high_integration_collaborative", "formal_participation", "online_expression"],
            default="formal_participation",
        )
        return pd.Series(rule_result, index=current.index, dtype="object")

    def _enforce_all_labels(self, current: pd.DataFrame, labels: pd.Series) -> pd.Series:
        if len(current) < 4:
            return labels
        adjusted = labels.copy()
        required = [
            "high_integration_collaborative",
            "formal_participation",
            "online_expression",
            "low_integration_isolated",
        ]
        score_high = _norm(current["social_life_total_score"]) + _norm(current["stable_copresence_partner_count"])
        score_formal = _norm(current["formal_activity_participation_count"]) + _norm(current["activity_signin_rate"])
        score_online = _norm(current["online_interaction_count"]) + _norm(current["post_reply_activity"])
        score_low = _norm(current["social_isolation_index"]) + _norm(current["social_life_total_score"], reverse=True)
        ranking_map = {
            "high_integration_collaborative": score_high,
            "formal_participation": score_formal,
            "online_expression": score_online,
            "low_integration_isolated": score_low,
        }
        for label in required:
            if (adjusted == label).sum() > 0:
                continue
            target_score = ranking_map[label]
            candidate_idx = target_score.sort_values(ascending=False).index
            for idx in candidate_idx:
                if adjusted.iloc[idx] != label:
                    adjusted.iloc[idx] = label
                    break
        return adjusted

    def classify(self) -> pd.DataFrame:
        current = _safe_read_features(self._feature_path())
        if current.empty:
            return pd.DataFrame()
        current["XH"] = current["XH"].astype(str)

        thresholds = self._build_base_thresholds(current)
        rule_meta = self._load_rule_meta()

        labels = self._classify_with_profile(current, thresholds, profile_name="strict")
        counts = labels.value_counts()
        required_labels = {
            "high_integration_collaborative",
            "formal_participation",
            "online_expression",
            "low_integration_isolated",
        }
        if not required_labels.issubset(set(counts.index)):
            labels = self._classify_with_profile(current, thresholds, profile_name="relaxed")
        labels = self._enforce_all_labels(current, labels)
        current["subtype_key"] = labels

        current["rule_name"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("rule_name", ""))
        current["subtype_label"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("label_cn", ""))
        current["explanation"] = current["subtype_key"].map(lambda x: rule_meta.get(x, {}).get("explanation_template", ""))
        current["warning_level"] = np.where(current["subtype_key"] == "low_integration_isolated", "high", "normal")
        current["mode_key"] = "social_life"
        current["mode_name"] = "社交生活模式"
        current["rule_version"] = "v1"
        current["created_at"] = pd.Timestamp.now()

        cols = [
            "XH",
            "mode_key",
            "mode_name",
            "subtype_key",
            "subtype_label",
            "rule_name",
            "warning_level",
            "social_life_total_score",
            "formal_activity_participation_count",
            "formal_activity_frequency",
            "activity_signin_rate",
            "checkin_consistency_index",
            "online_interaction_count",
            "post_reply_activity",
            "interaction_quality_index",
            "multi_scene_engagement_index",
            "offline_online_balance_index",
            "stable_copresence_partner_count",
            "social_diversity_index",
            "social_circle_density",
            "social_isolation_index",
            "explanation",
            "created_at",
        ]
        existing = [col for col in cols if col in current.columns]
        return current[existing].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path) -> Path:
        result = self.classify()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if result.empty:
            csv_path = output_path.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            return csv_path
        try:
            result.to_parquet(output_path, index=False)
            return output_path
        except Exception:
            csv_path = output_path.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            return csv_path
