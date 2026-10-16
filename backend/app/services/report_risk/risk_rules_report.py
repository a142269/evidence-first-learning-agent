from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _safe_read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _quantile(series: pd.Series, q: float, fallback: float) -> float:
    values = _to_numeric(series).dropna()
    if values.empty:
        return fallback
    return float(values.quantile(q))


def _clip01(series: pd.Series) -> pd.Series:
    return _to_numeric(series).fillna(0.0).clip(0.0, 1.0)


@dataclass
class RiskRuleEngine:
    project_root: Path

    def _rules_cfg_path(self) -> Path:
        return self.project_root / "configs" / "rules" / "risk_rules.yaml"

    def _model_cfg_path(self) -> Path:
        return self.project_root / "configs" / "reports" / "risk_model_report.yaml"

    def _feature_path(self) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "risk" / "risk_features.parquet"
        if parquet_path.exists():
            return parquet_path
        return parquet_path.with_suffix(".csv")

    def _load_rules_cfg(self) -> dict:
        path = self._rules_cfg_path()
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _load_model_cfg(self) -> dict:
        path = self._model_cfg_path()
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _build_thresholds(self, df: pd.DataFrame, cfg: dict, shift: int = 0) -> dict[str, float]:
        q_cfg = cfg.get("threshold_quantiles", {})
        q_night = float(q_cfg.get("night_activity_high", 0.8)) + shift / 100.0
        q_formal = float(q_cfg.get("formal_activity_low", 0.2)) - shift / 100.0
        q_stable = float(q_cfg.get("stable_partner_low", 0.2)) - shift / 100.0
        q_online = float(q_cfg.get("online_low", 0.2)) - shift / 100.0
        q_offline = float(q_cfg.get("offline_low", 0.2)) - shift / 100.0
        q_shift = float(q_cfg.get("lib_dorm_shift_high", 0.7)) + shift / 100.0
        q_night = float(np.clip(q_night, 0.5, 0.95))
        q_shift = float(np.clip(q_shift, 0.5, 0.95))
        q_formal = float(np.clip(q_formal, 0.05, 0.5))
        q_stable = float(np.clip(q_stable, 0.05, 0.5))
        q_online = float(np.clip(q_online, 0.05, 0.5))
        q_offline = float(np.clip(q_offline, 0.05, 0.5))
        return {
            "night_activity_high": _quantile(df.get("night_activity_index", pd.Series(dtype=float)), q_night, 0.7),
            "lib_dorm_shift_high": _quantile(df.get("lib_to_dorm_shift_index", pd.Series(dtype=float)), q_shift, 0.5),
            "formal_activity_low": _quantile(df.get("formal_activity_participation_count", pd.Series(dtype=float)), q_formal, 1.0),
            "stable_partner_low": _quantile(df.get("stable_copresence_partner_count", pd.Series(dtype=float)), q_stable, 1.0),
            "online_low": _quantile(df.get("online_interaction_count", pd.Series(dtype=float)), q_online, 1.0),
            "offline_low": _quantile(df.get("offline_activity_index", pd.Series(dtype=float)), q_offline, 0.3),
            "night_q": q_night,
            "shift_q": q_shift,
            "formal_q": q_formal,
            "stable_q": q_stable,
            "online_q": q_online,
            "offline_q": q_offline,
        }

    def _classify_rule_labels(self, df: pd.DataFrame, cfg: dict, shift: int = 0) -> tuple[pd.DataFrame, dict]:
        t = self._build_thresholds(df, cfg, shift=shift)
        labels_cfg = cfg.get("risk_definitions", {})
        lifestyle_hit_label = set(labels_cfg.get("lifestyle_abnormal_risk", {}).get("fusion_labels", ["节律紊乱预警型"]))
        social_hit_label = set(labels_cfg.get("social_low_integration_risk", {}).get("fusion_labels", ["低融入孤立型"]))

        out = df.copy()
        out["cond_lifestyle_label"] = out.get("lifestyle_health_final_label", "").astype(str).isin(lifestyle_hit_label).astype(int)
        out["cond_night_spike"] = (
            (out.get("night_activity_index", 0.0) >= t["night_activity_high"])
            & (out.get("night_activity_peer_pct", 0.5) >= max(t["night_q"], 0.7))
            & (out.get("night_activity_index_delta_4w", 0.0) > 0)
        ).astype(int)
        out["cond_running_decline_4w"] = (out.get("running_frequency_decline_4w", 0) >= 1).astype(int)
        out["cond_lib_dorm_shift"] = (
            (out.get("lib_to_dorm_shift_index", 0.0) >= t["lib_dorm_shift_high"])
            & (out.get("lib_to_dorm_shift_index_delta_4w", 0.0) > 0)
        ).astype(int)
        out["lifestyle_abnormal_risk"] = (
            out[["cond_lifestyle_label", "cond_night_spike", "cond_running_decline_4w", "cond_lib_dorm_shift"]].sum(axis=1) > 0
        ).astype(int)

        out["cond_social_label"] = out.get("social_life_final_label", "").astype(str).isin(social_hit_label).astype(int)
        out["cond_activity_low"] = (
            (out.get("formal_activity_participation_count", 0.0) <= t["formal_activity_low"])
            | (out.get("formal_activity_peer_pct", 0.5) <= t["formal_q"])
            | (out.get("formal_activity_participation_count_delta_4w", 0.0) < 0)
        ).astype(int)
        out["cond_stable_partner_low"] = (
            (out.get("stable_copresence_partner_count", 0.0) <= t["stable_partner_low"])
            | (out.get("stable_partner_peer_pct", 0.5) <= t["stable_q"])
        ).astype(int)
        out["cond_dual_low"] = (
            (out.get("online_interaction_count", 0.0) <= t["online_low"])
            & (out.get("offline_activity_index", 0.0) <= t["offline_low"])
        ).astype(int)
        out["social_low_integration_risk"] = (
            out[["cond_social_label", "cond_activity_low", "cond_stable_partner_low", "cond_dual_low"]].sum(axis=1) > 0
        ).astype(int)

        ratios = {
            "lifestyle_abnormal_ratio": float(out["lifestyle_abnormal_risk"].mean() if len(out) else 0.0),
            "social_low_integration_ratio": float(out["social_low_integration_risk"].mean() if len(out) else 0.0),
        }
        return out, {"thresholds": t, "ratios": ratios, "shift": shift}

    def _auto_iterate_rules(self, df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
        current, meta = self._classify_rule_labels(df, cfg, shift=0)
        ratio_l = meta["ratios"]["lifestyle_abnormal_ratio"]
        ratio_s = meta["ratios"]["social_low_integration_ratio"]
        needs = ratio_l <= 0.0 or ratio_s <= 0.0 or ratio_l >= 0.75 or ratio_s >= 0.75
        if not needs:
            meta["adjusted"] = False
            return current, meta
        shift = -10 if (ratio_l <= 0.0 or ratio_s <= 0.0) else 10
        adjusted, meta2 = self._classify_rule_labels(df, cfg, shift=shift)
        meta2["adjusted"] = True
        meta2["before"] = meta
        return adjusted, meta2

    def _factor_text(self, row: pd.Series) -> str:
        mapping = {
            "cond_lifestyle_label": "生活节律模式命中（节律紊乱预警型）",
            "cond_night_spike": "夜间活跃较历史与同群体显著升高",
            "cond_running_decline_4w": "连续4周运动频率下降",
            "cond_lib_dorm_shift": "图书馆使用向宿舍停留偏移",
            "cond_social_label": "社交模式命中（低融入孤立型）",
            "cond_activity_low": "活动参与低或近周持续走低",
            "cond_stable_partner_low": "稳定共现伙伴数偏低",
            "cond_dual_low": "线上互动与线下参与双低",
        }
        factors = [text for key, text in mapping.items() if int(row.get(key, 0)) == 1]
        if len(factors) < 3:
            fillers = [
                "低投入得分偏高",
                "学业下滑风险存在",
                "建议结合导师访谈进行复核",
            ]
            factors.extend([x for x in fillers if x not in factors])
        return json.dumps(factors[:5], ensure_ascii=False)

    def _trend_text(self, row: pd.Series) -> str:
        night_delta = float(row.get("night_activity_index_delta_4w", 0.0))
        run_delta = float(row.get("running_frequency_delta_4w", 0.0))
        formal_delta = float(row.get("formal_activity_participation_count_delta_4w", 0.0))
        if not np.isfinite(night_delta):
            night_delta = 0.0
        if not np.isfinite(run_delta):
            run_delta = 0.0
        if not np.isfinite(formal_delta):
            formal_delta = 0.0
        values = {
            "night_activity_delta_4w": round(night_delta, 4),
            "running_frequency_delta_4w": round(run_delta, 4),
            "formal_activity_delta_4w": round(formal_delta, 4),
        }
        return json.dumps(values, ensure_ascii=False)

    def _peer_compare_text(self, row: pd.Series) -> str:
        values = {
            "night_activity_peer_pct": round(float(row.get("night_activity_peer_pct", 0.5)), 4),
            "formal_activity_peer_pct": round(float(row.get("formal_activity_peer_pct", 0.5)), 4),
            "stable_partner_peer_pct": round(float(row.get("stable_partner_peer_pct", 0.5)), 4),
        }
        return json.dumps(values, ensure_ascii=False)

    def _intervention_text(self, row: pd.Series) -> str:
        """Generate intervention text: learning behavior first, then lifestyle/social."""
        advices = []
        # Primary: learning-focused intervention
        fail_score = float(row.get("fail_risk_score", 0.0) or 0.0)
        decline_score = float(row.get("academic_decline_score", 0.0) or 0.0)
        engagement_score = float(row.get("low_engagement_score", 0.0) or 0.0)
        if fail_score >= 0.5 or decline_score >= 0.5:
            advices.append("优先围绕挂科风险课程制定学业修复计划，补齐任务并增加有效学习时长")
        elif engagement_score >= 0.4:
            advices.append("建议提升到课率与课程资源利用深度，安排每周学习目标与过程反馈")
        else:
            advices.append("保持当前学习节奏，持续跟踪学业指标变化")
        # Supplementary: lifestyle/social (important but after learning)
        if int(row.get("lifestyle_abnormal_risk", 0)) == 1:
            advices.append("同步开展作息-运动联合调整，连续2周跟踪夜间活跃与运动连续性")
        if int(row.get("social_low_integration_risk", 0)) == 1:
            advices.append("安排同专业同年级同伴联结任务，提升线下参与频次以促进协作学习")
        return "；".join(advices)

    def _build_composite(self, df: pd.DataFrame, model_cfg: dict) -> tuple[pd.DataFrame, dict]:
        out = df.copy()
        # Weights: learning/academic ~90%, lifestyle/social auxiliary ~10%
        weights = model_cfg.get("composite", {}).get(
            "weights",
            {
                "academic_decline_score": 0.35,
                "fail_risk_score": 0.28,
                "low_engagement_score": 0.20,
                "lifestyle_abnormal_risk": 0.05,
                "social_low_integration_risk": 0.05,
                "status_change_factor": 0.07,
            },
        )
        score = pd.Series(0.0, index=out.index)
        for key, wt in weights.items():
            score = score + _clip01(out.get(key, 0.0)) * float(wt)
        out["composite_risk_score"] = score.clip(0.0, 1.0)

        levels = model_cfg.get("composite", {}).get(
            "levels",
            {"high": 0.70, "medium": 0.40},
        )
        high_cut = float(levels.get("high", 0.70))
        medium_cut = float(levels.get("medium", 0.40))
        out["risk_level"] = np.where(
            out["composite_risk_score"] >= high_cut,
            "high",
            np.where(out["composite_risk_score"] >= medium_cut, "medium", "low"),
        )
        level_dist = out["risk_level"].value_counts(normalize=True).to_dict()
        level_counts = out["risk_level"].value_counts().to_dict()
        missing_levels = [lv for lv in ["high", "medium", "low"] if level_counts.get(lv, 0) == 0]
        adjusted = False
        before = {"high": high_cut, "medium": medium_cut, "distribution": level_dist}
        if missing_levels or max(level_dist.values(), default=0) > 0.85:
            high_cut = float(out["composite_risk_score"].quantile(0.8))
            medium_cut = float(out["composite_risk_score"].quantile(0.5))
            out["risk_level"] = np.where(
                out["composite_risk_score"] >= high_cut,
                "high",
                np.where(out["composite_risk_score"] >= medium_cut, "medium", "low"),
            )
            adjusted = True

        out["composite_attention_risk"] = (out["risk_level"].isin(["high", "medium"])).astype(int)
        out["risk_label"] = "composite_attention_risk"
        out["risk_score"] = out["composite_risk_score"]
        out["top_factors"] = out.apply(self._factor_text, axis=1)
        out["trend_4w"] = out.apply(self._trend_text, axis=1)
        out["peer_compare"] = out.apply(self._peer_compare_text, axis=1)
        out["intervention_advice"] = out.apply(self._intervention_text, axis=1)
        return out, {"adjusted": adjusted, "before": before, "after": {"high": high_cut, "medium": medium_cut}}

    def run(self) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
        cfg = self._load_rules_cfg()
        model_cfg = self._load_model_cfg()
        features = _safe_read_table(self._feature_path())
        if features.empty:
            return pd.DataFrame(), pd.DataFrame(), {"error": "risk_features为空"}
        features["XH"] = features["XH"].astype(str)
        rules_df, rule_meta = self._auto_iterate_rules(features, cfg)
        rules_df["risk_label"] = np.where(
            rules_df["lifestyle_abnormal_risk"] + rules_df["social_low_integration_risk"] > 0,
            "risk_hit",
            "risk_clear",
        )
        rules_df["risk_level"] = np.where(
            (rules_df["lifestyle_abnormal_risk"] + rules_df["social_low_integration_risk"]) >= 2,
            "high",
            np.where((rules_df["lifestyle_abnormal_risk"] + rules_df["social_low_integration_risk"]) == 1, "medium", "low"),
        )
        rules_df["risk_score"] = (
            0.5 * rules_df["lifestyle_abnormal_risk"].astype(float) + 0.5 * rules_df["social_low_integration_risk"].astype(float)
        )
        rules_df["top_factors"] = rules_df.apply(self._factor_text, axis=1)
        rules_df["trend_4w"] = rules_df.apply(self._trend_text, axis=1)
        rules_df["peer_compare"] = rules_df.apply(self._peer_compare_text, axis=1)
        rules_df["intervention_advice"] = rules_df.apply(self._intervention_text, axis=1)
        rules_df["created_at"] = pd.Timestamp.now()

        composite_df, composite_meta = self._build_composite(rules_df, model_cfg)
        rule_cols = [
            "XH",
            "major",
            "grade",
            "lifestyle_abnormal_risk",
            "social_low_integration_risk",
            "risk_label",
            "risk_level",
            "risk_score",
            "top_factors",
            "trend_4w",
            "peer_compare",
            "intervention_advice",
            "created_at",
        ]
        comp_cols = [
            "XH",
            "major",
            "grade",
            "composite_attention_risk",
            "risk_label",
            "risk_level",
            "risk_score",
            "academic_decline_score",
            "fail_risk_score",
            "low_engagement_score",
            "lifestyle_abnormal_risk",
            "social_low_integration_risk",
            "status_change_factor",
            "top_factors",
            "trend_4w",
            "peer_compare",
            "intervention_advice",
            "created_at",
        ]
        rule_result = rules_df[[c for c in rule_cols if c in rules_df.columns]].sort_values("XH").reset_index(drop=True)
        composite_result = composite_df[[c for c in comp_cols if c in composite_df.columns]].sort_values("XH").reset_index(drop=True)
        meta = {"rule_iteration": rule_meta, "composite_iteration": composite_meta}
        return rule_result, composite_result, meta

    def save(self, rule_output_path: Path, composite_output_path: Path) -> tuple[Path, Path, dict, dict, dict]:
        rule_result, composite_result, meta = self.run()
        rule_output_path.parent.mkdir(parents=True, exist_ok=True)
        composite_output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            rule_result.to_parquet(rule_output_path, index=False)
            rule_saved = rule_output_path
        except Exception:
            rule_saved = rule_output_path.with_suffix(".csv")
            rule_result.to_csv(rule_saved, index=False, encoding="utf-8-sig")
        try:
            composite_result.to_parquet(composite_output_path, index=False)
            composite_saved = composite_output_path
        except Exception:
            composite_saved = composite_output_path.with_suffix(".csv")
            composite_result.to_csv(composite_saved, index=False, encoding="utf-8-sig")

        rule_summary = {
            "shape": [int(rule_result.shape[0]), int(rule_result.shape[1])],
            "distribution": {
                "lifestyle_abnormal_risk": rule_result["lifestyle_abnormal_risk"].value_counts(dropna=False).to_dict()
                if "lifestyle_abnormal_risk" in rule_result.columns
                else {},
                "social_low_integration_risk": rule_result["social_low_integration_risk"].value_counts(dropna=False).to_dict()
                if "social_low_integration_risk" in rule_result.columns
                else {},
                "risk_level": rule_result["risk_level"].value_counts(dropna=False).to_dict() if "risk_level" in rule_result.columns else {},
            },
            "sample": rule_result.head(3).replace({np.nan: None}).to_dict(orient="records"),
            "fields": list(rule_result.columns),
            "iteration": meta.get("rule_iteration", {}),
        }
        composite_summary = {
            "shape": [int(composite_result.shape[0]), int(composite_result.shape[1])],
            "distribution": {
                "composite_attention_risk": composite_result["composite_attention_risk"].value_counts(dropna=False).to_dict()
                if "composite_attention_risk" in composite_result.columns
                else {},
                "risk_level": composite_result["risk_level"].value_counts(dropna=False).to_dict() if "risk_level" in composite_result.columns else {},
            },
            "sample": composite_result.head(3).replace({np.nan: None}).to_dict(orient="records"),
            "fields": list(composite_result.columns),
            "iteration": meta.get("composite_iteration", {}),
        }
        return rule_saved, composite_saved, rule_summary, composite_summary, meta
