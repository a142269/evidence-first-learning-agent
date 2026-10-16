from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _safe_read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".json":
        try:
            return pd.read_json(path)
        except Exception:
            text = path.read_text(encoding="utf-8")
            try:
                payload = json.loads(text)
            except Exception:
                try:
                    return pd.read_json(path, lines=True)
                except Exception:
                    return pd.DataFrame()
            if isinstance(payload, list):
                return pd.DataFrame(payload)
            if isinstance(payload, dict):
                for key in ["data", "records", "sample", "items", "rows"]:
                    rows = payload.get(key)
                    if isinstance(rows, list):
                        return pd.DataFrame(rows)
                try:
                    return pd.DataFrame(payload)
                except Exception:
                    return pd.DataFrame([payload])
            return pd.DataFrame()
    return pd.DataFrame()


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            loaded = json.loads(text)
            if isinstance(loaded, list):
                return [str(v) for v in loaded if str(v).strip()]
        except Exception:
            pass
        parts = [seg.strip() for seg in text.replace("；", ";").split(";")]
        return [seg for seg in parts if seg and seg.lower() != "nan"]
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [text]


def _score_level(score: float) -> str:
    if score >= 0.75:
        return "高"
    if score >= 0.45:
        return "中"
    return "低"


def _warning_light(level: str) -> str:
    value = str(level).lower()
    if value == "high":
        return "red"
    if value == "medium":
        return "yellow"
    return "green"


def _safe_label(value: Any) -> str:
    if value is None:
        return "未识别"
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return "未识别"
    return text


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return {}
    return {}


@dataclass
class IndividualPortraitService:
    project_root: Path
    _ods_behavior_timeline_cache: pd.DataFrame | None = field(default=None, init=False, repr=False)

    def _prefer_json_path(self, base_parquet_path: Path) -> Path:
        full_json_path = base_parquet_path.with_suffix(".full.json")
        if full_json_path.exists():
            return full_json_path
        json_path = base_parquet_path.with_suffix(".json")
        if json_path.exists():
            return json_path
        csv_path = base_parquet_path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
        if base_parquet_path.exists():
            return base_parquet_path
        return json_path

    def _risk_feature_path(self) -> Path:
        parquet_path = self.project_root / "data" / "feature_store" / "risk" / "risk_features.parquet"
        return self._prefer_json_path(parquet_path)

    def _risk_result_path(self) -> Path:
        parquet_path = self.project_root / "data" / "ads" / "report_risk" / "risk_composite_results_report.parquet"
        return self._prefer_json_path(parquet_path)

    def _learning_behavior_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "learning_behavior_fusion_results.json"

    def _learning_outcome_path(self) -> Path:
        return self.project_root / "data" / "ads" / "pattern_results" / "learning_outcome_fusion_results.json"

    def _lifestyle_path(self) -> Path:
        parquet_path = self.project_root / "data" / "ads" / "pattern_results" / "lifestyle_health_fusion_results.parquet"
        return self._prefer_json_path(parquet_path)

    def _social_path(self) -> Path:
        parquet_path = self.project_root / "data" / "ads" / "pattern_results" / "social_life_fusion_results.parquet"
        return self._prefer_json_path(parquet_path)

    def _course_path(self) -> Path:
        parquet_path = self.project_root / "data" / "ads" / "pattern_results" / "course_exploration_fusion_results.parquet"
        return self._prefer_json_path(parquet_path)

    def _output_path(self) -> Path:
        return self.project_root / "data" / "ads" / "portraits" / "individual_portraits.json"

    def _history_paths(self) -> dict[str, Path]:
        modes_root = self.project_root / "data" / "feature_store" / "modes"
        return {
            "lifestyle_health": self._prefer_json_path(modes_root / "lifestyle_health_features_history.parquet"),
            "social_life": self._prefer_json_path(modes_root / "social_life_features_history.parquet"),
            "course_exploration": self._prefer_json_path(modes_root / "course_exploration_features_history.parquet"),
        }

    def _ods_grade_class_paths(self) -> list[Path]:
        ods_root = self.project_root / "data" / "ods" / "lifestyle_health"
        return [
            ods_root / "体育课.xlsx",
            ods_root / "体测数据.xlsx",
        ]

    def _attendance_summary_path(self) -> Path:
        return self.project_root / "data" / "ods" / "learning_logs" / "考勤汇总.xlsx"

    def _course_selection_path(self) -> Path:
        return self.project_root / "data" / "ods" / "course_selection" / "学生选课信息.xlsx"

    def _pe_course_path(self) -> Path:
        return self.project_root / "data" / "ods" / "lifestyle_health" / "体育课.xlsx"

    def _running_punch_path(self) -> Path:
        return self.project_root / "data" / "ods" / "lifestyle_health" / "跑步打卡.xlsx"

    def _student_base_path(self) -> Path:
        return self.project_root / "data" / "ods" / "student_base" / "学生基本信息.xlsx"

    def _load_student_base_profile(self) -> pd.DataFrame:
        path = self._student_base_path()
        if not path.exists():
            return pd.DataFrame(columns=["XH", "major_base", "academy_base", "grade_base", "class_name_base"])
        try:
            base = pd.read_excel(path)
        except Exception:
            return pd.DataFrame(columns=["XH", "major_base", "academy_base", "grade_base", "class_name_base"])
        id_col = "XH" if "XH" in base.columns else ("IDSERTAL" if "IDSERTAL" in base.columns else ("USER_ID" if "USER_ID" in base.columns else None))
        if not id_col:
            return pd.DataFrame(columns=["XH", "major_base", "academy_base", "grade_base", "class_name_base"])
        major_col = "ZY" if "ZY" in base.columns else ("MAJOR" if "MAJOR" in base.columns else None)
        academy_col = "XY" if "XY" in base.columns else ("YX" if "YX" in base.columns else ("ACADEMY" if "ACADEMY" in base.columns else None))
        grade_col = "NJ" if "NJ" in base.columns else ("GRADE" if "GRADE" in base.columns else None)
        class_col = "BJ" if "BJ" in base.columns else ("CLASS_NAME" if "CLASS_NAME" in base.columns else None)
        out = pd.DataFrame({"XH": base[id_col].astype(str).str.strip()})
        out["major_base"] = base[major_col].astype(str).str.strip() if major_col else ""
        out["academy_base"] = base[academy_col].astype(str).str.strip() if academy_col else ""
        out["grade_base"] = base[grade_col].astype(str).str.strip() if grade_col else ""
        out["class_name_base"] = base[class_col].astype(str).str.strip() if class_col else ""
        for col in ["major_base", "academy_base", "grade_base", "class_name_base"]:
            out[col] = out[col].replace({"nan": "", "None": "", "null": ""})
        out = out[out["XH"] != ""]
        return out.drop_duplicates(subset=["XH"], keep="last")

    def _load_ods_grade_class_map(self) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for path in self._ods_grade_class_paths():
            if not path.exists():
                continue
            try:
                frame = pd.read_excel(path)
            except Exception:
                continue
            required = {"XH", "NJ", "BJ"}
            if not required.issubset(set(frame.columns)):
                continue
            sub = frame[["XH", "NJ", "BJ"]].copy()
            sub["XH"] = sub["XH"].astype(str).str.strip()
            sub["NJ"] = sub["NJ"].astype(str).str.strip()
            sub["BJ"] = sub["BJ"].astype(str).str.strip()
            sub = sub[(sub["XH"] != "") & (sub["NJ"] != "") & (sub["BJ"] != "")]
            if not sub.empty:
                frames.append(sub)
        if not frames:
            return pd.DataFrame(columns=["XH", "ods_grade", "ods_class_name", "ods_mapped"])
        merged = pd.concat(frames, ignore_index=True)

        def _pick_mode(series: pd.Series) -> str:
            vc = series.value_counts(dropna=True)
            if vc.empty:
                return ""
            return str(vc.index[0]).strip()

        grouped = (
            merged.groupby("XH", as_index=False)
            .agg(
                ods_grade=("NJ", _pick_mode),
                ods_class_name=("BJ", _pick_mode),
            )
        )
        grouped["ods_mapped"] = 1
        return grouped

    def _prepare_risk_features(self) -> pd.DataFrame:
        df = _safe_read(self._risk_feature_path())
        if df.empty:
            return pd.DataFrame(columns=["XH"])
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        base_profile = self._load_student_base_profile()
        if not base_profile.empty:
            out = out.merge(base_profile, on="XH", how="left")
            if "major_base" in out.columns:
                out["major"] = out["major_base"].where(out["major_base"].astype(str).str.strip() != "", out.get("major", ""))
            if "academy_base" in out.columns:
                out["academy"] = out["academy_base"].where(out["academy_base"].astype(str).str.strip() != "", out.get("academy", ""))
            if "grade_base" in out.columns:
                out["grade"] = out["grade_base"].where(out["grade_base"].astype(str).str.strip() != "", out.get("grade", ""))
            if "class_name_base" in out.columns:
                out["class_name"] = out["class_name_base"].where(out["class_name_base"].astype(str).str.strip() != "", out.get("class_name", ""))
            out = out.drop(columns=[c for c in ["major_base", "academy_base", "grade_base", "class_name_base"] if c in out.columns])
        out["major"] = out.get("major", "未提供专业").fillna("未提供专业").astype(str).str.strip()
        out["major"] = out["major"].replace({"": "未提供专业", "nan": "未提供专业", "None": "未提供专业"})
        out["grade"] = out.get("grade", "未知年级").fillna("未知年级").astype(str).str.strip()
        out["grade"] = out["grade"].replace({"": "未知年级", "nan": "未知年级", "None": "未知年级"})
        if "academy" not in out.columns:
            out["academy"] = "未提供学院信息"
        out["academy"] = out["academy"].fillna("未提供学院信息").astype(str).str.strip()
        out["academy"] = out["academy"].replace({"": "未提供学院信息", "nan": "未提供学院信息", "None": "未提供学院信息"})
        if "class_name" not in out.columns:
            out["class_name"] = out["grade"].astype(str) + "-" + out["major"].astype(str) + "-默认班"
        out["class_name"] = out["class_name"].fillna(out["grade"].astype(str) + "-" + out["major"].astype(str) + "-默认班").astype(str).str.strip()
        empty_class = out["class_name"] == ""
        out.loc[empty_class, "class_name"] = out.loc[empty_class, "grade"].astype(str) + "-" + out.loc[empty_class, "major"].astype(str) + "-默认班"
        if "peer_group" not in out.columns:
            out["peer_group"] = out["major"]
        cols = [
            "XH",
            "major",
            "grade",
            "academy",
            "class_name",
            "peer_group",
            "academic_decline_score",
            "fail_risk_score",
            "low_engagement_score",
            "night_activity_index",
            "library_activity_index",
            "dorm_stay_ratio",
            "online_interaction_count",
            "stable_copresence_partner_count",
            "social_isolation_index",
            "night_activity_peer_pct",
            "formal_activity_peer_pct",
            "stable_partner_peer_pct",
        ]
        for col in cols:
            if col not in out.columns:
                out[col] = 0.0 if col not in {"XH", "major", "grade", "academy", "class_name", "peer_group"} else ""
        return out[cols].drop_duplicates("XH")

    def _prepare_risk_result(self) -> pd.DataFrame:
        df = _safe_read(self._risk_result_path())
        if df.empty:
            return pd.DataFrame(columns=["XH"])
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        cols = [
            "XH",
            "risk_level",
            "risk_score",
            "top_factors",
            "trend_4w",
            "peer_compare",
            "intervention_advice",
            "lifestyle_abnormal_risk",
            "social_low_integration_risk",
        ]
        existing = [c for c in cols if c in out.columns]
        return out[existing].drop_duplicates("XH")

    def _prepare_learning_behavior(self) -> pd.DataFrame:
        df = _safe_read(self._learning_behavior_path())
        if df.empty:
            return pd.DataFrame(columns=["XH"])
        out = df.copy()
        out["XH"] = out.get("student_id", out.get("XH", "")).astype(str)
        out["learning_behavior_label"] = out.get("final_label", "未识别")
        out["learning_behavior_score"] = pd.to_numeric(out.get("mode_score", 0.0), errors="coerce").fillna(0.0)
        out["learning_behavior_factors"] = out.get("explanation_factors", "[]")
        out["learning_behavior_warning"] = np.where(out.get("risk_flag", 0).fillna(0).astype(int) > 0, "high", "low")
        out["learning_behavior_label"] = out["learning_behavior_label"].fillna("未识别").astype(str)
        out["learning_behavior_factors"] = out["learning_behavior_factors"].fillna("[]")
        return out[
            ["XH", "learning_behavior_label", "learning_behavior_score", "learning_behavior_factors", "learning_behavior_warning"]
        ].drop_duplicates("XH")

    def _prepare_learning_outcome(self) -> pd.DataFrame:
        df = _safe_read(self._learning_outcome_path())
        if df.empty:
            return pd.DataFrame(columns=["XH"])
        out = df.copy()
        out["XH"] = out.get("student_id", out.get("XH", "")).astype(str)
        out["learning_outcome_label"] = out.get("final_label", "未识别")
        out["learning_outcome_score"] = pd.to_numeric(out.get("mode_score", 0.0), errors="coerce").fillna(0.0)
        out["learning_outcome_factors"] = out.get("explanation_factors", "[]")
        out["learning_outcome_warning"] = np.where(out.get("risk_flag", 0).fillna(0).astype(int) > 0, "high", "low")
        out["learning_outcome_label"] = out["learning_outcome_label"].fillna("未识别").astype(str)
        out["learning_outcome_factors"] = out["learning_outcome_factors"].fillna("[]")
        return out[
            ["XH", "learning_outcome_label", "learning_outcome_score", "learning_outcome_factors", "learning_outcome_warning"]
        ].drop_duplicates("XH")

    def _prepare_lifestyle(self) -> pd.DataFrame:
        df = _safe_read(self._lifestyle_path())
        if df.empty:
            return pd.DataFrame(columns=["XH"])
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        out["lifestyle_health_label"] = out.get("final_subtype_label", out.get("subtype_label", "未识别"))
        out["lifestyle_health_score"] = pd.to_numeric(out.get("mode_score", 0.0), errors="coerce").fillna(0.0)
        out["lifestyle_health_factors"] = out.get("final_explanation", "[]")
        out["lifestyle_health_warning"] = out.get("warning_level", "normal").fillna("normal").astype(str).str.lower()
        out["lifestyle_health_label"] = out["lifestyle_health_label"].fillna("未识别").astype(str)
        out["lifestyle_health_factors"] = out["lifestyle_health_factors"].fillna("[]")
        return out[
            ["XH", "lifestyle_health_label", "lifestyle_health_score", "lifestyle_health_factors", "lifestyle_health_warning"]
        ].drop_duplicates("XH")

    def _prepare_social(self) -> pd.DataFrame:
        df = _safe_read(self._social_path())
        if df.empty:
            return pd.DataFrame(columns=["XH"])
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        out["social_life_label"] = out.get("final_subtype_label", out.get("subtype_label", "未识别"))
        out["social_life_score"] = pd.to_numeric(out.get("mode_score", 0.0), errors="coerce").fillna(0.0)
        out["social_life_factors"] = out.get("final_explanation", "[]")
        out["social_life_warning"] = out.get("warning_level", "normal").fillna("normal").astype(str).str.lower()
        out["social_life_label"] = out["social_life_label"].fillna("未识别").astype(str)
        out["social_life_factors"] = out["social_life_factors"].fillna("[]")
        return out[["XH", "social_life_label", "social_life_score", "social_life_factors", "social_life_warning"]].drop_duplicates("XH")

    def _prepare_course(self) -> pd.DataFrame:
        df = _safe_read(self._course_path())
        if df.empty:
            return pd.DataFrame(columns=["XH"])
        out = df.copy()
        out["XH"] = out["XH"].astype(str)
        out["course_exploration_label"] = out.get("final_label", "未识别")
        out["course_exploration_score"] = pd.to_numeric(out.get("mode_score", 0.0), errors="coerce").fillna(0.0)
        out["course_exploration_factors"] = out.get("top_factors", "[]")
        out["course_exploration_warning"] = out.get("warning_level", "normal").fillna("normal").astype(str).str.lower()
        out["course_exploration_label"] = out["course_exploration_label"].fillna("未识别").astype(str)
        out["course_exploration_factors"] = out["course_exploration_factors"].fillna("[]")
        return out[
            ["XH", "course_exploration_label", "course_exploration_score", "course_exploration_factors", "course_exploration_warning"]
        ].drop_duplicates("XH")

    def _load_histories(self) -> dict[str, pd.DataFrame]:
        calendar = self._load_academic_calendar()
        output: dict[str, pd.DataFrame] = {}
        for mode_key, path in self._history_paths().items():
            frame = _safe_read(path)
            if frame.empty:
                output[mode_key] = pd.DataFrame(columns=["XH", "snapshot_date", "time_window", "academic_window"])
                continue
            frame = frame.copy()
            frame["XH"] = frame["XH"].astype(str)
            frame["snapshot_date"] = pd.to_datetime(frame.get("snapshot_date"), errors="coerce")
            frame = frame.dropna(subset=["snapshot_date"])
            if "time_window" not in frame.columns:
                frame["time_window"] = ""
            frame["time_window"] = frame["time_window"].fillna("").astype(str).str.strip()
            if not calendar.empty:
                frame = self._attach_academic_window(frame, calendar)
            else:
                frame["academic_window"] = ""
            output[mode_key] = frame
        return output

    def _load_academic_calendar(self) -> pd.DataFrame:
        path = self._attendance_summary_path()
        if not path.exists():
            return pd.DataFrame(columns=["calendar_date", "academic_window"])
        try:
            df = pd.read_excel(path, usecols=["XN", "XQ", "ZC", "RQ"])
        except Exception:
            return pd.DataFrame(columns=["calendar_date", "academic_window"])
        if df.empty:
            return pd.DataFrame(columns=["calendar_date", "academic_window"])
        out = df.copy()
        out["calendar_date"] = pd.to_datetime(out.get("RQ"), unit="ms", errors="coerce")
        out = out.dropna(subset=["calendar_date"])
        out["XN"] = out.get("XN", "").fillna("").astype(str).str.strip()
        out["XQ"] = pd.to_numeric(out.get("XQ"), errors="coerce").fillna(0).astype(int)
        out["ZC"] = pd.to_numeric(out.get("ZC"), errors="coerce").fillna(0).astype(int)
        out["academic_window"] = out.apply(
            lambda row: f"{row['XN']}学年-第{row['XQ']}学期-第{row['ZC']}周" if row["XN"] and row["XQ"] > 0 and row["ZC"] > 0 else "",
            axis=1,
        )
        out = out[out["academic_window"] != ""]
        if out.empty:
            return pd.DataFrame(columns=["calendar_date", "academic_window"])
        out = out[["calendar_date", "academic_window"]].drop_duplicates(subset=["calendar_date"], keep="last").sort_values("calendar_date")
        return out

    def _attach_academic_window(self, frame: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or calendar.empty:
            frame["academic_window"] = ""
            return frame
        left = frame.sort_values("snapshot_date").copy()
        right = calendar.sort_values("calendar_date").copy()
        joined = pd.merge_asof(
            left,
            right,
            left_on="snapshot_date",
            right_on="calendar_date",
            direction="nearest",
            tolerance=pd.Timedelta(days=45),
        )
        joined["academic_window"] = joined.get("academic_window", "").fillna("").astype(str).str.strip()
        joined = joined.drop(columns=[c for c in ["calendar_date"] if c in joined.columns])
        return joined

    def _load_student_time_refs(self) -> dict[str, dict[str, list[str]]]:
        rows: list[dict[str, Any]] = []
        attendance_path = self._attendance_summary_path()
        if attendance_path.exists():
            try:
                att = pd.read_excel(attendance_path, usecols=["XH", "XN", "XQ", "ZC", "RQ"])
                if not att.empty:
                    att = att.copy()
                    att["XH"] = att.get("XH", "").astype(str).str.strip()
                    att["XN"] = att.get("XN", "").fillna("").astype(str).str.strip()
                    att["XQ"] = pd.to_numeric(att.get("XQ"), errors="coerce").fillna(0).astype(int)
                    att["ZC"] = pd.to_numeric(att.get("ZC"), errors="coerce").fillna(0).astype(int)
                    att["ref_date"] = pd.to_datetime(att.get("RQ"), unit="ms", errors="coerce")
                    for _, item in att.iterrows():
                        sid = str(item.get("XH", "")).strip()
                        if not sid or pd.isna(item.get("ref_date")):
                            continue
                        xn = str(item.get("XN", "")).strip()
                        xq = int(item.get("XQ", 0))
                        zc = int(item.get("ZC", 0))
                        rows.append(
                            {
                                "XH": sid,
                                "ref_date": item.get("ref_date"),
                                "week_label": f"{xn}学年-第{xq}学期-第{zc}周" if xn and xq > 0 and zc > 0 else "",
                                "term_label": f"{xn}学年-第{xq}学期" if xn and xq > 0 else "",
                            }
                        )
            except Exception:
                pass
        selection_path = self._course_selection_path()
        if selection_path.exists():
            try:
                sel = pd.read_excel(selection_path, usecols=["XH", "KKXN", "KKXQ", "XKRQ"])
                if not sel.empty:
                    sel = sel.copy()
                    sel["XH"] = sel.get("XH", "").astype(str).str.strip()
                    sel["KKXN"] = sel.get("KKXN", "").fillna("").astype(str).str.strip()
                    sel["KKXQ"] = pd.to_numeric(sel.get("KKXQ"), errors="coerce").fillna(0).astype(int)
                    sel["ref_date"] = pd.to_datetime(sel.get("XKRQ"), errors="coerce")
                    for _, item in sel.iterrows():
                        sid = str(item.get("XH", "")).strip()
                        if not sid:
                            continue
                        rows.append(
                            {
                                "XH": sid,
                                "ref_date": item.get("ref_date"),
                                "week_label": "",
                                "term_label": f"{str(item.get('KKXN', '')).strip()}学年-第{int(item.get('KKXQ', 0))}学期" if str(item.get("KKXN", "")).strip() and int(item.get("KKXQ", 0)) > 0 else "",
                            }
                        )
            except Exception:
                pass
        pe_path = self._pe_course_path()
        if pe_path.exists():
            try:
                pe = pd.read_excel(pe_path, usecols=["XH", "XQ"])
                if not pe.empty:
                    pe = pe.copy()
                    pe["XH"] = pe.get("XH", "").astype(str).str.strip()
                    pe["XQ"] = pe.get("XQ", "").fillna("").astype(str).str.strip()
                    for _, item in pe.iterrows():
                        sid = str(item.get("XH", "")).strip()
                        term = str(item.get("XQ", "")).strip()
                        if not sid or not term:
                            continue
                        rows.append({"XH": sid, "ref_date": pd.NaT, "week_label": "", "term_label": term})
            except Exception:
                pass
        run_path = self._running_punch_path()
        if run_path.exists():
            try:
                run = pd.read_excel(run_path, usecols=["XH", "TERM_ID", "WEEKNUM", "PUNCH_DAY"])
                if not run.empty:
                    run = run.copy()
                    run["XH"] = run.get("XH", "").astype(str).str.strip()
                    run["TERM_ID"] = run.get("TERM_ID", "").fillna("").astype(str).str.strip()
                    run["WEEKNUM"] = pd.to_numeric(run.get("WEEKNUM"), errors="coerce").fillna(0).astype(int)
                    run["ref_date"] = pd.to_datetime(run.get("PUNCH_DAY"), errors="coerce")
                    for _, item in run.iterrows():
                        sid = str(item.get("XH", "")).strip()
                        if not sid:
                            continue
                        term_id = str(item.get("TERM_ID", "")).strip()
                        week_num = int(item.get("WEEKNUM", 0))
                        rows.append(
                            {
                                "XH": sid,
                                "ref_date": item.get("ref_date"),
                                "week_label": self._academic_week_label(item.get("ref_date"), week_num),
                                "term_label": self._academic_term_label(item.get("ref_date")),
                            }
                        )
            except Exception:
                pass
        if not rows:
            return {}
        out = pd.DataFrame(rows)
        out["XH"] = out["XH"].astype(str).str.strip()
        out["ref_date"] = pd.to_datetime(out.get("ref_date"), errors="coerce")
        out = out[out["XH"] != ""]
        out = out.sort_values("ref_date", na_position="first")
        refs: dict[str, dict[str, list[str]]] = {}
        for sid, g in out.groupby("XH"):
            week_labels = [x for x in g["week_label"].astype(str).tolist() if x]
            term_labels = [x for x in g["term_label"].astype(str).tolist() if x]
            refs[str(sid)] = {
                "week_labels": list(dict.fromkeys(week_labels)),
                "term_labels": list(dict.fromkeys(term_labels)),
            }
        return refs

    def _academic_term_label(self, snapshot_date: Any) -> str:
        dt = pd.to_datetime(snapshot_date, errors="coerce")
        if pd.isna(dt):
            return ""
        year = int(dt.year)
        month = int(dt.month)
        day = int(dt.day)
        first_term = (month > 9) or (month == 9 and day >= 1)
        start_year = year if first_term else year - 1
        term_no = 1 if first_term else 2
        return f"{start_year}-{start_year+1}学年-第{term_no}学期"

    def _academic_week_label(self, snapshot_date: Any, week_hint: int = 0) -> str:
        term_label = self._academic_term_label(snapshot_date)
        if not term_label:
            return ""
        week_no = int(week_hint) if int(pd.to_numeric(week_hint, errors="coerce") or 0) > 0 else int(pd.to_datetime(snapshot_date, errors="coerce").isocalendar().week)
        return f"{term_label}-第{week_no}周"

    def _parse_datetime_series(self, series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() > 0:
            parsed_ms = pd.to_datetime(numeric, unit="ms", errors="coerce")
            parsed_s = pd.to_datetime(numeric, unit="s", errors="coerce")
            parsed_excel = pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")
            valid_ms = parsed_ms.between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"))
            valid_s = parsed_s.between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"))
            valid_excel = parsed_excel.between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"))
            if valid_ms.sum() >= valid_s.sum() and valid_ms.sum() >= valid_excel.sum() and valid_ms.sum() > 0:
                return parsed_ms
            if valid_s.sum() >= valid_excel.sum() and valid_s.sum() > 0:
                return parsed_s
            if valid_excel.sum() > 0:
                return parsed_excel
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().sum() > 0:
            return parsed
        text = series.astype(str).str.strip()
        month_like = text.str.match(r"^\d{6}$", na=False)
        out = pd.to_datetime(text, format="%Y-%m-%d %H:%M:%S", errors="coerce")
        missing = out.isna()
        if missing.any():
            out.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y-%m-%d", errors="coerce")
        missing = out.isna()
        if missing.any():
            out.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y/%m/%d %H:%M:%S", errors="coerce")
        missing = out.isna()
        if missing.any():
            out.loc[missing] = pd.to_datetime(text.loc[missing], format="%Y/%m/%d", errors="coerce")
        if month_like.any():
            out.loc[month_like] = pd.to_datetime(text.loc[month_like] + "01", format="%Y%m%d", errors="coerce")
        return out

    def _collect_ods_behavior_records(self) -> pd.DataFrame:
        sources: list[tuple[Path, str, list[str], float]] = [
            (self._attendance_summary_path(), "RQ", ["XH"], 0.12),
            (self.project_root / "data" / "ods" / "learning_logs" / "图书馆打卡记录.xlsx", "visittime", ["XH"], 0.22),
            (self.project_root / "data" / "ods" / "learning_logs" / "学生签到记录.xlsx", "ATTEND_TIME", ["XH"], 0.16),
            (self.project_root / "data" / "ods" / "learning_logs" / "学生作业提交记录.xlsx", "ANSWER_TIME", ["XH"], 0.20),
            (self.project_root / "data" / "ods" / "learning_logs" / "考试提交记录.xlsx", "ANSWER_TIME", ["XH"], 0.22),
            (self.project_root / "data" / "ods" / "learning_logs" / "讨论记录.xlsx", "CREATE_TIME", ["XH", "CREATER_LOGIN_NAME"], 0.12),
            (self.project_root / "data" / "ods" / "learning_logs" / "课堂任务参与.xlsx", "CREATE_TIME", ["XH", "USER_ID"], 0.20),
            (self._course_selection_path(), "XKRQ", ["XH"], 0.10),
            (self._running_punch_path(), "PUNCH_DAY", ["XH"], 0.14),
            (self.project_root / "data" / "ods" / "lifestyle_health" / "上网统计.xlsx", "TJNY", ["XH"], 0.08),
        ]
        rows: list[pd.DataFrame] = []
        for path, time_col, id_cols, weight in sources:
            if not path.exists():
                continue
            try:
                frame = pd.read_excel(path)
            except Exception:
                continue
            if frame.empty or time_col not in frame.columns:
                continue
            sid_col = next((col for col in id_cols if col in frame.columns), None)
            if sid_col is None:
                continue
            part = pd.DataFrame()
            part["XH"] = frame[sid_col].astype(str).str.strip()
            part["snapshot_date"] = self._parse_datetime_series(frame[time_col])
            part["snapshot_date"] = pd.to_datetime(part["snapshot_date"], errors="coerce")
            part = part[
                part["snapshot_date"].between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"), inclusive="both")
            ]
            part = part[(part["XH"] != "") & part["snapshot_date"].notna()]
            if part.empty:
                continue
            part["weight"] = float(weight)
            rows.append(part[["XH", "snapshot_date", "weight"]])
        for path in (self.project_root / "data" / "ods").glob("**/*.xlsx"):
            if any(path == item[0] for item in sources):
                continue
            try:
                headers = pd.read_excel(path, nrows=0)
            except Exception:
                continue
            cols = set(str(c) for c in headers.columns)
            if "XH" not in cols or "XN" not in cols or "XQ" not in cols:
                continue
            usecols = [col for col in ["XH", "XN", "XQ", "ZC", "RQ"] if col in cols]
            try:
                frame = pd.read_excel(path, usecols=usecols)
            except Exception:
                continue
            if frame.empty:
                continue
            part = pd.DataFrame()
            part["XH"] = frame["XH"].astype(str).str.strip()
            if "RQ" in frame.columns:
                part["snapshot_date"] = self._parse_datetime_series(frame["RQ"])
            else:
                xn = frame["XN"].astype(str).str.extract(r"(\d{4})", expand=False)
                year = pd.to_numeric(xn, errors="coerce")
                term = pd.to_numeric(frame["XQ"], errors="coerce").fillna(1).astype(int)
                week = pd.to_numeric(frame["ZC"], errors="coerce").fillna(1).astype(int) if "ZC" in frame.columns else pd.Series(1, index=frame.index)
                month = np.where(term == 2, 3, 9)
                part["snapshot_date"] = pd.to_datetime(
                    {
                        "year": np.where(term == 2, year + 1, year).astype("Int64"),
                        "month": month,
                        "day": 1,
                    },
                    errors="coerce",
                ) + pd.to_timedelta((week - 1).clip(lower=0) * 7, unit="D")
            part["snapshot_date"] = pd.to_datetime(part["snapshot_date"], errors="coerce")
            part = part[
                part["snapshot_date"].between(pd.Timestamp("2000-01-01"), pd.Timestamp("2035-12-31"), inclusive="both")
            ]
            part = part[(part["XH"] != "") & part["snapshot_date"].notna()]
            if part.empty:
                continue
            part["weight"] = 0.06
            rows.append(part[["XH", "snapshot_date", "weight"]])
        if not rows:
            return pd.DataFrame(columns=["XH", "snapshot_date", "weight"])
        all_rows = pd.concat(rows, ignore_index=True)
        all_rows["snapshot_date"] = pd.to_datetime(all_rows["snapshot_date"], errors="coerce")
        all_rows = all_rows.dropna(subset=["snapshot_date"])
        return all_rows

    def _load_ods_behavior_timeline(self) -> pd.DataFrame:
        if self._ods_behavior_timeline_cache is not None:
            return self._ods_behavior_timeline_cache
        records = self._collect_ods_behavior_records()
        if records.empty:
            self._ods_behavior_timeline_cache = pd.DataFrame(columns=["XH", "academic_window", "snapshot_date", "behavior_proxy_score", "event_count"])
            return self._ods_behavior_timeline_cache
        calendar = self._load_academic_calendar()
        if calendar.empty:
            records["academic_window"] = records["snapshot_date"].apply(self._academic_term_label)
        else:
            records = self._attach_academic_window(records, calendar)
            records["academic_window"] = records.get("academic_window", "").fillna("").astype(str).str.strip()
            missing = records["academic_window"] == ""
            if missing.any():
                records.loc[missing, "academic_window"] = records.loc[missing, "snapshot_date"].apply(self._academic_term_label)
        records["academic_window"] = records["academic_window"].fillna("").astype(str).str.strip()
        invalid = ~records["academic_window"].str.match(r"^\d{4}-\d{4}学年-第\d+学期$", na=False)
        if invalid.any():
            records.loc[invalid, "academic_window"] = records.loc[invalid, "snapshot_date"].apply(self._academic_term_label)
        records = records[records["academic_window"] != ""]
        grouped = (
            records.groupby(["XH", "academic_window"], as_index=False)
            .agg(
                weighted_count=("weight", "sum"),
                event_count=("weight", "count"),
                snapshot_date=("snapshot_date", "max"),
            )
            .sort_values(["XH", "snapshot_date"])
        )
        grouped["weighted_count"] = pd.to_numeric(grouped["weighted_count"], errors="coerce").fillna(0.0)
        grouped["event_count"] = pd.to_numeric(grouped["event_count"], errors="coerce").fillna(0).astype(int)
        grouped["behavior_proxy_score"] = grouped.groupby("XH")["weighted_count"].transform(
            lambda s: (s - s.min()) / (s.max() - s.min()) if float((s.max() - s.min())) > 1e-9 else 0.5
        )
        grouped["behavior_proxy_score"] = grouped["behavior_proxy_score"].clip(0.0, 1.0).round(4)
        self._ods_behavior_timeline_cache = grouped[["XH", "academic_window", "snapshot_date", "behavior_proxy_score", "event_count"]]
        return self._ods_behavior_timeline_cache

    def _resolve_timeline_key(self, student_id: str, time_window: str, academic_window: str, snapshot_date: Any, time_refs: dict[str, dict[str, list[str]]]) -> str:
        academic_window_text = str(academic_window or "").strip()
        if academic_window_text:
            if re.match(r"^\d{4}-\d{4}学年-第\d+学期(?:-第\d+周)?$", academic_window_text):
                return academic_window_text
            return academic_window_text
        time_window_text = str(time_window or "").strip()
        refs = time_refs.get(str(student_id), {})
        week_labels = [x for x in refs.get("week_labels", []) if re.match(r"^\d{4}-\d{4}学年-第\d+学期-第\d+周$", str(x))]
        term_labels = [x for x in refs.get("term_labels", []) if re.match(r"^\d{4}-\d{4}学年-第\d+学期$", str(x))]
        if "学期" in time_window_text and term_labels:
            return term_labels[-1]
        if "8周" in time_window_text and week_labels:
            return week_labels[-2] if len(week_labels) >= 2 else week_labels[-1]
        if "4周" in time_window_text and week_labels:
            return week_labels[-1]
        if time_window_text and week_labels:
            return week_labels[-1]
        snapshot = pd.to_datetime(snapshot_date, errors="coerce")
        if pd.notna(snapshot):
            if "周" in time_window_text:
                return self._academic_week_label(snapshot)
            return self._academic_term_label(snapshot)
        if time_window_text:
            if "学期" in time_window_text:
                return ""
            if "周" in time_window_text:
                return ""
            return time_window_text
        return ""

    def _parse_time_label(self, label: str) -> dict[str, Any]:
        text = str(label or "").strip()
        if not text:
            return {"granularity": "unknown", "label": ""}
        week_match = re.match(r"^(\d{4}(?:-\d{4})?)学年-第(\d+)学期-第(\d+)周$", text)
        if week_match:
            year, term, week = week_match.groups()
            term_i = int(term)
            week_i = int(week)
            return {
                "granularity": "week",
                "label": text,
                "academic_year": year,
                "term": term_i,
                "week": week_i,
                "sort_key": f"{year}-{term_i:02d}-{week_i:02d}",
            }
        term_match = re.match(r"^(\d{4}(?:-\d{4})?)学年-第(\d+)学期$", text)
        if term_match:
            year, term = term_match.groups()
            term_i = int(term)
            return {
                "granularity": "term",
                "label": text,
                "academic_year": year,
                "term": term_i,
                "sort_key": f"{year}-{term_i:02d}",
            }
        term_week_match = re.match(r"^TERM(\d+)-第(\d+)周$", text)
        if term_week_match:
            term_id, week = term_week_match.groups()
            return {
                "granularity": "week",
                "label": text,
                "academic_year": f"TERM{term_id}",
                "term": int(term_id),
                "week": int(week),
                "sort_key": f"TERM{int(term_id):04d}-{int(week):02d}",
            }
        term_only_match = re.match(r"^TERM(\d+)$", text)
        if term_only_match:
            term_id = int(term_only_match.group(1))
            return {
                "granularity": "term",
                "label": text,
                "academic_year": f"TERM{term_id}",
                "term": term_id,
                "sort_key": f"TERM{term_id:04d}",
            }
        date_value = pd.to_datetime(text, errors="coerce")
        if pd.notna(date_value):
            return {
                "granularity": "date",
                "label": str(date_value.date()),
                "sort_key": str(date_value.date()),
            }
        if "学期" in text:
            return {"granularity": "term", "label": text, "sort_key": text}
        if "周" in text:
            return {"granularity": "week", "label": text, "sort_key": text}
        return {"granularity": "unknown", "label": text, "sort_key": text}

    def _standardize_time_axis(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        if not records:
            return {
                "granularity": "week",
                "labels": [],
                "timeline_score": {},
                "mixed_conflict_detected": False,
                "resolution_strategy": "none",
                "time_caliber_note": "时间口径统一为学年-学期-周；当前暂无可用时序点。",
                "series_by_granularity": {"week": {}, "term": {}, "date": {}},
                "render_spec": {"chart_type": "line", "split_required": False},
            }
        frame = pd.DataFrame(records).copy()
        frame["parsed"] = frame["timeline_key"].apply(self._parse_time_label)
        frame["granularity"] = frame["parsed"].apply(lambda x: str(x.get("granularity", "unknown")))
        week_count = int((frame["granularity"] == "week").sum())
        term_count = int((frame["granularity"] == "term").sum())
        date_count = int((frame["granularity"] == "date").sum())
        target = "week" if week_count > 0 else ("term" if term_count > 0 else "date")
        conflict_rows = frame[(frame["granularity"] != target) & (frame["granularity"] != "unknown")]
        mixed_conflict = not conflict_rows.empty
        frame["score"] = pd.to_numeric(frame.get("score"), errors="coerce").fillna(0.0).clip(0.0, 1.0)

        def _target_label(item: dict[str, Any]) -> str:
            granularity = str(item.get("granularity", "unknown"))
            label = str(item.get("label", "")).strip()
            if target == granularity and label:
                return label
            if target == "term" and granularity == "week":
                year = str(item.get("academic_year", "")).strip()
                term = int(pd.to_numeric(item.get("term", 0), errors="coerce") or 0)
                if year and term > 0:
                    return f"{year}学年-第{term}学期"
            if target == "date":
                return label
            return ""

        frame["target_label"] = frame["parsed"].apply(_target_label)
        usable = frame[frame["target_label"] != ""].copy()
        usable = usable.sort_values("snapshot_date")
        if usable.empty:
            usable = frame.copy()
            usable["target_label"] = usable["timeline_key"].astype(str)
        grouped = usable.groupby("target_label", as_index=False)["score"].mean()
        grouped["score"] = grouped["score"].round(4)
        timeline_score = {str(item["target_label"]): float(item["score"]) for _, item in grouped.iterrows()}
        labels = list(timeline_score.keys())
        series_by_granularity: dict[str, dict[str, float]] = {"week": {}, "term": {}, "date": {}}
        for granularity in ["week", "term", "date"]:
            part = frame[frame["granularity"] == granularity]
            if part.empty:
                continue
            series = part.groupby("timeline_key", as_index=False)["score"].mean()
            series_by_granularity[granularity] = {
                str(item["timeline_key"]): float(round(float(item["score"]), 4))
                for _, item in series.iterrows()
            }
        frame["derived_term_label"] = frame["parsed"].apply(
            lambda item: (
                (
                    f"系统学期编码{int(pd.to_numeric(item.get('term', 0), errors='coerce') or 0)}"
                    if str(item.get("academic_year", "")).strip().startswith("TERM")
                    else f"{str(item.get('academic_year', '')).strip()}学年-第{int(pd.to_numeric(item.get('term', 0), errors='coerce') or 0)}学期"
                )
                if str(item.get("academic_year", "")).strip() and int(pd.to_numeric(item.get("term", 0), errors="coerce") or 0) > 0
                else ""
            )
        )
        term_part = frame[frame["derived_term_label"] != ""]
        if not term_part.empty:
            term_series = term_part.groupby("derived_term_label", as_index=False)["score"].mean()
            merged_term_series = dict(series_by_granularity.get("term", {}))
            merged_term_series.update(
                {
                    str(item["derived_term_label"]): float(round(float(item["score"]), 4))
                    for _, item in term_series.iterrows()
                }
            )
            series_by_granularity["term"] = merged_term_series
        resolution = "none"
        chart_type = "line"
        split_required = False
        if mixed_conflict:
            if target == "week":
                resolution = "split_chart"
                split_required = True
            elif target == "term":
                resolution = "downsample_to_term"
            else:
                resolution = "downgrade_bar"
                chart_type = "bar"
        note = (
            "时间口径统一为学年-学期-周；同图仅允许单一粒度，出现冲突时自动拆图或降级柱图。"
            if mixed_conflict
            else "时间口径统一为学年-学期-周；当前轨迹可直接按单一粒度绘制。"
        )
        return {
            "granularity": target,
            "labels": labels,
            "timeline_score": timeline_score,
            "mixed_conflict_detected": mixed_conflict,
            "resolution_strategy": resolution,
            "time_caliber_note": note,
            "series_by_granularity": series_by_granularity,
            "render_spec": {"chart_type": chart_type, "split_required": split_required},
        }

    def _state_by_delta(self, delta: float, value: float, risk_level: str, prev_state: str) -> tuple[str, str]:
        if delta >= 0.10 and value >= 0.68:
            return "爆发期", "阶段得分显著上行并超过高位阈值"
        if delta <= -0.10 or (risk_level == "high" and value < 0.46):
            return "预警期", "阶段得分下滑明显且预警信号增强"
        if prev_state == "预警期" and delta >= 0.05:
            return "恢复期", "预警后连续回升，进入恢复轨道"
        if abs(delta) <= 0.03:
            return "平台期", "阶段波动较小，保持平台状态"
        return "进入期", "处于过渡阶段，建议继续观察"

    def _hmm_decode_states(self, labels: list[str], values: list[float], risk_level: str) -> tuple[list[str], list[str]]:
        if not labels or not values:
            return [], []
        states = ["进入期", "平台期", "预警期", "恢复期", "爆发期"]
        state_center = {"进入期": 0.52, "平台期": 0.58, "预警期": 0.36, "恢复期": 0.50, "爆发期": 0.74}
        transition = {
            "进入期": {"进入期": 0.40, "平台期": 0.23, "预警期": 0.14, "恢复期": 0.14, "爆发期": 0.09},
            "平台期": {"进入期": 0.18, "平台期": 0.44, "预警期": 0.18, "恢复期": 0.14, "爆发期": 0.06},
            "预警期": {"进入期": 0.12, "平台期": 0.08, "预警期": 0.55, "恢复期": 0.22, "爆发期": 0.03},
            "恢复期": {"进入期": 0.16, "平台期": 0.24, "预警期": 0.14, "恢复期": 0.40, "爆发期": 0.06},
            "爆发期": {"进入期": 0.12, "平台期": 0.21, "预警期": 0.05, "恢复期": 0.17, "爆发期": 0.45},
        }
        if risk_level == "high":
            transition["预警期"]["预警期"] = 0.62
            transition["平台期"]["预警期"] = 0.24
        emission_sigma = 0.12
        n = len(values)
        dp: list[dict[str, float]] = [dict() for _ in range(n)]
        prev: list[dict[str, str]] = [dict() for _ in range(n)]
        for state in states:
            diff = float(values[0] - state_center[state])
            emission = float(np.exp(-(diff * diff) / (2 * emission_sigma * emission_sigma)))
            prior = 1.0 / len(states)
            dp[0][state] = float(np.log(max(prior * emission, 1e-9)))
            prev[0][state] = ""
        for i in range(1, n):
            delta = float(values[i] - values[i - 1])
            for state in states:
                diff = float(values[i] - state_center[state])
                emission = float(np.exp(-(diff * diff) / (2 * emission_sigma * emission_sigma)))
                best_score = -1e18
                best_prev = states[0]
                for prev_state in states:
                    trans = float(transition.get(prev_state, {}).get(state, 0.05))
                    score = dp[i - 1][prev_state] + float(np.log(max(trans * emission, 1e-9)))
                    if prev_state == state and abs(delta) <= 0.03:
                        score += 0.18
                    if state == "预警期" and (delta <= -0.08 or values[i] <= 0.40):
                        score += 0.22
                    if state == "爆发期" and (delta >= 0.08 and values[i] >= 0.68):
                        score += 0.24
                    if state == "恢复期" and prev_state == "预警期" and delta >= 0.05:
                        score += 0.25
                    if score > best_score:
                        best_score = score
                        best_prev = prev_state
                dp[i][state] = best_score
                prev[i][state] = best_prev
        end_state = max(states, key=lambda s: dp[-1][s])
        decoded = [end_state]
        for i in range(n - 1, 0, -1):
            decoded.append(prev[i][decoded[-1]])
        decoded.reverse()
        reasons: list[str] = []
        for i, state in enumerate(decoded):
            if i == 0:
                reasons.append("HMM初始状态识别")
                continue
            delta = float(values[i] - values[i - 1])
            if state == "预警期":
                reasons.append("HMM识别到下行风险信号增强")
            elif state == "恢复期":
                reasons.append("HMM识别到预警后回升")
            elif state == "爆发期":
                reasons.append("HMM识别到高位跃升")
            elif abs(delta) <= 0.03:
                reasons.append("HMM识别为平台稳定波动")
            else:
                reasons.append("HMM识别为过渡阶段")
        return decoded, reasons

    def _build_trajectory_story(self, student_id: str, row: pd.Series, histories: dict[str, pd.DataFrame], time_refs: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        mapping = {
            "lifestyle_health": ("lifestyle_health_total_score", "生活节律与运动健康"),
            "social_life": ("social_life_total_score", "社交生活"),
            "course_exploration": ("course_exploration_total_score", "选课探索"),
        }
        mode_presence: dict[str, int] = {}
        for mode_key, (score_col, mode_name) in mapping.items():
            hist = histories.get(mode_key, pd.DataFrame())
            if hist.empty:
                mode_presence[mode_key] = 0
                continue
            part = hist[hist["XH"] == str(student_id)]
            if part.empty or score_col not in part.columns:
                mode_presence[mode_key] = 0
                continue
            mode_presence[mode_key] = int(len(part))
            if "time_window" not in part.columns:
                part["time_window"] = ""
            if "academic_window" not in part.columns:
                part["academic_window"] = ""
            part = part[["snapshot_date", "time_window", "academic_window", score_col]].copy()
            part[score_col] = pd.to_numeric(part[score_col], errors="coerce")
            part = part.dropna(subset=[score_col]).sort_values("snapshot_date")
            for _, item in part.iterrows():
                records.append(
                    {
                        "timeline_key": self._resolve_timeline_key(
                            student_id=student_id,
                            time_window=str(item.get("time_window", "")),
                            academic_window=str(item.get("academic_window", "")),
                            snapshot_date=item.get("snapshot_date"),
                            time_refs=time_refs,
                        ),
                        "snapshot_date": str(pd.to_datetime(item["snapshot_date"]).date()),
                        "mode": mode_name,
                        "score": float(np.clip(item[score_col], 0.0, 1.0)),
                    }
                )
        ods_timeline = self._load_ods_behavior_timeline()
        if not ods_timeline.empty:
            student_ods = ods_timeline[ods_timeline["XH"] == str(student_id)].copy()
            student_ods = student_ods.sort_values("snapshot_date")
            mode_presence["multi_source_proxy"] = int(len(student_ods))
            for _, item in student_ods.iterrows():
                records.append(
                    {
                        "timeline_key": str(item.get("academic_window", "")),
                        "snapshot_date": str(pd.to_datetime(item.get("snapshot_date")).date()),
                        "mode": "多源行为代理",
                        "score": float(np.clip(float(pd.to_numeric(item.get("behavior_proxy_score", 0.0), errors="coerce") or 0.0), 0.0, 1.0)),
                    }
                )
        else:
            mode_presence["multi_source_proxy"] = 0
        records.sort(key=lambda x: x["snapshot_date"])
        axis = self._standardize_time_axis(records)
        term_series = axis.get("series_by_granularity", {}).get("term", {}) if isinstance(axis, dict) else {}
        report_granularity = "term" if isinstance(term_series, dict) and len(term_series) > 0 else str(axis.get("granularity", "week"))
        report_timeline_score = term_series if report_granularity == "term" else axis.get("timeline_score", {})
        if not isinstance(report_timeline_score, dict):
            report_timeline_score = {}
        axis["report_granularity"] = report_granularity
        axis["report_timeline_score"] = report_timeline_score
        timeline_score = report_timeline_score
        values = [float(v) for v in timeline_score.values()]
        labels = list(timeline_score.keys())
        risk_level = str(row.get("risk_level", "low")).lower()
        state_sequence: list[dict[str, Any]] = []
        turning_points: list[dict[str, Any]] = []
        trajectory_segments: list[dict[str, Any]] = []
        if labels:
            hmm_states, hmm_reasons = self._hmm_decode_states(labels=labels, values=values, risk_level=risk_level)
            for i in range(len(labels)):
                value = values[i]
                state = hmm_states[i] if i < len(hmm_states) else "进入期"
                reason = hmm_reasons[i] if i < len(hmm_reasons) else "状态识别"
                state_sequence.append(
                    {
                        "time_label": labels[i],
                        "score": round(value, 4),
                        "state": state,
                        "transition_reason": reason,
                    }
                )
                if i == 0:
                    continue
                prev_value = values[i - 1]
                delta = float(value - prev_value)
                trajectory_segments.append(
                    {
                        "start_date": labels[i - 1],
                        "end_date": labels[i],
                        "delta": round(delta, 4),
                        "phase": state,
                    }
                )
                if abs(delta) >= 0.06 or state != state_sequence[-2]["state"]:
                    turning_points.append(
                        {
                            "time_label": labels[i],
                            "delta": round(delta, 4),
                            "from_state": state_sequence[-2]["state"],
                            "to_state": state,
                            "evidence_hint": reason,
                        }
                    )
        trend = _to_dict(row.get("trend_4w"))
        night_delta = float(pd.to_numeric(trend.get("night_activity_delta_4w", 0.0), errors="coerce") or 0.0)
        running_delta = float(pd.to_numeric(trend.get("running_frequency_delta_4w", 0.0), errors="coerce") or 0.0)
        activity_delta = float(pd.to_numeric(trend.get("formal_activity_delta_4w", 0.0), errors="coerce") or 0.0)
        event_chain: list[dict[str, Any]] = []
        if night_delta > 0.03:
            event_chain.append(
                {
                    "trigger": "夜间活跃连续上升",
                    "evidence": [f"近4周夜间活跃变化{night_delta:+.3f}"] + _to_list(row.get("lifestyle_health_factors"))[:1],
                    "impact": "学习行为代理稳定性下降，预警状态触发概率上升",
                    "suggestion": "将夜间高强度线上活动前置到22:30前，连续执行7天",
                    "observation_window": "7天 + 4周",
                }
            )
        if running_delta < -0.03:
            event_chain.append(
                {
                    "trigger": "运动频率下降",
                    "evidence": [f"近4周运动频率变化{running_delta:+.3f}"],
                    "impact": "节律恢复能力减弱，恢复期持续性不足",
                    "suggestion": "每周固定2次30分钟运动并在周末复盘执行率",
                    "observation_window": "14天",
                }
            )
        if activity_delta < -0.03:
            event_chain.append(
                {
                    "trigger": "正式活动参与下降",
                    "evidence": [f"近4周正式活动变化{activity_delta:+.3f}"],
                    "impact": "同伴支持场景减少，课程任务推进效率降低",
                    "suggestion": "每周至少安排1次线下协作学习或班级活动",
                    "observation_window": "7天",
                }
            )
        if not event_chain:
            event_chain.append(
                {
                    "trigger": "序列波动处于可控区间",
                    "evidence": ["近4周关键行为代理波动未越阈值"],
                    "impact": "状态以进入期/平台期为主",
                    "suggestion": "保持当前节律，按周持续监测",
                    "observation_window": "7天",
                }
            )
        if state_sequence:
            states = [str(item.get("state", "进入期")) for item in state_sequence]
            unique_states = sorted(set(states))
            probabilities = [states.count(state) / len(states) for state in unique_states if states]
            entropy = 0.0
            for probability in probabilities:
                if probability > 0:
                    entropy += float(-probability * np.log2(probability))
            normalized_entropy = 0.0
            if len(unique_states) > 1:
                normalized_entropy = float(round(entropy / np.log2(len(unique_states)), 4))
        else:
            normalized_entropy = 0.0
        point_count = len(values)
        mode_coverage = float(round(sum(1 for _, count in mode_presence.items() if count > 0) / max(1, len(mode_presence)), 4))
        confidence_score = float(round(min(1.0, 0.35 + 0.1 * point_count + 0.25 * mode_coverage - (0.15 if axis.get("mixed_conflict_detected") else 0.0)), 4))
        confidence_level = "高" if confidence_score >= 0.75 else ("中" if confidence_score >= 0.5 else "低")
        state_sequence_for_entropy = [item.get("state", "") for item in state_sequence]
        trajectory_pattern = "持续稳健型"
        if state_sequence_for_entropy:
            if "爆发期" in state_sequence_for_entropy and "预警期" in state_sequence_for_entropy:
                trajectory_pattern = "波动跃迁型"
            elif "预警期" in state_sequence_for_entropy and state_sequence_for_entropy[-1] == "恢复期":
                trajectory_pattern = "回升修复型"
            elif state_sequence_for_entropy[-1] == "预警期":
                trajectory_pattern = "高开低走型"
        return {
            "time_axis_standard": axis,
            "state_sequence": state_sequence,
            "turning_points": turning_points[:6],
            "event_chain": event_chain[:4],
            "confidence": {
                "score": confidence_score,
                "level": confidence_level,
                "sample_points": point_count,
                "mode_coverage": mode_coverage,
                "trajectory_entropy": normalized_entropy,
                "sample_sufficiency": "充分" if point_count >= 4 else ("一般" if point_count >= 2 else "不足"),
                "trajectory_pattern": trajectory_pattern,
            },
            "time_caliber_note": (
                "报告叙事默认按学期展示，周级序列保留用于关键拐点与证据链解释。"
                if report_granularity == "term"
                else axis.get("time_caliber_note", "")
            ),
            "state_transition_rules": [
                {"to_state": "爆发期", "condition": "Δscore>=+0.10 且 score>=0.68"},
                {"to_state": "预警期", "condition": "Δscore<=-0.10 或高风险且score<0.46"},
                {"to_state": "恢复期", "condition": "上一状态为预警期且 Δscore>=+0.05"},
                {"to_state": "平台期", "condition": "|Δscore|<=0.03"},
                {"to_state": "进入期", "condition": "其余过渡场景"},
            ],
            "state_model": {
                "method": "hmm_like_viterbi",
                "description": "使用状态转移概率+观测发射概率进行时序状态识别，输出阶段迁移路径。",
            },
        }

    def _compose_core_factors(self, row: pd.Series) -> str:
        factors: list[str] = []
        factors.extend(_to_list(row.get("top_factors")))
        for key in [
            "learning_behavior_factors",
            "learning_outcome_factors",
            "lifestyle_health_factors",
            "social_life_factors",
            "course_exploration_factors",
        ]:
            factors.extend(_to_list(row.get(key)))
        uniq: list[str] = []
        for factor in factors:
            factor_text = str(factor).strip()
            if factor_text and factor_text not in uniq:
                uniq.append(factor_text)
            if len(uniq) >= 5:
                break
        return json.dumps(uniq[:5], ensure_ascii=False)

    def _compose_mode_tags(self, row: pd.Series) -> str:
        main_tags = [
            _safe_label(row.get("learning_behavior_label")),
            _safe_label(row.get("learning_outcome_label")),
            _safe_label(row.get("lifestyle_health_label")),
            _safe_label(row.get("social_life_label")),
            _safe_label(row.get("course_exploration_label")),
        ]
        short_phrases = _to_list(row.get("core_explain_factors"))[:5]
        light_level = _warning_light(str(row.get("risk_level", "low")))
        payload = {
            "main_tags": main_tags,
            "feature_phrases": short_phrases,
            "risk_warning_light": light_level,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _legacy_trajectory_payload(self, story: dict[str, Any]) -> dict[str, Any]:
        state_sequence = story.get("state_sequence", []) if isinstance(story, dict) else []
        event_chain = story.get("event_chain", []) if isinstance(story, dict) else []
        current_phase = "进入期"
        if state_sequence:
            current_phase = str(state_sequence[-1].get("state", "进入期"))
        key_nodes = [str(item.get("trigger", "")) for item in event_chain if str(item.get("trigger", "")).strip()]
        if not key_nodes and current_phase:
            key_nodes = [f"当前阶段为{current_phase}，建议保持周级观察。"]
        return {
            "phase": current_phase,
            "timeline_score": (
                story.get("time_axis_standard", {}).get("report_timeline_score", {})
                if isinstance(story.get("time_axis_standard", {}), dict)
                else {}
            ),
            "trajectory_segments": [
                {
                    "start_date": str(item.get("start_date", "")),
                    "end_date": str(item.get("end_date", "")),
                    "delta": float(pd.to_numeric(item.get("delta", 0.0), errors="coerce") or 0.0),
                    "phase": str(item.get("phase", "进入期")),
                }
                for item in (
                    [
                        {
                            "start_date": state_sequence[i - 1].get("time_label", ""),
                            "end_date": state_sequence[i].get("time_label", ""),
                            "delta": float(pd.to_numeric(state_sequence[i].get("score", 0.0), errors="coerce") or 0.0)
                            - float(pd.to_numeric(state_sequence[i - 1].get("score", 0.0), errors="coerce") or 0.0),
                            "phase": state_sequence[i].get("state", "进入期"),
                        }
                        for i in range(1, len(state_sequence))
                    ]
                )
            ],
            "key_nodes": key_nodes[:4],
            "time_caliber_note": story.get("time_caliber_note", ""),
        }

    def _trajectory_for_student(self, student_id: str, row: pd.Series, histories: dict[str, pd.DataFrame], time_refs: dict[str, dict[str, list[str]]]) -> str:
        story = self._build_trajectory_story(student_id=student_id, row=row, histories=histories, time_refs=time_refs)
        return json.dumps(self._legacy_trajectory_payload(story), ensure_ascii=False)

    def _key_behavior_analysis(self, row: pd.Series) -> str:
        risk_events: list[str] = []
        positive_events: list[str] = []
        trend = _to_dict(row.get("trend_4w"))
        night_delta = float(pd.to_numeric(trend.get("night_activity_delta_4w", 0.0), errors="coerce") or 0.0)
        running_delta = float(pd.to_numeric(trend.get("running_frequency_delta_4w", 0.0), errors="coerce") or 0.0)
        activity_delta = float(pd.to_numeric(trend.get("formal_activity_delta_4w", 0.0), errors="coerce") or 0.0)
        if night_delta > 0.03:
            risk_events.append("深夜活跃上升")
        if running_delta < -0.03:
            risk_events.append("运动频率下降")
        if activity_delta < -0.03:
            risk_events.append("线下参与下降")
        if running_delta > 0.03:
            positive_events.append("运动习惯改善")
        if night_delta < -0.03:
            positive_events.append("作息节律改善")
        if activity_delta > 0.03:
            positive_events.append("协作参与提升")
        behavior_factors = _to_list(row.get("learning_behavior_factors"))
        outcome_factors = _to_list(row.get("learning_outcome_factors"))
        key_phrases = []
        for phrase in behavior_factors + outcome_factors:
            text = str(phrase).strip()
            if text and text not in key_phrases:
                key_phrases.append(text)
            if len(key_phrases) >= 5:
                break
        if not risk_events:
            risk_events.append("当前未发现显著新增风险行为事件")
        if not positive_events:
            positive_events.append("当前未发现显著正向行为跳变")
        payload = {
            "risk_events": risk_events,
            "positive_events": positive_events,
            "key_phrases": key_phrases,
            "primary_mode_label": _safe_label(row.get("learning_behavior_label")),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _compose_attribution(self, row: pd.Series) -> str:
        behavior_factor = {
            "score": float(round(float(row.get("learning_behavior_score", 0.0)), 4)),
            "evidence": _to_list(row.get("learning_behavior_factors"))[:3],
            "extra": f"低投入风险分={float(pd.to_numeric(row.get('low_engagement_score', 0.0), errors='coerce') or 0.0):.3f}",
        }
        result_factor = {
            "score": float(round(float(row.get("learning_outcome_score", 0.0)), 4)),
            "evidence": _to_list(row.get("learning_outcome_factors"))[:3],
            "extra": f"学业下滑分={float(pd.to_numeric(row.get('academic_decline_score', 0.0), errors='coerce') or 0.0):.3f},挂科风险分={float(pd.to_numeric(row.get('fail_risk_score', 0.0), errors='coerce') or 0.0):.3f}",
        }
        environment_factor = {
            "score": float(
                round(
                    (
                        float(pd.to_numeric(row.get("lifestyle_health_score", 0.0), errors="coerce") or 0.0)
                        + float(pd.to_numeric(row.get("social_life_score", 0.0), errors="coerce") or 0.0)
                    )
                    / 2.0,
                    4,
                )
            ),
            "evidence": (_to_list(row.get("lifestyle_health_factors")) + _to_list(row.get("social_life_factors")))[:3],
            "extra": f"夜间活跃指数={float(pd.to_numeric(row.get('night_activity_index', 0.0), errors='coerce') or 0.0):.3f},社交孤立指数={float(pd.to_numeric(row.get('social_isolation_index', 0.0), errors='coerce') or 0.0):.3f}",
        }
        return json.dumps({"behavior": behavior_factor, "result": result_factor, "environment": environment_factor}, ensure_ascii=False)

    def _compose_radar(self, row: pd.Series) -> str:
        keys = [
            ("学习行为", "learning_behavior_score", "learning_behavior_peer_avg"),
            ("学习成果", "learning_outcome_score", "learning_outcome_peer_avg"),
            ("生活节律与运动健康", "lifestyle_health_score", "lifestyle_health_peer_avg"),
            ("社交生活", "social_life_score", "social_life_peer_avg"),
            ("选课探索", "course_exploration_score", "course_exploration_peer_avg"),
        ]
        student = {}
        peer = {}
        for label, score_col, peer_col in keys:
            student[label] = float(round(float(row.get(score_col, 0.0)) * 100, 2))
            peer[label] = float(round(float(row.get(peer_col, 0.0)) * 100, 2))
        return json.dumps({"student_score": student, "peer_avg_score": peer}, ensure_ascii=False)

    def _compose_advice(self, row: pd.Series) -> tuple[str, str]:
        """Generate advice direction and plan.

        Policy: learning behavior is the primary intervention axis. Lifestyle,
        social, and self-discipline factors are important supplementary
        recommendations — all presented together but with learning first.
        """
        risk_level = str(row.get("risk_level", "low")).lower()
        labels = [
            str(row.get("learning_behavior_label", "")),
            str(row.get("learning_outcome_label", "")),
            str(row.get("lifestyle_health_label", "")),
            str(row.get("social_life_label", "")),
            str(row.get("course_exploration_label", "")),
        ]
        if risk_level == "high":
            direction = "以学习投入与课程完成为核心抓手，同步调整生活节律与社交支持，多维协同降低学业风险"
            plan = [
                "第1周：补齐所有延迟任务，确保本周到课率达100%，每日至少完成1项课程资源学习",
                "第2-3周：聚焦两门核心课程，每周完成3次图书馆深度学习并增加课堂互动频次",
                "第4周：与导师复盘学业及多维行为指标变化，制定下阶段综合修复计划",
            ]
        elif risk_level == "medium":
            direction = "巩固学习行为优势维度，针对学业波动因子做定向补强，配合节律与社交维度持续跟踪"
            plan = [
                "第1周：复核本月学习任务完成率与课程进度，补齐延迟提交并提升作业质量",
                "第2-3周：每周安排3次图书馆学习时段，增加课堂讨论参与，同步保持运动与社交节奏",
                "第4周：根据同群体学业分位变化调整学习策略与选课规划",
            ]
        else:
            direction = "巩固当前成长态势，以学习探索为主线提升综合产出"
            plan = [
                "第1-2周：保持稳定学习节奏与到课习惯，拓展1个高阶学习目标或竞赛方向",
                "第3周：参与1次学术项目或学科竞赛活动，提升成果转化",
                "第4周：复盘五模式得分，形成下周期个人成长计划",
            ]
        # Primary: learning behavior specific inserts
        if any("低参与失衡型" in x for x in labels):
            plan.insert(1, "每周安排2次课堂互动或讨论区高质量发言，提升学习参与深度")
        # Supplementary: lifestyle/social (important but secondary priority)
        if any("节律紊乱预警型" in x for x in labels):
            plan.append("调整作息节律，减少夜间活跃时段，保持连续两周晨间规律活动以支撑学习状态")
        if any("低融入孤立型" in x for x in labels):
            plan.append("每周至少参与1次线下社团或班级活动，扩展稳定同伴联结以促进协作学习")
        return direction, "；".join(plan[:6])

    def run(self) -> pd.DataFrame:
        base = self._prepare_risk_features()
        risk = self._prepare_risk_result()
        learn_behavior = self._prepare_learning_behavior()
        learn_outcome = self._prepare_learning_outcome()
        lifestyle = self._prepare_lifestyle()
        social = self._prepare_social()
        course = self._prepare_course()
        histories = self._load_histories()
        time_refs = self._load_student_time_refs()
        ods_grade_class = self._load_ods_grade_class_map()
        frames = [base, risk, learn_behavior, learn_outcome, lifestyle, social, course]
        student_ids: set[str] = set()
        for frame in frames:
            if "XH" in frame.columns:
                student_ids.update(frame["XH"].astype(str).tolist())
        if not student_ids:
            return pd.DataFrame()
        result = pd.DataFrame({"XH": sorted(student_ids)})
        for frame in frames:
            if frame.empty:
                continue
            result = result.merge(frame, on="XH", how="left")
        if not ods_grade_class.empty:
            result = result.merge(ods_grade_class, on="XH", how="left")
        else:
            result["ods_grade"] = ""
            result["ods_class_name"] = ""
            result["ods_mapped"] = 0
        result["major"] = result.get("major", "未提供专业").fillna("未提供专业").astype(str).str.strip()
        result["major"] = result["major"].replace({"": "未提供专业", "nan": "未提供专业", "None": "未提供专业"})
        result["grade"] = result.get("grade", "未知年级").fillna("未知年级").astype(str).str.strip()
        result["grade"] = result["grade"].replace({"": "未知年级", "nan": "未知年级", "None": "未知年级"})
        result["academy"] = result.get("academy", "未提供学院信息").fillna("未提供学院信息").astype(str).str.strip()
        result["academy"] = result["academy"].replace({"": "未提供学院信息", "nan": "未提供学院信息", "None": "未提供学院信息"})
        known_academy = result[
            (result["academy"] != "未提供学院信息")
            & (result["major"] != "未提供专业")
        ][["major", "academy"]]
        if not known_academy.empty:
            major_to_academy = (
                known_academy.groupby("major")["academy"]
                .agg(lambda s: s.value_counts().index[0])
                .to_dict()
            )
            need_fill = (result["academy"] == "未提供学院信息") & (result["major"] != "未提供专业")
            result.loc[need_fill, "academy"] = result.loc[need_fill, "major"].map(major_to_academy).fillna("未提供学院信息")
        result["class_name"] = result.get("class_name", result["grade"].astype(str) + "-" + result["major"].astype(str) + "-默认班").fillna(
            result["grade"].astype(str) + "-" + result["major"].astype(str) + "-默认班"
        )
        result["ods_grade"] = result.get("ods_grade", "").fillna("").astype(str).str.strip()
        result["ods_class_name"] = result.get("ods_class_name", "").fillna("").astype(str).str.strip()
        result["ods_mapped"] = pd.to_numeric(result.get("ods_mapped", 0), errors="coerce").fillna(0).astype(int)
        has_ods_grade = result["ods_grade"] != ""
        has_ods_class = result["ods_class_name"] != ""
        result.loc[has_ods_grade, "grade"] = result.loc[has_ods_grade, "ods_grade"]
        result.loc[has_ods_class, "class_name"] = result.loc[has_ods_class, "ods_class_name"]
        result["is_special_student"] = result["ods_mapped"] == 0
        result["special_reason"] = np.where(
            result["is_special_student"],
            "体育课/体测缺失（第二学位等特殊学生）",
            "",
        )
        result.loc[result["is_special_student"], "grade"] = "特殊学生"
        result.loc[result["is_special_student"], "class_name"] = "特殊学生"
        result["peer_group"] = result["major"].astype(str) + "|" + result["grade"].astype(str)
        result["risk_level"] = result.get("risk_level", "low").fillna("low")
        result["risk_score"] = pd.to_numeric(result.get("risk_score", 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)
        mode_score_cols = [
            "learning_behavior_score",
            "learning_outcome_score",
            "lifestyle_health_score",
            "social_life_score",
            "course_exploration_score",
        ]
        for col in mode_score_cols:
            result[col] = pd.to_numeric(result.get(col, 0.0), errors="coerce").fillna(0.0).clip(0.0, 1.0)
        group_peer = result.groupby(["grade", "major"], dropna=False)[mode_score_cols].transform("mean")
        for col in mode_score_cols:
            peer_col = col.replace("_score", "_peer_avg")
            result[peer_col] = pd.to_numeric(group_peer[col], errors="coerce").fillna(0.0).clip(0.0, 1.0)
        result["overall_growth_score"] = result[mode_score_cols].mean(axis=1).fillna(0.0)
        result["overall_growth_level"] = result["overall_growth_score"].apply(_score_level)
        result["trend_4w"] = result.get("trend_4w", "{}").fillna("{}")
        result["peer_compare"] = result.get("peer_compare", "{}").fillna("{}")
        result["top_factors"] = result.get("top_factors", "[]").fillna("[]")
        result["core_explain_factors"] = result.apply(self._compose_core_factors, axis=1)
        result["mode_tags"] = result.apply(self._compose_mode_tags, axis=1)
        result["trajectory_story"] = result.apply(
            lambda row: json.dumps(
                self._build_trajectory_story(
                    student_id=str(row["XH"]),
                    row=row,
                    histories=histories,
                    time_refs=time_refs,
                ),
                ensure_ascii=False,
            ),
            axis=1,
        )
        result["trajectory_evolution"] = result["trajectory_story"].apply(
            lambda story_text: json.dumps(self._legacy_trajectory_payload(_to_dict(story_text)), ensure_ascii=False)
        )
        result["key_behavior_analysis"] = result.apply(self._key_behavior_analysis, axis=1)
        result["attribution_3d"] = result.apply(self._compose_attribution, axis=1)
        result["radar_chart_data"] = result.apply(self._compose_radar, axis=1)
        advice_tuple = result.apply(self._compose_advice, axis=1)
        result["advice_direction"] = advice_tuple.apply(lambda x: x[0])
        result["advice_plan"] = advice_tuple.apply(lambda x: x[1])
        result["risk_warning_light"] = result["risk_level"].astype(str).map(_warning_light)
        result["behavior_proxy_statement"] = "本画像基于校园行为与学业数据代理特征生成，不构成医学或心理诊断。"
        result["created_at"] = pd.Timestamp.now()
        ordered_cols = [
            "XH",
            "major",
            "grade",
            "academy",
            "class_name",
            "peer_group",
            "is_special_student",
            "special_reason",
            "risk_level",
            "risk_score",
            "risk_warning_light",
            "overall_growth_score",
            "overall_growth_level",
            "learning_behavior_label",
            "learning_behavior_score",
            "learning_behavior_peer_avg",
            "learning_outcome_label",
            "learning_outcome_score",
            "learning_outcome_peer_avg",
            "lifestyle_health_label",
            "lifestyle_health_score",
            "lifestyle_health_peer_avg",
            "social_life_label",
            "social_life_score",
            "social_life_peer_avg",
            "course_exploration_label",
            "course_exploration_score",
            "course_exploration_peer_avg",
            "radar_chart_data",
            "mode_tags",
            "top_factors",
            "core_explain_factors",
            "trajectory_story",
            "trajectory_evolution",
            "key_behavior_analysis",
            "attribution_3d",
            "trend_4w",
            "peer_compare",
            "advice_direction",
            "advice_plan",
            "behavior_proxy_statement",
            "created_at",
        ]
        existing_cols = [c for c in ordered_cols if c in result.columns]
        return result[existing_cols].sort_values(["is_special_student", "XH"], ascending=[False, True]).reset_index(drop=True)

    def save(self, output_path: Path | None = None) -> tuple[Path, dict[str, Any]]:
        target = output_path or self._output_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        portrait = self.run()
        if portrait.empty:
            empty_target = target if target.suffix.lower() == ".json" else target.with_suffix(".json")
            empty_target.write_text("[]", encoding="utf-8")
            return empty_target, {"row_count": 0, "risk_distribution": {}, "avg_growth_score": 0.0}
        portrait = portrait.sort_values(["is_special_student", "XH"], ascending=[False, True]).reset_index(drop=True)
        json_path = target if target.suffix.lower() == ".json" else target.with_suffix(".json")
        portrait.to_json(json_path, orient="records", force_ascii=False)
        risk_distribution = portrait["risk_level"].value_counts(normalize=True).round(4).to_dict()
        summary = {
            "row_count": int(len(portrait)),
            "risk_distribution": risk_distribution,
            "avg_growth_score": float(round(portrait["overall_growth_score"].mean(), 4)),
            "special_student_count": int(portrait["is_special_student"].sum()) if "is_special_student" in portrait.columns else 0,
            "output_files": [str(json_path)],
        }
        return json_path, summary
