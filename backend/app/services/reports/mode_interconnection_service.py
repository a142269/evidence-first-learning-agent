from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _safe_corr(left: pd.Series, right: pd.Series) -> float:
    pair = pd.DataFrame({"left": pd.to_numeric(left, errors="coerce"), "right": pd.to_numeric(right, errors="coerce")}).dropna()
    if len(pair) < 3:
        return 0.0
    if float(pair["left"].std(ddof=0)) == 0.0 or float(pair["right"].std(ddof=0)) == 0.0:
        return 0.0
    value = float(pair["left"].corr(pair["right"]))
    if not np.isfinite(value):
        return 0.0
    return value


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


@dataclass
class ModeInterconnectionService:
    project_root: Path
    min_group_n: int = 30

    def _prefer_json_path(self, base_parquet_path: Path) -> Path:
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
        return self.project_root / "data" / "ads" / "portraits" / "individual_portraits.json"

    def _risk_feature_path(self) -> Path:
        return self._prefer_json_path(self.project_root / "data" / "feature_store" / "risk" / "risk_features.parquet")

    def _lifestyle_history_path(self) -> Path:
        return self._prefer_json_path(
            self.project_root / "data" / "feature_store" / "modes" / "lifestyle_health_features_history.parquet"
        )

    def _social_history_path(self) -> Path:
        return self._prefer_json_path(self.project_root / "data" / "feature_store" / "modes" / "social_life_features_history.parquet")

    def _course_history_path(self) -> Path:
        return self._prefer_json_path(
            self.project_root / "data" / "feature_store" / "modes" / "course_exploration_features_history.parquet"
        )

    def _output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "mode_interconnection_results.json"

    def _risk_flag_output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "cross_dimension_risk_flags.json"

    def _load_individual(self) -> pd.DataFrame:
        df = _safe_read(self._individual_path())
        if df.empty:
            return pd.DataFrame()
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        score_cols = [
            "learning_behavior_score",
            "learning_outcome_score",
            "lifestyle_health_score",
            "social_life_score",
            "course_exploration_score",
        ]
        for col in score_cols:
            out[col] = pd.to_numeric(out.get(col, 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)
        return out

    def _latest_per_student(self, frame: pd.DataFrame, score_cols: list[str]) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["XH"] + score_cols)
        out = frame.copy()
        out["XH"] = out["XH"].astype(str)
        out["snapshot_date"] = pd.to_datetime(out.get("snapshot_date"), errors="coerce")
        out = out.sort_values(["XH", "snapshot_date"]).groupby("XH", as_index=False).tail(1)
        for col in score_cols:
            out[col] = pd.to_numeric(out.get(col, 0.0), errors="coerce").fillna(0.0)
        keep = ["XH"] + score_cols
        return out[keep]

    def _load_feature_view(self, portrait: pd.DataFrame) -> pd.DataFrame:
        risk = _safe_read(self._risk_feature_path())
        risk_keep = self._latest_per_student(
            risk,
            [
                "low_engagement_score",
                "night_activity_index",
                "library_activity_index",
                "academic_decline_score",
                "fail_risk_score",
            ],
        )
        lifestyle = _safe_read(self._lifestyle_history_path())
        lifestyle_keep = self._latest_per_student(
            lifestyle,
            ["running_frequency", "rhythm_volatility_index", "night_activity_index", "lifestyle_health_total_score"],
        )
        social = _safe_read(self._social_history_path())
        social_keep = self._latest_per_student(
            social,
            ["social_isolation_index", "stable_copresence_partner_count", "social_life_total_score", "online_interaction_count"],
        )
        course = _safe_read(self._course_history_path())
        course_keep = self._latest_per_student(
            course,
            ["challenge_depth_index", "prerequisite_challenge_rate", "high_risk_course_ratio", "gpa_return_rate"],
        )
        out = portrait.copy()
        for frame in [risk_keep, lifestyle_keep, social_keep, course_keep]:
            if not frame.empty:
                out = out.merge(frame, on="XH", how="left")
        numeric_cols = [
            "low_engagement_score",
            "night_activity_index",
            "library_activity_index",
            "academic_decline_score",
            "fail_risk_score",
            "running_frequency",
            "rhythm_volatility_index",
            "lifestyle_health_total_score",
            "social_isolation_index",
            "stable_copresence_partner_count",
            "social_life_total_score",
            "online_interaction_count",
            "challenge_depth_index",
            "prerequisite_challenge_rate",
            "high_risk_course_ratio",
            "gpa_return_rate",
        ]
        for col in numeric_cols:
            if col not in out.columns:
                out[col] = 0.0
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        out["rhythm_stability"] = (1.0 - out["rhythm_volatility_index"]).clip(0.0, 1.0)
        out["class_focus_proxy"] = (1.0 - out["low_engagement_score"]).clip(0.0, 1.0)
        out["recovery_speed_4w"] = (1.0 - out["academic_decline_score"]).clip(0.0, 1.0)
        out["recovery_speed_8w"] = out["gpa_return_rate"].clip(0.0, 1.0)
        out["challenge_index_m5"] = (
            0.45 * out["challenge_depth_index"] + 0.35 * out["prerequisite_challenge_rate"] + 0.20 * out["high_risk_course_ratio"]
        ).clip(0.0, 1.0)
        out["behavior_density"] = (out["library_activity_index"] * out["class_focus_proxy"]).clip(0.0, 1.0)
        out["efficiency_conversion"] = out["learning_outcome_score"] / (out["behavior_density"] + 1e-3)
        return out

    def _correlation_matrix(self, frame: pd.DataFrame) -> dict[str, Any]:
        cols = [
            "learning_behavior_score",
            "learning_outcome_score",
            "lifestyle_health_score",
            "social_life_score",
            "course_exploration_score",
        ]
        cn = {
            "learning_behavior_score": "M1_学习行为",
            "learning_outcome_score": "M2_学习成果",
            "lifestyle_health_score": "M3_身心健康",
            "social_life_score": "M4_社交生活",
            "course_exploration_score": "M5_选课探索",
        }
        corr = pd.DataFrame(0.0, index=cols, columns=cols)
        for col_i in cols:
            for col_j in cols:
                if col_i == col_j:
                    corr.loc[col_i, col_j] = 1.0
                else:
                    corr.loc[col_i, col_j] = _safe_corr(frame[col_i], frame[col_j])
        corr.index = [cn.get(x, x) for x in corr.index]
        corr.columns = [cn.get(x, x) for x in corr.columns]
        matrix = corr.round(4).to_dict()
        links = []
        for i, col_i in enumerate(cols):
            for col_j in cols[i + 1 :]:
                value = float(corr.loc[cn[col_i], cn[col_j]])
                links.append({"path": f"{cn[col_i]}↔{cn[col_j]}", "corr": round(value, 4)})
        links = sorted(links, key=lambda x: abs(x["corr"]), reverse=True)
        return {"method": "pearson", "matrix": matrix, "top_links": links[:8]}

    def _path_energy_support(self, frame: pd.DataFrame) -> dict[str, Any]:
        data = frame.dropna(subset=["rhythm_stability", "class_focus_proxy"])
        n = int(len(data))
        rho_focus = _safe_corr(data["rhythm_stability"], data["class_focus_proxy"]) if n > 2 else 0.0
        rho_m1 = _safe_corr(data["rhythm_stability"], data["learning_behavior_score"]) if n > 2 else 0.0
        return {
            "path_name": "M3->M1 精力支撑链",
            "sample_size": n,
            "is_valid": n >= self.min_group_n,
            "rho_rhythm_focus": round(rho_focus, 4),
            "rho_rhythm_m1": round(rho_m1, 4),
            "statement": "节律稳定度越高，课堂专注代理与学习行为得分越高（行为代理结论）。",
        }

    def _path_peer_effect(self, frame: pd.DataFrame) -> dict[str, Any]:
        data = frame.copy()
        if data.empty:
            return {"path_name": "M4×M1->M2 同伴效应链", "sample_size": 0, "is_valid": False}
        social_q_low = float(data["social_life_score"].quantile(0.3))
        social_q_high = float(data["social_life_score"].quantile(0.7))
        m1_mid = float(data["learning_behavior_score"].median())
        low_social = data[data["social_life_score"] <= social_q_low]
        high_social = data[data["social_life_score"] >= social_q_high]
        low_social_low_m1 = low_social[low_social["learning_behavior_score"] <= m1_mid]
        high_social_low_m1 = high_social[high_social["learning_behavior_score"] <= m1_mid]
        rec4_gap = float(high_social_low_m1["recovery_speed_4w"].mean() - low_social_low_m1["recovery_speed_4w"].mean())
        rec8_gap = float(high_social_low_m1["recovery_speed_8w"].mean() - low_social_low_m1["recovery_speed_8w"].mean())
        return {
            "path_name": "M4×M1->M2 同伴效应链",
            "sample_size": int(len(data)),
            "is_valid": int(len(low_social_low_m1) + len(high_social_low_m1)) >= self.min_group_n,
            "group_sizes": {
                "low_social_low_m1": int(len(low_social_low_m1)),
                "high_social_low_m1": int(len(high_social_low_m1)),
            },
            "recovery_gap_4w": round(rec4_gap, 4),
            "recovery_gap_8w": round(rec8_gap, 4),
            "statement": "高社交融入组在低学习行为阶段的恢复速度通常更快（4周/8周双口径）。",
        }

    def _path_motivation_drive(self, frame: pd.DataFrame) -> dict[str, Any]:
        data = frame.copy()
        if data.empty:
            return {"path_name": "M5->M1 动力驱动链", "sample_size": 0, "is_valid": False}
        low_q = float(data["challenge_index_m5"].quantile(0.33))
        high_q = float(data["challenge_index_m5"].quantile(0.67))
        data["challenge_bucket"] = np.where(
            data["challenge_index_m5"] <= low_q,
            "low",
            np.where(data["challenge_index_m5"] >= high_q, "high", "mid"),
        )
        grouped = (
            data.groupby("challenge_bucket", as_index=False)
            .agg(
                m1_mean=("learning_behavior_score", "mean"),
                focus_mean=("class_focus_proxy", "mean"),
                n=("XH", "count"),
            )
            .sort_values("challenge_bucket")
        )
        return {
            "path_name": "M5->M1 动力驱动链",
            "sample_size": int(len(data)),
            "is_valid": int(grouped["n"].sum()) >= self.min_group_n,
            "challenge_bins": grouped.to_dict("records"),
            "statement": "挑战度与投入存在分层差异，可识别志向不匹配导致的投入下降。",
        }

    def _path_efficiency_conversion(self, frame: pd.DataFrame) -> dict[str, Any]:
        data = frame.copy()
        if data.empty:
            return {"path_name": "M1->M2 效能转化链", "sample_size": 0, "is_valid": False}
        density_q = float(data["behavior_density"].quantile(0.75))
        outcome_q = float(data["learning_outcome_score"].quantile(0.4))
        ineffective = data[(data["behavior_density"] >= density_q) & (data["learning_outcome_score"] <= outcome_q)]
        rho = _safe_corr(data["behavior_density"], data["learning_outcome_score"]) if len(data) > 2 else 0.0
        return {
            "path_name": "M1->M2 效能转化链",
            "sample_size": int(len(data)),
            "is_valid": int(len(data)) >= self.min_group_n,
            "rho_density_outcome": round(rho, 4),
            "ineffective_effort_count": int(len(ineffective)),
            "ineffective_effort_ratio": float(round(len(ineffective) / max(len(data), 1), 4)),
            "statement": "行为密度可量化学习投入质量，识别无效努力代理人群。",
        }

    def _cross_dimension_flags(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame[["XH", "learning_outcome_score", "social_life_score", "lifestyle_health_score", "learning_behavior_score"]].copy()
        cond_a = (out["learning_outcome_score"] >= 0.6) & (out["social_life_score"] <= 0.2)
        cond_b = (out["learning_outcome_score"] >= 0.6) & (out["lifestyle_health_score"] <= 0.2)
        cond_c = (out["learning_behavior_score"] >= 0.6) & (out["learning_outcome_score"] <= 0.35)
        out["flag_social_hidden_risk"] = cond_a.astype(int)
        out["flag_health_hidden_risk"] = cond_b.astype(int)
        out["flag_conversion_gap"] = cond_c.astype(int)
        out["flag_score"] = out[["flag_social_hidden_risk", "flag_health_hidden_risk", "flag_conversion_gap"]].sum(axis=1)
        return out

    def run(self) -> dict[str, Any]:
        portrait = self._load_individual()
        if portrait.empty:
            return {
                "meta": {"row_count": 0, "week_granularity": "student_week", "min_group_n": self.min_group_n},
                "correlation_matrix": {},
                "key_paths": {},
                "custom_achievements": {},
                "student_profiles": {},
            }
        feature_view = self._load_feature_view(portrait)
        corr = self._correlation_matrix(feature_view)
        p1 = self._path_energy_support(feature_view)
        p2 = self._path_peer_effect(feature_view)
        p3 = self._path_motivation_drive(feature_view)
        p4 = self._path_efficiency_conversion(feature_view)
        flags = self._cross_dimension_flags(feature_view)
        student_profiles: dict[str, Any] = {}
        for _, row in flags.iterrows():
            sid = str(row["XH"])
            issues = []
            if int(row["flag_social_hidden_risk"]) == 1:
                issues.append("成果较好但社交融入偏弱")
            if int(row["flag_health_hidden_risk"]) == 1:
                issues.append("成果较好但身心节律偏弱")
            if int(row["flag_conversion_gap"]) == 1:
                issues.append("行为投入较高但成果转化偏低")
            student_profiles[sid] = {
                "cross_dimension_flag_score": int(row["flag_score"]),
                "cross_dimension_flags": issues,
            }
        domino = {
            "primary_chain_strength": {
                "M3_to_M1": p1.get("rho_rhythm_m1", 0.0),
                "M4xM1_to_M2_4w": p2.get("recovery_gap_4w", 0.0),
                "M4xM1_to_M2_8w": p2.get("recovery_gap_8w", 0.0),
                "M1_to_M2": p4.get("rho_density_outcome", 0.0),
            },
            "insight": "当驱动层维度下降时，执行层与产出层出现连锁下滑风险，应优先进行跨维联动干预。",
        }
        hidden = flags[flags["flag_score"] > 0][["XH", "flag_social_hidden_risk", "flag_health_hidden_risk", "flag_conversion_gap", "flag_score"]]
        hidden = hidden.sort_values(["flag_score", "XH"], ascending=[False, True]).head(200)
        return {
            "meta": {
                "row_count": int(len(feature_view)),
                "week_granularity": "student_week",
                "min_group_n": int(self.min_group_n),
                "recovery_window": ["4w", "8w"],
                "challenge_index_definition": "0.45*challenge_depth_index + 0.35*prerequisite_challenge_rate + 0.20*high_risk_course_ratio",
            },
            "correlation_matrix": corr,
            "key_paths": {
                "energy_support_chain": p1,
                "peer_effect_chain": p2,
                "motivation_drive_chain": p3,
                "efficiency_conversion_chain": p4,
            },
            "custom_achievements": {
                "domino_effect_dashboard": domino,
                "cross_dimension_risk_detector": {
                    "flagged_student_count": int(len(hidden)),
                    "top_flagged_students": hidden.to_dict("records"),
                },
            },
            "student_profiles": student_profiles,
        }

    def save(self, output_path: Path | None = None, flag_output_path: Path | None = None) -> tuple[Path, Path, dict[str, Any]]:
        result = self.run()
        target = output_path or self._output_path()
        flag_target = flag_output_path or self._risk_flag_output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        flag_target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        flags_payload = {
            "meta": result.get("meta", {}),
            "cross_dimension_risk_detector": result.get("custom_achievements", {}).get("cross_dimension_risk_detector", {}),
            "student_profiles": result.get("student_profiles", {}),
        }
        flag_target.write_text(json.dumps(flags_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        summary = {
            "row_count": int(result.get("meta", {}).get("row_count", 0)),
            "flagged_student_count": int(
                result.get("custom_achievements", {}).get("cross_dimension_risk_detector", {}).get("flagged_student_count", 0)
            ),
            "output_files": [str(target), str(flag_target)],
        }
        return target, flag_target, summary
