from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


def _safe_read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _norm(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    min_v = values.min(skipna=True)
    max_v = values.max(skipna=True)
    if pd.isna(min_v) or pd.isna(max_v) or min_v == max_v:
        return pd.Series(0.0, index=values.index)
    return ((values - min_v) / (max_v - min_v)).fillna(0.0)


def _safe_silhouette(x_scaled: np.ndarray, labels: np.ndarray) -> float:
    try:
        if len(np.unique(labels)) <= 1 or len(labels) <= len(np.unique(labels)):
            return -1.0
        return float(silhouette_score(x_scaled, labels))
    except Exception:
        return -1.0


@dataclass
class LifestyleHealthPatternClusterer:
    project_root: Path
    n_clusters: int = 4

    @property
    def core_features(self) -> list[str]:
        return [
            "lifestyle_health_total_score",
            "physical_test_total_score",
            "fitness_base_index",
            "pe_course_completion_rate",
            "running_frequency",
            "continuous_missed_exercise_weeks",
            "exercise_continuity_index",
            "night_activity_index",
            "circadian_entropy",
            "day_night_activity_ratio",
            "dorm_stay_ratio",
            "lib_to_dorm_shift_index",
            "activity_radius_index",
            "rhythm_volatility_index",
        ]

    def _feature_path(self) -> Path:
        p = self.project_root / "data" / "feature_store" / "modes" / "lifestyle_health_features.parquet"
        return p if p.exists() else p.with_suffix(".csv")

    def _cluster_output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "lifestyle_health_cluster_results.parquet"

    def _prepare(self) -> tuple[pd.DataFrame, np.ndarray]:
        raw = _safe_read(self._feature_path())
        if raw.empty:
            return pd.DataFrame(), np.empty((0, 0))
        data = raw.copy()
        for col in self.core_features:
            if col not in data.columns:
                data[col] = 0.0
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(data[self.core_features].values)
        return data, x_scaled

    def _evaluate_models(self, x_scaled: np.ndarray) -> tuple[str, np.ndarray, np.ndarray, dict]:
        eval_scores: dict[str, float] = {}
        labels_map: dict[str, np.ndarray] = {}
        confidence_map: dict[str, np.ndarray] = {}

        kmeans = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=20)
        k_labels = kmeans.fit_predict(x_scaled)
        eval_scores["kmeans"] = _safe_silhouette(x_scaled, k_labels)
        labels_map["kmeans"] = k_labels
        dist = kmeans.transform(x_scaled)
        min_dist = dist[np.arange(len(x_scaled)), k_labels]
        confidence_map["kmeans"] = np.exp(-min_dist / (np.std(min_dist) + 1e-6))

        agg = AgglomerativeClustering(n_clusters=self.n_clusters, linkage="ward")
        a_labels = agg.fit_predict(x_scaled)
        eval_scores["agglomerative"] = _safe_silhouette(x_scaled, a_labels)
        labels_map["agglomerative"] = a_labels
        a_conf = np.zeros(len(x_scaled))
        for c in np.unique(a_labels):
            idx = np.where(a_labels == c)[0]
            center = x_scaled[idx].mean(axis=0)
            d = np.linalg.norm(x_scaled[idx] - center, axis=1)
            a_conf[idx] = np.exp(-d / (np.std(d) + 1e-6))
        confidence_map["agglomerative"] = a_conf

        gmm = GaussianMixture(n_components=self.n_clusters, random_state=42)
        gmm.fit(x_scaled)
        g_labels = gmm.predict(x_scaled)
        eval_scores["gmm"] = _safe_silhouette(x_scaled, g_labels)
        labels_map["gmm"] = g_labels
        confidence_map["gmm"] = gmm.predict_proba(x_scaled).max(axis=1)

        best_model = max(eval_scores.items(), key=lambda x: x[1])[0]
        return best_model, labels_map[best_model], confidence_map[best_model], eval_scores

    def _map_cluster_to_subtype(self, data: pd.DataFrame, cluster_ids: np.ndarray) -> dict[int, str]:
        tmp = data.copy()
        tmp["_cluster"] = cluster_ids
        center = tmp.groupby("_cluster")[[
            "lifestyle_health_total_score",
            "running_frequency",
            "continuous_missed_exercise_weeks",
            "night_activity_index",
            "circadian_entropy",
            "dorm_stay_ratio",
            "lib_to_dorm_shift_index",
            "rhythm_volatility_index",
        ]].mean()
        energy = center["lifestyle_health_total_score"] + 0.4 * center["running_frequency"] - 0.6 * center["night_activity_index"]
        warning = center["circadian_entropy"] + 0.8 * center["rhythm_volatility_index"] + 0.5 * center["lib_to_dorm_shift_index"] - 0.4 * center["lifestyle_health_total_score"]
        low_ex = center["continuous_missed_exercise_weeks"] + 0.6 * center["dorm_stay_ratio"] - 0.5 * center["running_frequency"]
        night = center["night_activity_index"] + 0.5 * center["circadian_entropy"] - 0.3 * center["running_frequency"]
        mapping: dict[int, str] = {}
        warning_cluster = int(warning.idxmax())
        mapping[warning_cluster] = "rhythm_disorder_warning"
        remain = [c for c in center.index if c not in mapping]
        vitality_cluster = int(energy.loc[remain].idxmax())
        mapping[vitality_cluster] = "regular_vitality"
        remain = [c for c in center.index if c not in mapping]
        low_ex_cluster = int(low_ex.loc[remain].idxmax())
        mapping[low_ex_cluster] = "low_exercise_static"
        remain = [c for c in center.index if c not in mapping]
        if remain:
            night_cluster = int(night.loc[remain].idxmax())
            mapping[night_cluster] = "late_schedule_active"
        return mapping

    def _explain_factors(self, row: pd.Series) -> list[str]:
        factors = {
            "lifestyle_health_total_score": float(row.get("lifestyle_health_total_score", 0.0)),
            "running_frequency": float(row.get("running_frequency", 0.0)),
            "night_activity_index": float(row.get("night_activity_index", 0.0)),
            "circadian_entropy": float(row.get("circadian_entropy", 0.0)),
            "continuous_missed_exercise_weeks": float(row.get("continuous_missed_exercise_weeks", 0.0)),
            "rhythm_volatility_index": float(row.get("rhythm_volatility_index", 0.0)),
        }
        return [k for k, _ in sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:3]]

    def run(self) -> tuple[pd.DataFrame, dict]:
        data, x_scaled = self._prepare()
        if data.empty:
            return pd.DataFrame(), {}
        best_model, labels, confidence, eval_scores = self._evaluate_models(x_scaled)
        mapping = self._map_cluster_to_subtype(data, labels)
        result = data.copy()
        result["cluster_model"] = best_model
        result["cluster_id"] = labels.astype(int)
        result["cluster_subtype_key"] = result["cluster_id"].map(mapping)
        label_cn_map = {
            "regular_vitality": "规律活力型",
            "late_schedule_active": "晚间行为活跃型",
            "low_exercise_static": "运动不足静态型",
            "rhythm_disorder_warning": "节律紊乱预警型",
        }
        result["cluster_subtype_label"] = result["cluster_subtype_key"].map(label_cn_map).fillna("晚间行为活跃型")
        result["cluster_confidence"] = np.clip(confidence, 0.0, 1.0)
        result["mode_key"] = "lifestyle_health"
        result["mode_name"] = "生活节律与运动健康模式"
        result["cluster_explain_factors"] = result.apply(self._explain_factors, axis=1)
        result["created_at"] = pd.Timestamp.now()
        cols = [
            "XH", "mode_key", "mode_name", "cluster_model", "cluster_id",
            "cluster_subtype_key", "cluster_subtype_label", "cluster_confidence",
            "lifestyle_health_total_score", "night_activity_index", "circadian_entropy",
            "running_frequency", "continuous_missed_exercise_weeks", "rhythm_volatility_index",
            "cluster_explain_factors", "created_at",
        ]
        summary = {
            "best_model": best_model,
            "model_scores": eval_scores,
            "cluster_distribution": result["cluster_subtype_label"].value_counts(dropna=False).to_dict(),
        }
        return result[cols].sort_values("XH").reset_index(drop=True), summary

    def save(self, output_path: Path | None = None) -> tuple[Path, dict]:
        target = output_path or self._cluster_output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        result, summary = self.run()
        if result.empty:
            json_path = target.with_suffix(".json")
            json_path.write_text("[]", encoding="utf-8")
            return json_path, summary
        try:
            result.to_parquet(target, index=False)
            result.to_json(target.with_suffix(".json"), orient="records", force_ascii=False)
            return target, summary
        except Exception:
            csv_path = target.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            result.to_json(target.with_suffix(".json"), orient="records", force_ascii=False)
            return csv_path, summary


@dataclass
class SocialLifePatternClusterer:
    project_root: Path
    n_clusters: int = 4

    @property
    def core_features(self) -> list[str]:
        return [
            "social_life_total_score",
            "formal_activity_participation_count",
            "formal_activity_frequency",
            "activity_signin_rate",
            "online_interaction_count",
            "post_reply_activity",
            "online_expression_ratio",
            "stable_copresence_partner_count",
            "social_diversity_index",
            "multi_scene_engagement_index",
            "offline_online_balance_index",
            "social_isolation_index",
        ]

    def _feature_path(self) -> Path:
        p = self.project_root / "data" / "feature_store" / "modes" / "social_life_features.parquet"
        return p if p.exists() else p.with_suffix(".csv")

    def _cluster_output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "social_life_cluster_results.parquet"

    def _prepare(self) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
        raw = _safe_read(self._feature_path())
        if raw.empty:
            return pd.DataFrame(), pd.DataFrame(), np.empty((0, 0))
        data = raw.copy()
        for col in self.core_features:
            if col not in data.columns:
                data[col] = 0.0
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)
        x = data[self.core_features].copy()
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x.values)
        x_scaled_df = pd.DataFrame(x_scaled, columns=self.core_features, index=data.index)
        return data, x_scaled_df, x_scaled

    def _evaluate_models(self, x_scaled: np.ndarray) -> tuple[str, np.ndarray, np.ndarray, dict]:
        eval_scores: dict[str, float] = {}
        label_map: dict[str, np.ndarray] = {}
        conf_map: dict[str, np.ndarray] = {}

        kmeans = KMeans(n_clusters=self.n_clusters, random_state=42, n_init=20)
        k_labels = kmeans.fit_predict(x_scaled)
        eval_scores["kmeans"] = float(silhouette_score(x_scaled, k_labels))
        label_map["kmeans"] = k_labels
        dist = kmeans.transform(x_scaled)
        min_dist = dist[np.arange(len(x_scaled)), k_labels]
        conf_map["kmeans"] = np.exp(-min_dist / (np.std(min_dist) + 1e-6))

        agg = AgglomerativeClustering(n_clusters=self.n_clusters, linkage="ward")
        a_labels = agg.fit_predict(x_scaled)
        eval_scores["agglomerative"] = float(silhouette_score(x_scaled, a_labels))
        label_map["agglomerative"] = a_labels
        a_conf = np.zeros(len(x_scaled))
        for c in np.unique(a_labels):
            idx = np.where(a_labels == c)[0]
            center = x_scaled[idx].mean(axis=0)
            d = np.linalg.norm(x_scaled[idx] - center, axis=1)
            a_conf[idx] = np.exp(-d / (np.std(d) + 1e-6))
        conf_map["agglomerative"] = a_conf

        gmm = GaussianMixture(n_components=self.n_clusters, random_state=42)
        gmm.fit(x_scaled)
        g_labels = gmm.predict(x_scaled)
        eval_scores["gmm"] = float(silhouette_score(x_scaled, g_labels))
        label_map["gmm"] = g_labels
        conf_map["gmm"] = gmm.predict_proba(x_scaled).max(axis=1)

        best = max(eval_scores.items(), key=lambda x: x[1])[0]
        return best, label_map[best], conf_map[best], eval_scores

    def _map_cluster_to_subtype(self, data: pd.DataFrame, cluster_ids: np.ndarray) -> dict[int, str]:
        tmp = data.copy()
        tmp["_cluster"] = cluster_ids
        center = tmp.groupby("_cluster")[[
            "social_life_total_score",
            "formal_activity_participation_count",
            "activity_signin_rate",
            "online_interaction_count",
            "online_expression_ratio",
            "stable_copresence_partner_count",
            "multi_scene_engagement_index",
            "social_isolation_index",
        ]].mean()

        high_score = center["social_life_total_score"] + 0.5 * center["stable_copresence_partner_count"] + 0.3 * center["multi_scene_engagement_index"] - 0.8 * center["social_isolation_index"]
        low_score = center["social_isolation_index"] - 0.6 * center["social_life_total_score"]
        online_score = center["online_interaction_count"] + 0.8 * center["online_expression_ratio"] - 0.3 * center["stable_copresence_partner_count"]
        mapping: dict[int, str] = {}
        low_cluster = int(low_score.idxmax())
        mapping[low_cluster] = "low_integration_isolated"
        high_cluster = int(high_score.drop(index=low_cluster).idxmax())
        mapping[high_cluster] = "high_integration_collaborative"
        rem = [c for c in center.index.tolist() if c not in mapping]
        online_cluster = int(online_score.loc[rem].idxmax())
        mapping[online_cluster] = "online_expression"
        rem = [c for c in center.index.tolist() if c not in mapping]
        if rem:
            mapping[int(rem[0])] = "formal_participation"
        return mapping

    def _explain_factors(self, row: pd.Series) -> list[str]:
        factors = {
            "formal_activity_participation_count": float(row.get("formal_activity_participation_count", 0.0)),
            "online_interaction_count": float(row.get("online_interaction_count", 0.0)),
            "stable_copresence_partner_count": float(row.get("stable_copresence_partner_count", 0.0)),
            "social_isolation_index": float(row.get("social_isolation_index", 0.0)),
            "multi_scene_engagement_index": float(row.get("multi_scene_engagement_index", 0.0)),
            "offline_online_balance_index": float(row.get("offline_online_balance_index", 0.0)),
        }
        top = sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        return [name for name, _ in top]

    def run(self) -> tuple[pd.DataFrame, dict]:
        data, _, x_scaled = self._prepare()
        if data.empty:
            return pd.DataFrame(), {}
        best_model, labels, confidence, eval_scores = self._evaluate_models(x_scaled)
        mapping = self._map_cluster_to_subtype(data, labels)

        result = data.copy()
        result["cluster_model"] = best_model
        result["cluster_id"] = labels.astype(int)
        result["cluster_subtype_key"] = result["cluster_id"].map(mapping)
        label_cn_map = {
            "high_integration_collaborative": "高融入协同型",
            "formal_participation": "正式参与型",
            "online_expression": "线上表达型",
            "low_integration_isolated": "低融入孤立型",
        }
        result["cluster_subtype_label"] = result["cluster_subtype_key"].map(label_cn_map).fillna("正式参与型")
        result["cluster_confidence"] = np.clip(confidence, 0.0, 1.0)
        result["mode_key"] = "social_life"
        result["mode_name"] = "社交生活模式"
        result["cluster_explain_factors"] = result.apply(self._explain_factors, axis=1)
        result["created_at"] = pd.Timestamp.now()

        cols = [
            "XH", "mode_key", "mode_name", "cluster_model", "cluster_id",
            "cluster_subtype_key", "cluster_subtype_label", "cluster_confidence",
            "social_life_total_score", "formal_activity_participation_count",
            "online_interaction_count", "stable_copresence_partner_count",
            "social_isolation_index", "cluster_explain_factors", "created_at",
        ]
        summary = {
            "best_model": best_model,
            "model_scores": eval_scores,
            "cluster_distribution": result["cluster_subtype_label"].value_counts().to_dict(),
        }
        return result[cols].sort_values("XH").reset_index(drop=True), summary

    def save(self, output_path: Path | None = None) -> tuple[Path, dict]:
        target = output_path or self._cluster_output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        result, summary = self.run()
        if result.empty:
            json_path = target.with_suffix(".json")
            json_path.write_text("[]", encoding="utf-8")
            return json_path, summary
        try:
            result.to_parquet(target, index=False)
            json_path = target.with_suffix(".json")
            result.to_json(json_path, orient="records", force_ascii=False)
            return target, summary
        except Exception:
            csv_path = target.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            json_path = target.with_suffix(".json")
            result.to_json(json_path, orient="records", force_ascii=False)
            return csv_path, summary


@dataclass
class CourseExplorationPatternClusterer:
    project_root: Path
    n_clusters: int = 4

    @property
    def core_features(self) -> list[str]:
        return [
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
        ]

    @property
    def cn_feature_map(self) -> dict[str, str]:
        return {
            "course_exploration_total_score": "选课探索总分",
            "cross_discipline_course_ratio": "跨学科选课比例",
            "course_planning_proactivity": "选课规划主动性",
            "retake_dependency_ratio": "重修依赖度",
            "assessment_preference_index": "考核方式偏好",
            "high_risk_course_ratio": "高风险课程占比",
            "course_exploration_breadth": "课程探索广度",
            "major_drift_trajectory": "专业偏移轨迹",
            "gpa_return_rate": "绩点回报率",
            "challenge_depth_index": "课程挑战深度",
            "prerequisite_challenge_rate": "先修挑战率",
            "extension_improvement_ratio": "拓展提高课程占比",
            "professional_loyalty_index": "专业忠诚度",
            "late_selection_ratio": "晚选课占比",
        }

    def _feature_path(self) -> Path:
        p = self.project_root / "data" / "feature_store" / "modes" / "course_exploration_features.parquet"
        return p if p.exists() else p.with_suffix(".csv")

    def _cluster_output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "course_exploration_cluster_results.parquet"

    def _prepare(self) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
        raw = _safe_read(self._feature_path())
        if raw.empty:
            return pd.DataFrame(), pd.DataFrame(), np.empty((0, 0))
        data = raw.copy()
        for col in self.core_features:
            if col not in data.columns:
                data[col] = 0.0
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)
        x = data[self.core_features].copy()
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x.values)
        x_scaled_df = pd.DataFrame(x_scaled, columns=self.core_features, index=data.index)
        return data, x_scaled_df, x_scaled

    def _evaluate_models(self, x_scaled: np.ndarray) -> tuple[str, np.ndarray, np.ndarray, dict]:
        cluster_num = min(max(2, self.n_clusters), max(2, len(x_scaled) - 1))
        eval_scores: dict[str, float] = {}
        label_map: dict[str, np.ndarray] = {}
        conf_map: dict[str, np.ndarray] = {}

        kmeans = KMeans(n_clusters=cluster_num, random_state=42, n_init=20)
        k_labels = kmeans.fit_predict(x_scaled)
        eval_scores["kmeans"] = _safe_silhouette(x_scaled, k_labels)
        label_map["kmeans"] = k_labels
        dist = kmeans.transform(x_scaled)
        min_dist = dist[np.arange(len(x_scaled)), k_labels]
        conf_map["kmeans"] = np.exp(-min_dist / (np.std(min_dist) + 1e-6))

        agg = AgglomerativeClustering(n_clusters=cluster_num, linkage="ward")
        a_labels = agg.fit_predict(x_scaled)
        eval_scores["agglomerative"] = _safe_silhouette(x_scaled, a_labels)
        label_map["agglomerative"] = a_labels
        a_conf = np.zeros(len(x_scaled))
        for c in np.unique(a_labels):
            idx = np.where(a_labels == c)[0]
            center = x_scaled[idx].mean(axis=0)
            d = np.linalg.norm(x_scaled[idx] - center, axis=1)
            a_conf[idx] = np.exp(-d / (np.std(d) + 1e-6))
        conf_map["agglomerative"] = a_conf

        gmm = GaussianMixture(n_components=cluster_num, random_state=42)
        gmm.fit(x_scaled)
        g_labels = gmm.predict(x_scaled)
        eval_scores["gmm"] = _safe_silhouette(x_scaled, g_labels)
        label_map["gmm"] = g_labels
        conf_map["gmm"] = gmm.predict_proba(x_scaled).max(axis=1)

        best = max(eval_scores.items(), key=lambda x: x[1])[0]
        return best, label_map[best], conf_map[best], eval_scores

    def _map_cluster_to_subtype(self, data: pd.DataFrame, cluster_ids: np.ndarray) -> dict[int, str]:
        tmp = data.copy()
        tmp["_cluster"] = cluster_ids
        center = tmp.groupby("_cluster")[[
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
        ]].mean()
        target_score = (
            center["cross_discipline_course_ratio"]
            + center["challenge_depth_index"]
            + center["prerequisite_challenge_rate"]
            + center["extension_improvement_ratio"]
            + 0.5 * center["course_planning_proactivity"]
            - 0.3 * center["major_drift_trajectory"]
        )
        stable_score = (
            center["professional_loyalty_index"]
            + center["gpa_return_rate"]
            + (1 - center["major_drift_trajectory"])
            + (1 - center["retake_dependency_ratio"])
        )
        conservative_score = (
            center["assessment_preference_index"]
            + (1 - center["high_risk_course_ratio"])
            + center["gpa_return_rate"]
            + (1 - center["challenge_depth_index"])
        )
        drifting_score = (
            center["major_drift_trajectory"]
            + center["late_selection_ratio"]
            + center["retake_dependency_ratio"]
            + 0.4 * center["cross_discipline_course_ratio"]
            - 0.3 * center["course_planning_proactivity"]
        )

        label_scores = {
            "target_oriented_explorer": target_score,
            "stable_deepening": stable_score,
            "gpa_conservative": conservative_score,
            "drifting_probe": drifting_score,
        }
        mapping: dict[int, str] = {}
        used_cluster: set[int] = set()
        for label, score_series in sorted(label_scores.items(), key=lambda item: item[1].max(), reverse=True):
            for cluster_id in score_series.sort_values(ascending=False).index.tolist():
                if int(cluster_id) not in used_cluster:
                    mapping[int(cluster_id)] = label
                    used_cluster.add(int(cluster_id))
                    break
        remaining_clusters = [int(c) for c in center.index.tolist() if int(c) not in used_cluster]
        fallback_labels = [lab for lab in ["stable_deepening", "target_oriented_explorer", "gpa_conservative", "drifting_probe"] if lab not in mapping.values()]
        for idx, cluster_id in enumerate(remaining_clusters):
            mapping[cluster_id] = fallback_labels[idx % len(fallback_labels)] if fallback_labels else "stable_deepening"
        return mapping

    def _explain_factors(self, scaled_row: pd.Series) -> list[str]:
        top = scaled_row.abs().sort_values(ascending=False).head(3).index.tolist()
        return [self.cn_feature_map.get(name, name) for name in top]

    def _rebalance_labels(self, data: pd.DataFrame, labels: pd.Series) -> pd.Series:
        if len(data) < 20:
            return labels
        adjusted = labels.copy()
        ratio = adjusted.value_counts(normalize=True)
        target_min = max(6, int(len(data) * 0.06))
        target_max = int(len(data) * 0.65)
        score_map = {
            "target_oriented_explorer": (
                _norm(data["cross_discipline_course_ratio"])
                + _norm(data["challenge_depth_index"])
                + _norm(data["prerequisite_challenge_rate"])
            ),
            "stable_deepening": (
                _norm(data["professional_loyalty_index"])
                + _norm(data["gpa_return_rate"])
                + (1 - _norm(data["major_drift_trajectory"]))
            ),
            "gpa_conservative": (
                _norm(data["assessment_preference_index"])
                + (1 - _norm(data["high_risk_course_ratio"]))
                + _norm(data["gpa_return_rate"])
            ),
            "drifting_probe": (
                _norm(data["major_drift_trajectory"])
                + _norm(data["late_selection_ratio"])
                + _norm(data["retake_dependency_ratio"])
            ),
        }
        for key in ["target_oriented_explorer", "stable_deepening", "drifting_probe", "gpa_conservative"]:
            current_count = int((adjusted == key).sum())
            if current_count >= target_min:
                continue
            need = target_min - current_count
            changed = 0
            for idx in score_map[key].sort_values(ascending=False).index.tolist():
                if adjusted.loc[idx] == key:
                    continue
                adjusted.loc[idx] = key
                changed += 1
                if changed >= need:
                    break
        counts = adjusted.value_counts()
        dominant_label = counts.idxmax()
        dominant_count = int(counts.max())
        if dominant_count > target_max:
            overflow = dominant_count - target_max
            for key in ["target_oriented_explorer", "stable_deepening", "drifting_probe", "gpa_conservative"]:
                if key == dominant_label:
                    continue
                need = max(0, target_min - int((adjusted == key).sum()))
                transfer = max(need, overflow // 3)
                if transfer <= 0:
                    continue
                candidates = score_map[key].sort_values(ascending=False).index.tolist()
                moved = 0
                for idx in candidates:
                    if adjusted.loc[idx] != dominant_label:
                        continue
                    adjusted.loc[idx] = key
                    moved += 1
                    overflow -= 1
                    if moved >= transfer or overflow <= 0:
                        break
                if overflow <= 0:
                    break
        return adjusted

    def _build_summary(self, result: pd.DataFrame, eval_scores: dict) -> dict:
        if result.empty:
            return {"shape": [0, 0], "distribution": {}, "sample": [], "model_scores": eval_scores}
        return {
            "shape": [int(result.shape[0]), int(result.shape[1])],
            "distribution": result["cluster_label"].value_counts(dropna=False).to_dict(),
            "model_scores": eval_scores,
            "sample": result.head(3).replace({np.nan: None}).to_dict(orient="records"),
        }

    def run(self) -> tuple[pd.DataFrame, dict]:
        data, x_scaled_df, x_scaled = self._prepare()
        if data.empty:
            return pd.DataFrame(), {}
        best_model, labels, confidence, eval_scores = self._evaluate_models(x_scaled)
        mapping = self._map_cluster_to_subtype(data, labels)
        result = data.copy()
        result["cluster_model"] = best_model
        result["cluster_id"] = labels.astype(int)
        result["cluster_subtype_key"] = result["cluster_id"].map(mapping)
        result["cluster_subtype_key"] = self._rebalance_labels(data, result["cluster_subtype_key"].astype(str))
        label_cn_map = {
            "target_oriented_explorer": "目标导向探索型",
            "stable_deepening": "稳健深耕型",
            "gpa_conservative": "绩点保守型",
            "drifting_probe": "漂移试探型",
        }
        result["cluster_label"] = result["cluster_subtype_key"].map(label_cn_map).fillna("稳健深耕型")
        result["cluster_confidence"] = np.clip(confidence, 0.0, 1.0)
        result["mode_key"] = "course_exploration"
        result["mode_name"] = "选课探索模式"
        result["cluster_top_factors"] = [self._explain_factors(x_scaled_df.iloc[i]) for i in range(len(result))]
        result["created_at"] = pd.Timestamp.now()
        cols = [
            "XH",
            "mode_key",
            "mode_name",
            "cluster_model",
            "cluster_id",
            "cluster_subtype_key",
            "cluster_label",
            "cluster_confidence",
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
            "cluster_top_factors",
            "created_at",
        ]
        result = result[cols].sort_values("XH").reset_index(drop=True)
        summary = self._build_summary(result, eval_scores)
        return result, summary

    def save(self, output_path: Path | None = None) -> tuple[Path, dict]:
        target = output_path or self._cluster_output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        result, summary = self.run()
        try:
            result.to_parquet(target, index=False)
            target.with_suffix(".json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            return target, summary
        except Exception:
            csv_path = target.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            csv_path.with_suffix(".json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            return csv_path, summary
