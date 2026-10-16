from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_BEHAVIOR_FUSION = (
    PROJECT_ROOT / "data" / "ads" / "pattern_results" / "learning_behavior_fusion_results.json"
)
DEFAULT_OUTCOME_FUSION = (
    PROJECT_ROOT / "data" / "ads" / "pattern_results" / "learning_outcome_fusion_results.json"
)
DEFAULT_LIFESTYLE_FUSION = (
    PROJECT_ROOT / "data" / "ads" / "pattern_results" / "lifestyle_health_fusion_results(2).json"
)
DEFAULT_SOCIAL_FUSION = (
    PROJECT_ROOT / "data" / "ads" / "pattern_results" / "social_life_fusion_results(2).json"
)
DEFAULT_COURSE_FUSION = (
    PROJECT_ROOT / "data" / "ads" / "pattern_results" / "course_exploration_fusion_results(2).json"
)

DEFAULT_BEHAVIOR_FEATURES = (
    PROJECT_ROOT / "data" / "feature_store" / "modes" / "learning_behavior_features.json"
)
DEFAULT_OUTCOME_FEATURES = (
    PROJECT_ROOT / "data" / "feature_store" / "modes" / "learning_outcome_features.json"
)

DEFAULT_OUTPUT_PARQUET = (
    PROJECT_ROOT / "data" / "feature_store" / "risk" / "risk_features.parquet"
)
DEFAULT_OUTPUT_JSON = (
    PROJECT_ROOT / "data" / "feature_store" / "risk" / "risk_features.json"
)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def normalize_student_id(value: Any) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = re.sub(r"\s+", "", text)
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text or None


def clamp01(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(lower=0.0, upper=1.0)


def percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return pd.Series(np.nan, index=series.index, dtype="float64")
    return numeric.rank(method="average", pct=True, ascending=ascending)


def warning_level_to_score(series: pd.Series) -> pd.Series:
    mapping = {"normal": 0.15, "low": 0.25, "medium": 0.60, "high": 0.90}
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.map(mapping).fillna(0.30)


def load_json_payload(path: Path) -> Any:
    if not path.exists():
        LOGGER.warning("Missing input JSON: %s", path)
        return []

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        LOGGER.warning("Empty input JSON: %s", path)
        return []

    return json.loads(text)


def payload_to_records(payload: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            return payload["records"]
        if isinstance(payload.get("data"), list):
            return payload["data"]
        if isinstance(payload.get("sample"), list):
            LOGGER.warning("Using sample records from %s because full records were not found.", path.name)
            return payload["sample"]

    LOGGER.warning("Unsupported JSON structure for %s. Returning empty records.", path.name)
    return []


def load_json_table(path: Path) -> pd.DataFrame:
    payload = load_json_payload(path)
    records = payload_to_records(payload, path)
    if not records:
        return pd.DataFrame(columns=["student_id"])

    df = pd.DataFrame(records)
    id_column = "student_id" if "student_id" in df.columns else "XH" if "XH" in df.columns else None
    if id_column is None:
        LOGGER.warning("No student id column found in %s.", path.name)
        return pd.DataFrame(columns=["student_id"])

    df["student_id"] = df[id_column].apply(normalize_student_id)
    df = df[df["student_id"].notna()].copy()
    return df


def standardize_learning_behavior_fusion(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["student_id"])

    columns = {
        "final_label": "learning_behavior_final_label",
        "mode_score": "learning_behavior_mode_score",
        "fusion_confidence": "learning_behavior_fusion_confidence",
        "rule_confidence": "learning_behavior_rule_confidence",
        "cluster_confidence": "learning_behavior_cluster_confidence",
        "risk_flag": "learning_behavior_mode_risk_flag",
        "explanation_factors": "learning_behavior_explanation_factors",
    }
    keep = ["student_id", *[col for col in columns if col in df.columns]]
    return df[keep].rename(columns=columns)


def standardize_learning_outcome_fusion(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["student_id"])

    columns = {
        "final_label": "learning_outcome_final_label",
        "mode_score": "learning_outcome_mode_score",
        "fusion_confidence": "learning_outcome_fusion_confidence",
        "rule_confidence": "learning_outcome_rule_confidence",
        "cluster_confidence": "learning_outcome_cluster_confidence",
        "risk_flag": "learning_outcome_mode_risk_flag",
        "explanation_factors": "learning_outcome_explanation_factors",
    }
    keep = ["student_id", *[col for col in columns if col in df.columns]]
    return df[keep].rename(columns=columns)


def standardize_lifestyle_fusion(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["student_id"])

    standardized = pd.DataFrame({"student_id": df["student_id"]})
    standardized["lifestyle_health_final_label"] = df.get("final_subtype_label", df.get("subtype_label"))
    standardized["lifestyle_health_mode_score"] = pd.to_numeric(
        df.get("lifestyle_health_total_score", df.get("mode_score")),
        errors="coerce",
    )
    standardized["lifestyle_health_confidence"] = pd.to_numeric(df.get("mode_confidence"), errors="coerce")
    standardized["lifestyle_health_warning_level"] = df.get("warning_level")
    standardized["lifestyle_health_explanation"] = df.get("final_explanation")
    return standardized


def standardize_social_fusion(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["student_id"])

    standardized = pd.DataFrame({"student_id": df["student_id"]})
    standardized["social_life_final_label"] = df.get("final_subtype_label", df.get("subtype_label"))
    standardized["social_life_mode_score"] = pd.to_numeric(
        df.get("social_life_total_score", df.get("mode_score")),
        errors="coerce",
    )
    standardized["social_life_confidence"] = pd.to_numeric(df.get("mode_confidence"), errors="coerce")
    standardized["social_life_warning_level"] = df.get("warning_level")
    standardized["social_isolation_index"] = pd.to_numeric(df.get("social_isolation_index"), errors="coerce")
    standardized["social_life_explanation"] = df.get("final_explanation")
    return standardized


def standardize_course_fusion(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["student_id"])

    standardized = pd.DataFrame({"student_id": df["student_id"]})
    standardized["course_exploration_final_label"] = df.get("final_label")
    standardized["course_exploration_mode_score"] = pd.to_numeric(
        df.get("course_exploration_total_score", df.get("mode_score")),
        errors="coerce",
    )
    standardized["course_exploration_confidence"] = pd.to_numeric(df.get("mode_confidence"), errors="coerce")
    standardized["course_exploration_warning_level"] = df.get("warning_level")
    standardized["course_exploration_explanation"] = df.get("top_factors")
    return standardized


def merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    merged = pd.DataFrame(columns=["student_id"])
    for frame in frames:
        if frame.empty:
            continue
        if merged.empty:
            merged = frame.copy()
        else:
            merged = merged.merge(frame, on="student_id", how="outer")
    return merged


def label_score(series: pd.Series, mapping: dict[str, float], default: float) -> pd.Series:
    return series.astype(str).str.strip().map(mapping).fillna(default)


def build_proxy_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "missing_feature_ratio" not in df.columns:
        left = pd.to_numeric(df.get("missing_feature_ratio_x"), errors="coerce")
        right = pd.to_numeric(df.get("missing_feature_ratio_y"), errors="coerce")
        if left is not None or right is not None:
            df["missing_feature_ratio"] = left.combine_first(right)

    for column in [
        "learning_behavior_score",
        "active_learning_score",
        "discussion_engagement_score",
        "library_immersion_score",
        "sign_completion_rate",
        "resource_depth",
        "video_completion_rate",
        "ddl_pressure_index",
        "slow_submit_ratio",
        "fast_submit_ratio",
        "not_done_rate",
        "learning_outcome_score",
        "learning_outcome_base_score",
        "avg_gpa",
        "fail_ratio",
        "retake_ratio",
        "credit_earn_ratio",
        "evaluation_strength_score",
        "scholarship_strength_score",
        "language_ability_score",
        "competition_strength_score",
        "rank_stability_score",
    ]:
        if column not in df.columns:
            df[column] = np.nan

    df["resource_view_count_percentile"] = percentile_rank(df.get("resource_view_count"))
    df["interaction_initiative_percentile"] = percentile_rank(df.get("interaction_initiative"))
    df["discussion_activity_percentile"] = percentile_rank(df.get("discussion_activity"))
    df["submit_delay_percentile"] = percentile_rank(df.get("avg_submit_delay_hours"))
    df["major_rank_avg_percentile"] = percentile_rank(df.get("major_rank_avg"))
    df["class_rank_avg_percentile"] = percentile_rank(df.get("class_rank_avg"))

    df["low_engagement_score"] = (
        0.35 * (1 - clamp01(df["learning_behavior_score"]).fillna(0.5))
        + 0.20 * (1 - clamp01(df["active_learning_score"]).fillna(0.5))
        + 0.15 * (1 - clamp01(df["discussion_engagement_score"]).fillna(0.5))
        + 0.15 * (1 - clamp01(df["library_immersion_score"]).fillna(0.5))
        + 0.10 * (1 - clamp01(df["sign_completion_rate"]).fillna(0.5))
        + 0.05 * clamp01(df.get("missing_feature_ratio", pd.Series(np.nan, index=df.index))).fillna(0.3)
    ).clip(0.0, 1.0)

    gpa_pressure = (1 - (pd.to_numeric(df["avg_gpa"], errors="coerce") / 4.0)).clip(0.0, 1.0).fillna(0.5)
    fail_pressure = (pd.to_numeric(df["fail_ratio"], errors="coerce") / 0.25).clip(0.0, 1.0).fillna(0.0)
    eval_decline_pressure = pd.Series(
        np.where(
            pd.to_numeric(df.get("evaluation_growth_proxy"), errors="coerce").notna(),
            ((-pd.to_numeric(df.get("evaluation_growth_proxy"), errors="coerce")) / 15.0).clip(0.0, 1.0),
            1 - clamp01(df.get("evaluation_strength_score", pd.Series(np.nan, index=df.index))).fillna(0.5),
        ),
        index=df.index,
    )
    rank_pressure = (1 - (pd.to_numeric(df["rank_stability_score"], errors="coerce") / 0.35)).clip(0.0, 1.0).fillna(0.5)

    df["academic_decline_score"] = (
        0.25 * (1 - clamp01(df["learning_outcome_score"]).fillna(0.5))
        + 0.20 * (1 - clamp01(df["learning_outcome_base_score"]).fillna(0.5))
        + 0.20 * gpa_pressure
        + 0.15 * fail_pressure
        + 0.10 * eval_decline_pressure
        + 0.10 * rank_pressure
    ).clip(0.0, 1.0)

    df["fail_risk_score"] = (
        0.30 * (pd.to_numeric(df.get("fail_ratio"), errors="coerce") / 0.30).clip(0.0, 1.0).fillna(0.0)
        + 0.25 * (pd.to_numeric(df.get("failed_course_count"), errors="coerce") / 3.0).clip(0.0, 1.0).fillna(0.0)
        + 0.15 * ((75 - pd.to_numeric(df.get("avg_course_score"), errors="coerce")) / 20.0).clip(0.0, 1.0).fillna(0.0)
        + 0.10 * ((60 - pd.to_numeric(df.get("min_course_score"), errors="coerce")) / 20.0).clip(0.0, 1.0).fillna(0.0)
        + 0.10 * (1 - clamp01(df.get("pass_ratio", pd.Series(np.nan, index=df.index))).fillna(0.8))
        + 0.10 * (pd.to_numeric(df.get("retake_ratio"), errors="coerce") / 0.15).clip(0.0, 1.0).fillna(0.0)
    ).clip(0.0, 1.0)

    lifestyle_mapping = {
        "节律紊乱预警型": 0.95,
        "晚间行为活跃型": 0.65,
        "运动不足静态型": 0.60,
        "规律活力型": 0.15,
    }
    social_mapping = {
        "低融入孤立型": 0.90,
        "线上表达型": 0.45,
        "正式参与型": 0.25,
        "高融入协同型": 0.10,
    }
    course_mapping = {
        "漂移试探型": 0.90,
        "绩点保守型": 0.60,
        "稳健深耕型": 0.25,
        "目标导向探索型": 0.15,
    }

    df["lifestyle_abnormal_score"] = (
        0.65 * label_score(df.get("lifestyle_health_final_label", pd.Series(index=df.index)), lifestyle_mapping, 0.40)
        + 0.20 * (1 - clamp01(df.get("lifestyle_health_mode_score", pd.Series(index=df.index))).fillna(0.5))
        + 0.15 * warning_level_to_score(df.get("lifestyle_health_warning_level", pd.Series(index=df.index)))
    ).clip(0.0, 1.0)

    df["social_low_integration_score"] = (
        0.45 * label_score(df.get("social_life_final_label", pd.Series(index=df.index)), social_mapping, 0.40)
        + 0.30 * clamp01(df.get("social_isolation_index", pd.Series(index=df.index))).fillna(0.5)
        + 0.15 * (1 - clamp01(df.get("social_life_mode_score", pd.Series(index=df.index))).fillna(0.5))
        + 0.10 * warning_level_to_score(df.get("social_life_warning_level", pd.Series(index=df.index)))
    ).clip(0.0, 1.0)

    df["course_exploration_misalignment_score"] = (
        0.60 * label_score(df.get("course_exploration_final_label", pd.Series(index=df.index)), course_mapping, 0.40)
        + 0.25 * (1 - clamp01(df.get("course_exploration_mode_score", pd.Series(index=df.index))).fillna(0.5))
        + 0.15 * warning_level_to_score(df.get("course_exploration_warning_level", pd.Series(index=df.index)))
    ).clip(0.0, 1.0)

    high_warning_count = (
        df.get("lifestyle_health_warning_level", pd.Series(index=df.index)).astype(str).str.lower().eq("high").astype(int)
        + df.get("social_life_warning_level", pd.Series(index=df.index)).astype(str).str.lower().eq("high").astype(int)
        + df.get("course_exploration_warning_level", pd.Series(index=df.index)).astype(str).str.lower().eq("high").astype(int)
    )
    df["status_change_factor"] = np.select(
        [high_warning_count >= 2, high_warning_count == 1],
        [1.0, 0.5],
        default=0.0,
    )

    return df


def build_field_check(df: pd.DataFrame) -> dict[str, Any]:
    field_check: dict[str, Any] = {"shape": list(df.shape), "field_coverage": {}}
    for column in sorted(df.columns):
        field_check["field_coverage"][column] = round(float(df[column].notna().mean()), 4)
    return field_check


def save_outputs(df: pd.DataFrame, parquet_path: Path, json_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df.to_parquet(parquet_path, index=False)
        LOGGER.info("Saved parquet risk features to: %s", parquet_path)
    except Exception as exc:
        LOGGER.warning("Failed to save parquet risk features: %s", exc)

    records = df.astype(object).where(pd.notna(df), None).to_dict(orient="records")
    summary = {
        "shape": list(df.shape),
        "columns": df.columns.tolist(),
        "field_check": build_field_check(df),
        "sample": records[:5],
        "records": records,
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"risk_features shape: {df.shape}")
    print(f"risk_features columns: {df.columns.tolist()}")
    print("risk_features sample:")
    print(json.dumps(summary["sample"][:3], ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified five-mode risk feature table.")
    parser.add_argument("--behavior-fusion", type=Path, default=DEFAULT_BEHAVIOR_FUSION)
    parser.add_argument("--outcome-fusion", type=Path, default=DEFAULT_OUTCOME_FUSION)
    parser.add_argument("--lifestyle-fusion", type=Path, default=DEFAULT_LIFESTYLE_FUSION)
    parser.add_argument("--social-fusion", type=Path, default=DEFAULT_SOCIAL_FUSION)
    parser.add_argument("--course-fusion", type=Path, default=DEFAULT_COURSE_FUSION)
    parser.add_argument("--behavior-features", type=Path, default=DEFAULT_BEHAVIOR_FEATURES)
    parser.add_argument("--outcome-features", type=Path, default=DEFAULT_OUTCOME_FEATURES)
    parser.add_argument("--output-parquet", type=Path, default=DEFAULT_OUTPUT_PARQUET)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()

    try:
        behavior_features = load_json_table(args.behavior_features)
        outcome_features = load_json_table(args.outcome_features)
        behavior_fusion = standardize_learning_behavior_fusion(load_json_table(args.behavior_fusion))
        outcome_fusion = standardize_learning_outcome_fusion(load_json_table(args.outcome_fusion))
        lifestyle_fusion = standardize_lifestyle_fusion(load_json_table(args.lifestyle_fusion))
        social_fusion = standardize_social_fusion(load_json_table(args.social_fusion))
        course_fusion = standardize_course_fusion(load_json_table(args.course_fusion))

        LOGGER.info("behavior_features shape: %s", behavior_features.shape)
        LOGGER.info("outcome_features shape: %s", outcome_features.shape)
        LOGGER.info("behavior_fusion shape: %s", behavior_fusion.shape)
        LOGGER.info("outcome_fusion shape: %s", outcome_fusion.shape)
        LOGGER.info("lifestyle_fusion shape: %s", lifestyle_fusion.shape)
        LOGGER.info("social_fusion shape: %s", social_fusion.shape)
        LOGGER.info("course_fusion shape: %s", course_fusion.shape)

        merged = merge_frames(
            [
                behavior_features,
                outcome_features,
                behavior_fusion,
                outcome_fusion,
                lifestyle_fusion,
                social_fusion,
                course_fusion,
            ]
        )
        merged = build_proxy_features(merged)
        save_outputs(merged, args.output_parquet, args.output_json)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to build risk features: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
