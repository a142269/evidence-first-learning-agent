from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def _safe_read_excel(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        return pd.DataFrame()
    frame = pd.read_excel(file_path)
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame


def _norm(series: pd.Series, reverse: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    min_v = values.min(skipna=True)
    max_v = values.max(skipna=True)
    if pd.isna(min_v) or pd.isna(max_v) or max_v == min_v:
        output = pd.Series(0.0, index=values.index)
    else:
        output = (values - min_v) / (max_v - min_v)
    if reverse:
        output = 1 - output
    return output.fillna(0.0)


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _max_consecutive_zero(values: Iterable[float]) -> int:
    longest = 0
    current = 0
    for value in values:
        if pd.isna(value) or float(value) <= 0:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest


def _ensure_student_id(frame: pd.DataFrame, candidates: list[str]) -> pd.DataFrame:
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

@dataclass
class LifestyleHealthFeatureBuilder:
    project_root: Path

    def _ods_path(self, *parts: str) -> Path:
        return self.project_root.joinpath("data", "ods", *parts)

    def load_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "physical_test": _safe_read_excel(self._ods_path("lifestyle_health", "体测数据.xlsx")),
            "fitness_exam": _safe_read_excel(self._ods_path("lifestyle_health", "学生体能考核.xlsx")),
            "pe_course": _safe_read_excel(self._ods_path("lifestyle_health", "体育课.xlsx")),
            "running": _safe_read_excel(self._ods_path("lifestyle_health", "跑步打卡.xlsx")),
            "daily_exercise": _safe_read_excel(self._ods_path("lifestyle_health", "日常锻炼.xlsx")),
            "access": _safe_read_excel(self._ods_path("social_activity", "门禁数据.xlsx")),
            "internet": _safe_read_excel(self._ods_path("lifestyle_health", "上网统计.xlsx")),
            "library": _safe_read_excel(self._ods_path("learning_logs", "图书馆打卡记录.xlsx")),
        }

    def build(self) -> pd.DataFrame:
        tables = self.load_tables()
        tables["physical_test"] = _ensure_student_id(tables["physical_test"], ["XH"])
        tables["fitness_exam"] = _ensure_student_id(tables["fitness_exam"], ["XH"])
        tables["pe_course"] = _ensure_student_id(tables["pe_course"], ["XH"])
        tables["running"] = _ensure_student_id(tables["running"], ["XH"])
        tables["daily_exercise"] = _ensure_student_id(tables["daily_exercise"], ["XH"])
        tables["access"] = _ensure_student_id(tables["access"], ["XH", "IDSERTAL"])
        tables["internet"] = _ensure_student_id(tables["internet"], ["XH"])
        tables["library"] = _ensure_student_id(tables["library"], ["XH"])

        students = set()
        for table in tables.values():
            if "XH" in table.columns:
                students.update(table["XH"].dropna().astype(str))
        if not students:
            return pd.DataFrame()

        df = pd.DataFrame({"XH": sorted(students)})

        physical = tables["physical_test"].copy()
        if not physical.empty and "XH" in physical.columns:
            physical["XH"] = physical["XH"].astype(str)
            zf = physical.assign(ZF_NUM=_to_numeric(physical["ZF"])).groupby("XH")["ZF_NUM"].mean() if "ZF" in physical.columns else pd.Series(dtype=float)
            if "BMI" in physical.columns:
                physical["TCNF_NUM"] = _to_numeric(physical["TCNF"]) if "TCNF" in physical.columns else np.nan
                physical["BMI_NUM"] = _to_numeric(physical["BMI"])
                physical = physical.sort_values(["XH", "TCNF_NUM"], na_position="last")
                first_bmi = physical.groupby("XH")["BMI_NUM"].first()
                last_bmi = physical.groupby("XH")["BMI_NUM"].last()
                bmi_change = ((last_bmi - first_bmi) / (first_bmi.replace(0, np.nan))).abs()
            else:
                bmi_change = pd.Series(dtype=float)

            fitness_fields = [col for col in ["FHL", "WS", "LDTY", "ZWTQQ", "BB", "YQ", "YWQZ", "YTXS"] if col in physical.columns]
            if fitness_fields:
                for field in fitness_fields:
                    physical[field] = _to_numeric(physical[field])
                fitness = physical.groupby("XH")[fitness_fields].mean(numeric_only=True)
                for reverse_col in ["WS", "BB", "YQ"]:
                    if reverse_col in fitness.columns:
                        fitness[reverse_col] = -fitness[reverse_col]
                fitness_base = fitness.mean(axis=1, skipna=True)
            else:
                fitness_base = pd.Series(dtype=float)
        else:
            zf = pd.Series(dtype=float)
            bmi_change = pd.Series(dtype=float)
            fitness_base = pd.Series(dtype=float)

        fitness_exam = tables["fitness_exam"].copy()
        if not fitness_exam.empty and "XH" in fitness_exam.columns and "HSCJ" in fitness_exam.columns:
            fitness_exam["XH"] = fitness_exam["XH"].astype(str)
            hscj = fitness_exam.assign(HSCJ_NUM=_to_numeric(fitness_exam["HSCJ"])).groupby("XH")["HSCJ_NUM"].mean()
        else:
            hscj = pd.Series(dtype=float)

        body_score = 0.7 * _norm(df["XH"].map(zf).astype(float)) + 0.3 * _norm(df["XH"].map(hscj).astype(float))
        df["physical_test_total_score"] = body_score
        df["bmi_change_rate"] = df["XH"].map(bmi_change).fillna(0.0)
        df["fitness_base_index"] = _norm(df["XH"].map(fitness_base).astype(float))

        pe_course = tables["pe_course"].copy()
        if not pe_course.empty and "XH" in pe_course.columns:
            pe_course["XH"] = pe_course["XH"].astype(str)
            kc_sum = pe_course.assign(KC_NUM=_to_numeric(pe_course["KC"])).groupby("XH")["KC_NUM"].sum(min_count=1) if "KC" in pe_course.columns else pd.Series(dtype=float)
            zkc_sum = pe_course.assign(ZKC_NUM=_to_numeric(pe_course["ZKC"])).groupby("XH")["ZKC_NUM"].sum(min_count=1) if "ZKC" in pe_course.columns else pd.Series(dtype=float)
            pe_rate = kc_sum / zkc_sum.replace(0, np.nan)
        else:
            pe_rate = pd.Series(dtype=float)
        df["pe_course_completion_rate"] = df["XH"].map(pe_rate).fillna(0.0)

        running = tables["running"].copy()
        if not running.empty and "XH" in running.columns:
            running["XH"] = running["XH"].astype(str)
            running["PUNCH_DAY_DT"] = _to_datetime(running["PUNCH_DAY"]) if "PUNCH_DAY" in running.columns else pd.NaT
            running["PUNCH_TIME_DT"] = _to_datetime(running["PUNCH_TIME"]) if "PUNCH_TIME" in running.columns else pd.NaT
            running["week_key"] = running["PUNCH_DAY_DT"].dt.isocalendar().week.astype("Int64")
            run_days = running.groupby("XH")["PUNCH_DAY"].nunique() if "PUNCH_DAY" in running.columns else pd.Series(dtype=float)
            run_weeks = running.groupby("XH")["week_key"].nunique()
            running_frequency = run_days / run_weeks.replace(0, np.nan)
            week_days_std = running.groupby(["XH", "week_key"])["PUNCH_DAY"].nunique().groupby("XH").std()
            continuity = 1 / (1 + week_days_std.fillna(0))
            run_hour = running["PUNCH_TIME_DT"].dt.hour
            morning = running.assign(_is_morning=((run_hour >= 5) & (run_hour < 9)).astype(int)).groupby("XH")["_is_morning"].mean()
            late = running.assign(_is_late=((run_hour >= 21) | (run_hour < 1)).astype(int)).groupby("XH")["_is_late"].mean()
            weekend = running.assign(_is_weekend=(running["PUNCH_DAY_DT"].dt.dayofweek >= 5).astype(int)).groupby("XH")["_is_weekend"].mean()
        else:
            running_frequency = pd.Series(dtype=float)
            continuity = pd.Series(dtype=float)
            morning = pd.Series(dtype=float)
            late = pd.Series(dtype=float)
            weekend = pd.Series(dtype=float)

        df["running_frequency"] = df["XH"].map(running_frequency).fillna(0.0)
        df["exercise_continuity_index"] = df["XH"].map(continuity).fillna(0.0)
        df["morning_exercise_ratio"] = df["XH"].map(morning).fillna(0.0)
        df["late_exercise_ratio"] = df["XH"].map(late).fillna(0.0)
        df["weekend_exercise_ratio"] = df["XH"].map(weekend).fillna(0.0)

        daily = tables["daily_exercise"].copy()
        if not daily.empty and "XH" in daily.columns:
            daily["XH"] = daily["XH"].astype(str)
            if "DKCS" in daily.columns:
                daily["DKCS"] = _to_numeric(daily["DKCS"])
            if "ZC" in daily.columns:
                daily["ZC_NUM"] = _to_numeric(daily["ZC"])
                daily = daily.sort_values(["XH", "ZC_NUM"], na_position="last")
            miss_weeks = daily.groupby("XH")["DKCS"].apply(_max_consecutive_zero) if "DKCS" in daily.columns else pd.Series(dtype=float)
            adherence = (daily.assign(_ok=(_to_numeric(daily["DKCS"]) >= 3).astype(int)).groupby("XH")["_ok"].mean()) if "DKCS" in daily.columns else pd.Series(dtype=float)
        else:
            miss_weeks = pd.Series(dtype=float)
            adherence = pd.Series(dtype=float)
        df["continuous_missed_exercise_weeks"] = df["XH"].map(miss_weeks).fillna(0.0)
        df["sports_adherence_rate"] = df["XH"].map(adherence).fillna(0.0)

        access = tables["access"].copy()
        if not access.empty and "XH" in access.columns:
            access["XH"] = access["XH"].astype(str)
            access["LOGINTIME_DT"] = _to_datetime(access["LOGINTIME"]) if "LOGINTIME" in access.columns else pd.NaT
            access_hour = access["LOGINTIME_DT"].dt.hour
            night_access = access.assign(_night=((access_hour >= 0) & (access_hour < 5)).astype(int)).groupby("XH")["_night"].sum()
            day_count = access.assign(_day=((access_hour >= 6) & (access_hour < 22)).astype(int)).groupby("XH")["_day"].sum()
            night_count = access.assign(_night_all=((access_hour >= 22) | (access_hour < 6)).astype(int)).groupby("XH")["_night_all"].sum()
            day_night_ratio = day_count / (night_count + 1)
            if "LOGINADDRESS" in access.columns:
                address = access["LOGINADDRESS"].astype(str)
                dorm_ratio = access.assign(_dorm=address.str.contains("宿舍|公寓|寝室", regex=True).astype(int)).groupby("XH")["_dorm"].mean()
                access_loc_cnt = access.groupby("XH")["LOGINADDRESS"].nunique()
            else:
                dorm_ratio = pd.Series(dtype=float)
                access_loc_cnt = pd.Series(dtype=float)
            weekly_night_std = access.assign(
                _week=access["LOGINTIME_DT"].dt.isocalendar().week.astype("Int64"),
                _night=((access_hour >= 22) | (access_hour < 6)).astype(int),
            ).groupby(["XH", "_week"])["_night"].sum().groupby("XH").std()
        else:
            night_access = pd.Series(dtype=float)
            day_night_ratio = pd.Series(dtype=float)
            dorm_ratio = pd.Series(dtype=float)
            access_loc_cnt = pd.Series(dtype=float)
            weekly_night_std = pd.Series(dtype=float)

        library = tables["library"].copy()
        if not library.empty and "XH" in library.columns:
            library["XH"] = library["XH"].astype(str)
            library["visittime_dt"] = _to_datetime(library["visittime"]) if "visittime" in library.columns else pd.NaT
            lib_activity = library.groupby("XH").size()
            lib_hour = library["visittime_dt"].dt.hour
            night_lib_ratio = library.assign(_night=((lib_hour >= 21) | (lib_hour < 5)).astype(int)).groupby("XH")["_night"].mean()
            lib_loc_cnt = library.groupby("XH")["gateno"].nunique() if "gateno" in library.columns else pd.Series(dtype=float)
            event_cnt = library.groupby("XH").size()
        else:
            lib_activity = pd.Series(dtype=float)
            night_lib_ratio = pd.Series(dtype=float)
            lib_loc_cnt = pd.Series(dtype=float)
            event_cnt = pd.Series(dtype=float)

        internet = tables["internet"].copy()
        if not internet.empty and "XH" in internet.columns:
            internet["XH"] = internet["XH"].astype(str)
            internet["TJNY_NUM"] = _to_numeric(internet["TJNY"]) if "TJNY" in internet.columns else np.nan
            internet["SWLJSC_NUM"] = _to_numeric(internet["SWLJSC"]) if "SWLJSC" in internet.columns else np.nan
            internet = internet.sort_values(["XH", "TJNY_NUM"], na_position="last")
            prev = internet.groupby("XH")["SWLJSC_NUM"].shift(1)
            growth = ((internet["SWLJSC_NUM"] - prev) / prev.replace(0, np.nan)).groupby(internet["XH"]).last()
        else:
            growth = pd.Series(dtype=float)

        event_total = df["XH"].map(access.groupby("XH").size() if not access.empty and "XH" in access.columns else pd.Series(dtype=float)).fillna(0) + df["XH"].map(event_cnt).fillna(0)
        location_total = df["XH"].map(access_loc_cnt).fillna(0) + df["XH"].map(lib_loc_cnt).fillna(0)
        activity_radius = location_total / event_total.replace(0, np.nan)

        df["nighttime_access_freq"] = df["XH"].map(night_access).fillna(0.0)
        df["online_duration_growth_rate"] = df["XH"].map(growth).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        df["day_night_activity_ratio"] = df["XH"].map(day_night_ratio).fillna(1.0)
        df["dorm_stay_ratio"] = df["XH"].map(dorm_ratio).fillna(0.0)
        df["library_activity_index"] = _norm(df["XH"].map(lib_activity).astype(float))
        df["night_library_ratio"] = df["XH"].map(night_lib_ratio).fillna(0.0)
        df["activity_radius_index"] = activity_radius.fillna(0.0)
        df["rhythm_volatility_index"] = df["XH"].map(weekly_night_std).fillna(0.0)

        event_hours = []
        if not access.empty and "LOGINTIME_DT" in access.columns:
            event_hours.append(access[["XH", "LOGINTIME_DT"]].rename(columns={"LOGINTIME_DT": "event_time"}))
        if not running.empty and "PUNCH_TIME_DT" in running.columns:
            event_hours.append(running[["XH", "PUNCH_TIME_DT"]].rename(columns={"PUNCH_TIME_DT": "event_time"}))
        if not library.empty and "visittime_dt" in library.columns:
            event_hours.append(library[["XH", "visittime_dt"]].rename(columns={"visittime_dt": "event_time"}))
        if event_hours:
            events = pd.concat(event_hours, ignore_index=True)
            events = events.dropna(subset=["event_time"])
            events["hour"] = events["event_time"].dt.hour
            hour_counts = events.groupby(["XH", "hour"]).size().rename("cnt").reset_index()
            total_counts = hour_counts.groupby("XH")["cnt"].transform("sum")
            hour_counts["p"] = hour_counts["cnt"] / total_counts
            entropy = (-hour_counts["p"] * np.log(hour_counts["p"])).groupby(hour_counts["XH"]).sum() / np.log(24)
        else:
            entropy = pd.Series(dtype=float)
        df["circadian_entropy"] = df["XH"].map(entropy).fillna(0.0)

        df["night_activity_index"] = (
            0.7 * _norm(df["nighttime_access_freq"])
            + 0.3 * _norm(df["late_exercise_ratio"])
        )
        df["lib_to_dorm_shift_index"] = _norm(df["dorm_stay_ratio"]) - _norm(df["library_activity_index"])
        df["sedentary_proxy_index"] = _norm(df["dorm_stay_ratio"]) - _norm(df["activity_radius_index"])

        body = 0.45 * _norm(df["physical_test_total_score"]) + 0.35 * _norm(df["fitness_base_index"]) + 0.20 * _norm(df["pe_course_completion_rate"])
        exercise = (
            0.30 * _norm(df["running_frequency"])
            + 0.20 * _norm(df["exercise_continuity_index"])
            + 0.20 * _norm(df["sports_adherence_rate"])
            + 0.15 * _norm(df["morning_exercise_ratio"])
            + 0.15 * _norm(df["weekend_exercise_ratio"])
        )
        rhythm = (
            0.20 * _norm(df["day_night_activity_ratio"])
            + 0.15 * _norm(df["library_activity_index"])
            + 0.20 * _norm(df["activity_radius_index"])
            + 0.15 * _norm(df["circadian_entropy"], reverse=True)
            + 0.15 * _norm(df["night_activity_index"], reverse=True)
            + 0.15 * _norm(df["rhythm_volatility_index"], reverse=True)
        )
        df["lifestyle_health_total_score"] = 0.30 * body + 0.30 * exercise + 0.40 * rhythm

        df["feature_grain"] = "student_week"
        df["time_window"] = "近4周"
        df["snapshot_date"] = pd.Timestamp.now().normalize()

        ordered = [
            "XH",
            "feature_grain",
            "time_window",
            "snapshot_date",
            "physical_test_total_score",
            "bmi_change_rate",
            "fitness_base_index",
            "pe_course_completion_rate",
            "running_frequency",
            "continuous_missed_exercise_weeks",
            "exercise_continuity_index",
            "sports_adherence_rate",
            "morning_exercise_ratio",
            "late_exercise_ratio",
            "weekend_exercise_ratio",
            "nighttime_access_freq",
            "online_duration_growth_rate",
            "night_activity_index",
            "circadian_entropy",
            "day_night_activity_ratio",
            "dorm_stay_ratio",
            "library_activity_index",
            "night_library_ratio",
            "lib_to_dorm_shift_index",
            "activity_radius_index",
            "sedentary_proxy_index",
            "rhythm_volatility_index",
            "lifestyle_health_total_score",
        ]
        existing = [col for col in ordered if col in df.columns]
        return df[existing].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = self.build()
        history_path = output_path.with_name("lifestyle_health_features_history.parquet")
        if history_path.exists():
            try:
                old = pd.read_parquet(history_path)
                result_history = pd.concat([old, result], ignore_index=True)
                result_history = result_history.drop_duplicates(subset=["XH", "snapshot_date"], keep="last")
            except Exception:
                result_history = result.copy()
        else:
            result_history = result.copy()
        try:
            result.to_parquet(output_path, index=False)
            result_history.to_parquet(history_path, index=False)
            return output_path
        except Exception:
            csv_path = output_path.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            result_history.to_csv(history_path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
            return csv_path
