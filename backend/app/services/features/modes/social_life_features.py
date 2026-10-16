from __future__ import annotations

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


def _ensure_student_id(frame: pd.DataFrame, candidates: list[str]) -> pd.DataFrame:
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


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


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


def _entropy_from_counts(row: pd.Series) -> float:
    vals = _to_numeric(row).fillna(0.0).values.astype(float)
    total = vals.sum()
    if total <= 0:
        return 0.0
    probs = vals[vals > 0] / total
    if len(probs) <= 1:
        return 0.0
    return float(-(probs * np.log(probs)).sum() / np.log(len(vals)))


def _normalized_entropy_from_weight_frame(frame: pd.DataFrame, id_col: str, key_col: str, weight_col: str) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    work = frame[[id_col, key_col, weight_col]].copy()
    work = work.dropna(subset=[id_col, key_col])
    if work.empty:
        return pd.Series(dtype=float)
    work[weight_col] = _to_numeric(work[weight_col]).fillna(0.0)
    work = work[work[weight_col] > 0]
    if work.empty:
        return pd.Series(dtype=float)
    agg = work.groupby([id_col, key_col], as_index=False)[weight_col].sum()
    agg["total"] = agg.groupby(id_col)[weight_col].transform("sum")
    agg = agg[agg["total"] > 0]
    if agg.empty:
        return pd.Series(dtype=float)
    agg["p"] = agg[weight_col] / agg["total"]
    entropy = (-(agg["p"] * np.log(agg["p"]))).groupby(agg[id_col]).sum()
    unique_cnt = agg.groupby(id_col)[key_col].nunique()
    denom = np.log(unique_cnt.clip(lower=2))
    normalized = entropy / denom
    return normalized.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _hour_entropy_from_events(frame: pd.DataFrame, id_col: str = "XH", time_col: str = "event_time") -> pd.Series:
    if frame.empty or id_col not in frame.columns or time_col not in frame.columns:
        return pd.Series(dtype=float)
    work = frame[[id_col, time_col]].copy()
    work[time_col] = pd.to_datetime(work[time_col], errors="coerce")
    work = work.dropna(subset=[time_col])
    if work.empty:
        return pd.Series(dtype=float)
    work["hour"] = work[time_col].dt.hour
    hour_counts = work.groupby([id_col, "hour"]).size().rename("cnt").reset_index()
    hour_counts["total"] = hour_counts.groupby(id_col)["cnt"].transform("sum")
    hour_counts = hour_counts[hour_counts["total"] > 0]
    if hour_counts.empty:
        return pd.Series(dtype=float)
    hour_counts["p"] = hour_counts["cnt"] / hour_counts["total"]
    entropy = (-(hour_counts["p"] * np.log(hour_counts["p"]))).groupby(hour_counts[id_col]).sum()
    return (entropy / np.log(24)).replace([np.inf, -np.inf], np.nan).fillna(0.0)


@dataclass
class SocialLifeFeatureBuilder:
    project_root: Path

    def _ods_path(self, *parts: str) -> Path:
        return self.project_root.joinpath("data", "ods", *parts)

    def load_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "club_activity": _safe_read_excel(self._ods_path("social_activity", "社团活动.xlsx")),
            "checkin": _safe_read_excel(self._ods_path("learning_logs", "学生签到记录.xlsx")),
            "discussion": _safe_read_excel(self._ods_path("learning_logs", "讨论记录.xlsx")),
            "class_participation": _safe_read_excel(self._ods_path("learning_logs", "课堂任务参与.xlsx")),
            "library": _safe_read_excel(self._ods_path("learning_logs", "图书馆打卡记录.xlsx")),
            "access": _safe_read_excel(self._ods_path("social_activity", "门禁数据.xlsx")),
        }

    def build(self) -> pd.DataFrame:
        tables = self.load_tables()
        tables["club_activity"] = _ensure_student_id(tables["club_activity"], ["XH", "IDSERTAL", "USER_ID"])
        tables["checkin"] = _ensure_student_id(tables["checkin"], ["XH", "IDSERTAL", "USER_ID"])
        tables["discussion"] = _ensure_student_id(tables["discussion"], ["XH", "CREATER_LOGIN_NAME", "USER_ID", "IDSERTAL"])
        tables["class_participation"] = _ensure_student_id(tables["class_participation"], ["XH", "USER_ID", "IDSERTAL"])
        tables["library"] = _ensure_student_id(tables["library"], ["XH", "IDSERTAL", "USER_ID"])
        tables["access"] = _ensure_student_id(tables["access"], ["XH", "IDSERTAL", "USER_ID"])

        students = set()
        for table in tables.values():
            if "XH" in table.columns:
                students.update(table["XH"].dropna().astype(str).str.strip())
        students = {student for student in students if student}
        if not students:
            return pd.DataFrame()

        df = pd.DataFrame({"XH": sorted(students)})

        club = tables["club_activity"].copy()
        if not club.empty and "XH" in club.columns:
            club["XH"] = club["XH"].astype(str)
            club["HDRQ_DT"] = _to_datetime(club["HDRQ"]) if "HDRQ" in club.columns else pd.NaT
            formal_cnt = club.groupby("XH").size()
            club["_week"] = club["HDRQ_DT"].dt.isocalendar().week.astype("Int64")
            club_active_weeks = club.groupby("XH")["_week"].nunique()
        else:
            formal_cnt = pd.Series(dtype=float)
            club_active_weeks = pd.Series(dtype=float)

        checkin = tables["checkin"].copy()
        if not checkin.empty and "XH" in checkin.columns:
            checkin["XH"] = checkin["XH"].astype(str)
            checkin["ATTEND_TIME_DT"] = _to_datetime(checkin["ATTEND_TIME"]) if "ATTEND_TIME" in checkin.columns else pd.NaT
            checkin["ACTIVE_STATE_STR"] = checkin["ACTIVE_STATE"].astype(str).str.strip() if "ACTIVE_STATE" in checkin.columns else ""
            valid_checkin = checkin["ACTIVE_STATE_STR"].isin({"1", "3", "11"})
            signin_rate = valid_checkin.groupby(checkin["XH"]).mean()
            checkin_cnt = checkin.groupby("XH").size()
            checkin["_week"] = checkin["ATTEND_TIME_DT"].dt.isocalendar().week.astype("Int64")
            weekly_checkin_std = checkin.groupby(["XH", "_week"]).size().groupby("XH").std().fillna(0.0)
        else:
            signin_rate = pd.Series(dtype=float)
            checkin_cnt = pd.Series(dtype=float)
            weekly_checkin_std = pd.Series(dtype=float)

        discussion = tables["discussion"].copy()
        if not discussion.empty and "XH" in discussion.columns:
            discussion["XH"] = discussion["XH"].astype(str)
            discussion["CREATE_TIME_DT"] = _to_datetime(discussion["CREATE_TIME"]) if "CREATE_TIME" in discussion.columns else pd.NaT
            discussion_cnt = discussion.groupby("XH").size()
            discussion_reply = (
                discussion["REPLY_CONTENT"].astype(str).str.strip().ne("").groupby(discussion["XH"]).sum()
                if "REPLY_CONTENT" in discussion.columns
                else pd.Series(dtype=float)
            )
            post_cnt = discussion.groupby("XH")["TOPIC_ID"].nunique() if "TOPIC_ID" in discussion.columns else pd.Series(dtype=float)
            discussion_course = (
                discussion[["XH", "COURSE_ID"]]
                .rename(columns={"COURSE_ID": "course_key"})
                .assign(weight=1.0)
                if "COURSE_ID" in discussion.columns
                else pd.DataFrame(columns=["XH", "course_key", "weight"])
            )
        else:
            discussion_cnt = pd.Series(dtype=float)
            discussion_reply = pd.Series(dtype=float)
            post_cnt = pd.Series(dtype=float)
            discussion_course = pd.DataFrame(columns=["XH", "course_key", "weight"])

        task = tables["class_participation"].copy()
        if not task.empty and "XH" in task.columns:
            task["XH"] = task["XH"].astype(str)
            task["CREATE_TIME_DT"] = _to_datetime(task["CREATE_TIME"]) if "CREATE_TIME" in task.columns else pd.NaT
            interaction_fields = [field for field in ["BBS_NUM", "TOPIC_NUM", "REPLY_NUM", "PICK_NUM", "ANSWER_NUM"] if field in task.columns]
            for field in interaction_fields:
                task[field] = _to_numeric(task[field]).fillna(0.0)
            if interaction_fields:
                task["interaction_sum"] = task[interaction_fields].sum(axis=1)
                task_interaction = task.groupby("XH")["interaction_sum"].sum()
            else:
                task_interaction = pd.Series(dtype=float)
            task_signin = task.groupby("XH")["SIGN_RATE"].mean() if "SIGN_RATE" in task.columns else pd.Series(dtype=float)
            task_topic = task.groupby("XH")["TOPIC_NUM"].sum() if "TOPIC_NUM" in task.columns else pd.Series(dtype=float)
            task_reply = task.groupby("XH")["REPLY_NUM"].sum() if "REPLY_NUM" in task.columns else pd.Series(dtype=float)
            task_pick = task.groupby("XH")["PICK_NUM"].sum() if "PICK_NUM" in task.columns else pd.Series(dtype=float)
            task_answer = task.groupby("XH")["ANSWER_NUM"].sum() if "ANSWER_NUM" in task.columns else pd.Series(dtype=float)
            task_rate = task.groupby("XH")["TASK_RATE"].mean() if "TASK_RATE" in task.columns else pd.Series(dtype=float)
            task_course = (
                task.assign(_course=task["COURSE_ID"].astype(str) if "COURSE_ID" in task.columns else np.nan)
                .assign(_weight=(task["interaction_sum"] + 1.0) if "interaction_sum" in task.columns else 1.0)
                [["XH", "_course", "_weight"]]
                .rename(columns={"_course": "course_key", "_weight": "weight"})
                if "COURSE_ID" in task.columns
                else pd.DataFrame(columns=["XH", "course_key", "weight"])
            )
        else:
            task_interaction = pd.Series(dtype=float)
            task_signin = pd.Series(dtype=float)
            task_topic = pd.Series(dtype=float)
            task_reply = pd.Series(dtype=float)
            task_pick = pd.Series(dtype=float)
            task_answer = pd.Series(dtype=float)
            task_rate = pd.Series(dtype=float)
            task_course = pd.DataFrame(columns=["XH", "course_key", "weight"])

        library = tables["library"].copy()
        if not library.empty and "XH" in library.columns:
            library["XH"] = library["XH"].astype(str)
            library["visittime_dt"] = _to_datetime(library["visittime"]) if "visittime" in library.columns else pd.NaT
            library["event_date"] = library["visittime_dt"].dt.date
            library["location"] = library["gateno"].astype(str) if "gateno" in library.columns else "LIB_UNKNOWN"
            library_cnt = library.groupby("XH").size()
            library_unique_loc = library.groupby("XH")["location"].nunique()
        else:
            library_cnt = pd.Series(dtype=float)
            library_unique_loc = pd.Series(dtype=float)

        access = tables["access"].copy()
        if not access.empty and "XH" in access.columns:
            access["XH"] = access["XH"].astype(str)
            access["LOGINTIME_DT"] = _to_datetime(access["LOGINTIME"]) if "LOGINTIME" in access.columns else pd.NaT
            access["event_date"] = access["LOGINTIME_DT"].dt.date
            access["location"] = access["LOGINADDRESS"].astype(str).str.strip() if "LOGINADDRESS" in access.columns else "ACCESS_UNKNOWN"
            access_cnt = access.groupby("XH").size()
            access_unique_loc = access.groupby("XH")["location"].nunique()
        else:
            access_cnt = pd.Series(dtype=float)
            access_unique_loc = pd.Series(dtype=float)

        co_frames: list[pd.DataFrame] = []
        if not library.empty:
            co_frames.append(
                library[["XH", "event_date", "location"]]
                .dropna(subset=["event_date"])
                .assign(channel="library")
            )
        if not access.empty:
            co_frames.append(
                access[["XH", "event_date", "location"]]
                .dropna(subset=["event_date"])
                .assign(channel="access")
            )

        if co_frames:
            co_events = pd.concat(co_frames, ignore_index=True)
            co_events["slot_key"] = (
                co_events["channel"].astype(str)
                + "|"
                + co_events["event_date"].astype(str)
                + "|"
                + co_events["location"].astype(str)
            )
            slot_students = co_events.groupby("slot_key")["XH"].agg(lambda x: sorted(set(x))).tolist()
            pair_counter: dict[tuple[str, str], int] = {}
            for members in slot_students:
                member_count = len(members)
                if member_count < 2:
                    continue
                for i in range(member_count):
                    for j in range(i + 1, member_count):
                        pair = (members[i], members[j])
                        pair_counter[pair] = pair_counter.get(pair, 0) + 1

            partner_all: dict[str, set[str]] = {}
            partner_stable: dict[str, set[str]] = {}
            for (a, b), count in pair_counter.items():
                partner_all.setdefault(a, set()).add(b)
                partner_all.setdefault(b, set()).add(a)
                if count >= 3:
                    partner_stable.setdefault(a, set()).add(b)
                    partner_stable.setdefault(b, set()).add(a)
            stable_partner_cnt = pd.Series({k: len(v) for k, v in partner_stable.items()}, dtype=float)
            all_partner_cnt = pd.Series({k: len(v) for k, v in partner_all.items()}, dtype=float)
            social_density = stable_partner_cnt / all_partner_cnt.replace(0, np.nan)
        else:
            stable_partner_cnt = pd.Series(dtype=float)
            all_partner_cnt = pd.Series(dtype=float)
            social_density = pd.Series(dtype=float)

        df["formal_activity_participation_count"] = df["XH"].map(formal_cnt).fillna(0.0)
        df["formal_activity_frequency"] = (
            df["XH"].map(formal_cnt).fillna(0.0) /
            df["XH"].map(club_active_weeks).replace(0, np.nan)
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        df["activity_signin_rate"] = (
            0.7 * df["XH"].map(signin_rate).fillna(0.0)
            + 0.3 * df["XH"].map(task_signin).fillna(0.0)
        )
        df["checkin_consistency_index"] = (
            1 / (1 + df["XH"].map(weekly_checkin_std).fillna(0.0))
        ).clip(lower=0.0, upper=1.0)
        df["online_interaction_count"] = (
            df["XH"].map(discussion_cnt).fillna(0.0)
            + df["XH"].map(discussion_reply).fillna(0.0)
            + df["XH"].map(task_interaction).fillna(0.0)
        )
        df["post_reply_activity"] = (
            0.5 * df["XH"].map(post_cnt).fillna(0.0)
            + 0.3 * df["XH"].map(task_topic).fillna(0.0)
            + 0.2 * (df["XH"].map(discussion_reply).fillna(0.0) + df["XH"].map(task_reply).fillna(0.0))
        )
        df["stable_copresence_partner_count"] = df["XH"].map(stable_partner_cnt).fillna(0.0)
        df["offline_activity_index"] = _norm(
            df["formal_activity_participation_count"]
            + 0.6 * df["XH"].map(checkin_cnt).fillna(0.0)
            + 0.4 * (df["XH"].map(library_cnt).fillna(0.0) + df["XH"].map(access_cnt).fillna(0.0))
        )

        diversity_frame = pd.DataFrame(
            {
                "formal": df["formal_activity_participation_count"],
                "checkin": df["XH"].map(checkin_cnt).fillna(0.0),
                "discussion": df["XH"].map(discussion_cnt).fillna(0.0),
                "task_interaction": df["XH"].map(task_interaction).fillna(0.0),
                "library": df["XH"].map(library_cnt).fillna(0.0),
                "access": df["XH"].map(access_cnt).fillna(0.0),
                "library_loc": df["XH"].map(library_unique_loc).fillna(0.0),
                "access_loc": df["XH"].map(access_unique_loc).fillna(0.0),
            }
        )
        df["social_diversity_index"] = diversity_frame.apply(_entropy_from_counts, axis=1)
        df["social_circle_density"] = df["XH"].map(social_density).fillna(0.0).clip(lower=0.0, upper=1.0)
        course_frame = pd.concat([discussion_course, task_course], ignore_index=True)
        df["course_interaction_diversity"] = df["XH"].map(
            _normalized_entropy_from_weight_frame(course_frame, id_col="XH", key_col="course_key", weight_col="weight")
        ).fillna(0.0)
        event_frames: list[pd.DataFrame] = []
        for event_df, time_col in [
            (club, "HDRQ_DT"),
            (checkin, "ATTEND_TIME_DT"),
            (discussion, "CREATE_TIME_DT"),
            (task, "CREATE_TIME_DT"),
            (library, "visittime_dt"),
            (access, "LOGINTIME_DT"),
        ]:
            if not event_df.empty and "XH" in event_df.columns and time_col in event_df.columns:
                event_frames.append(event_df[["XH", time_col]].rename(columns={time_col: "event_time"}))
        if event_frames:
            time_events = pd.concat(event_frames, ignore_index=True)
            time_entropy = _hour_entropy_from_events(time_events, id_col="XH", time_col="event_time")
        else:
            time_entropy = pd.Series(dtype=float)
        df["social_time_entropy"] = df["XH"].map(time_entropy).fillna(0.0)
        df["interaction_quality_index"] = _norm(
            0.5 * df["XH"].map(task_pick).fillna(0.0)
            + 0.3 * df["XH"].map(task_answer).fillna(0.0)
            + 0.2 * df["XH"].map(task_rate).fillna(0.0)
        )
        scene_active_count = (
            (df["formal_activity_participation_count"] > 0).astype(int)
            + (df["XH"].map(checkin_cnt).fillna(0.0) > 0).astype(int)
            + (df["XH"].map(discussion_cnt).fillna(0.0) > 0).astype(int)
            + (df["XH"].map(task_interaction).fillna(0.0) > 0).astype(int)
            + (df["XH"].map(library_cnt).fillna(0.0) > 0).astype(int)
            + (df["XH"].map(access_cnt).fillna(0.0) > 0).astype(int)
        )
        df["multi_scene_engagement_index"] = (scene_active_count / 6.0).clip(lower=0.0, upper=1.0)
        df["social_isolation_index"] = (
            1
            - (
                0.35 * _norm(df["stable_copresence_partner_count"])
                + 0.25 * _norm(df["social_diversity_index"])
                + 0.20 * _norm(df["formal_activity_participation_count"])
                + 0.20 * _norm(df["online_interaction_count"])
            )
        ).clip(lower=0.0, upper=1.0)
        df["online_expression_ratio"] = (
            _to_numeric(df["online_interaction_count"]) /
            (
                _to_numeric(df["online_interaction_count"])
                + _to_numeric(df["offline_activity_index"]) * 100.0
                + 1.0
            )
        ).fillna(0.0)
        df["offline_online_balance_index"] = (
            1 - (_norm(df["online_interaction_count"]) - _norm(df["offline_activity_index"])).abs()
        ).clip(lower=0.0, upper=1.0)

        formal_engagement = (
            0.35 * _norm(df["formal_activity_participation_count"])
            + 0.25 * _norm(df["formal_activity_frequency"])
            + 0.35 * _norm(df["activity_signin_rate"])
            + 0.05 * _norm(df["checkin_consistency_index"])
        )
        copresence_component = (
            0.50 * _norm(df["stable_copresence_partner_count"])
            + 0.30 * _norm(df["social_circle_density"])
            + 0.20 * _norm(df["social_diversity_index"])
        )
        online_component = (
            0.45 * _norm(df["online_interaction_count"])
            + 0.35 * _norm(df["post_reply_activity"])
            + 0.20 * _norm(df["online_expression_ratio"])
        )
        quality_diversity_component = (
            0.35 * _norm(df["interaction_quality_index"])
            + 0.35 * _norm(df["course_interaction_diversity"])
            + 0.30 * _norm(df["multi_scene_engagement_index"])
        )
        stability_balance_component = (
            0.40 * _norm(df["offline_online_balance_index"])
            + 0.35 * _norm(df["checkin_consistency_index"])
            + 0.25 * _norm(df["social_time_entropy"])
        )
        warning_penalty = _norm(df["social_isolation_index"])
        df["social_life_total_score"] = (
            0.25 * formal_engagement
            + 0.20 * copresence_component
            + 0.20 * online_component
            + 0.15 * quality_diversity_component
            + 0.20 * stability_balance_component
            - 0.10 * warning_penalty
        ).clip(lower=0.0, upper=1.0)

        df["feature_grain"] = "student_week"
        df["time_window"] = "近8周"
        df["snapshot_date"] = pd.Timestamp.now().normalize()

        ordered = [
            "XH",
            "feature_grain",
            "time_window",
            "snapshot_date",
            "formal_activity_participation_count",
            "formal_activity_frequency",
            "activity_signin_rate",
            "checkin_consistency_index",
            "online_interaction_count",
            "post_reply_activity",
            "interaction_quality_index",
            "stable_copresence_partner_count",
            "social_diversity_index",
            "course_interaction_diversity",
            "social_time_entropy",
            "social_circle_density",
            "multi_scene_engagement_index",
            "offline_activity_index",
            "online_expression_ratio",
            "offline_online_balance_index",
            "social_isolation_index",
            "social_life_total_score",
        ]
        existing = [col for col in ordered if col in df.columns]
        return df[existing].sort_values("XH").reset_index(drop=True)

    def save(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = self.build()
        history_path = output_path.with_name("social_life_features_history.parquet")
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
            return output_path
        except Exception:
            csv_path = output_path.with_suffix(".csv")
            result.to_csv(csv_path, index=False, encoding="utf-8-sig")
            history.to_csv(history_path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
            return csv_path
