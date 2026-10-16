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
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "feature_store" / "modes" / "learning_outcome_features.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "ads" / "pattern_results" / "learning_outcome_pattern_results.json"
PATTERN_VERSION = "v1"

REQUIRED_COLUMNS = {
    "student_id": None,
    "course_count": np.nan,
    "avg_course_score": np.nan,
    "avg_gpa": np.nan,
    "credit_earn_ratio": np.nan,
    "fail_ratio": np.nan,
    "failed_course_count": np.nan,
    "excellent_ratio": np.nan,
    "retake_count": np.nan,
    "retake_ratio": np.nan,
    "weighted_score_by_credit": np.nan,
    "weighted_gpa_by_credit": np.nan,
    "learning_outcome_base_score": np.nan,
    "evaluation_total_score_avg": np.nan,
    "major_rank_avg": np.nan,
    "major_rank_best": np.nan,
    "class_rank_avg": np.nan,
    "class_rank_best": np.nan,
    "rank_stability_score": np.nan,
    "evaluation_growth_proxy": np.nan,
    "evaluation_strength_score": np.nan,
    "scholarship_count": np.nan,
    "scholarship_level_score": np.nan,
    "scholarship_strength_score": np.nan,
    "cet_score_max": np.nan,
    "cet_pass_ratio": np.nan,
    "cet4_pass_flag": None,
    "cet6_pass_flag": None,
    "language_ability_score": np.nan,
    "competition_count": np.nan,
    "competition_level_score": np.nan,
    "competition_strength_score": np.nan,
    "learning_outcome_score": np.nan,
    "outcome_level": None,
    "academic_risk_level": None,
    "achievement_profile": None,
    "outcome_feature_count": np.nan,
    "missing_feature_ratio": np.nan,
    "growth_potential_flag": None,
    "stability_flag": None,
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

    LOGGER.info("Loaded learning outcome features with shape: %s", df.shape)
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


def to_bool(value: Any, default: bool = False) -> bool:
    if value is None or pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return bool(value)


def is_high(value: Any, threshold: float = 0.7) -> bool:
    numeric_value = to_float(value)
    return numeric_value is not None and numeric_value >= threshold


def is_medium(value: Any, low: float = 0.4, high: float = 0.7) -> bool:
    numeric_value = to_float(value)
    return numeric_value is not None and low <= numeric_value < high


def is_low(value: Any, threshold: float = 0.4) -> bool:
    numeric_value = to_float(value)
    return numeric_value is not None and numeric_value < threshold


def rank_is_good(value: Any, threshold: float = 30) -> bool:
    numeric_value = to_float(value)
    return numeric_value is not None and numeric_value <= threshold


def finalize_rule_score(score: float, matched_rules: list[str], reasons: list[str]) -> tuple[float, list[str], list[str]]:
    return round(float(np.clip(score, 0.0, 1.0)), 6), list(dict.fromkeys(matched_rules)), list(dict.fromkeys(reasons))


def score_stable_excellent(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    outcome_score = to_float(safe_get(row, "learning_outcome_score", np.nan))
    base_score = to_float(safe_get(row, "learning_outcome_base_score", np.nan))
    fail_ratio = to_float(safe_get(row, "fail_ratio", np.nan))
    avg_gpa = to_float(safe_get(row, "avg_gpa", np.nan))
    rank_stability = to_float(safe_get(row, "rank_stability_score", np.nan))
    side_strength = max(
        to_float(safe_get(row, "evaluation_strength_score", np.nan), 0.0) or 0.0,
        to_float(safe_get(row, "scholarship_strength_score", np.nan), 0.0) or 0.0,
        to_float(safe_get(row, "language_ability_score", np.nan), 0.0) or 0.0,
        to_float(safe_get(row, "competition_strength_score", np.nan), 0.0) or 0.0,
    )

    if str(safe_get(row, "outcome_level", "")).lower() == "high":
        score += 0.20
        matched_rules.append("stable_high_outcome_level")
        reasons.append("整体学习成果处于高位")
    if is_high(outcome_score, 0.68):
        score += 0.18
        matched_rules.append("stable_high_outcome_score")
        reasons.append("学习成果综合分较高")
    if is_high(base_score, 0.63):
        score += 0.14
        matched_rules.append("stable_high_base_score")
        reasons.append("成绩基础与绩点表现较强")
    if fail_ratio is not None and fail_ratio <= 0.05:
        score += 0.12
        matched_rules.append("stable_low_fail_ratio")
        reasons.append("挂科压力低，学业基础较稳")
    if avg_gpa is not None and avg_gpa >= 3.45:
        score += 0.12
        matched_rules.append("stable_high_gpa")
        reasons.append("绩点表现稳定且较高")
    if rank_is_good(safe_get(row, "major_rank_best", np.nan), 20) or rank_is_good(safe_get(row, "class_rank_best", np.nan), 10):
        score += 0.10
        matched_rules.append("stable_good_rank")
        reasons.append("排名表现靠前")
    if rank_stability is not None and rank_stability >= 0.18:
        score += 0.06
        matched_rules.append("stable_rank_stability")
        reasons.append("排名波动相对较小")
    if side_strength >= 0.55:
        score += 0.10
        matched_rules.append("stable_strong_side_achievement")
        reasons.append("语言、竞赛或奖学金等成果中至少一项较强")
    if to_bool(safe_get(row, "stability_flag", False)):
        score += 0.08
        matched_rules.append("stable_stability_flag")
        reasons.append("整体学业表现具备稳定优势")

    return finalize_rule_score(score, matched_rules, reasons)


def score_growth_potential(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    outcome_score = to_float(safe_get(row, "learning_outcome_score", np.nan))
    base_score = to_float(safe_get(row, "learning_outcome_base_score", np.nan))
    fail_ratio = to_float(safe_get(row, "fail_ratio", np.nan))
    growth_proxy = to_float(safe_get(row, "evaluation_growth_proxy", np.nan))
    growth_flag = to_bool(safe_get(row, "growth_potential_flag", False))
    side_strength = max(
        to_float(safe_get(row, "evaluation_strength_score", np.nan), 0.0) or 0.0,
        to_float(safe_get(row, "scholarship_strength_score", np.nan), 0.0) or 0.0,
        to_float(safe_get(row, "language_ability_score", np.nan), 0.0) or 0.0,
        to_float(safe_get(row, "competition_strength_score", np.nan), 0.0) or 0.0,
    )
    outcome_level = str(safe_get(row, "outcome_level", "")).lower()
    academic_risk = str(safe_get(row, "academic_risk_level", "")).lower()

    if growth_flag:
        score += 0.24
        matched_rules.append("growth_flag_true")
        reasons.append("成长潜力信号较明显")
    if growth_proxy is not None and growth_proxy >= 3:
        score += 0.18
        matched_rules.append("growth_positive_evaluation_trend")
        reasons.append("综合测评呈现上升趋势")
    if outcome_level == "medium":
        score += 0.14
        matched_rules.append("growth_medium_outcome_level")
        reasons.append("当前学习成果处于中段提升区间")
    elif outcome_level == "high":
        score += 0.04
        matched_rules.append("growth_high_outcome_level")
        reasons.append("当前成果基础已经不低")
    if is_medium(base_score, 0.40, 0.65):
        score += 0.10
        matched_rules.append("growth_mid_base_score")
        reasons.append("成绩基础具备进一步提升空间")
    if fail_ratio is not None and fail_ratio <= 0.10:
        score += 0.10
        matched_rules.append("growth_low_fail_pressure")
        reasons.append("当前挂科压力不高")
    if side_strength >= 0.58:
        score += 0.14
        matched_rules.append("growth_strong_side_dimension")
        reasons.append("语言能力或竞赛奖学金等侧面表现较强")
    if academic_risk in {"low", "medium"}:
        score += 0.08
        matched_rules.append("growth_risk_not_high")
        reasons.append("学业风险尚可控")
    if not to_bool(safe_get(row, "stability_flag", False)):
        score += 0.04
        matched_rules.append("growth_not_fully_stable")
        reasons.append("更体现成长性而非长期稳定领先")

    return finalize_rule_score(score, matched_rules, reasons)


def score_recovery_fluctuation(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    retake_count = to_float(safe_get(row, "retake_count", np.nan), 0.0) or 0.0
    retake_ratio = to_float(safe_get(row, "retake_ratio", np.nan), 0.0) or 0.0
    fail_ratio = to_float(safe_get(row, "fail_ratio", np.nan), 0.0) or 0.0
    failed_course_count = to_float(safe_get(row, "failed_course_count", np.nan), 0.0) or 0.0
    outcome_score = to_float(safe_get(row, "learning_outcome_score", np.nan))
    base_score = to_float(safe_get(row, "learning_outcome_base_score", np.nan))
    academic_risk = str(safe_get(row, "academic_risk_level", "")).lower()
    growth_proxy = to_float(safe_get(row, "evaluation_growth_proxy", np.nan))

    if retake_count > 0 or retake_ratio >= 0.03:
        score += 0.20
        matched_rules.append("recovery_has_retake_history")
        reasons.append("存在重修经历，但并非完全失稳")
    if 0.04 <= fail_ratio <= 0.18 or failed_course_count >= 1:
        score += 0.18
        matched_rules.append("recovery_has_fail_pressure")
        reasons.append("曾有一定挂科或波动压力")
    if is_medium(outcome_score, 0.42, 0.65):
        score += 0.16
        matched_rules.append("recovery_mid_outcome_score")
        reasons.append("当前成果水平仍处于可修复区间")
    if base_score is not None and base_score >= 0.42:
        score += 0.10
        matched_rules.append("recovery_base_not_collapsed")
        reasons.append("成绩基础尚未明显失守")
    if academic_risk == "medium":
        score += 0.12
        matched_rules.append("recovery_medium_risk")
        reasons.append("当前更像阶段性波动而非持续承压")
    elif academic_risk == "low":
        score += 0.06
        matched_rules.append("recovery_low_risk")
        reasons.append("风险水平已有一定缓和")
    if growth_proxy is None or growth_proxy >= 0:
        score += 0.08
        matched_rules.append("recovery_non_negative_trend")
        reasons.append("综合测评未呈明显继续下滑")
    if to_bool(safe_get(row, "growth_potential_flag", False)):
        score += 0.08
        matched_rules.append("recovery_growth_signal")
        reasons.append("存在恢复后的再提升信号")

    return finalize_rule_score(score, matched_rules, reasons)


def score_under_pressure(row: pd.Series) -> tuple[float, list[str], list[str]]:
    score = 0.0
    matched_rules: list[str] = []
    reasons: list[str] = []

    outcome_score = to_float(safe_get(row, "learning_outcome_score", np.nan))
    base_score = to_float(safe_get(row, "learning_outcome_base_score", np.nan))
    fail_ratio = to_float(safe_get(row, "fail_ratio", np.nan), 0.0) or 0.0
    failed_course_count = to_float(safe_get(row, "failed_course_count", np.nan), 0.0) or 0.0
    retake_ratio = to_float(safe_get(row, "retake_ratio", np.nan), 0.0) or 0.0
    avg_gpa = to_float(safe_get(row, "avg_gpa", np.nan))
    academic_risk = str(safe_get(row, "academic_risk_level", "")).lower()
    missing_ratio = to_float(safe_get(row, "missing_feature_ratio", np.nan), 0.0) or 0.0

    if str(safe_get(row, "outcome_level", "")).lower() == "low":
        score += 0.18
        matched_rules.append("pressure_low_outcome_level")
        reasons.append("学习成果整体处于低位")
    if is_low(outcome_score, 0.42):
        score += 0.16
        matched_rules.append("pressure_low_outcome_score")
        reasons.append("学习成果综合表现整体偏弱")
    if is_low(base_score, 0.45):
        score += 0.14
        matched_rules.append("pressure_low_base_score")
        reasons.append("成绩基础与核心学业表现偏弱")
    if fail_ratio >= 0.15 or failed_course_count >= 2:
        score += 0.16
        matched_rules.append("pressure_high_fail_burden")
        reasons.append("挂科压力较高")
    if retake_ratio >= 0.08:
        score += 0.08
        matched_rules.append("pressure_high_retake_ratio")
        reasons.append("重修修复压力较明显")
    if avg_gpa is not None and avg_gpa < 2.70:
        score += 0.10
        matched_rules.append("pressure_low_gpa")
        reasons.append("绩点水平偏低")
    if academic_risk == "high":
        score += 0.10
        matched_rules.append("pressure_high_academic_risk")
        reasons.append("综合学业风险偏高")

    weak_side_count = 0
    for column in ["scholarship_strength_score", "language_ability_score", "competition_strength_score"]:
        value = to_float(safe_get(row, column, np.nan))
        if value is not None and value < 0.35:
            weak_side_count += 1
    if weak_side_count >= 2:
        score += 0.06
        matched_rules.append("pressure_weak_side_outcomes")
        reasons.append("奖学金、语言或竞赛表现整体偏弱")
    if missing_ratio >= 0.45:
        score += 0.04
        matched_rules.append("pressure_high_missing_ratio")
        reasons.append("有效成果特征覆盖不足")

    return finalize_rule_score(score, matched_rules, reasons)


def compute_confidence(best_score: float, second_score: float) -> float:
    margin = max(best_score - second_score, 0.0)
    margin_component = min(margin * 1.4, 1.0)
    confidence = 0.60 * best_score + 0.40 * margin_component
    if best_score < 0.45:
        confidence = min(confidence, 0.58)
    return round(float(np.clip(confidence, 0.0, 1.0)), 6)


def build_risk_flag(row: pd.Series, learning_outcome_type: str) -> bool:
    fail_ratio = to_float(safe_get(row, "fail_ratio", np.nan), 0.0) or 0.0
    retake_ratio = to_float(safe_get(row, "retake_ratio", np.nan), 0.0) or 0.0
    outcome_score = to_float(safe_get(row, "learning_outcome_score", np.nan), 1.0) or 1.0
    academic_risk = str(safe_get(row, "academic_risk_level", "")).lower()

    if learning_outcome_type == "边缘承压型":
        return True
    if fail_ratio >= 0.18:
        return True
    if academic_risk == "high":
        return True
    if retake_ratio >= 0.08 and outcome_score < 0.45:
        return True
    return False


def classify_student(row: pd.Series) -> dict[str, Any]:
    score_results = {
        "稳定卓越型": score_stable_excellent(row),
        "潜力成长型": score_growth_potential(row),
        "波动修复型": score_recovery_fluctuation(row),
        "边缘承压型": score_under_pressure(row),
    }

    sorted_results = sorted(score_results.items(), key=lambda item: item[1][0], reverse=True)
    best_type, best_result = sorted_results[0]
    second_score = sorted_results[1][1][0] if len(sorted_results) > 1 else 0.0
    best_score, matched_rules, reasons = best_result

    if len(sorted_results) > 1 and abs(best_score - second_score) < 0.03:
        ordered_priority = ["稳定卓越型", "边缘承压型", "波动修复型", "潜力成长型"]
        top_candidates = [item for item in sorted_results if abs(item[1][0] - best_score) < 0.03]
        top_candidates.sort(key=lambda item: ordered_priority.index(item[0]))
        best_type, best_result = top_candidates[0]
        best_score, matched_rules, reasons = best_result

    confidence = compute_confidence(best_score, second_score)
    top_reasons = list(dict.fromkeys(reasons))[:3]
    generated_at = datetime.now().isoformat(timespec="seconds")

    return {
        "student_id": safe_get(row, "student_id", None),
        "learning_outcome_type": best_type,
        "learning_outcome_score": to_float(safe_get(row, "learning_outcome_score", np.nan)),
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
                "learning_outcome_type",
                "learning_outcome_score",
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
    distribution = df["learning_outcome_type"].value_counts(dropna=False).to_dict() if not df.empty else {}
    print(f"classification_distribution: {distribution}")
    json_ready_df = df.astype(object).where(pd.notna(df), None)
    records = json_ready_df.to_dict(orient="records")
    print("JSON preview:")
    print(json.dumps(records[:3], ensure_ascii=False, indent=2))
    LOGGER.info("Saving learning outcome pattern results to: %s", output_path)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
    LOGGER.info("Learning outcome pattern results saved successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify students into rule-based learning outcome patterns from merged outcome features."
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
        LOGGER.exception("Failed to classify learning outcome patterns: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
