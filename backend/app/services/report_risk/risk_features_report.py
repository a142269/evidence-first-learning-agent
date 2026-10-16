from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _safe_read_excel(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_excel(path)
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame


def _safe_read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _safe_read_json_records(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        records = obj.get("records") or obj.get("sample") or []
    elif isinstance(obj, list):
        records = obj
    else:
        records = []
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame


def _resolve_student_id(frame: pd.DataFrame, candidates: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    for col in candidates:
        if col in result.columns:
            result["XH"] = result[col].astype(str)
            break
    if "XH" in result.columns:
        result["XH"] = result["XH"].astype(str)
    return result


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _norm(series: pd.Series, reverse: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    min_v = values.min(skipna=True)
    max_v = values.max(skipna=True)
    if pd.isna(min_v) or pd.isna(max_v) or min_v == max_v:
        out = pd.Series(0.0, index=values.index)
    else:
        out = (values - min_v) / (max_v - min_v)
    if reverse:
        out = 1 - out
    return out.fillna(0.0).clip(0.0, 1.0)


def _pct_rank(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().sum() <= 1:
        return pd.Series(0.5, index=values.index)
    return values.rank(pct=True, method="average").fillna(0.5).clip(0.0, 1.0)


def _extract_last4_stats(frame: pd.DataFrame, value_col: str) -> pd.DataFrame:
    if frame.empty or "XH" not in frame.columns or value_col not in frame.columns:
        return pd.DataFrame(columns=["XH", f"{value_col}_last", f"{value_col}_prev_mean", f"{value_col}_delta_4w", f"{value_col}_decline_4w"])
    work = frame.copy()
    work["snapshot_date"] = _to_datetime(work["snapshot_date"]) if "snapshot_date" in work.columns else pd.NaT
    work[value_col] = _to_numeric(work[value_col])
    work = work.dropna(subset=["XH", value_col]).sort_values(["XH", "snapshot_date"])
    grouped = []
    for sid, sub in work.groupby("XH"):
        vals = sub[value_col].tail(4).tolist()
        if not vals:
            continue
        last = float(vals[-1])
        prev = vals[:-1]
        prev_mean = float(np.mean(prev)) if prev else float(last)
        delta = float(last - vals[0]) if len(vals) >= 2 else 0.0
        decline = int(len(vals) >= 4 and vals[0] > vals[1] > vals[2] > vals[3])
        grouped.append(
            {
                "XH": str(sid),
                f"{value_col}_last": last,
                f"{value_col}_prev_mean": prev_mean,
                f"{value_col}_delta_4w": delta,
                f"{value_col}_decline_4w": decline,
            }
        )
    return pd.DataFrame(grouped)


def _term_key(series: pd.Series) -> pd.Series:
    dt = _to_datetime(series)
    semester = np.where(dt.dt.month >= 7, 2, 1)
    return dt.dt.year.astype("Int64") * 10 + pd.Series(semester, index=dt.index, dtype="Int64")


@dataclass
class RiskFeatureBuilder:
    project_root: Path

    def _config_path(self) -> Path:
        return self.project_root / "configs" / "rules" / "risk_rules.yaml"

    def _mode_feature_path(self, name: str) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "modes" / f"{name}.parquet"
        if parquet_path.exists():
            return parquet_path
        return parquet_path.with_suffix(".csv")

    def _load_config(self) -> dict:
        path = self._config_path()
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _load_fusion(self, file_name: str) -> pd.DataFrame:
        frame = _safe_read_json_records(self.project_root / "330results" / file_name)
        return _resolve_student_id(frame, ["XH", "IDSERTAL", "USER_ID", "student_id"])

    def _load_students(self) -> pd.DataFrame:
        base = _safe_read_excel(self.project_root / "data" / "ods" / "student_base" / "学生基本信息.xlsx")
        base = _resolve_student_id(base, ["XH", "IDSERTAL", "USER_ID"])
        if base.empty or "XH" not in base.columns:
            return pd.DataFrame(columns=["XH", "major", "grade"])
        major_col = "ZY" if "ZY" in base.columns else ("MAJOR" if "MAJOR" in base.columns else None)
        grade_col = "NJ" if "NJ" in base.columns else ("GRADE" if "GRADE" in base.columns else None)
        result = pd.DataFrame({"XH": base["XH"].astype(str)})
        result["major"] = base[major_col].astype(str) if major_col else "未知专业"
        result["grade"] = base[grade_col].astype(str) if grade_col else "未知年级"
        return result.drop_duplicates(subset=["XH"], keep="last")

    def _load_status_factor(self) -> pd.Series:
        status = _safe_read_excel(self.project_root / "data" / "ods" / "student_base" / "学籍异动.xlsx")
        status = _resolve_student_id(status, ["XH", "IDSERTAL", "USER_ID"])
        if status.empty:
            return pd.Series(dtype=float)
        text_cols = [col for col in ["YDLBDM", "YDYYDM", "YDSM", "YXZ"] if col in status.columns]
        if not text_cols:
            return pd.Series(dtype=float)
        signals = status[text_cols].astype(str).agg("|".join, axis=1)
        flag = signals.str.contains("休学|留级|退学|延长|学业", regex=True).astype(int)
        return flag.groupby(status["XH"]).max().astype(float)

    def _load_grade_components(self) -> pd.DataFrame:
        grades = _safe_read_excel(self.project_root / "data" / "ods" / "grade_records" / "学生成绩.xlsx")
        grades = _resolve_student_id(grades, ["XH", "IDSERTAL", "USER_ID"])
        if grades.empty or "XH" not in grades.columns:
            return pd.DataFrame(columns=["XH", "academic_decline_raw", "fail_risk_raw"])
        if "KSSJ" not in grades.columns:
            return pd.DataFrame(columns=["XH", "academic_decline_raw", "fail_risk_raw"])
        grades["term_key"] = _term_key(grades["KSSJ"])
        score_col = "KCCJ" if "KCCJ" in grades.columns else ("JDCJ" if "JDCJ" in grades.columns else None)
        if score_col is None:
            return pd.DataFrame(columns=["XH", "academic_decline_raw", "fail_risk_raw"])
        grades["score"] = _to_numeric(grades[score_col])
        grades = grades.dropna(subset=["term_key", "score"])
        if grades.empty:
            return pd.DataFrame(columns=["XH", "academic_decline_raw", "fail_risk_raw"])
        term_stats = (
            grades.assign(fail=(grades["score"] < 60).astype(float))
            .groupby(["XH", "term_key"])
            .agg(term_score=("score", "mean"), fail_ratio=("fail", "mean"))
            .reset_index()
            .sort_values(["XH", "term_key"])
        )
        rows = []
        for sid, sub in term_stats.groupby("XH"):
            recent = sub.tail(2)
            current_score = float(recent["term_score"].iloc[-1])
            if len(recent) == 2:
                prev_score = float(recent["term_score"].iloc[0])
                decline = max((prev_score - current_score) / max(abs(prev_score), 1.0), 0.0)
            else:
                decline = np.nan
            fail_risk = float(recent["fail_ratio"].iloc[-1])
            rows.append({"XH": str(sid), "academic_decline_raw": decline, "fail_risk_raw": fail_risk})
        return pd.DataFrame(rows)

    def field_check(self) -> dict:
        lifestyle = self._load_fusion("lifestyle_health_fusion_results.json")
        social = self._load_fusion("social_life_fusion_results.json")
        course = self._load_fusion("course_exploration_fusion_results.json")
        ods_files = {
            "门禁": self.project_root / "data" / "ods" / "social_activity" / "门禁数据.xlsx",
            "上网": self.project_root / "data" / "ods" / "lifestyle_health" / "上网统计.xlsx",
            "跑步": self.project_root / "data" / "ods" / "lifestyle_health" / "跑步打卡.xlsx",
            "日常锻炼": self.project_root / "data" / "ods" / "lifestyle_health" / "日常锻炼.xlsx",
            "图书馆": self.project_root / "data" / "ods" / "learning_logs" / "图书馆打卡记录.xlsx",
            "成绩": self.project_root / "data" / "ods" / "grade_records" / "学生成绩.xlsx",
            "学籍异动": self.project_root / "data" / "ods" / "student_base" / "学籍异动.xlsx",
        }
        ods_summary = {}
        for key, path in ods_files.items():
            frame = _safe_read_excel(path)
            cols = [str(c).strip() for c in frame.columns]
            ods_summary[key] = {
                "exists": path.exists(),
                "rows": int(len(frame)),
                "id_candidates": [c for c in ["XH", "IDSERTAL", "USER_ID"] if c in cols],
                "columns": cols[:20],
            }
        return {
            "fusion_fields": {
                "lifestyle_health": list(lifestyle.columns),
                "social_life": list(social.columns),
                "course_exploration": list(course.columns),
            },
            "ods_fields": ods_summary,
        }

    def build(self) -> tuple[pd.DataFrame, dict]:
        config = self._load_config()
        id_candidates = config.get("id_mapping", {}).get("candidates", ["XH", "IDSERTAL", "USER_ID"])

        lifestyle_fusion = _resolve_student_id(self._load_fusion("lifestyle_health_fusion_results.json"), id_candidates)
        social_fusion = _resolve_student_id(self._load_fusion("social_life_fusion_results.json"), id_candidates)
        course_fusion = _resolve_student_id(self._load_fusion("course_exploration_fusion_results.json"), id_candidates)

        lifestyle_cur = _resolve_student_id(_safe_read_table(self._mode_feature_path("lifestyle_health_features")), id_candidates)
        lifestyle_hist = _resolve_student_id(_safe_read_table(self._mode_feature_path("lifestyle_health_features_history")), id_candidates)
        social_cur = _resolve_student_id(_safe_read_table(self._mode_feature_path("social_life_features")), id_candidates)
        social_hist = _resolve_student_id(_safe_read_table(self._mode_feature_path("social_life_features_history")), id_candidates)
        course_cur = _resolve_student_id(_safe_read_table(self._mode_feature_path("course_exploration_features")), id_candidates)

        students = set()
        for frame in [lifestyle_fusion, social_fusion, course_fusion, lifestyle_cur, social_cur, course_cur]:
            if "XH" in frame.columns:
                students.update(frame["XH"].dropna().astype(str))
        students_df = pd.DataFrame({"XH": sorted(students)})

        student_base = self._load_students()
        df = students_df.merge(student_base, on="XH", how="left")
        df["major"] = df["major"].fillna("未知专业")
        df["grade"] = df["grade"].fillna("未知年级")
        df["peer_group"] = df["major"].astype(str) + "|" + df["grade"].astype(str)

        if not lifestyle_fusion.empty:
            cols = [c for c in ["XH", "final_subtype_label", "subtype_label"] if c in lifestyle_fusion.columns]
            lf = lifestyle_fusion[cols].drop_duplicates(subset=["XH"], keep="last")
            lf["lifestyle_health_final_label"] = lf["final_subtype_label"] if "final_subtype_label" in lf.columns else lf["subtype_label"]
            df = df.merge(lf[["XH", "lifestyle_health_final_label"]], on="XH", how="left")
        else:
            df["lifestyle_health_final_label"] = ""

        if not social_fusion.empty:
            cols = [c for c in ["XH", "final_subtype_label", "subtype_label"] if c in social_fusion.columns]
            sf = social_fusion[cols].drop_duplicates(subset=["XH"], keep="last")
            sf["social_life_final_label"] = sf["final_subtype_label"] if "final_subtype_label" in sf.columns else sf["subtype_label"]
            df = df.merge(sf[["XH", "social_life_final_label"]], on="XH", how="left")
        else:
            df["social_life_final_label"] = ""

        lifestyle_cols = [
            "XH",
            "night_activity_index",
            "running_frequency",
            "lib_to_dorm_shift_index",
            "library_activity_index",
            "dorm_stay_ratio",
            "lifestyle_health_total_score",
        ]
        social_cols = [
            "XH",
            "formal_activity_participation_count",
            "formal_activity_frequency",
            "stable_copresence_partner_count",
            "online_interaction_count",
            "offline_activity_index",
            "social_life_total_score",
            "social_isolation_index",
        ]
        course_cols = ["XH", "course_exploration_total_score", "high_risk_course_ratio"]

        if not lifestyle_cur.empty:
            df = df.merge(lifestyle_cur[[c for c in lifestyle_cols if c in lifestyle_cur.columns]], on="XH", how="left")
        if not social_cur.empty:
            df = df.merge(social_cur[[c for c in social_cols if c in social_cur.columns]], on="XH", how="left")
        if not course_cur.empty:
            df = df.merge(course_cur[[c for c in course_cols if c in course_cur.columns]], on="XH", how="left")

        trend_sources = []
        for hist, metrics in [
            (lifestyle_hist, ["running_frequency", "night_activity_index", "lib_to_dorm_shift_index"]),
            (social_hist, ["formal_activity_participation_count", "online_interaction_count", "offline_activity_index"]),
        ]:
            for metric in metrics:
                trend_sources.append(_extract_last4_stats(hist, metric))
        for trend in trend_sources:
            if not trend.empty:
                df = df.merge(trend, on="XH", how="left")

        for col in [
            "night_activity_index",
            "running_frequency",
            "lib_to_dorm_shift_index",
            "formal_activity_participation_count",
            "stable_copresence_partner_count",
            "online_interaction_count",
            "offline_activity_index",
            "library_activity_index",
            "social_isolation_index",
            "high_risk_course_ratio",
            "course_exploration_total_score",
            "lifestyle_health_total_score",
            "social_life_total_score",
        ]:
            if col in df.columns:
                df[col] = _to_numeric(df[col]).fillna(0.0)

        if "night_activity_index" in df.columns:
            df["night_activity_peer_pct"] = df.groupby("peer_group")["night_activity_index"].transform(_pct_rank)
        else:
            df["night_activity_peer_pct"] = 0.5
        if "formal_activity_participation_count" in df.columns:
            df["formal_activity_peer_pct"] = df.groupby("peer_group")["formal_activity_participation_count"].transform(_pct_rank)
        else:
            df["formal_activity_peer_pct"] = 0.5
        if "stable_copresence_partner_count" in df.columns:
            df["stable_partner_peer_pct"] = df.groupby("peer_group")["stable_copresence_partner_count"].transform(_pct_rank)
        else:
            df["stable_partner_peer_pct"] = 0.5

        grade_components = self._load_grade_components()
        df = df.merge(grade_components, on="XH", how="left")

        fallback_decline = _norm(df.get("course_exploration_total_score", pd.Series(0.0, index=df.index)), reverse=True)
        df["academic_decline_score"] = _to_numeric(df["academic_decline_raw"]) if "academic_decline_raw" in df.columns else np.nan
        df["academic_decline_score"] = df["academic_decline_score"].fillna(fallback_decline).clip(0.0, 1.0)

        fallback_fail = _norm(df.get("high_risk_course_ratio", pd.Series(0.0, index=df.index)))
        df["fail_risk_score"] = _to_numeric(df["fail_risk_raw"]) if "fail_risk_raw" in df.columns else np.nan
        df["fail_risk_score"] = df["fail_risk_score"].fillna(fallback_fail).clip(0.0, 1.0)

        low_engage_parts = []
        low_engage_parts.append(_norm(df.get("formal_activity_participation_count", pd.Series(0.0, index=df.index)), reverse=True))
        low_engage_parts.append(_norm(df.get("offline_activity_index", pd.Series(0.0, index=df.index)), reverse=True))
        low_engage_parts.append(_norm(df.get("library_activity_index", pd.Series(0.0, index=df.index)), reverse=True))
        low_engage_parts.append(_norm(df.get("running_frequency", pd.Series(0.0, index=df.index)), reverse=True))
        df["low_engagement_score"] = pd.concat(low_engage_parts, axis=1).mean(axis=1).clip(0.0, 1.0)

        status_factor = self._load_status_factor()
        df["status_change_factor"] = df["XH"].map(status_factor).fillna(0.0).clip(0.0, 1.0)

        for col in [
            "running_frequency_decline_4w",
            "night_activity_index_delta_4w",
            "lib_to_dorm_shift_index_delta_4w",
            "formal_activity_participation_count_delta_4w",
            "online_interaction_count_delta_4w",
            "offline_activity_index_delta_4w",
        ]:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = _to_numeric(df[col]).fillna(0.0)

        df["feature_grain"] = "student_week"
        df["time_window"] = "近4周+历史回看"
        df["snapshot_date"] = pd.Timestamp.now().normalize()

        ordered = [
            "XH",
            "major",
            "grade",
            "peer_group",
            "feature_grain",
            "time_window",
            "snapshot_date",
            "lifestyle_health_final_label",
            "social_life_final_label",
            "night_activity_index",
            "night_activity_peer_pct",
            "night_activity_index_prev_mean",
            "night_activity_index_delta_4w",
            "running_frequency",
            "running_frequency_prev_mean",
            "running_frequency_delta_4w",
            "running_frequency_decline_4w",
            "lib_to_dorm_shift_index",
            "lib_to_dorm_shift_index_prev_mean",
            "lib_to_dorm_shift_index_delta_4w",
            "formal_activity_participation_count",
            "formal_activity_peer_pct",
            "formal_activity_participation_count_delta_4w",
            "stable_copresence_partner_count",
            "stable_partner_peer_pct",
            "online_interaction_count",
            "online_interaction_count_delta_4w",
            "offline_activity_index",
            "offline_activity_index_delta_4w",
            "library_activity_index",
            "dorm_stay_ratio",
            "social_isolation_index",
            "course_exploration_total_score",
            "high_risk_course_ratio",
            "academic_decline_score",
            "fail_risk_score",
            "low_engagement_score",
            "status_change_factor",
        ]
        existing = [c for c in ordered if c in df.columns]
        result = df[existing].sort_values("XH").reset_index(drop=True)
        field_check = self.field_check()
        return result, field_check

    def save(self, output_path: Path) -> tuple[Path, dict, dict]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result, field_check = self.build()
        try:
            result.to_parquet(output_path, index=False)
            saved_path = output_path
        except Exception:
            saved_path = output_path.with_suffix(".csv")
            result.to_csv(saved_path, index=False, encoding="utf-8-sig")
        summary = {
            "shape": [int(result.shape[0]), int(result.shape[1])],
            "distribution": {
                "lifestyle_health_final_label": result["lifestyle_health_final_label"].value_counts(dropna=False).to_dict() if "lifestyle_health_final_label" in result.columns else {},
                "social_life_final_label": result["social_life_final_label"].value_counts(dropna=False).to_dict() if "social_life_final_label" in result.columns else {},
            },
            "sample": result.head(3).replace({np.nan: None}).to_dict(orient="records"),
            "fields": list(result.columns),
            "field_check": field_check,
        }
        return saved_path, summary, field_check
