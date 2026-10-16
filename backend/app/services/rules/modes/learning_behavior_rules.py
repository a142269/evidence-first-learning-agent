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


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "feature_store" / "modes" / "learning_behavior_features.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "ads" / "pattern_results" / "learning_behavior_pattern_results.json"
PATTERN_VERSION = "v1"

REQUIRED_COLUMNS = {
    "student_id": None,
    "task_completion_rate": np.nan,
    "video_completion_rate": np.nan,
    "active_learning_score": np.nan,
    "discussion_engagement_score": np.nan,
    "done_rate": np.nan,
    "not_done_rate": np.nan,
    "ddl_pressure_index": np.nan,
    "slow_submit_ratio": np.nan,
    "library_immersion_score": np.nan,
    "learning_behavior_score": np.nan,
    "engagement_level": None,
    "procrastination_risk": None,
    "participation_balance": None,
    "behavior_feature_count": np.nan,
    "missing_feature_ratio": np.nan,
    "learning_task_stability": np.nan,
    "assignment_exam_record_count": np.nan,
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
    return text.strip("_")


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


def ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    for column, default_value in REQUIRED_COLUMNS.items():
        if column not in df.columns:
            LOGGER.warning("Missing input column '%s'; filling with default values.", column)
            df[column] = default_value
    return df


def load_features(path: Path) -> pd.DataFrame:
    empty_df = pd.DataFrame(columns=list(REQUIRED_COLUMNS.keys()))
    if not path.exists():
        LOGGER.warning("Input feature JSON not found: %s", path)
        return empty_df

    try:
        raw_text = path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        LOGGER.warning("Failed to read feature JSON %s: %s", path, exc)
        return empty_df

    if not raw_text:
        LOGGER.warning("Input feature JSON is empty: %s", path)
        return empty_df

    try:
        records = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        LOGGER.warning("Failed to parse input JSON %s: %s", path, exc)
        return empty_df

    if not isinstance(records, list):
        LOGGER.warning("Input feature JSON is not a records list: %s", path)
        return empty_df

    df = pd.DataFrame(records)
    if df.empty:
        LOGGER.warning("Input feature JSON has no valid records: %s", path)
        return empty_df

    df = df.rename(columns={column: normalize_column_name(column) for column in df.columns})
    if "studentid" in df.columns and "student_id" not in df.columns:
        df = df.rename(columns={"studentid": "student_id"})
    if "xh" in df.columns and "student_id" not in df.columns:
        df = df.rename(columns={"xh": "student_id"})

    df = ensure_required_columns(df)
    df["student_id"] = df["student_id"].apply(normalize_student_id)
    df = df[df["student_id"].notna()].copy()

    LOGGER.info("Loaded learning behavior features with shape: %s", df.shape)
    print(f"input_df shape: {df.shape}")
    print(f"input_df columns: {df.columns.tolist()}")
    return df


def safe_get(row: pd.Series, col: str, default: Any) -> Any:
    value = row.get(col, default)
    if pd.isna(value):
        return default
    return value


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_high(value: Any, threshold: float = 0.7) -> bool:
    numeric_value = to_float(value)
    return numeric_value is not None and numeric_value >= threshold


def is_medium(value: Any, low: float = 0.4, high: float = 0.7) -> bool:
    numeric_value = to_float(value)
    return numeric_value is not None and low <= numeric_value < high


def is_low(value: Any, threshold: float = 0.4) -> bool:
    numeric_value = to_float(value)
    return numeric_value is not None and numeric_value < threshold


def finalize_rule_score(score: float, matched_rules: list[str], reasons: list[str]) -> tuple[float, list[str], list[str]]:
    return round(float(np.clip(score, 0.0, 1.0)), 6), list(dict.fromkeys(matched_rules)), list(dict.fromkeys(reasons))


def score_deep_engagement(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    behavior_score = to_float(safe_get(row, "learning_behavior_score", np.nan))
    active_score = to_float(safe_get(row, "active_learning_score", np.nan))
    discussion_score = to_float(safe_get(row, "discussion_engagement_score", np.nan))
    library_score = to_float(safe_get(row, "library_immersion_score", np.nan))
    engagement_level = str(safe_get(row, "engagement_level", "")).lower()
    missing_ratio = to_float(safe_get(row, "missing_feature_ratio", np.nan), 1.0)
    feature_count = to_float(safe_get(row, "behavior_feature_count", np.nan), 0.0)

    if engagement_level == "high":
        score += 0.24
        matched_rules.append("deep_high_engagement_level")
        reasons.append("整体学习参与等级处于高位")
    if is_high(behavior_score, 0.18):
        score += 0.22
        matched_rules.append("deep_high_behavior_score")
        reasons.append("综合学习行为表现较强")
    if is_high(active_score, 0.05):
        score += 0.14
        matched_rules.append("deep_high_active_learning")
        reasons.append("课堂任务参与较积极")
    if is_high(discussion_score, 0.08):
        score += 0.14
        matched_rules.append("deep_high_discussion")
        reasons.append("课堂与讨论互动较活跃")
    if is_high(library_score, 0.48):
        score += 0.10
        matched_rules.append("deep_high_library")
        reasons.append("图书馆学习浸润程度较高")
    if missing_ratio <= 0.40:
        score += 0.08
        matched_rules.append("deep_low_missing_ratio")
        reasons.append("行为特征覆盖较完整")
    if feature_count >= 36:
        score += 0.05
        matched_rules.append("deep_rich_feature_coverage")
        reasons.append("多源学习行为都有体现")
    if str(safe_get(row, "participation_balance", "")) == "mixed":
        score += 0.03
        matched_rules.append("deep_balanced_participation")
        reasons.append("课堂、讨论与场馆参与较均衡")

    return finalize_rule_score(score, matched_rules, reasons)


def score_normal_execution(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    behavior_score = to_float(safe_get(row, "learning_behavior_score", np.nan))
    active_score = to_float(safe_get(row, "active_learning_score", np.nan))
    discussion_score = to_float(safe_get(row, "discussion_engagement_score", np.nan))
    library_score = to_float(safe_get(row, "library_immersion_score", np.nan))
    engagement_level = str(safe_get(row, "engagement_level", "")).lower()
    missing_ratio = to_float(safe_get(row, "missing_feature_ratio", np.nan), 1.0)
    feature_count = to_float(safe_get(row, "behavior_feature_count", np.nan), 0.0)
    stability = to_float(safe_get(row, "learning_task_stability", np.nan))

    if engagement_level == "medium":
        score += 0.20
        matched_rules.append("normal_medium_engagement_level")
        reasons.append("整体参与处于中等偏稳水平")
    elif engagement_level == "high":
        score += 0.10
        matched_rules.append("normal_high_engagement_level")
        reasons.append("整体参与水平不低")

    if is_medium(behavior_score, 0.05, 0.18):
        score += 0.18
        matched_rules.append("normal_mid_behavior_score")
        reasons.append("学习行为整体较为稳健")
    if is_medium(active_score, 0.01, 0.05):
        score += 0.12
        matched_rules.append("normal_mid_active_learning")
        reasons.append("课堂任务执行较稳定")
    if is_medium(discussion_score, 0.02, 0.08):
        score += 0.12
        matched_rules.append("normal_mid_discussion")
        reasons.append("讨论参与度处于常规区间")
    if is_medium(library_score, 0.25, 0.48):
        score += 0.08
        matched_rules.append("normal_mid_library")
        reasons.append("图书馆使用频率较为平稳")
    if missing_ratio <= 0.45:
        score += 0.08
        matched_rules.append("normal_acceptable_missing_ratio")
        reasons.append("关键行为信息较充足")
    if feature_count >= 30:
        score += 0.08
        matched_rules.append("normal_sufficient_feature_count")
        reasons.append("可用行为特征较为完整")
    if stability is not None and stability >= 0.35:
        score += 0.08
        matched_rules.append("normal_task_stability")
        reasons.append("任务执行节奏较平稳")
    if str(safe_get(row, "participation_balance", "")) in {"mixed", "classroom_task"}:
        score += 0.06
        matched_rules.append("normal_execution_oriented_balance")
        reasons.append("参与结构偏向日常执行型")

    return finalize_rule_score(score, matched_rules, reasons)


def score_deadline_driven(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    behavior_score = to_float(safe_get(row, "learning_behavior_score", np.nan))
    active_score = to_float(safe_get(row, "active_learning_score", np.nan))
    discussion_score = to_float(safe_get(row, "discussion_engagement_score", np.nan))
    library_score = to_float(safe_get(row, "library_immersion_score", np.nan))
    engagement_level = str(safe_get(row, "engagement_level", "")).lower()
    procrastination_risk = str(safe_get(row, "procrastination_risk", "")).lower()
    assignment_record_count = to_float(safe_get(row, "assignment_exam_record_count", np.nan))
    missing_ratio = to_float(safe_get(row, "missing_feature_ratio", np.nan), 1.0)

    if assignment_record_count is not None and assignment_record_count > 0:
        score += 0.18
        matched_rules.append("ddl_has_submission_records")
        reasons.append("存在较明确的作业或考试提交行为")
    if is_medium(behavior_score, 0.04, 0.16):
        score += 0.16
        matched_rules.append("ddl_mid_behavior_score")
        reasons.append("整体学习行为不低，但不属于深度投入")
    if engagement_level in {"medium", "high"}:
        score += 0.08
        matched_rules.append("ddl_not_low_engagement")
        reasons.append("并非完全低参与状态")
    if active_score is not None and active_score >= 0.01:
        score += 0.08
        matched_rules.append("ddl_has_task_activity")
        reasons.append("日常任务仍有一定完成投入")
    if discussion_score is None or discussion_score < 0.03:
        score += 0.12
        matched_rules.append("ddl_low_discussion")
        reasons.append("主动讨论投入不突出")
    if library_score is None or library_score < 0.25:
        score += 0.10
        matched_rules.append("ddl_low_library_presence")
        reasons.append("场馆学习沉浸度偏弱")
    if procrastination_risk in {"medium", "high"}:
        score += 0.10
        matched_rules.append("ddl_medium_high_procrastination_risk")
        reasons.append("提交节奏带有一定拖后倾向")
    if 0.35 <= missing_ratio <= 0.65:
        score += 0.06
        matched_rules.append("ddl_mid_missing_ratio")
        reasons.append("行为表现更集中在任务提交维度")
    if str(safe_get(row, "participation_balance", "")) in {"classroom_task", "mixed"}:
        score += 0.05
        matched_rules.append("ddl_task_oriented_balance")
        reasons.append("参与结构更偏向任务完成")

    return finalize_rule_score(score, matched_rules, reasons)


def score_low_participation(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    behavior_score = to_float(safe_get(row, "learning_behavior_score", np.nan))
    active_score = to_float(safe_get(row, "active_learning_score", np.nan))
    discussion_score = to_float(safe_get(row, "discussion_engagement_score", np.nan))
    library_score = to_float(safe_get(row, "library_immersion_score", np.nan))
    engagement_level = str(safe_get(row, "engagement_level", "")).lower()
    missing_ratio = to_float(safe_get(row, "missing_feature_ratio", np.nan), 0.0)
    feature_count = to_float(safe_get(row, "behavior_feature_count", np.nan), 999.0)

    if is_low(behavior_score, 0.03):
        score += 0.22
        matched_rules.append("low_low_behavior_score")
        reasons.append("综合学习行为得分偏低")
    if engagement_level == "low":
        score += 0.20
        matched_rules.append("low_low_engagement_level")
        reasons.append("整体参与等级偏低")
    if active_score is None or active_score < 0.01:
        score += 0.14
        matched_rules.append("low_low_active_learning")
        reasons.append("课堂学习参与度整体偏低")
    if discussion_score is None or discussion_score < 0.02:
        score += 0.14
        matched_rules.append("low_low_discussion")
        reasons.append("讨论互动参与不足")
    if library_score is None or library_score < 0.25:
        score += 0.08
        matched_rules.append("low_low_library")
        reasons.append("图书馆学习浸润较弱")
    if missing_ratio >= 0.55:
        score += 0.10
        matched_rules.append("low_high_missing_ratio")
        reasons.append("有效行为特征覆盖不足")
    if feature_count < 25:
        score += 0.08
        matched_rules.append("low_low_feature_count")
        reasons.append("可用行为特征数量偏少")

    return finalize_rule_score(score, matched_rules, reasons)


def compute_confidence(best_score: float, second_score: float) -> float:
    margin = max(best_score - second_score, 0.0)
    margin_component = min(margin * 1.4, 1.0)
    confidence = 0.60 * best_score + 0.40 * margin_component
    if best_score < 0.45:
        confidence = min(confidence, 0.58)
    return round(float(np.clip(confidence, 0.0, 1.0)), 6)


def build_risk_flag(row: pd.Series, learning_behavior_type: str) -> bool:
    behavior_score = to_float(safe_get(row, "learning_behavior_score", np.nan), 1.0) or 1.0
    missing_ratio = to_float(safe_get(row, "missing_feature_ratio", np.nan), 0.0) or 0.0
    if learning_behavior_type == "低参与失衡型":
        return True
    if behavior_score < 0.02:
        return True
    if missing_ratio >= 0.65:
        return True
    return False


def classify_student(row: pd.Series) -> dict[str, Any]:
    score_results = {
        "深度投入型": score_deep_engagement(row),
        "规范执行型": score_normal_execution(row),
        "截止驱动突击型": score_deadline_driven(row),
        "低参与失衡型": score_low_participation(row),
    }

    sorted_results = sorted(score_results.items(), key=lambda item: item[1][0], reverse=True)
    best_type, best_result = sorted_results[0]
    second_score = sorted_results[1][1][0] if len(sorted_results) > 1 else 0.0
    best_score, matched_rules, reasons = best_result

    if len(sorted_results) > 1 and abs(best_score - second_score) < 0.03:
        ordered_priority = ["深度投入型", "规范执行型", "截止驱动突击型", "低参与失衡型"]
        top_candidates = [item for item in sorted_results if abs(item[1][0] - best_score) < 0.03]
        top_candidates.sort(key=lambda item: ordered_priority.index(item[0]))
        best_type, best_result = top_candidates[0]
        best_score, matched_rules, reasons = best_result

    confidence = compute_confidence(best_score, second_score)
    top_reasons = list(dict.fromkeys(reasons))[:3]
    generated_at = datetime.now().isoformat(timespec="seconds")

    return {
        "student_id": safe_get(row, "student_id", None),
        "learning_behavior_type": best_type,
        "learning_behavior_score": to_float(safe_get(row, "learning_behavior_score", np.nan)),
        "rule_confidence": confidence,
        "matched_rules": matched_rules,
        "top_reasons": top_reasons,
        "risk_flag": build_risk_flag(row, best_type),
        "pattern_version": PATTERN_VERSION,
        "generated_at": generated_at,
    }


def classify_all(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        LOGGER.warning("Input dataframe is empty. Returning empty rule results.")
        return pd.DataFrame(
            columns=[
                "student_id",
                "learning_behavior_type",
                "learning_behavior_score",
                "rule_confidence",
                "matched_rules",
                "top_reasons",
                "risk_flag",
                "pattern_version",
                "generated_at",
            ]
        )

    return pd.DataFrame([classify_student(row) for _, row in df.iterrows()])


def save_results_json(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    distribution = df["learning_behavior_type"].value_counts(dropna=False).to_dict() if not df.empty else {}
    print(f"classification_distribution: {distribution}")
    json_ready_df = df.astype(object).where(pd.notna(df), None)
    records = json_ready_df.to_dict(orient="records")
    print("JSON preview:")
    print(json.dumps(records[:3], ensure_ascii=False, indent=2))
    LOGGER.info("Saving learning behavior pattern results to: %s", output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
    LOGGER.info("Learning behavior pattern results saved successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify students into rule-based learning behavior patterns from merged behavior features."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    try:
        feature_df = load_features(args.input)
        result_df = classify_all(feature_df)
        save_results_json(result_df, args.output)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Failed to classify learning behavior patterns: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
