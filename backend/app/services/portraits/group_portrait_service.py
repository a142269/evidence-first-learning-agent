from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.services.portraits.individual_portrait_service import IndividualPortraitService


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


def _risk_dist(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {}
    candidate_columns = ["risk_level", "course_fail_fused_risk_level", "warning_priority"]
    for column in candidate_columns:
        if column not in df.columns:
            continue
        values = (
            df[column]
            .astype(str)
            .str.strip()
            .str.lower()
            .replace({"": pd.NA, "nan": pd.NA, "none": pd.NA, "unknown": pd.NA})
            .dropna()
        )
        if values.empty:
            continue
        distribution = values.value_counts(normalize=True).round(4).to_dict()
        if column == "risk_level" and set(distribution.keys()) == {"low"}:
            continue
        return distribution
    return {}


def _mode_dist(df: pd.DataFrame, label_col: str) -> dict[str, float]:
    if label_col not in df.columns or df.empty:
        return {}
    labels = df[label_col].fillna("未识别").astype(str).str.strip()
    labels = labels.replace({"": "未识别", "nan": "未识别", "None": "未识别"})
    return labels.value_counts(normalize=True).round(4).to_dict()


@dataclass
class GroupPortraitService:
    project_root: Path

    def _prefer_json_path(self, base_parquet_path: Path) -> Path:
        full_json_path = base_parquet_path.with_suffix(".full.json")
        if full_json_path.exists():
            return full_json_path
        json_path = base_parquet_path.with_suffix(".json")
        if json_path.exists():
            return json_path
        csv_path = base_parquet_path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
        if base_parquet_path.exists():
            return base_parquet_path
        return json_path

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

    def _output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "portraits" / "group_portraits.json"

    def _risk_feature_path(self) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "risk" / "risk_features.parquet"
        return self._prefer_json_path(parquet_path)

    def _social_feature_path(self) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "modes" / "social_life_features.parquet"
        return self._prefer_json_path(parquet_path)

    def _business_warning_path(self) -> Path:
        return self.project_root / "data" / "ads" / "business_lists" / "all_student_business_warning_list.json"

    def _load_individual(self) -> pd.DataFrame:
        df = _safe_read(self._individual_path())
        if df.empty:
            builder = IndividualPortraitService(project_root=self.project_root)
            builder.save()
            df = _safe_read(self._individual_path())
        if df.empty:
            return pd.DataFrame()
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        out["grade"] = out.get("grade", "未知年级").fillna("未知年级")
        out["major"] = out.get("major", "未提供专业").fillna("未提供专业")
        if "academy" not in out.columns:
            out["academy"] = "未提供学院信息"
        out["academy"] = out["academy"].fillna("未提供学院信息")
        if "class_name" not in out.columns:
            out["class_name"] = out["grade"].astype(str) + "-" + out["major"].astype(str) + "-默认班"
        out["class_name"] = out["class_name"].fillna(out["grade"].astype(str) + "-" + out["major"].astype(str) + "-默认班")
        risk_feature = _safe_read(self._risk_feature_path())
        if not risk_feature.empty:
            risk_feature = risk_feature.copy()
            risk_feature["XH"] = risk_feature["XH"].astype(str)
            keep_cols = [
                "XH",
                "library_activity_index",
                "online_interaction_count",
                "night_activity_index",
                "low_engagement_score",
                "social_isolation_index",
                "stable_copresence_partner_count",
            ]
            for col in keep_cols:
                if col not in risk_feature.columns:
                    risk_feature[col] = 0.0
            out = out.merge(risk_feature[keep_cols], on="XH", how="left")
        social_feature = _safe_read(self._social_feature_path())
        if not social_feature.empty:
            social_feature = social_feature.copy()
            social_feature["XH"] = social_feature["XH"].astype(str)
            keep_social_cols = ["XH", "social_circle_density", "stable_copresence_partner_count", "social_isolation_index"]
            for col in keep_social_cols:
                if col not in social_feature.columns:
                    social_feature[col] = 0.0
            out = out.merge(social_feature[keep_social_cols], on="XH", how="left", suffixes=("", "_social"))
            out["stable_copresence_partner_count"] = pd.to_numeric(
                out.get("stable_copresence_partner_count", out.get("stable_copresence_partner_count_social", 0.0)),
                errors="coerce",
            ).fillna(0.0)
            out["social_isolation_index"] = pd.to_numeric(
                out.get("social_isolation_index", out.get("social_isolation_index_social", 0.0)),
                errors="coerce",
            ).fillna(0.0)
            out["social_circle_density"] = pd.to_numeric(out.get("social_circle_density", 0.0), errors="coerce").fillna(0.0)
        business_warning = _safe_read(self._business_warning_path())
        if not business_warning.empty:
            business_warning = business_warning.copy()
            business_warning["student_id"] = business_warning.get("student_id", "").astype(str)
            keep_business_cols = [
                "student_id",
                "course_fail_fused_risk_level",
                "warning_priority",
                "primary_risk_name_cn",
                "agreement_status",
                "low_learning_engagement_risk_level",
                "task_procrastination_risk_level",
                "classroom_interaction_low_risk_level",
                "learning_resource_low_use_risk_level",
                "academic_decline_risk_level",
                "achievement_weakness_risk_level",
                "lifestyle_abnormal_risk_level",
                "social_low_integration_risk_level",
                "course_exploration_misalignment_risk_level",
            ]
            for col in keep_business_cols:
                if col not in business_warning.columns:
                    business_warning[col] = ""
            business_view = business_warning[keep_business_cols].rename(columns={"student_id": "XH"})
            out = out.merge(business_view, on="XH", how="left")
            out["course_fail_fused_risk_level"] = out.get("course_fail_fused_risk_level", "low").fillna("low")
            out["warning_priority"] = out.get("warning_priority", "low").fillna("low")
            out["primary_risk_name_cn"] = out.get("primary_risk_name_cn", "未识别风险").fillna("未识别风险")
            out["agreement_status"] = out.get("agreement_status", "unknown").fillna("unknown")
            out["cross_mode_risk_combo"] = (
                "M1:"
                + out.get("low_learning_engagement_risk_level", "low").astype(str)
                + "|M3:"
                + out.get("lifestyle_abnormal_risk_level", "low").astype(str)
                + "|M4:"
                + out.get("social_low_integration_risk_level", "low").astype(str)
                + "|M5:"
                + out.get("course_exploration_misalignment_risk_level", "low").astype(str)
            )
        numeric_cols = [
            "library_activity_index",
            "online_interaction_count",
            "night_activity_index",
            "low_engagement_score",
            "social_isolation_index",
            "stable_copresence_partner_count",
            "social_circle_density",
        ]
        for col in numeric_cols:
            out[col] = pd.to_numeric(out.get(col, 0.0), errors="coerce").fillna(0.0)
        return out

    def _aggregate_dimension(self, df: pd.DataFrame, dimension: str) -> list[dict[str, Any]]:
        if df.empty or dimension not in df.columns:
            return []
        mode_score_cols = [
            "learning_behavior_score",
            "learning_outcome_score",
            "lifestyle_health_score",
            "social_life_score",
            "course_exploration_score",
            "overall_growth_score",
        ]
        existing_scores = [c for c in mode_score_cols if c in df.columns]
        grouped = df.groupby(dimension, dropna=False)
        rows: list[dict[str, Any]] = []
        for key, part in grouped:
            item: dict[str, Any] = {
                "group_key": str(key),
                "student_count": int(len(part)),
                "risk_distribution": _risk_dist(part),
                "mode_distribution": {
                    "learning_behavior": _mode_dist(part, "learning_behavior_label"),
                    "learning_outcome": _mode_dist(part, "learning_outcome_label"),
                    "lifestyle_health": _mode_dist(part, "lifestyle_health_label"),
                    "social_life": _mode_dist(part, "social_life_label"),
                    "course_exploration": _mode_dist(part, "course_exploration_label"),
                },
            }
            for score_col in existing_scores:
                item[f"avg_{score_col}"] = float(round(pd.to_numeric(part[score_col], errors="coerce").fillna(0.0).mean(), 4))
            item["resource_utilization"] = {
                "library_activity_avg": float(round(part.get("library_activity_index", pd.Series(dtype=float)).mean(), 4)),
                "online_interaction_avg": float(round(part.get("online_interaction_count", pd.Series(dtype=float)).mean(), 4)),
            }
            rows.append(item)
        rows.sort(key=lambda x: x["student_count"], reverse=True)
        return rows

    def _anomaly_clusters(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        if df.empty:
            return []
        low_label = "低参与失衡型"
        df = df.copy()
        df["is_low_participation"] = (df.get("learning_behavior_label", "").astype(str) == low_label).astype(int)
        overall_ratio = float(df["is_low_participation"].mean())
        grouped = df.groupby("class_name", dropna=False)["is_low_participation"].agg(["mean", "count"]).reset_index()
        grouped["delta"] = grouped["mean"] - overall_ratio
        grouped = grouped[grouped["count"] >= 20].sort_values("delta", ascending=False)
        result = []
        for _, row in grouped.head(20).iterrows():
            result.append(
                {
                    "class_name": str(row["class_name"]),
                    "student_count": int(row["count"]),
                    "low_participation_ratio": float(round(row["mean"], 4)),
                    "delta_vs_overall": float(round(row["delta"], 4)),
                }
            )
        return result

    def _mode_grouping_analysis(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {"risk_common_patterns": {}, "excellence_baseline": {}}
        risk_df = df[df["risk_level"].astype(str).isin(["high", "medium"])]
        if risk_df.empty:
            risk_common = {}
        else:
            risk_common = {
                "night_activity_high_ratio": float(round((risk_df["night_activity_index"] >= risk_df["night_activity_index"].quantile(0.7)).mean(), 4)),
                "low_participation_ratio": float(round((risk_df["learning_behavior_label"].astype(str) == "低参与失衡型").mean(), 4)),
                "social_isolation_ratio": float(round((risk_df["social_life_label"].astype(str) == "低融入孤立型").mean(), 4)),
                "late_stay_ratio": float(round((risk_df["lifestyle_health_label"].astype(str).str.contains("晚间|节律", regex=True)).mean(), 4)),
            }
        excellence_df = df[df["learning_outcome_label"].astype(str) == "稳定卓越型"]
        if excellence_df.empty:
            excellence = {}
        else:
            excellence = {
                "learning_behavior_score_p50": float(round(excellence_df["learning_behavior_score"].median(), 4)),
                "library_activity_index_p50": float(round(excellence_df["library_activity_index"].median(), 4)),
                "social_circle_density_p50": float(round(excellence_df["social_circle_density"].median(), 4)),
                "night_activity_index_p50": float(round(excellence_df["night_activity_index"].median(), 4)),
            }
        return {"risk_common_patterns": risk_common, "excellence_baseline": excellence}

    def _social_topology_proxy(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {"role_distribution": {}, "isolated_hotspots": []}
        out = df.copy()
        out["topology_role"] = "普通连接型"
        out.loc[
            (out["stable_copresence_partner_count"] <= out["stable_copresence_partner_count"].quantile(0.2))
            | (out["social_isolation_index"] >= out["social_isolation_index"].quantile(0.8)),
            "topology_role",
        ] = "低融入孤立型"
        out.loc[
            (out["stable_copresence_partner_count"] >= out["stable_copresence_partner_count"].quantile(0.8))
            & (out["social_circle_density"] >= out["social_circle_density"].quantile(0.7)),
            "topology_role",
        ] = "高连接核心型"
        role_distribution = out["topology_role"].value_counts(normalize=True).round(4).to_dict()
        isolated = out[out["topology_role"] == "低融入孤立型"]
        hotspots = (
            isolated.groupby("class_name", dropna=False)["XH"]
            .count()
            .sort_values(ascending=False)
            .head(15)
            .rename("isolated_count")
            .reset_index()
        )
        isolated_hotspots = [
            {"class_name": str(row["class_name"]), "isolated_count": int(row["isolated_count"])} for _, row in hotspots.iterrows()
        ]
        return {"role_distribution": role_distribution, "isolated_hotspots": isolated_hotspots}

    def run(self) -> dict[str, Any]:
        df = self._load_individual()
        if df.empty:
            return {
                "grade_portrait": [],
                "major_portrait": [],
                "academy_portrait": [],
                "class_portrait": [],
                "risk_group_distribution": {},
                "five_mode_distribution": {},
                "meta": {"row_count": 0},
            }
        five_mode_distribution = {
            "learning_behavior": _mode_dist(df, "learning_behavior_label"),
            "learning_outcome": _mode_dist(df, "learning_outcome_label"),
            "lifestyle_health": _mode_dist(df, "lifestyle_health_label"),
            "social_life": _mode_dist(df, "social_life_label"),
            "course_exploration": _mode_dist(df, "course_exploration_label"),
        }
        resource_dashboard = {
            "by_major": [
                {
                    "major": str(k),
                    "library_activity_avg": float(round(v["library_activity_index"], 4)),
                    "online_interaction_avg": float(round(v["online_interaction_count"], 4)),
                }
                for k, v in df.groupby("major")[["library_activity_index", "online_interaction_count"]].mean().to_dict("index").items()
            ]
        }
        resource_dashboard["by_major"] = sorted(resource_dashboard["by_major"], key=lambda x: x["library_activity_avg"], reverse=True)[:30]
        output = {
            "grade_portrait": self._aggregate_dimension(df, "grade"),
            "major_portrait": self._aggregate_dimension(df, "major"),
            "academy_portrait": self._aggregate_dimension(df, "academy"),
            "class_portrait": self._aggregate_dimension(df, "class_name")[:60],
            "warning_priority_portrait": self._aggregate_dimension(df, "warning_priority"),
            "fail_risk_level_portrait": self._aggregate_dimension(df, "course_fail_fused_risk_level"),
            "primary_risk_type_portrait": self._aggregate_dimension(df, "primary_risk_name_cn")[:30],
            "agreement_status_portrait": self._aggregate_dimension(df, "agreement_status"),
            "cross_mode_risk_combo_portrait": self._aggregate_dimension(df, "cross_mode_risk_combo")[:40],
            "risk_group_distribution": _risk_dist(df),
            "five_mode_distribution": five_mode_distribution,
            "anomaly_cluster_analysis": self._anomaly_clusters(df),
            "resource_utilization_dashboard": resource_dashboard,
            "mode_grouping_analysis": self._mode_grouping_analysis(df),
            "social_topology_proxy": self._social_topology_proxy(df),
            "meta": {
                "row_count": int(len(df)),
                "created_at": str(pd.Timestamp.now()),
                "behavior_proxy_statement": "群体画像基于行为代理数据统计，不构成医学或心理诊断。",
            },
        }
        return output

    def save(self, output_path: Path | None = None) -> tuple[Path, dict[str, Any]]:
        target = output_path or self._output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        result = self.run()
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        summary = {
            "row_count": int(result.get("meta", {}).get("row_count", 0)),
            "risk_group_distribution": result.get("risk_group_distribution", {}),
            "top_grade_count": len(result.get("grade_portrait", [])),
            "top_major_count": len(result.get("major_portrait", [])),
        }
        return target, summary
