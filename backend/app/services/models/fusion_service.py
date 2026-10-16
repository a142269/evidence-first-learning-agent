from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


def _safe_read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_json(path)


def _norm(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    min_v = values.min(skipna=True)
    max_v = values.max(skipna=True)
    if pd.isna(min_v) or pd.isna(max_v) or min_v == max_v:
        return pd.Series(0.0, index=values.index)
    return ((values - min_v) / (max_v - min_v)).fillna(0.0)


@dataclass
class LifestyleHealthFusionService:
    project_root: Path

    def _rule_path(self) -> Path:
        p = self.project_root / "data" / "ads" / "pattern_results" / "lifestyle_health_pattern_results.parquet"
        if p.exists():
            return p
        return p.with_suffix(".csv")

    def _cluster_path(self) -> Path:
        p = self.project_root / "data" / "ads" / "pattern_results" / "lifestyle_health_cluster_results.parquet"
        if p.exists():
            return p
        if p.with_suffix(".csv").exists():
            return p.with_suffix(".csv")
        return p.with_suffix(".json")

    def _output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "lifestyle_health_fusion_results.parquet"

    def run(self) -> pd.DataFrame:
        rule = _safe_read(self._rule_path())
        cluster = _safe_read(self._cluster_path())
        if rule.empty or cluster.empty:
            return pd.DataFrame()
        merged = rule.merge(
            cluster[["XH", "cluster_subtype_key", "cluster_subtype_label", "cluster_confidence", "cluster_explain_factors"]],
            on="XH",
            how="inner",
        )
        if merged.empty:
            return pd.DataFrame()
        merged["rule_confidence"] = np.select(
            [
                merged["subtype_key"] == "regular_vitality",
                merged["subtype_key"] == "late_schedule_active",
                merged["subtype_key"] == "low_exercise_static",
                merged["subtype_key"] == "rhythm_disorder_warning",
            ],
            [
                0.6 * _norm(merged["lifestyle_health_total_score"]) + 0.4 * _norm(merged["pe_course_completion_rate"]),
                0.7 * _norm(merged["night_activity_index"]) + 0.3 * _norm(1 / (merged["day_night_activity_ratio"] + 1e-6)),
                0.6 * _norm(merged["continuous_missed_exercise_weeks"]) + 0.4 * _norm(merged["dorm_stay_ratio"]),
                0.4 * _norm(merged["circadian_entropy"])
                + 0.4 * _norm(merged["rhythm_volatility_index"])
                + 0.2 * _norm(1 - merged["lifestyle_health_total_score"]),
            ],
            default=_norm(merged["lifestyle_health_total_score"]),
        )
        merged["rule_confidence"] = np.clip(merged["rule_confidence"], 0.0, 1.0)
        merged["cluster_confidence"] = pd.to_numeric(merged["cluster_confidence"], errors="coerce").fillna(0.5).clip(0.0, 1.0)
        final_key: list[str] = []
        final_source: list[str] = []
        final_conf: list[float] = []
        for _, row in merged.iterrows():
            rk = str(row["subtype_key"])
            ck = str(row["cluster_subtype_key"])
            rc = float(row["rule_confidence"])
            cc = float(row["cluster_confidence"])
            if rk == ck:
                fk = rk
                source = "rule+cluster"
                conf = min(1.0, 0.5 * rc + 0.5 * cc + 0.1)
            elif rk == "rhythm_disorder_warning" and row.get("warning_level", "normal") == "high" and rc >= 0.7:
                fk = rk
                source = "rule_priority_warning"
                conf = min(1.0, 0.7 * rc + 0.3 * cc)
            else:
                if cc >= rc:
                    fk = ck
                    source = "cluster_priority"
                    conf = 0.6 * cc + 0.4 * rc
                else:
                    fk = rk
                    source = "rule_priority"
                    conf = 0.6 * rc + 0.4 * cc
            final_key.append(fk)
            final_source.append(source)
            final_conf.append(float(np.clip(conf, 0.0, 1.0)))
        merged["final_subtype_key"] = final_key
        key_to_label = {
            "regular_vitality": "规律活力型",
            "late_schedule_active": "晚间行为活跃型",
            "low_exercise_static": "运动不足静态型",
            "rhythm_disorder_warning": "节律紊乱预警型",
        }
        merged["final_subtype_label"] = merged["final_subtype_key"].map(key_to_label).fillna("晚间行为活跃型")
        merged["fusion_source"] = final_source
        merged["mode_confidence"] = final_conf
        merged["mode_score"] = pd.to_numeric(merged["lifestyle_health_total_score"], errors="coerce").fillna(0.0)
        merged["mode_explain_factors"] = (
            "rule:" + merged["subtype_label"].astype(str) + ";cluster:" + merged["cluster_subtype_label"].astype(str)
        )
        merged["final_explanation"] = merged["explanation"].astype(str)
        merged["created_at"] = pd.Timestamp.now()
        cols = [
            "XH", "mode_score",
            "subtype_key", "subtype_label",
            "cluster_subtype_key", "cluster_subtype_label",
            "final_subtype_key", "final_subtype_label",
            "rule_confidence", "cluster_confidence", "mode_confidence",
            "fusion_source", "mode_explain_factors", "final_explanation",
            "lifestyle_health_total_score", "warning_level", "created_at",
        ]
        return merged[cols].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path | None = None) -> Path:
        target = output_path or self._output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        result = self.run()
        if result.empty:
            json_path = target.with_suffix(".json")
            json_path.write_text("[]", encoding="utf-8")
            return json_path
        try:
            result.to_parquet(target, index=False)
            result.to_json(target.with_suffix(".json"), orient="records", force_ascii=False)
            return target
        except Exception:
            csv_path = target.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            result.to_json(target.with_suffix(".json"), orient="records", force_ascii=False)
            return csv_path


@dataclass
class SocialLifeFusionService:
    project_root: Path

    def _rule_path(self) -> Path:
        p = self.project_root / "data" / "ads" / "pattern_results" / "social_life_pattern_results.parquet"
        if p.exists():
            return p
        return p.with_suffix(".csv")

    def _cluster_path(self) -> Path:
        p = self.project_root / "data" / "ads" / "pattern_results" / "social_life_cluster_results.parquet"
        if p.exists():
            return p
        if p.with_suffix(".csv").exists():
            return p.with_suffix(".csv")
        return p.with_suffix(".json")

    def _output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "social_life_fusion_results.parquet"

    def run(self) -> pd.DataFrame:
        rule = _safe_read(self._rule_path())
        cluster = _safe_read(self._cluster_path())
        if rule.empty or cluster.empty:
            return pd.DataFrame()
        merged = rule.merge(
            cluster[["XH", "cluster_subtype_key", "cluster_subtype_label", "cluster_confidence", "cluster_explain_factors"]],
            on="XH",
            how="inner",
        )
        if merged.empty:
            return pd.DataFrame()

        merged["rule_confidence"] = np.select(
            [
                merged["subtype_key"] == "high_integration_collaborative",
                merged["subtype_key"] == "formal_participation",
                merged["subtype_key"] == "online_expression",
                merged["subtype_key"] == "low_integration_isolated",
            ],
            [
                _norm(merged["social_life_total_score"]),
                0.6 * _norm(merged["formal_activity_participation_count"]) + 0.4 * _norm(merged["activity_signin_rate"]),
                0.7 * _norm(merged["online_interaction_count"]) + 0.3 * _norm(merged["post_reply_activity"]),
                _norm(merged["social_isolation_index"]),
            ],
            default=_norm(merged["social_life_total_score"]),
        )
        merged["rule_confidence"] = np.clip(merged["rule_confidence"], 0.0, 1.0)
        merged["cluster_confidence"] = pd.to_numeric(merged["cluster_confidence"], errors="coerce").fillna(0.5).clip(0.0, 1.0)

        final_key = []
        final_source = []
        final_conf = []
        for _, row in merged.iterrows():
            rk = row["subtype_key"]
            ck = row["cluster_subtype_key"]
            rc = float(row["rule_confidence"])
            cc = float(row["cluster_confidence"])
            if rk == ck:
                fk = rk
                source = "rule+cluster"
                conf = min(1.0, 0.5 * rc + 0.5 * cc + 0.1)
            elif (
                rk == "low_integration_isolated"
                and row["warning_level"] == "high"
                and rc >= 0.75
                and float(row.get("social_isolation_index", 0.0)) >= 0.75
            ):
                fk = rk
                source = "rule_priority_warning"
                conf = min(1.0, 0.7 * rc + 0.3 * cc)
            else:
                if cc >= rc:
                    fk = ck
                    source = "cluster_priority"
                    conf = 0.6 * cc + 0.4 * rc
                else:
                    fk = rk
                    source = "rule_priority"
                    conf = 0.6 * rc + 0.4 * cc
            final_key.append(fk)
            final_source.append(source)
            final_conf.append(float(np.clip(conf, 0.0, 1.0)))

        merged["final_subtype_key"] = final_key
        key_to_label = {
            "high_integration_collaborative": "高融入协同型",
            "formal_participation": "正式参与型",
            "online_expression": "线上表达型",
            "low_integration_isolated": "低融入孤立型",
        }
        merged["final_subtype_label"] = merged["final_subtype_key"].map(key_to_label).fillna("正式参与型")
        merged["fusion_source"] = final_source
        merged["mode_confidence"] = final_conf
        merged["mode_score"] = pd.to_numeric(merged["social_life_total_score"], errors="coerce").fillna(0.0)
        merged["mode_explain_factors"] = (
            "rule:" + merged["subtype_label"].astype(str) + ";cluster:" + merged["cluster_subtype_label"].astype(str)
        )
        merged["final_explanation"] = merged["explanation"].astype(str)
        merged["created_at"] = pd.Timestamp.now()

        cols = [
            "XH", "mode_score",
            "subtype_key", "subtype_label",
            "cluster_subtype_key", "cluster_subtype_label",
            "final_subtype_key", "final_subtype_label",
            "rule_confidence", "cluster_confidence", "mode_confidence",
            "fusion_source", "mode_explain_factors", "final_explanation",
            "social_life_total_score", "social_isolation_index", "warning_level", "created_at",
        ]
        return merged[cols].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path | None = None) -> Path:
        target = output_path or self._output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        result = self.run()
        if result.empty:
            json_path = target.with_suffix(".json")
            json_path.write_text("[]", encoding="utf-8")
            return json_path
        try:
            result.to_parquet(target, index=False)
            result.to_json(target.with_suffix(".json"), orient="records", force_ascii=False)
            return target
        except Exception:
            csv_path = target.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            result.to_json(target.with_suffix(".json"), orient="records", force_ascii=False)
            return csv_path


@dataclass
class CourseExplorationFusionService:
    project_root: Path
    warning_priority: dict[str, float] | None = None

    def _rule_path(self) -> Path:
        p = self.project_root / "data" / "ads" / "pattern_results" / "course_exploration_pattern_results.parquet"
        if p.exists():
            return p
        return p.with_suffix(".csv")

    def _cluster_path(self) -> Path:
        p = self.project_root / "data" / "ads" / "pattern_results" / "course_exploration_cluster_results.parquet"
        if p.exists():
            return p
        if p.with_suffix(".csv").exists():
            return p.with_suffix(".csv")
        return p.with_suffix(".json")

    def _output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "course_exploration_fusion_results.parquet"

    def _priority_weight(self, key: str) -> float:
        default = {"drifting_probe": 0.75, "gpa_conservative": 0.62, "target_oriented_explorer": 0.58, "stable_deepening": 0.55}
        if self.warning_priority:
            default.update(self.warning_priority)
        return float(default.get(key, 0.55))

    def _build_summary(self, frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {"shape": [0, 0], "distribution": {}, "sample": []}
        return {
            "shape": [int(frame.shape[0]), int(frame.shape[1])],
            "distribution": frame["final_label"].value_counts(dropna=False).to_dict(),
            "sample": frame.head(3).replace({np.nan: None}).to_dict(orient="records"),
        }

    def run(self) -> pd.DataFrame:
        rule = _safe_read(self._rule_path())
        cluster = _safe_read(self._cluster_path())
        if rule.empty or cluster.empty:
            return pd.DataFrame()
        merged = rule.merge(
            cluster[["XH", "cluster_subtype_key", "cluster_label", "cluster_confidence", "cluster_top_factors"]],
            on="XH",
            how="inner",
        )
        if merged.empty:
            return pd.DataFrame()
        merged["rule_confidence"] = pd.to_numeric(merged["rule_confidence"], errors="coerce").fillna(0.5).clip(0.0, 1.0)
        merged["cluster_confidence"] = pd.to_numeric(merged["cluster_confidence"], errors="coerce").fillna(0.5).clip(0.0, 1.0)
        merged["rule_label"] = merged["subtype_label"]
        merged["cluster_label"] = merged["cluster_label"].fillna("稳健深耕型")
        key_to_label = {
            "target_oriented_explorer": "目标导向探索型",
            "stable_deepening": "稳健深耕型",
            "gpa_conservative": "绩点保守型",
            "drifting_probe": "漂移试探型",
        }
        final_key: list[str] = []
        final_source: list[str] = []
        mode_confidence: list[float] = []
        for _, row in merged.iterrows():
            rk = str(row["subtype_key"])
            ck = str(row["cluster_subtype_key"])
            rc = float(row["rule_confidence"])
            cc = float(row["cluster_confidence"])
            if rk == ck:
                fk = rk
                source = "rule+cluster"
                conf = min(1.0, 0.55 * rc + 0.45 * cc + 0.08)
            elif rk == "drifting_probe" and rc >= 0.70:
                fk = rk
                source = "rule_priority_warning"
                conf = min(1.0, 0.70 * rc + 0.30 * cc)
            else:
                rule_weight = self._priority_weight(rk)
                cluster_weight = 1 - rule_weight
                rule_score = rule_weight * rc
                cluster_score = cluster_weight * cc
                if rule_score >= cluster_score:
                    fk = rk
                    source = "rule_priority"
                    conf = rule_score + cluster_score
                else:
                    fk = ck
                    source = "cluster_priority"
                    conf = rule_score + cluster_score
            final_key.append(fk)
            final_source.append(source)
            mode_confidence.append(float(np.clip(conf, 0.0, 1.0)))

        merged["final_subtype_key"] = final_key
        merged["final_label"] = merged["final_subtype_key"].map(key_to_label).fillna("稳健深耕型")
        merged["fusion_source"] = final_source
        merged["mode_confidence"] = mode_confidence
        merged["mode_score"] = pd.to_numeric(merged["course_exploration_total_score"], errors="coerce").fillna(0.0)
        merged["top_factors"] = (
            merged["cluster_top_factors"].astype(str) + "|" + merged["explanation"].astype(str)
        )
        merged["created_at"] = pd.Timestamp.now()
        cols = [
            "XH",
            "rule_label",
            "cluster_label",
            "final_label",
            "mode_score",
            "rule_confidence",
            "cluster_confidence",
            "mode_confidence",
            "top_factors",
            "fusion_source",
            "course_exploration_total_score",
            "warning_level",
            "created_at",
        ]
        return merged[cols].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path | None = None) -> Path:
        target = output_path or self._output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        result = self.run()
        summary = self._build_summary(result)
        try:
            result.to_parquet(target, index=False)
            target.with_suffix(".json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            return target
        except Exception:
            csv_path = target.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            csv_path.with_suffix(".json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            return csv_path
