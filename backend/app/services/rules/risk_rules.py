from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_FEATURES_PATH = (
    PROJECT_ROOT / "data" / "feature_store" / "risk" / "risk_features.parquet"
)
DEFAULT_FEATURES_JSON_PATH = (
    PROJECT_ROOT / "data" / "feature_store" / "risk" / "risk_features.json"
)
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "rules" / "risk_rules.yaml"
DEFAULT_RULE_OUTPUT = (
    PROJECT_ROOT / "data" / "ads" / "risk_warnings" / "risk_rule_results.parquet"
)
DEFAULT_RULE_JSON = (
    PROJECT_ROOT / "data" / "ads" / "risk_warnings" / "risk_rule_results.json"
)
DEFAULT_COMPOSITE_OUTPUT = (
    PROJECT_ROOT / "data" / "ads" / "risk_warnings" / "risk_composite_results.parquet"
)
DEFAULT_COMPOSITE_JSON = (
    PROJECT_ROOT / "data" / "ads" / "risk_warnings" / "risk_composite_results.json"
)

RISK_CODES = [
    "low_learning_engagement_risk",
    "task_procrastination_risk",
    "classroom_interaction_low_risk",
    "learning_resource_low_use_risk",
    "academic_decline_risk",
    "course_fail_risk",
    "retake_makeup_risk",
    "achievement_weakness_risk",
    "lifestyle_abnormal_risk",
    "social_low_integration_risk",
    "course_exploration_misalignment_risk",
]

RISK_NAME_MAP = {
    "low_learning_engagement_risk": "学习投入不足风险",
    "task_procrastination_risk": "任务拖延风险",
    "classroom_interaction_low_risk": "课堂互动不足风险",
    "learning_resource_low_use_risk": "学习资源利用不足风险",
    "academic_decline_risk": "学业下滑风险",
    "course_fail_risk": "挂科风险",
    "retake_makeup_risk": "重修补考风险",
    "achievement_weakness_risk": "成果弱势风险",
    "lifestyle_abnormal_risk": "生活节律异常风险",
    "social_low_integration_risk": "社交低融入风险",
    "course_exploration_misalignment_risk": "选课探索失衡风险",
}

INTERVENTION_MAP = {
    # --- Primary: learning behavior interventions ---
    "low_learning_engagement_risk": "建议从签到、任务完成和资源使用三项基础行为入手，安排周目标与过程反馈。",
    "task_procrastination_risk": "建议把作业和考试准备拆成多个节点，并增加提前提醒和阶段检查。",
    "classroom_interaction_low_risk": "建议通过课堂提问、小组回应和讨论区必做反馈提高互动频次。",
    "learning_resource_low_use_risk": "建议定向推荐课程资源、图书馆学习时段与线上学习清单。",
    "academic_decline_risk": "建议导师优先复盘成绩、绩点、测评与排名变化，安排阶段性学业修复计划。",
    "course_fail_risk": "建议围绕挂科与临界课程建立帮扶清单，优先保障核心课程通过。",
    "retake_makeup_risk": "建议围绕补考和重修课程建立专项修复安排，优先关注高学分课程。",
    "achievement_weakness_risk": "建议选择语言、竞赛、奖学金或综合测评中的一到两个方向做成果突破。",
    # --- Supplementary: non-academic factors (support learning interventions) ---
    "lifestyle_abnormal_risk": "建议关注夜间活动、运动频率与作息规律，恢复稳定生活节律以支撑学习状态。",
    "social_low_integration_risk": "建议推动学生参与正式活动和稳定同伴互动，提升融入程度以促进协作学习。",
    "course_exploration_misalignment_risk": "建议结合培养方案、兴趣方向与成绩表现优化选课结构，避免过度保守或漂移试探。",
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def clamp01(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(lower=0.0, upper=1.0)


def safe_series(df: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in df.columns:
        LOGGER.warning("Missing risk feature column '%s'; using default.", column)
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def score_to_level(score: pd.Series, low: float = 0.35, high: float = 0.65) -> pd.Series:
    return pd.Series(
        np.select(
            [score >= high, score >= low],
            ["high", "medium"],
            default="low",
        ),
        index=score.index,
    )


def load_features(parquet_path: Path, json_path: Path) -> pd.DataFrame:
    if parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
            LOGGER.info("Loaded risk features from parquet with shape: %s", df.shape)
            print(f"risk_features input shape: {df.shape}")
            print(f"risk_features columns: {df.columns.tolist()}")
            return df
        except Exception as exc:
            LOGGER.warning("Failed to load parquet risk features: %s", exc)

    if not json_path.exists():
        raise FileNotFoundError(f"Risk feature file not found: {parquet_path} or {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    records = payload["records"] if isinstance(payload, dict) and "records" in payload else payload
    df = pd.DataFrame(records)
    LOGGER.info("Loaded risk features from JSON with shape: %s", df.shape)
    print(f"risk_features input shape: {df.shape}")
    print(f"risk_features columns: {df.columns.tolist()}")
    return df


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        LOGGER.warning("Risk rule config not found: %s", path)
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_individual_scores(df: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame({"student_id": df["student_id"]})

    result["low_learning_engagement_risk_score"] = clamp01(safe_series(df, "low_engagement_score")).fillna(0.0)
    result["task_procrastination_risk_score"] = (
        0.35 * clamp01(safe_series(df, "ddl_pressure_index")).fillna(0.0)
        + 0.25 * clamp01(safe_series(df, "slow_submit_ratio")).fillna(0.0)
        + 0.20 * clamp01(safe_series(df, "submit_delay_percentile")).fillna(0.0)
        + 0.10 * clamp01(safe_series(df, "not_done_rate")).fillna(0.0)
        + 0.10 * (1 - clamp01(safe_series(df, "fast_submit_ratio")).fillna(0.0))
    ).clip(0.0, 1.0)
    result["classroom_interaction_low_risk_score"] = (
        0.30 * (1 - clamp01(safe_series(df, "discussion_engagement_score")).fillna(0.0))
        + 0.20 * (1 - clamp01(safe_series(df, "interaction_initiative_percentile")).fillna(0.0))
        + 0.20 * (1 - clamp01(safe_series(df, "discussion_activity_percentile")).fillna(0.0))
        + 0.15 * clamp01(safe_series(df, "empty_reply_ratio")).fillna(0.0)
        + 0.15 * (1 - clamp01(safe_series(df, "long_reply_ratio")).fillna(0.0))
    ).clip(0.0, 1.0)
    result["learning_resource_low_use_risk_score"] = (
        0.35 * (1 - clamp01(safe_series(df, "resource_view_count_percentile")).fillna(0.0))
        + 0.20 * (1 - clamp01(safe_series(df, "resource_depth")).fillna(0.0))
        + 0.20 * (1 - clamp01(safe_series(df, "video_completion_rate")).fillna(0.0))
        + 0.15 * (1 - clamp01(safe_series(df, "library_immersion_score")).fillna(0.0))
        + 0.10 * (1 - clamp01(safe_series(df, "learning_behavior_score")).fillna(0.0))
    ).clip(0.0, 1.0)

    result["academic_decline_risk_score"] = clamp01(safe_series(df, "academic_decline_score")).fillna(0.0)
    result["course_fail_risk_score"] = clamp01(safe_series(df, "fail_risk_score")).fillna(0.0)
    result["retake_makeup_risk_score"] = (
        0.45 * (safe_series(df, "retake_ratio") / 0.15).clip(0.0, 1.0).fillna(0.0)
        + 0.25 * (safe_series(df, "retake_count") / 2.0).clip(0.0, 1.0).fillna(0.0)
        + 0.15 * (safe_series(df, "fail_ratio") / 0.25).clip(0.0, 1.0).fillna(0.0)
        + 0.15 * ((75 - safe_series(df, "avg_course_score")) / 20.0).clip(0.0, 1.0).fillna(0.0)
    ).clip(0.0, 1.0)
    result["achievement_weakness_risk_score"] = (
        0.25 * (1 - clamp01(safe_series(df, "evaluation_strength_score")).fillna(0.0))
        + 0.25 * (1 - clamp01(safe_series(df, "scholarship_strength_score")).fillna(0.0))
        + 0.20 * (1 - clamp01(safe_series(df, "language_ability_score")).fillna(0.0))
        + 0.20 * (1 - clamp01(safe_series(df, "competition_strength_score")).fillna(0.0))
        + 0.10 * clamp01(safe_series(df, "missing_feature_ratio")).fillna(0.0)
    ).clip(0.0, 1.0)

    result["lifestyle_abnormal_risk_score"] = clamp01(safe_series(df, "lifestyle_abnormal_score")).fillna(0.0)
    result["social_low_integration_risk_score"] = clamp01(safe_series(df, "social_low_integration_score")).fillna(0.0)
    result["course_exploration_misalignment_risk_score"] = clamp01(
        safe_series(df, "course_exploration_misalignment_score")
    ).fillna(0.0)

    for risk_code in RISK_CODES:
        score_col = f"{risk_code}_score"
        level_col = f"{risk_code}_level"
        flag_col = f"{risk_code}_flag"
        scores = result[score_col]
        levels = score_to_level(scores)
        # If fixed thresholds cause >= 75% "high", fall back to quantile-based thresholds
        if float((levels == "high").mean()) >= 0.75:
            hi = float(scores.quantile(0.80))
            lo = float(scores.quantile(0.50))
            levels = score_to_level(scores, low=lo, high=hi)
        result[level_col] = levels
        result[flag_col] = result[level_col].isin(["medium", "high"])

    return result


def build_reason_flags(source_df: pd.DataFrame, score_df: pd.DataFrame) -> dict[str, pd.Series]:
    reasons: dict[str, pd.Series] = {}
    reasons["low_learning_engagement_risk"] = np.where(
        safe_series(source_df, "learning_behavior_score").fillna(1.0) < 0.25,
        "整体学习投入偏低",
        "课堂、讨论或图书馆投入不足",
    )
    reasons["task_procrastination_risk"] = np.where(
        safe_series(source_df, "slow_submit_ratio").fillna(0.0) >= 0.30,
        "任务提交明显靠近截止时间",
        "提交节奏偏慢且提前完成比例不足",
    )
    reasons["classroom_interaction_low_risk"] = np.where(
        safe_series(source_df, "empty_reply_ratio").fillna(0.0) >= 0.50,
        "互动内容质量偏低",
        "课堂与讨论区互动频率偏低",
    )
    reasons["learning_resource_low_use_risk"] = np.where(
        safe_series(source_df, "resource_view_count_percentile").fillna(1.0) <= 0.30,
        "学习资源访问量偏低",
        "资源使用深度不足",
    )
    reasons["academic_decline_risk"] = np.where(
        safe_series(source_df, "evaluation_growth_proxy").fillna(0.0) < -5,
        "综合测评呈下降趋势",
        "成绩、绩点或排名表现承压",
    )
    reasons["course_fail_risk"] = np.where(
        safe_series(source_df, "failed_course_count").fillna(0.0) >= 1,
        "已出现挂科或临界低分课程",
        "课程通过率偏低",
    )
    reasons["retake_makeup_risk"] = np.where(
        safe_series(source_df, "retake_count").fillna(0.0) >= 1,
        "已有重修或补考记录",
        "课程修复压力偏高",
    )
    reasons["achievement_weakness_risk"] = np.where(
        safe_series(source_df, "missing_feature_ratio").fillna(0.0) > 0.40,
        "外显成果覆盖不足",
        "奖学金、语言或竞赛成果整体偏弱",
    )
    reasons["lifestyle_abnormal_risk"] = np.where(
        source_df.get("lifestyle_health_final_label", pd.Series(index=source_df.index)).astype(str).eq("节律紊乱预警型"),
        "生活节律异常信号明显",
        "夜间活跃或运动不足趋势偏强",
    )
    reasons["social_low_integration_risk"] = np.where(
        source_df.get("social_life_final_label", pd.Series(index=source_df.index)).astype(str).eq("低融入孤立型"),
        "社交融入度偏低",
        "线下参与与稳定同伴互动不足",
    )
    reasons["course_exploration_misalignment_risk"] = np.where(
        source_df.get("course_exploration_final_label", pd.Series(index=source_df.index)).astype(str).eq("漂移试探型"),
        "选课方向存在漂移试探特征",
        "选课结构偏保守或探索失衡",
    )
    return reasons


def adaptive_composite_levels(score: pd.Series) -> tuple[pd.Series, dict[str, float]]:
    high_threshold = 0.70
    medium_threshold = 0.40
    levels = score_to_level(score, low=medium_threshold, high=high_threshold)
    high_ratio = float((levels == "high").mean())
    medium_ratio = float((levels == "medium").mean())

    if high_ratio == 0.0 or high_ratio >= 0.75 or medium_ratio == 0.0:
        high_threshold = float(score.quantile(0.80))
        medium_threshold = float(score.quantile(0.50))
        levels = score_to_level(score, low=medium_threshold, high=high_threshold)

    return levels, {"high_threshold": high_threshold, "medium_threshold": medium_threshold}


def build_composite_results(feature_df: pd.DataFrame, score_df: pd.DataFrame) -> pd.DataFrame:
    composite = pd.DataFrame({"student_id": feature_df["student_id"]})

    # Weights: learning/academic factors dominate (~90%), lifestyle/social auxiliary (~10%)
    composite["composite_attention_score"] = (
        0.28 * score_df["academic_decline_risk_score"]
        + 0.24 * score_df["course_fail_risk_score"]
        + 0.18 * score_df["low_learning_engagement_risk_score"]
        + 0.13 * score_df["task_procrastination_risk_score"]
        + 0.07 * score_df["course_exploration_misalignment_risk_score"]
        + 0.05 * score_df["lifestyle_abnormal_risk_score"]
        + 0.05 * score_df["social_low_integration_risk_score"]
    ).round(6)

    composite["risk_level"], threshold_info = adaptive_composite_levels(composite["composite_attention_score"])
    composite["composite_attention_risk"] = composite["risk_level"].isin(["medium", "high"])

    score_columns = [f"{risk_code}_score" for risk_code in RISK_CODES]
    score_matrix = score_df[score_columns].copy()
    score_matrix.columns = RISK_CODES

    primary_code = score_matrix.idxmax(axis=1)
    primary_score = score_matrix.max(axis=1)
    composite["primary_risk_code"] = primary_code
    composite["primary_risk_name_cn"] = composite["primary_risk_code"].map(RISK_NAME_MAP)
    composite["primary_risk_score"] = primary_score.round(6)
    composite["high_risk_count"] = (score_matrix >= 0.65).sum(axis=1)
    composite["medium_risk_count"] = ((score_matrix >= 0.35) & (score_matrix < 0.65)).sum(axis=1)

    reasons_map = build_reason_flags(feature_df, score_df)

    def build_top_factors(row_index: int) -> list[str]:
        sorted_codes = score_matrix.iloc[row_index].sort_values(ascending=False).head(3).index.tolist()
        return [str(reasons_map[code][row_index]) for code in sorted_codes]

    composite["top_factors"] = [build_top_factors(i) for i in range(len(composite))]

    composite["peer_compare"] = pd.Series(
        np.where(
            composite["composite_attention_score"] >= composite["composite_attention_score"].quantile(0.80),
            "处于全体学生风险较高区间",
            np.where(
                composite["composite_attention_score"] >= composite["composite_attention_score"].quantile(0.50),
                "处于全体学生风险中等区间",
                "处于全体学生风险较低区间",
            ),
        ),
        index=composite.index,
    )
    composite["trend_4w"] = "当前缺少稳定周序列，暂使用截面代理风险特征"
    composite["intervention_advice"] = composite["primary_risk_code"].map(INTERVENTION_MAP)
    composite["threshold_info"] = json.dumps(threshold_info, ensure_ascii=False)
    return composite


def save_dataframe(df: pd.DataFrame, parquet_path: Path, json_path: Path, preview_title: str) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(parquet_path, index=False)
        LOGGER.info("Saved %s parquet to: %s", preview_title, parquet_path)
    except Exception as exc:
        LOGGER.warning("Failed to save %s parquet: %s", preview_title, exc)

    records = df.astype(object).where(pd.notna(df), None).to_dict(orient="records")
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{preview_title} shape: {df.shape}")
    print(f"{preview_title} columns: {df.columns.tolist()}")
    print(f"{preview_title} preview:")
    print(json.dumps(records[:3], ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run five-mode risk rule engine.")
    parser.add_argument("--input-features", type=Path, default=DEFAULT_FEATURES_PATH)
    parser.add_argument("--input-features-json", type=Path, default=DEFAULT_FEATURES_JSON_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--rule-output", type=Path, default=DEFAULT_RULE_OUTPUT)
    parser.add_argument("--rule-json", type=Path, default=DEFAULT_RULE_JSON)
    parser.add_argument("--composite-output", type=Path, default=DEFAULT_COMPOSITE_OUTPUT)
    parser.add_argument("--composite-json", type=Path, default=DEFAULT_COMPOSITE_JSON)
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()

    try:
        feature_df = load_features(args.input_features, args.input_features_json)
        config = load_config(args.config)
        LOGGER.info("Loaded risk config with top-level keys: %s", list(config.keys()) if config else [])

        rule_df = build_individual_scores(feature_df)
        composite_df = build_composite_results(feature_df, rule_df)

        distribution = composite_df["risk_level"].value_counts(dropna=False).to_dict()
        print("composite risk distribution:")
        print(json.dumps(distribution, ensure_ascii=False, indent=2))

        save_dataframe(rule_df, args.rule_output, args.rule_json, "risk_rule_results")
        save_dataframe(composite_df, args.composite_output, args.composite_json, "risk_composite_results")
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to run risk rules: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
