from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

try:
    from scipy.optimize import linear_sum_assignment
except Exception:  # pragma: no cover
    linear_sum_assignment = None


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_FEATURE_PATH = PROJECT_ROOT / "data" / "feature_store" / "modes" / "learning_behavior_features.json"
DEFAULT_RULE_PATH = PROJECT_ROOT / "data" / "ads" / "pattern_results" / "learning_behavior_pattern_results.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "ads" / "pattern_results" / "learning_behavior_cluster_results.json"
PATTERN_VERSION = "cluster_v2"
N_CLUSTERS = 4
RANDOM_STATE = 42

SOURCE_FEATURE_COLUMNS = [
    "learning_behavior_score",
    "active_learning_score",
    "discussion_engagement_score",
    "library_immersion_score",
    "interaction_initiative",
    "discussion_activity",
    "resource_view_count",
    "behavior_feature_count",
    "missing_feature_ratio",
    "engagement_level",
    "participation_balance",
]

MODEL_FEATURE_COLUMNS = [
    "learning_behavior_score",
    "engagement_level_code",
    "active_learning_score",
    "discussion_engagement_score",
    "library_immersion_score",
    "log_interaction_initiative",
    "log_discussion_activity",
    "log_resource_view_count",
    "completeness_score",
    "balance_classroom_task",
    "balance_discussion",
    "balance_library",
    "balance_mixed",
]

FEATURE_WEIGHTS = {
    "learning_behavior_score": 1.80,
    "engagement_level_code": 1.20,
    "active_learning_score": 1.50,
    "discussion_engagement_score": 1.35,
    "library_immersion_score": 1.10,
    "log_interaction_initiative": 1.00,
    "log_discussion_activity": 1.00,
    "log_resource_view_count": 0.55,
    "completeness_score": 0.45,
    "balance_classroom_task": 0.45,
    "balance_discussion": 0.45,
    "balance_library": 0.45,
    "balance_mixed": 0.35,
}

RULE_LABEL_ORDER = ["深度投入型", "规范执行型", "截止驱动突击型", "低参与失衡型"]
RULE_LABEL_COLUMN = "learning_behavior_type"

FEATURE_EXPLANATIONS = {
    "learning_behavior_score": ("整体学习行为综合分高", "整体学习行为综合分低"),
    "engagement_level_code": ("整体参与等级较高", "整体参与等级偏低"),
    "active_learning_score": ("课堂任务参与活跃", "课堂任务参与偏弱"),
    "discussion_engagement_score": ("讨论互动较积极", "讨论互动不足"),
    "library_immersion_score": ("图书馆学习投入较高", "图书馆学习投入较弱"),
    "log_interaction_initiative": ("课堂回应主动性较强", "课堂回应主动性偏弱"),
    "log_discussion_activity": ("讨论区活动较频繁", "讨论区活动较少"),
    "log_resource_view_count": ("学习资源访问较充分", "学习资源访问较少"),
    "completeness_score": ("行为特征覆盖较完整", "行为特征覆盖较少"),
    "balance_classroom_task": ("参与结构偏课堂任务", "参与结构不偏课堂任务"),
    "balance_discussion": ("参与结构偏讨论互动", "参与结构不偏讨论互动"),
    "balance_library": ("参与结构偏图书馆学习", "参与结构不偏图书馆学习"),
    "balance_mixed": ("多源参与较均衡", "多源参与不够均衡"),
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def normalize_column_name(column_name: object) -> str:
    text = str(column_name).strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    if text in {"studentid", "xh"}:
        return "student_id"
    return text


def normalize_student_id(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\s+", "", text)
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text or None


def load_records_json(path: Path) -> pd.DataFrame:
    empty_df = pd.DataFrame(columns=["student_id"])
    if not path.exists():
        LOGGER.warning("Input JSON not found: %s", path)
        return empty_df

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        LOGGER.warning("Input JSON is empty: %s", path)
        return empty_df

    records = json.loads(raw_text)
    if not isinstance(records, list) or not records:
        LOGGER.warning("Input JSON has no valid records: %s", path)
        return empty_df

    df = pd.DataFrame(records)
    if df.empty:
        return empty_df

    df = df.rename(columns={column: normalize_column_name(column) for column in df.columns})
    if "student_id" not in df.columns:
        LOGGER.warning("Missing student_id in: %s", path)
        df["student_id"] = pd.Series(dtype="object")

    df["student_id"] = df["student_id"].apply(normalize_student_id)
    df = df[df["student_id"].notna()].copy()
    return df


def ensure_feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    for column in SOURCE_FEATURE_COLUMNS:
        if column not in df.columns:
            LOGGER.warning("Missing feature column '%s'; filling with NaN.", column)
            df[column] = np.nan

    numeric_columns = [
        "learning_behavior_score",
        "active_learning_score",
        "discussion_engagement_score",
        "library_immersion_score",
        "interaction_initiative",
        "discussion_activity",
        "resource_view_count",
        "behavior_feature_count",
        "missing_feature_ratio",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def build_engineered_features(feature_df: pd.DataFrame) -> pd.DataFrame:
    work_df = feature_df[["student_id", *SOURCE_FEATURE_COLUMNS]].copy()
    work_df["engagement_level_code"] = work_df["engagement_level"].map({"low": 0.0, "medium": 1.0, "high": 2.0})
    work_df["log_interaction_initiative"] = np.log1p(work_df["interaction_initiative"].clip(lower=0.0))
    work_df["log_discussion_activity"] = np.log1p(work_df["discussion_activity"].clip(lower=0.0))
    work_df["log_resource_view_count"] = np.log1p(work_df["resource_view_count"].clip(lower=0.0))
    work_df["completeness_score"] = 1.0 - work_df["missing_feature_ratio"].clip(lower=0.0, upper=1.0)
    work_df["balance_classroom_task"] = (work_df["participation_balance"] == "classroom_task").astype(float)
    work_df["balance_discussion"] = (work_df["participation_balance"] == "discussion").astype(float)
    work_df["balance_library"] = (work_df["participation_balance"] == "library").astype(float)
    work_df["balance_mixed"] = (work_df["participation_balance"] == "mixed").astype(float)
    return work_df


def prepare_feature_matrix(feature_df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    feature_df = ensure_feature_columns(feature_df.copy())
    work_df = build_engineered_features(feature_df)
    imputer = SimpleImputer(strategy="median")
    imputed = imputer.fit_transform(work_df[MODEL_FEATURE_COLUMNS])
    scaler = StandardScaler()
    scaled = scaler.fit_transform(imputed)
    weight_vector = np.array([FEATURE_WEIGHTS[column] for column in MODEL_FEATURE_COLUMNS], dtype="float64")
    scaled = scaled * weight_vector
    return work_df, scaled


def compute_alignment_purity(labels: np.ndarray, rule_labels: pd.Series | None) -> float:
    if rule_labels is None:
        return 0.0
    aligned_rule_labels = pd.Series(rule_labels).reset_index(drop=True)
    valid_mask = aligned_rule_labels.notna()
    if not valid_mask.any():
        return 0.0

    label_series = pd.Series(labels).reset_index(drop=True)[valid_mask]
    rule_series = aligned_rule_labels[valid_mask]
    matched = 0
    for _, cluster_frame in pd.DataFrame({"cluster": label_series, "rule": rule_series}).groupby("cluster"):
        matched += int(cluster_frame["rule"].value_counts().max())
    return matched / max(len(rule_series), 1)


def fit_candidate_models(x_scaled: np.ndarray, rule_labels: pd.Series | None) -> tuple[str, np.ndarray, object, pd.DataFrame]:
    candidates: list[dict[str, object]] = []
    model_specs = {
        "kmeans": KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=40),
        "agglomerative": AgglomerativeClustering(n_clusters=N_CLUSTERS),
        "gmm": GaussianMixture(n_components=N_CLUSTERS, random_state=RANDOM_STATE, reg_covar=1e-6),
    }

    for name, model in model_specs.items():
        if name == "gmm":
            model.fit(x_scaled)
            labels = model.predict(x_scaled)
        else:
            labels = model.fit_predict(x_scaled)

        unique_count = len(np.unique(labels))
        silhouette = float(silhouette_score(x_scaled, labels)) if unique_count > 1 else -1.0
        counts = pd.Series(labels).value_counts(normalize=True)
        imbalance_penalty = float(max(counts.max() - (1.0 / N_CLUSTERS), 0.0))
        purity = compute_alignment_purity(labels, rule_labels) if rule_labels is not None else 0.0
        composite = (silhouette * 0.45) + (purity * 0.45) - (imbalance_penalty * 0.20)
        candidates.append(
            {
                "algorithm": name,
                "labels": labels,
                "model": model,
                "silhouette": round(silhouette, 6),
                "purity": round(purity, 6),
                "imbalance_penalty": round(imbalance_penalty, 6),
                "composite": round(composite, 6),
            }
        )

    evaluation_df = pd.DataFrame(
        [
            {
                "algorithm": item["algorithm"],
                "silhouette": item["silhouette"],
                "purity": item["purity"],
                "imbalance_penalty": item["imbalance_penalty"],
                "composite": item["composite"],
            }
            for item in candidates
        ]
    ).sort_values(["composite", "purity", "silhouette"], ascending=False)

    best_algorithm = str(evaluation_df.iloc[0]["algorithm"])
    best_candidate = next(item for item in candidates if item["algorithm"] == best_algorithm)
    return best_algorithm, np.asarray(best_candidate["labels"]), best_candidate["model"], evaluation_df


def align_clusters_to_rules(labels: np.ndarray, rule_labels: pd.Series | None) -> tuple[dict[int, str], float]:
    if rule_labels is None:
        return {int(cluster_id): f"cluster_{cluster_id}" for cluster_id in np.unique(labels)}, 0.0

    aligned_rule_labels = pd.Series(rule_labels).reset_index(drop=True)
    valid_mask = aligned_rule_labels.notna()
    if not valid_mask.any():
        return {int(cluster_id): f"cluster_{cluster_id}" for cluster_id in np.unique(labels)}, 0.0

    cluster_values = sorted(int(cluster_id) for cluster_id in np.unique(labels))
    rule_values = [label for label in RULE_LABEL_ORDER if label in set(aligned_rule_labels.dropna())]
    if not rule_values:
        return {cluster_id: f"cluster_{cluster_id}" for cluster_id in cluster_values}, 0.0

    confusion = np.zeros((len(cluster_values), len(rule_values)), dtype=int)
    valid_frame = pd.DataFrame(
        {
            "cluster": pd.Series(labels).reset_index(drop=True)[valid_mask].astype(int).to_numpy(),
            "rule": aligned_rule_labels[valid_mask].to_numpy(),
        }
    )
    for row_index, cluster_id in enumerate(cluster_values):
        cluster_frame = valid_frame[valid_frame["cluster"] == cluster_id]
        for col_index, rule_label in enumerate(rule_values):
            confusion[row_index, col_index] = int((cluster_frame["rule"] == rule_label).sum())

    mapping: dict[int, str] = {}
    if linear_sum_assignment is not None and confusion.size > 0:
        row_ind, col_ind = linear_sum_assignment(confusion.max() - confusion)
        for row_index, col_index in zip(row_ind, col_ind):
            mapping[cluster_values[row_index]] = rule_values[col_index]

    for cluster_id in cluster_values:
        if cluster_id in mapping:
            continue
        cluster_frame = valid_frame[valid_frame["cluster"] == cluster_id]
        if cluster_frame.empty:
            mapping[cluster_id] = f"cluster_{cluster_id}"
        else:
            mapping[cluster_id] = str(cluster_frame["rule"].value_counts().idxmax())

    matched = sum(
        int(
            (
                valid_frame[valid_frame["cluster"] == cluster_id]["rule"] == mapped_label
            ).sum()
        )
        for cluster_id, mapped_label in mapping.items()
        if mapped_label in rule_values
    )
    purity = matched / max(len(valid_frame), 1)
    return mapping, purity


def compute_cluster_confidence(algorithm: str, model: object, x_scaled: np.ndarray, labels: np.ndarray) -> np.ndarray:
    if algorithm == "kmeans":
        distances = model.transform(x_scaled)
        assigned = distances[np.arange(len(labels)), labels]
        row_mean = np.maximum(distances.mean(axis=1), 1e-6)
        confidence = 1.0 - (assigned / row_mean)
        return np.clip(confidence, 0.0, 1.0)

    if algorithm == "gmm":
        probabilities = model.predict_proba(x_scaled)
        return np.clip(probabilities.max(axis=1), 0.0, 1.0)

    centroids = []
    for cluster_id in sorted(np.unique(labels)):
        centroids.append(x_scaled[labels == cluster_id].mean(axis=0))
    centroid_array = np.vstack(centroids)
    centroid_map = {cluster_id: index for index, cluster_id in enumerate(sorted(np.unique(labels)))}
    assigned_centroids = centroid_array[[centroid_map[int(cluster_id)] for cluster_id in labels]]
    distances = np.linalg.norm(x_scaled - assigned_centroids, axis=1)
    scale = max(float(np.percentile(distances, 90)), 1e-6)
    confidence = 1.0 - (distances / scale)
    return np.clip(confidence, 0.0, 1.0)


def build_cluster_explanations(feature_df: pd.DataFrame, labels: np.ndarray) -> dict[int, list[str]]:
    explanation_map: dict[int, list[str]] = {}
    for cluster_id in sorted(np.unique(labels)):
        cluster_frame = feature_df.loc[labels == cluster_id, MODEL_FEATURE_COLUMNS]
        cluster_mean = cluster_frame.mean(numeric_only=True)
        overall_mean = feature_df[MODEL_FEATURE_COLUMNS].mean(numeric_only=True)
        overall_std = feature_df[MODEL_FEATURE_COLUMNS].std(numeric_only=True).replace(0, np.nan)
        z_score = ((cluster_mean - overall_mean) / overall_std).fillna(0.0)
        top_features = z_score.abs().sort_values(ascending=False).head(4).index.tolist()

        factors: list[str] = []
        for feature_name in top_features:
            positive_text, negative_text = FEATURE_EXPLANATIONS.get(feature_name, (feature_name, feature_name))
            if feature_name.startswith("balance_"):
                if z_score[feature_name] > 0:
                    factors.append(positive_text)
                continue
            factors.append(positive_text if z_score[feature_name] >= 0 else negative_text)
        explanation_map[int(cluster_id)] = factors[:3]
    return explanation_map


def merge_rule_labels(feature_df: pd.DataFrame, rule_df: pd.DataFrame) -> pd.Series | None:
    if rule_df.empty or RULE_LABEL_COLUMN not in rule_df.columns:
        LOGGER.warning("Rule label file missing or does not contain '%s'.", RULE_LABEL_COLUMN)
        return None
    merged = feature_df[["student_id"]].merge(rule_df[["student_id", RULE_LABEL_COLUMN]], on="student_id", how="left")
    return merged[RULE_LABEL_COLUMN]


def build_cluster_results(feature_df: pd.DataFrame, rule_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if feature_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    work_df, x_scaled = prepare_feature_matrix(feature_df)
    rule_labels = merge_rule_labels(work_df, rule_df)
    best_algorithm, labels, model, evaluation_df = fit_candidate_models(x_scaled, rule_labels)
    cluster_label_map, purity = align_clusters_to_rules(labels, rule_labels)
    confidence = compute_cluster_confidence(best_algorithm, model, x_scaled, labels)
    explanation_map = build_cluster_explanations(work_df, labels)
    silhouette = float(evaluation_df.loc[evaluation_df["algorithm"] == best_algorithm, "silhouette"].iloc[0])

    result_df = work_df[["student_id"]].copy()
    result_df["cluster_algorithm"] = best_algorithm
    result_df["cluster_id"] = labels.astype(int)
    result_df["cluster_label"] = result_df["cluster_id"].map(cluster_label_map)
    result_df["cluster_confidence"] = np.round(confidence, 6)
    result_df["cluster_explanation_factors"] = result_df["cluster_id"].map(explanation_map)
    result_df["cluster_silhouette_score"] = round(silhouette, 6)
    result_df["cluster_alignment_purity"] = round(purity, 6)
    result_df["pattern_version"] = PATTERN_VERSION
    result_df["generated_at"] = datetime.now().isoformat(timespec="seconds")

    if rule_df.empty:
        result_df["rule_label"] = None
    else:
        result_df = result_df.merge(
            rule_df[["student_id", RULE_LABEL_COLUMN]],
            on="student_id",
            how="left",
        ).rename(columns={RULE_LABEL_COLUMN: "rule_label"})
        result_df["alignment_match"] = result_df["cluster_label"] == result_df["rule_label"]

    return result_df, evaluation_df


def save_results_json(result_df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_ready_df = result_df.astype(object).where(pd.notna(result_df), None)
    records = json_ready_df.to_dict(orient="records")
    print(f"cluster_result_count: {len(records)}")
    print("cluster_result_preview:")
    print(json.dumps(records[:3], ensure_ascii=False, indent=2))
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
    LOGGER.info("Saved learning behavior cluster results to: %s", output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build clustering-based learning behavior pattern results.")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURE_PATH)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    try:
        feature_df = load_records_json(args.features)
        rule_df = load_records_json(args.rules)
        print(f"feature_df shape: {feature_df.shape}")
        print(f"rule_df shape: {rule_df.shape}")

        result_df, evaluation_df = build_cluster_results(feature_df, rule_df)
        if not evaluation_df.empty:
            print("algorithm_evaluation:")
            print(evaluation_df.to_string(index=False))
        if not result_df.empty:
            print("cluster_distribution:")
            print(result_df["cluster_label"].value_counts(dropna=False).to_string())
        save_results_json(result_df, args.output)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to build learning behavior clustering results: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
