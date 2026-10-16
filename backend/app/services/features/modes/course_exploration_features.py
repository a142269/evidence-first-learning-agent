from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


def _safe_read_excel(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        return pd.DataFrame()
    frame = pd.read_excel(file_path)
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator_numeric = _to_numeric(denominator).replace(0, np.nan)
    return (_to_numeric(numerator) / denominator_numeric).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _norm(series: pd.Series, reverse: bool = False) -> pd.Series:
    values = _to_numeric(series)
    min_v = values.min(skipna=True)
    max_v = values.max(skipna=True)
    if pd.isna(min_v) or pd.isna(max_v) or min_v == max_v:
        output = pd.Series(0.0, index=values.index)
    else:
        output = (values - min_v) / (max_v - min_v)
    if reverse:
        output = 1 - output
    return output.fillna(0.0)


def _ensure_xh(frame: pd.DataFrame, candidates: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    for col in candidates:
        if col in result.columns:
            result["XH"] = result[col].astype(str).str.strip()
            break
    if "XH" in result.columns:
        result["XH"] = result["XH"].astype(str).str.strip()
    return result


def _first_existing_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in frame.columns:
            return col
    return None


def _flag_from_codes(series: pd.Series, positive_codes: set[str], positive_regex: str = "") -> pd.Series:
    values = series.astype(str).str.strip()
    code_flag = values.isin(positive_codes)
    if positive_regex:
        regex_flag = values.str.contains(positive_regex, regex=True, na=False)
        return code_flag | regex_flag
    return code_flag


def _entropy(row: pd.Series) -> float:
    vals = _to_numeric(row).fillna(0.0).values.astype(float)
    total = vals.sum()
    if total <= 0:
        return 0.0
    p = vals[vals > 0] / total
    if len(p) <= 1:
        return 0.0
    return float(-(p * np.log(p)).sum() / np.log(len(vals)))


@dataclass
class CourseExplorationFeatureBuilder:
    project_root: Path

    def _ods_path(self, *parts: str) -> Path:
        return self.project_root.joinpath("data", "ods", *parts)

    def load_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "base": _safe_read_excel(self._ods_path("student_base", "学生基本信息.xlsx")),
            "selection": _safe_read_excel(self._ods_path("course_selection", "学生选课信息.xlsx")),
            "course": _safe_read_excel(self._ods_path("course_selection", "课程信息.xlsx")),
            "grade": _safe_read_excel(self._ods_path("grade_records", "学生成绩.xlsx")),
        }

    def _build_summary(self, frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {"shape": [0, 0], "distribution": {}, "sample": []}
        if "course_exploration_total_score" in frame.columns:
            score_bucket = pd.cut(
                _to_numeric(frame["course_exploration_total_score"]).fillna(0.0),
                bins=[-0.01, 0.25, 0.5, 0.75, 1.01],
                labels=["very_low", "low_mid", "mid_high", "high"],
            )
            distribution = score_bucket.value_counts(dropna=False).to_dict()
        else:
            distribution = {}
        health_cols = [
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
            "course_exploration_total_score",
        ]
        feature_health = {}
        for col in health_cols:
            if col not in frame.columns:
                continue
            values = _to_numeric(frame[col]).fillna(0.0)
            feature_health[col] = {
                "std": float(values.std()),
                "nunique": int(values.nunique()),
                "zero_ratio": float((values == 0).mean()),
                "one_ratio": float((values == 1).mean()),
            }
        return {
            "shape": [int(frame.shape[0]), int(frame.shape[1])],
            "distribution": distribution,
            "feature_health": feature_health,
            "sample": frame.head(3).replace({np.nan: None}).to_dict(orient="records"),
        }

    def build(self) -> pd.DataFrame:
        tables = self.load_tables()
        tables["base"] = _ensure_xh(tables["base"], ["XH", "IDSERTAL", "USER_ID"])
        tables["selection"] = _ensure_xh(tables["selection"], ["XH", "IDSERTAL", "USER_ID"])
        tables["grade"] = _ensure_xh(tables["grade"], ["XH", "IDSERTAL", "USER_ID"])
        base = tables["base"]
        if "XH" in base.columns and not base.empty:
            students = sorted(base["XH"].dropna().astype(str).str.strip().unique())
        else:
            selection_students = (
                set(tables["selection"]["XH"].dropna().astype(str).str.strip())
                if "XH" in tables["selection"].columns
                else set()
            )
            grade_students = (
                set(tables["grade"]["XH"].dropna().astype(str).str.strip())
                if "XH" in tables["grade"].columns
                else set()
            )
            students = sorted(selection_students.union(grade_students))
        if not students:
            return pd.DataFrame()
        df = pd.DataFrame({"XH": students})

        selection = tables["selection"].copy()
        course = tables["course"].copy()
        grade = tables["grade"].copy()
        if not selection.empty and "XH" in selection.columns:
            selection["XH"] = selection["XH"].astype(str)
            if "XKRQ" in selection.columns:
                selection["XKRQ_DT"] = _to_datetime(selection["XKRQ"])
            if not course.empty and "KCH" in selection.columns and "KCH" in course.columns:
                join_cols = [col for col in ["KCH", "KCFLDM", "KCCCDM", "XF", "CJKHFS", "KNZXS", "KCM", "KCFL1"] if col in course.columns]
                selection = selection.merge(
                    course[join_cols].copy(),
                    on="KCH",
                    how="left",
                )
            selection["course_count"] = 1.0
            select_cnt = selection.groupby("XH")["course_count"].sum()
            retake_ratio = (
                _flag_from_codes(selection["SFCX"], {"2", "3", "4", "5"}, positive_regex="重修|补考|缓考|再次").groupby(selection["XH"]).mean()
                if "SFCX" in selection.columns
                else pd.Series(dtype=float)
            )
            credit = _to_numeric(selection["XF"]).groupby(selection["XH"]).sum() if "XF" in selection.columns else pd.Series(dtype=float)
            avg_credit = _to_numeric(selection["XF"]).groupby(selection["XH"]).mean() if "XF" in selection.columns else pd.Series(dtype=float)
            if "XKRQ_DT" in selection.columns:
                early_ratio = (selection["XKRQ_DT"].dt.day <= 10).groupby(selection["XH"]).mean()
                late_ratio = (selection["XKRQ_DT"].dt.day >= 20).groupby(selection["XH"]).mean()
            else:
                early_ratio = pd.Series(dtype=float)
                late_ratio = pd.Series(dtype=float)
            discipline_col = _first_existing_column(selection, ["KCFLDM", "KCLB", "XKZY"])
            if discipline_col is not None:
                type_matrix = pd.crosstab(selection["XH"], selection[discipline_col].astype(str))
            else:
                type_matrix = pd.DataFrame()
            type_entropy = type_matrix.apply(_entropy, axis=1) if not type_matrix.empty else pd.Series(dtype=float)
            if not type_matrix.empty:
                dominant_ratio = type_matrix.max(axis=1) / type_matrix.sum(axis=1).replace(0, np.nan)
                cross_discipline_ratio = (1 - dominant_ratio).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            else:
                cross_discipline_ratio = pd.Series(dtype=float)
            level_ratio = (
                selection["KCCCDM"].astype(str).str.contains("2|3|高级|提高", regex=True).groupby(selection["XH"]).mean()
                if "KCCCDM" in selection.columns
                else pd.Series(dtype=float)
            )
            challenge_depth = (
                (
                    0.5 * _to_numeric(selection["KCCCDM"]).fillna(1.0)
                    + 0.35 * _to_numeric(selection["KNZXS"]).fillna(2.0)
                    + 0.15 * _to_numeric(selection["XF"]).fillna(0.0)
                ).groupby(selection["XH"]).mean()
                if "KCCCDM" in selection.columns
                else pd.Series(dtype=float)
            )
            prerequisite_challenge_rate = (
                (_to_numeric(selection["KNZXS"]).fillna(0.0) >= 4).groupby(selection["XH"]).mean()
                if "KNZXS" in selection.columns
                else pd.Series(dtype=float)
            )
            kcm_flag = (
                selection["KCM"].astype(str).str.contains("拓展|提高|进阶|荣誉", regex=True)
                if "KCM" in selection.columns
                else pd.Series(False, index=selection.index)
            )
            kcfl1_flag = (
                selection["KCFL1"].astype(str).str.contains("拓展|提高|进阶", regex=True)
                if "KCFL1" in selection.columns
                else pd.Series(False, index=selection.index)
            )
            kcccdm_flag = (
                selection["KCCCDM"].astype(str).str.contains("3|高级|提高", regex=True)
                if "KCCCDM" in selection.columns
                else pd.Series(False, index=selection.index)
            )
            knzxs_flag = (
                _to_numeric(selection["KNZXS"]).fillna(0.0) >= 4
                if "KNZXS" in selection.columns
                else pd.Series(False, index=selection.index)
            )
            high_credit_flag = (
                _to_numeric(selection["XF"]).fillna(0.0) >= 3.5
                if "XF" in selection.columns
                else pd.Series(False, index=selection.index)
            )
            extension_improvement_ratio = (
                (kcm_flag | kcfl1_flag | kcccdm_flag | knzxs_flag | high_credit_flag).groupby(selection["XH"]).mean()
            )
            assessment_preference = (
                selection["CJKHFS"].astype(str).str.contains("考查|论文|课程设计|开卷|报告|答辩", regex=True).groupby(selection["XH"]).mean()
                if "CJKHFS" in selection.columns
                else pd.Series(dtype=float)
            )
            if {"CJKHFS", "KCCCDM"}.issubset(selection.columns):
                risk_raw = (
                    selection["KCCCDM"].astype(str).str.contains("3|高级|提高|难", regex=True)
                    | selection["CJKHFS"].astype(str).str.contains("闭卷|统考|考试", regex=True)
                )
                high_risk_ratio = risk_raw.groupby(selection["XH"]).mean()
            else:
                high_risk_ratio = pd.Series(dtype=float)
            year_shift = (
                selection.groupby(["XH", "KKXN"])["KCFLDM"].nunique().groupby("XH").std()
                if set(["KKXN", "KCFLDM"]).issubset(selection.columns)
                else pd.Series(dtype=float)
            )
            if set(["KKXN", "KKXQ"]).issubset(selection.columns) and discipline_col is not None:
                term_key = selection["KKXN"].astype(str) + "-" + selection["KKXQ"].astype(str)
                tmp_major = (
                    selection.assign(_term=term_key, _disc=selection[discipline_col].astype(str))
                    .groupby(["XH", "_term", "_disc"])
                    .size()
                    .reset_index(name="cnt")
                    .sort_values(["XH", "_term", "cnt"], ascending=[True, True, False])
                )
                dominant_term = tmp_major.drop_duplicates(["XH", "_term"], keep="first")
                term_switch_ratio = (
                    dominant_term.groupby("XH")["_disc"].apply(lambda s: float((s != s.shift(1)).sum()) / max(len(s) - 1, 1))
                )
            else:
                term_switch_ratio = pd.Series(dtype=float)
        else:
            select_cnt = pd.Series(dtype=float)
            retake_ratio = pd.Series(dtype=float)
            credit = pd.Series(dtype=float)
            avg_credit = pd.Series(dtype=float)
            early_ratio = pd.Series(dtype=float)
            late_ratio = pd.Series(dtype=float)
            cross_discipline_ratio = pd.Series(dtype=float)
            type_entropy = pd.Series(dtype=float)
            level_ratio = pd.Series(dtype=float)
            challenge_depth = pd.Series(dtype=float)
            prerequisite_challenge_rate = pd.Series(dtype=float)
            extension_improvement_ratio = pd.Series(dtype=float)
            assessment_preference = pd.Series(dtype=float)
            high_risk_ratio = pd.Series(dtype=float)
            year_shift = pd.Series(dtype=float)
            term_switch_ratio = pd.Series(dtype=float)

        if not grade.empty and "XH" in grade.columns:
            grade["XH"] = grade["XH"].astype(str)
            grade_avg = _to_numeric(grade["KCCJ"]).groupby(grade["XH"]).mean() if "KCCJ" in grade.columns else pd.Series(dtype=float)
            grade_var = _to_numeric(grade["KCCJ"]).groupby(grade["XH"]).std() if "KCCJ" in grade.columns else pd.Series(dtype=float)
            pass_ratio = (_to_numeric(grade["KCCJ"]) >= 60).groupby(grade["XH"]).mean() if "KCCJ" in grade.columns else pd.Series(dtype=float)
            gpa_avg = _to_numeric(grade["JDCJ"]).groupby(grade["XH"]).mean() if "JDCJ" in grade.columns else pd.Series(dtype=float)
            grade_retake_ratio = (
                _flag_from_codes(grade["CXBKBZ"], {"2", "3", "4", "5"}, positive_regex="重修|补考|缓考|再次").groupby(grade["XH"]).mean()
                if "CXBKBZ" in grade.columns
                else pd.Series(dtype=float)
            )
            exam_risk_ratio = (
                _flag_from_codes(grade["KSLXDM"], {"2", "3", "4"}, positive_regex="闭卷|统考|考试").groupby(grade["XH"]).mean()
                if "KSLXDM" in grade.columns
                else pd.Series(dtype=float)
            )
            drift_ratio = (
                (grade["KCH"].astype(str).str[:2] != grade["TDKCH"].astype(str).str[:2]).groupby(grade["XH"]).mean()
                if set(["KCH", "TDKCH"]).issubset(grade.columns)
                else pd.Series(dtype=float)
            )
        else:
            grade_avg = pd.Series(dtype=float)
            grade_var = pd.Series(dtype=float)
            pass_ratio = pd.Series(dtype=float)
            gpa_avg = pd.Series(dtype=float)
            grade_retake_ratio = pd.Series(dtype=float)
            exam_risk_ratio = pd.Series(dtype=float)
            drift_ratio = pd.Series(dtype=float)

        df["course_selection_count"] = df["XH"].map(select_cnt).fillna(0.0)
        df["cross_discipline_course_ratio"] = df["XH"].map(cross_discipline_ratio).fillna(0.0)
        df["course_planning_proactivity"] = (
            0.7 * df["XH"].map(early_ratio).fillna(0.0) + 0.3 * (1 - df["XH"].map(late_ratio).fillna(0.0))
        ).clip(lower=0.0, upper=1.0)
        df["retake_dependency_ratio"] = (
            0.7 * df["XH"].map(retake_ratio).fillna(0.0) + 0.3 * df["XH"].map(grade_retake_ratio).fillna(0.0)
        ).clip(lower=0.0, upper=1.0)
        df["assessment_preference_index"] = (
            0.6 * df["XH"].map(assessment_preference).fillna(0.0) + 0.4 * (1 - df["XH"].map(exam_risk_ratio).fillna(0.0))
        ).clip(lower=0.0, upper=1.0)
        df["high_risk_course_ratio"] = (
            0.75 * df["XH"].map(high_risk_ratio).fillna(0.0) + 0.25 * df["XH"].map(exam_risk_ratio).fillna(0.0)
        ).clip(lower=0.0, upper=1.0)
        df["course_exploration_breadth"] = df["XH"].map(type_entropy).fillna(0.0)
        df["challenge_depth_index"] = _norm(
            0.7 * df["XH"].map(challenge_depth).fillna(0.0) + 0.3 * df["XH"].map(level_ratio).fillna(0.0)
        )
        df["prerequisite_challenge_rate"] = df["XH"].map(prerequisite_challenge_rate).fillna(0.0)
        df["extension_improvement_ratio"] = df["XH"].map(extension_improvement_ratio).fillna(0.0)
        df["late_selection_ratio"] = df["XH"].map(late_ratio).fillna(0.0)
        df["major_drift_trajectory"] = _norm(
            0.45 * df["XH"].map(year_shift).fillna(0.0)
            + 0.35 * df["XH"].map(term_switch_ratio).fillna(0.0)
            + 0.20 * df["XH"].map(drift_ratio).fillna(0.0)
        )
        df["professional_loyalty_index"] = (
            1 - (0.6 * df["cross_discipline_course_ratio"] + 0.4 * df["major_drift_trajectory"])
        ).clip(lower=0.0, upper=1.0)
        df["gpa_return_rate"] = _norm(
            _safe_div(df["XH"].map(gpa_avg).fillna(0.0), 1 + 1.2 * df["high_risk_course_ratio"] + 0.3 * _norm(df["XH"].map(avg_credit).fillna(0.0)))
            + 0.2 * _norm(df["XH"].map(pass_ratio).fillna(0.0))
            - 0.1 * _norm(df["XH"].map(grade_var).fillna(0.0))
        )
        df["prerequisite_challenge_rate"] = (
            0.7 * _norm(df["prerequisite_challenge_rate"])
            + 0.3 * _norm(df["challenge_depth_index"])
        ).clip(lower=0.0, upper=1.0)
        df["extension_improvement_ratio"] = (
            0.8 * _norm(df["extension_improvement_ratio"])
            + 0.2 * _norm(df["course_exploration_breadth"])
        ).clip(lower=0.0, upper=1.0)
        df["elective_diversity_index"] = df["course_exploration_breadth"]
        df["cross_level_course_ratio"] = df["XH"].map(level_ratio).fillna(0.0)
        df["course_load_index"] = _norm(df["XH"].map(credit).fillna(0.0))
        df["retake_course_ratio"] = df["retake_dependency_ratio"]
        df["grade_protection_index"] = (
            0.6 * _norm(df["XH"].map(grade_avg).fillna(0.0))
            + 0.4 * _norm(df["XH"].map(pass_ratio).fillna(0.0))
            - 0.3 * _norm(df["XH"].map(grade_var).fillna(0.0))
        ).clip(lower=0.0, upper=1.0)
        df["exploration_shift_index"] = _norm(df["major_drift_trajectory"])
        df["course_drift_ratio"] = df["major_drift_trajectory"]
        risk_balance_index = (1 - (df["high_risk_course_ratio"] - 0.55).abs() * 1.8).clip(lower=0.0, upper=1.0)

        df["course_exploration_total_score"] = (
            0.10 * _norm(df["cross_discipline_course_ratio"])
            + 0.11 * _norm(df["course_planning_proactivity"])
            + 0.10 * _norm(df["course_exploration_breadth"])
            + 0.10 * _norm(df["challenge_depth_index"])
            + 0.08 * _norm(df["prerequisite_challenge_rate"])
            + 0.08 * _norm(df["extension_improvement_ratio"])
            + 0.10 * _norm(df["professional_loyalty_index"])
            + 0.13 * _norm(df["gpa_return_rate"])
            + 0.10 * _norm(risk_balance_index)
            - 0.08 * _norm(df["retake_dependency_ratio"])
            - 0.06 * _norm(df["late_selection_ratio"])
            - 0.05 * _norm(df["major_drift_trajectory"])
            - 0.03 * _norm(df["assessment_preference_index"])
        ).clip(lower=0.0, upper=1.0)

        df["feature_grain"] = "student_term"
        df["time_window"] = "近2学期"
        df["snapshot_date"] = pd.Timestamp.now().normalize()

        ordered = [
            "XH",
            "feature_grain",
            "time_window",
            "snapshot_date",
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
            "course_selection_count",
            "elective_diversity_index",
            "cross_level_course_ratio",
            "course_load_index",
            "late_selection_ratio",
            "retake_course_ratio",
            "grade_protection_index",
            "exploration_shift_index",
            "course_drift_ratio",
            "course_exploration_total_score",
        ]
        return df[ordered].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = self.build()
        history_path = output_path.with_name("course_exploration_features_history.parquet")
        summary_path = output_path.with_suffix(".json")
        if history_path.exists():
            try:
                old = pd.read_parquet(history_path)
                history = pd.concat([old, result], ignore_index=True)
                history = history.drop_duplicates(subset=["XH", "snapshot_date"], keep="last")
            except Exception:
                history = result.copy()
        else:
            history = result.copy()
        try:
            result.to_parquet(output_path, index=False)
            history.to_parquet(history_path, index=False)
            summary_path.write_text(
                json.dumps(self._build_summary(result), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            return output_path
        except Exception:
            csv_path = output_path.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            history.to_csv(history_path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
            csv_path.with_suffix(".json").write_text(
                json.dumps(self._build_summary(result), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            return csv_path
