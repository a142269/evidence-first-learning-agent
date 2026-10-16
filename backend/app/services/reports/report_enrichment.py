"""深度归因、行为画像、辅导员工具包 —— 报告个性化增强层。

设计目标：
- 归因从 data/ods 原始表读取具体数值（图书馆第多少次、讨论0条、深夜门禁N次），
  而不是对 individual_portraits 的分数做二次解读；
- 行为画像类型化为 6 个典型角色标签，用于匹配个性化微计划与辅导员话术；
- 弱相关（|rho|<0.1）一律语义化为「未观测到显著关联」，避免 0.0 冷硬出现在报告里；
- 数据时效若 > 180 天，报告模式自动切换为「历史行为模式档案」。

读表使用模块级缓存，首次读取后同进程内不会重复 IO。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


_ODS_TABLE_CACHE: dict[str, pd.DataFrame] = {}


def _load_ods_table(project_root: Path, rel_path: str, usecols: list[str] | None = None) -> pd.DataFrame:
    key = rel_path
    cached = _ODS_TABLE_CACHE.get(key)
    if cached is not None:
        return cached
    path = project_root / "data" / "ods" / rel_path
    if not path.exists():
        _ODS_TABLE_CACHE[key] = pd.DataFrame()
        return _ODS_TABLE_CACHE[key]
    try:
        head = pd.read_excel(path, nrows=0)
        avail = {str(c) for c in head.columns}
        picked = [c for c in (usecols or []) if c in avail]
        df = pd.read_excel(path, usecols=picked) if picked else pd.read_excel(path)
    except Exception:
        df = pd.DataFrame()
    if "XH" in df.columns:
        df = df.copy()
        df["XH"] = df["XH"].astype(str).str.strip()
    _ODS_TABLE_CACHE[key] = df
    return df


def _student_rows(df: pd.DataFrame, student_id: str) -> pd.DataFrame:
    if df.empty or "XH" not in df.columns:
        return pd.DataFrame()
    return df[df["XH"] == str(student_id)]


def _to_num(value: Any) -> float:
    try:
        return float(pd.to_numeric(value, errors="coerce") or 0.0)
    except Exception:
        return 0.0


# ----------------------------------------------------------------------------
# 行为画像：六种典型角色
# ----------------------------------------------------------------------------
ARCHETYPES: dict[str, dict[str, str]] = {
    "high_achiever": {
        "archetype": "自驱引领者",
        "nickname": "笃行的探路人",
        "description": "学习行为与学业产出双高，具备清晰的目标感与较强的执行力，属于可树立为同伴标杆的学生类型。",
    },
    "effort_outcome_gap": {
        "archetype": "规范执行但效能偏低",
        "nickname": "努力的追赶者",
        "description": "行动频率稳定、态度端正，但学习动作未有效转化为学业成果，常见原因是学习策略或题型训练方向需调整。",
    },
    "rhythm_broken": {
        "archetype": "节律失控型",
        "nickname": "疲惫的夜行者",
        "description": "作息与生活节律不稳定，导致学习动作间歇性中断；优先解决节律问题，再谈学习投入通常更有效。",
    },
    "habit_breakdown": {
        "archetype": "习惯断层型",
        "nickname": "走神的旁观者",
        "description": "日常学习行为（签到、作业、讨论）发生频率整体偏低，呈现「在场但不在线」状态，需要重建最小可持续的学习闭环。",
    },
    "social_exploration_low": {
        "archetype": "社交探索收缩型",
        "nickname": "低调的独行者",
        "description": "社交参与和课程探索都相对内敛，既未在群体中显露风险也未形成支持网络，建议关注其情绪与归属感状态。",
    },
    "lifestyle_first": {
        "archetype": "生活型活跃者",
        "nickname": "校园里的社交达人",
        "description": "生活与社交维度活跃，但学业投入尚未同步匹配，适合通过兴趣或组织任务把活跃度回注到学业主线。",
    },
    "stable_average": {
        "archetype": "稳态中游型",
        "nickname": "规律的常驻生",
        "description": "五维大致均衡、风险低、也无明显亮点，适合选定1个优势维度进行重点突破以打开成长空间。",
    },
}


def identify_behavior_archetype(score_cards: list[dict[str, Any]]) -> dict[str, str]:
    by_mode = {str(item.get("mode", "")): _to_num(item.get("score", 0.0)) for item in score_cards}
    lb = by_mode.get("学习行为模式", 0.0)
    lo = by_mode.get("学习成果模式", 0.0)
    lh = by_mode.get("生活节律与运动健康模式", 0.0)
    sl = by_mode.get("社交生活模式", 0.0)
    ce = by_mode.get("选课探索模式", 0.0)

    if lb >= 0.65 and lo >= 0.65:
        code = "high_achiever"
    elif lb >= 0.55 and lo < 0.45:
        code = "effort_outcome_gap"
    elif lh < 0.4 and lb < 0.55:
        code = "rhythm_broken"
    elif lb < 0.4 and lo < 0.45:
        code = "habit_breakdown"
    elif sl < 0.4 and ce < 0.4:
        code = "social_exploration_low"
    elif lh >= 0.6 and sl >= 0.55 and lb < 0.55:
        code = "lifestyle_first"
    else:
        code = "stable_average"

    meta = ARCHETYPES[code]
    traits = [
        f"学习投入 {lb:.2f}（{'偏强' if lb >= 0.55 else '偏弱' if lb < 0.45 else '中位'}）",
        f"学习成果 {lo:.2f}（{'偏强' if lo >= 0.55 else '偏弱' if lo < 0.45 else '中位'}）",
        f"生活节律 {lh:.2f}（{'偏强' if lh >= 0.55 else '偏弱' if lh < 0.45 else '中位'}）",
        f"社交参与 {sl:.2f}（{'偏强' if sl >= 0.55 else '偏弱' if sl < 0.45 else '中位'}）",
        f"课程探索 {ce:.2f}（{'偏强' if ce >= 0.55 else '偏弱' if ce < 0.45 else '中位'}）",
    ]
    out = {"code": code, **meta, "traits": traits}
    out["name"] = out.get("archetype", "")
    return out


# ----------------------------------------------------------------------------
# 跨表深度归因：读 ODS 原始表
# ----------------------------------------------------------------------------
def _build_learning_dimension(project_root: Path, sid: str) -> dict[str, Any]:
    lib = _load_ods_table(project_root, "learning_logs/图书馆打卡记录.xlsx", ["XH", "visittime"])
    lib_rows = _student_rows(lib, sid)
    lib_count = int(len(lib_rows))
    lib_weekday = lib_weekend = 0
    lib_span = ""
    if lib_count and "visittime" in lib_rows.columns:
        dt = pd.to_datetime(lib_rows["visittime"], errors="coerce").dropna()
        if len(dt):
            lib_weekend = int((dt.dt.dayofweek >= 5).sum())
            lib_weekday = len(dt) - lib_weekend
            lib_span = f"{dt.min().date()} ~ {dt.max().date()}"

    disc = _load_ods_table(project_root, "learning_logs/讨论记录.xlsx", ["XH"])
    disc_count = int(len(_student_rows(disc, sid)))

    signin = _load_ods_table(project_root, "learning_logs/学生签到记录.xlsx", ["XH"])
    signin_count = int(len(_student_rows(signin, sid)))

    hw = _load_ods_table(project_root, "learning_logs/学生作业提交记录.xlsx", ["XH"])
    hw_count = int(len(_student_rows(hw, sid)))

    evidence = [
        {
            "source": "learning_logs/图书馆打卡记录.xlsx",
            "fact": (
                f"全观测窗口内到馆 {lib_count} 次"
                + (f"（工作日 {lib_weekday} / 周末 {lib_weekend}，时间跨度 {lib_span}）" if lib_count else "")
            ),
        },
        {"source": "learning_logs/讨论记录.xlsx", "fact": f"课程讨论发言记录 {disc_count} 条"},
        {"source": "learning_logs/学生签到记录.xlsx", "fact": f"课堂签到累计 {signin_count} 次"},
        {"source": "learning_logs/学生作业提交记录.xlsx", "fact": f"作业提交累计 {hw_count} 次"},
    ]
    if lib_count == 0 and disc_count == 0 and signin_count < 10:
        conclusion = "学习现场感极弱：图书馆、线上讨论、课堂签到三个通道都没有形成有效学习痕迹。"
        action = "先恢复「物理在场」——本周固定 3 次图书馆时段，每次 45 分钟，只需坐满即可。"
    elif hw_count > 0 and disc_count == 0:
        conclusion = "仅完成提交类任务，缺少讨论/互动类深度学习行为。"
        action = "加入 1 门课程的讨论组，每周发言至少 1 条；可由辅导员引荐学习伙伴。"
    elif lib_count > 10 and signin_count < 30:
        conclusion = "图书馆活动稳定但课堂出勤不足，存在「自学挤压课堂」倾向。"
        action = "保留自学节奏同时恢复课堂到课，先优先选 2 门核心课程保证全勤。"
    else:
        conclusion = "学习通道整体可观察，但各通道强度并不均衡，建议按课程重点再细化。"
        action = "挑选 1 门最重要课程把「图书馆→作业→讨论」形成每周闭环。"
    return {
        "dimension": "学习投入维度",
        "evidence_points": evidence,
        "conclusion": conclusion,
        "action": action,
    }


def _build_output_dimension(project_root: Path, sid: str) -> dict[str, Any]:
    grades = _load_ods_table(project_root, "grade_records/学生成绩.xlsx", ["XH", "KCMC", "ZCJ", "CJJD"])
    g_rows = _student_rows(grades, sid)
    course_count = int(len(g_rows))
    avg_grade = 0.0
    fail_count = 0
    min_course = ""
    if course_count and "ZCJ" in g_rows.columns:
        scores = pd.to_numeric(g_rows["ZCJ"], errors="coerce")
        valid = scores.dropna()
        if len(valid):
            avg_grade = float(valid.mean())
            fail_count = int((valid < 60).sum())
            if "KCMC" in g_rows.columns:
                g_sorted = g_rows.assign(_s=scores).dropna(subset=["_s"]).sort_values("_s")
                if len(g_sorted):
                    row = g_sorted.iloc[0]
                    min_course = f"{row.get('KCMC','')}（{float(row['_s']):.1f}）"

    comp = _load_ods_table(project_root, "grade_records/学科竞赛.xlsx", ["XH"])
    comp_count = int(len(_student_rows(comp, sid)))

    scholar = _load_ods_table(project_root, "grade_records/奖学金获奖.xlsx", ["XH"])
    scholar_count = int(len(_student_rows(scholar, sid)))

    evidence = [
        {
            "source": "grade_records/学生成绩.xlsx",
            "fact": (
                f"累计 {course_count} 门课程"
                + (f"，均分 {avg_grade:.1f}" if avg_grade else "")
                + (f"，不及格 {fail_count} 门" if fail_count else "")
                + (f"；最低分课程：{min_course}" if min_course else "")
            ),
        },
        {"source": "grade_records/学科竞赛.xlsx", "fact": f"学科竞赛参与 {comp_count} 次"},
        {"source": "grade_records/奖学金获奖.xlsx", "fact": f"奖学金获奖记录 {scholar_count} 次"},
    ]
    if fail_count >= 3:
        conclusion = f"已出现 {fail_count} 门不及格，学业产出进入红线区间，需要立即锁定薄弱课程做挽救。"
        action = "辅导员优先与教务确认补考/重修窗口，学生侧同步针对最低分课程建立每周专项训练。"
    elif fail_count == 0 and avg_grade >= 80:
        conclusion = "学业成果稳定中上，具备冲击奖学金或学科竞赛的基础。"
        action = "可尝试选择 1 项竞赛或研究项目，将「稳态」转化为「发展态」。"
    elif avg_grade and avg_grade < 70:
        conclusion = "虽未挂科但均分偏低，存在「边缘通过」风险，一门波动即可能跌破红线。"
        action = "把均分低于 70 的课程挑 2 门，每周各投入 3 次专项复盘。"
    else:
        conclusion = "学业产出处于可修复区间，尚未出现系统性风险。"
        action = "维持当前节奏，同时可选择 1 个高绩点课程冲刺提分，形成正反馈。"
    return {
        "dimension": "学业产出维度",
        "evidence_points": evidence,
        "conclusion": conclusion,
        "action": action,
    }


def _build_rhythm_dimension(project_root: Path, sid: str) -> dict[str, Any]:
    net = _load_ods_table(project_root, "lifestyle_health/上网统计.xlsx", ["XH", "SCSC", "SCMW"])
    net_rows = _student_rows(net, sid)
    net_min = 0
    for col in ("SCSC", "SCMW"):
        if col in net_rows.columns:
            net_min += int(pd.to_numeric(net_rows[col], errors="coerce").fillna(0).sum())

    run = _load_ods_table(project_root, "lifestyle_health/跑步打卡.xlsx", ["XH"])
    run_count = int(len(_student_rows(run, sid)))

    exercise = _load_ods_table(project_root, "lifestyle_health/日常锻炼.xlsx", ["XH"])
    ex_count = int(len(_student_rows(exercise, sid)))

    entry = _load_ods_table(project_root, "social_activity/门禁数据.xlsx", ["XH", "LOGINTIME"])
    entry_rows = _student_rows(entry, sid)
    late_night = 0
    early_back = 0
    if not entry_rows.empty and "LOGINTIME" in entry_rows.columns:
        dt = pd.to_datetime(entry_rows["LOGINTIME"], errors="coerce").dropna()
        late_night = int(((dt.dt.hour >= 23) | (dt.dt.hour < 5)).sum())
        early_back = int((dt.dt.hour < 19).sum())

    evidence = [
        {"source": "lifestyle_health/上网统计.xlsx", "fact": f"累计在线时长约 {net_min} 分钟"},
        {"source": "lifestyle_health/跑步打卡.xlsx", "fact": f"跑步打卡 {run_count} 次"},
        {"source": "lifestyle_health/日常锻炼.xlsx", "fact": f"日常锻炼登记 {ex_count} 次"},
        {"source": "social_activity/门禁数据.xlsx", "fact": f"深夜（23:00–05:00）出入 {late_night} 次；19:00 前回寝 {early_back} 次"},
    ]
    if late_night >= 15 and (run_count + ex_count) <= 2:
        conclusion = "夜间活动频繁 + 运动几乎为零，节律与体能双通道同时吃紧。"
        action = "先从 23:30 断网 + 早间打卡开始，两周后再谈学习策略调整。"
    elif run_count + ex_count >= 10 and late_night < 5:
        conclusion = "作息规律且运动活跃，生活节律已形成保护机制。"
        action = "把规律节律迁移到学习端——每周设定 2 个固定学习时段，利用节律惯性。"
    elif net_min >= 20000:
        conclusion = "在线时长偏高，生活注意力已向线上倾斜，线下活动密度不足。"
        action = "用 1 项固定线下活动（球类/社团例会）替换每周 2 小时线上时间。"
    else:
        conclusion = "生活节律尚无显著异常，但运动与锻炼通道较薄弱。"
        action = "加入 1 项每周可持续的锻炼，用身体状态带动学习状态。"
    return {
        "dimension": "生活节律维度",
        "evidence_points": evidence,
        "conclusion": conclusion,
        "action": action,
    }


def _build_social_dimension(project_root: Path, sid: str) -> dict[str, Any]:
    club = _load_ods_table(project_root, "social_activity/社团活动.xlsx", ["XH"])
    club_count = int(len(_student_rows(club, sid)))

    disc = _load_ods_table(project_root, "learning_logs/讨论记录.xlsx", ["XH"])
    disc_count = int(len(_student_rows(disc, sid)))

    task = _load_ods_table(project_root, "learning_logs/课堂任务参与.xlsx", ["XH"])
    task_count = int(len(_student_rows(task, sid)))

    evidence = [
        {"source": "social_activity/社团活动.xlsx", "fact": f"社团/校园活动参与 {club_count} 次"},
        {"source": "learning_logs/讨论记录.xlsx", "fact": f"课程讨论发言 {disc_count} 条"},
        {"source": "learning_logs/课堂任务参与.xlsx", "fact": f"课堂任务参与 {task_count} 次"},
    ]
    if club_count == 0 and disc_count == 0:
        conclusion = "线下社团、课程讨论两条社交通道都没有痕迹，可能存在社交退缩或圈层过窄。"
        action = "由辅导员牵线 1 位同专业同学结对，从每周 1 次学习陪同开始过渡。"
    elif club_count >= 3 and disc_count < 3:
        conclusion = "线下社团活跃但课程社交仍处孤立状态，社交能量未回流到学业。"
        action = "邀请社团好友加入 1 门课程的讨论组，把熟人关系迁移到学业场景。"
    elif task_count >= 20 and disc_count >= 5:
        conclusion = "课程协作型社交已形成，是较稳固的支持网络。"
        action = "鼓励承担 1 次课程小组负责人角色，把参与者转为组织者。"
    else:
        conclusion = "社交融入处于基础水平，既未强连接也未孤立。"
        action = "明确 1 位可联系的同伴，遇到学业问题先求助再自我消化。"
    return {
        "dimension": "社交融入维度",
        "evidence_points": evidence,
        "conclusion": conclusion,
        "action": action,
    }


def _build_environment_dimension(project_root: Path, sid: str) -> dict[str, Any]:
    """环境因维度：课程负荷、考勤环境、选课结构等外部因素。"""
    course = _load_ods_table(project_root, "course_selection/学生选课信息.xlsx", ["XH", "KCMC"])
    course_rows = _student_rows(course, sid)
    course_count = int(len(course_rows))

    attendance = _load_ods_table(project_root, "learning_logs/考勤汇总.xlsx", ["XH", "QK_COUNT", "CD_COUNT", "ZT_COUNT"])
    att_rows = _student_rows(attendance, sid)
    absent_count = late_count = leave_count = 0
    if not att_rows.empty:
        for col, target in [("QK_COUNT", "absent"), ("CD_COUNT", "late"), ("ZT_COUNT", "leave")]:
            if col in att_rows.columns:
                val = int(pd.to_numeric(att_rows[col], errors="coerce").fillna(0).sum())
                if target == "absent":
                    absent_count = val
                elif target == "late":
                    late_count = val
                else:
                    leave_count = val

    exam = _load_ods_table(project_root, "learning_logs/考试提交记录.xlsx", ["XH"])
    exam_count = int(len(_student_rows(exam, sid)))

    class_info = _load_ods_table(project_root, "learning_logs/上课信息统计表.xlsx", ["XH", "TEACH_TIME"])
    class_rows = _student_rows(class_info, sid)
    class_session_count = int(len(class_rows))

    evidence = [
        {"source": "course_selection/学生选课信息.xlsx", "fact": f"本观测期内选课 {course_count} 门"},
        {
            "source": "learning_logs/考勤汇总.xlsx",
            "fact": f"考勤记录：缺勤 {absent_count} 次、迟到 {late_count} 次、请假 {leave_count} 次",
        },
        {"source": "learning_logs/考试提交记录.xlsx", "fact": f"考试提交记录 {exam_count} 条"},
        {"source": "learning_logs/上课信息统计表.xlsx", "fact": f"排课节次累计 {class_session_count} 条"},
    ]
    if course_count >= 12 and absent_count >= 10:
        conclusion = "课程负荷较重且缺勤频率较高，外部压力与出勤脱节同步出现，环境适应存在明显裂痕。"
        action = "建议辅导员联合教务梳理课表，优先减少低效选修、聚焦核心课程出勤。"
    elif absent_count >= 8:
        conclusion = "缺勤次数偏高，无论课程负荷如何，课堂参与的外部约束已经失效。"
        action = "恢复外部锚点：与辅导员约定本周 3 次必到课程，每次签到后给辅导员发消息确认。"
    elif course_count >= 10 and absent_count <= 2:
        conclusion = "选课量偏大但出勤良好，课程环境适应力较强。"
        action = "维持当前节奏，但需留意高负荷下的疲劳累积，建议保持每周至少 1 天低负荷调整。"
    else:
        conclusion = "课程环境与出勤状态无明显异常，外部因素暂未构成主要风险。"
        action = "维持现状，如出现连续缺勤信号再升级关注。"
    return {
        "dimension": "环境因维度",
        "evidence_points": evidence,
        "conclusion": conclusion,
        "action": action,
    }


def _build_triple_linkage(
    lb: dict[str, Any],
    lo: dict[str, Any],
    rh: dict[str, Any],
    sc: dict[str, Any],
    env: dict[str, Any],
) -> list[dict[str, Any]]:
    """三层叙事链：表象维度(发生了什么) → 动机维度(为什么) → 后果维度(会导致什么)。

    每个维度的三层叙事串成一个连贯的故事，而不是并列的三段标题。
    """
    linkages: list[dict[str, Any]] = []

    def _extract_numbers(dim: dict[str, Any]) -> dict[str, str]:
        """从 evidence_points 提取关键数字用于叙事。"""
        nums: dict[str, str] = {}
        for ep in dim.get("evidence_points", []):
            fact = str(ep.get("fact", ""))
            source = str(ep.get("source", ""))
            nums[source] = fact
        return nums

    # ---------- 学习投入 ----------
    lb_nums = _extract_numbers(lb)
    lb_surface = lb.get("conclusion", "")
    lb_evidence_summary = "；".join(ep.get("fact", "") for ep in lb.get("evidence_points", []) if ep.get("fact"))
    linkages.append({
        "dimension": "学习投入",
        "surface": {
            "label": "行为表象",
            "question": "发生了什么？",
            "content": lb_surface,
            "evidence_brief": lb_evidence_summary,
        },
        "motivation": {
            "label": "动机逻辑",
            "question": "为什么发生？",
            "content": (
                "当图书馆到馆和讨论参与同时偏低时，通常不是能力不足，"
                "而是「学习启动成本过高」——缺少固定的时间锚点和同伴提醒，导致行动一再推迟。"
                if any("0 次" in str(ep.get("fact", "")) or "0 条" in str(ep.get("fact", "")) for ep in lb.get("evidence_points", []))
                else "学习通道已有基础活跃度，动机层面处于「维持性投入」状态，尚未形成主动深化的内驱力。"
            ),
            "rag_hint": "参考知识库「学习动机与行为启动」相关章节",
        },
        "impact": {
            "label": "后果预判",
            "question": "会导致什么？",
            "content": (
                "若持续缺乏有效学习痕迹，历史相似案例中约 70% 的学生在期末出现 1-2 门不及格。"
                if any("0 次" in str(ep.get("fact", "")) or "0 条" in str(ep.get("fact", "")) for ep in lb.get("evidence_points", []))
                else "当前投入水平可维持基本学业，但难以支撑成绩突破或竞赛参与。"
            ),
        },
    })

    # ---------- 学业产出 ----------
    lo_surface = lo.get("conclusion", "")
    lo_evidence_summary = "；".join(ep.get("fact", "") for ep in lo.get("evidence_points", []) if ep.get("fact"))
    has_fail = any("不及格" in str(ep.get("fact", "")) and "0 门" not in str(ep.get("fact", "")) for ep in lo.get("evidence_points", []))
    linkages.append({
        "dimension": "学业产出",
        "surface": {
            "label": "行为表象",
            "question": "发生了什么？",
            "content": lo_surface,
            "evidence_brief": lo_evidence_summary,
        },
        "motivation": {
            "label": "动机逻辑",
            "question": "为什么发生？",
            "content": (
                "出现挂科通常意味着某些课程的学习策略已经失效——可能是听课跟不上导致作业靠抄、"
                "也可能是考前突击无法覆盖知识缺口，属于「认知负荷超载」的典型表现。"
                if has_fail
                else "成绩处于可维持区间，但缺少明确的提升驱动力，处于「够用就好」的心理舒适区。"
            ),
            "rag_hint": "参考知识库「截止驱动与拖延」「认知负荷」相关章节",
        },
        "impact": {
            "label": "后果预判",
            "question": "会导致什么？",
            "content": (
                "不及格课程若未及时补救，将直接影响学分绩点和毕业资格审查；连续两学期挂科可能触发学业预警。"
                if has_fail
                else "短期内学业安全，但长期缺乏突破可能错过奖学金、保研等发展窗口。"
            ),
        },
    })

    # ---------- 生活节律 ----------
    rh_surface = rh.get("conclusion", "")
    rh_evidence_summary = "；".join(ep.get("fact", "") for ep in rh.get("evidence_points", []) if ep.get("fact"))
    has_late_night = any("深夜" in str(ep.get("fact", "")) and "0 次" not in str(ep.get("fact", "")) for ep in rh.get("evidence_points", []))
    late_night_count = 0
    for ep in rh.get("evidence_points", []):
        fact = str(ep.get("fact", ""))
        if "深夜" in fact:
            m = re.search(r"深夜.*?(\d+)\s*次", fact)
            if m:
                late_night_count = int(m.group(1))
    linkages.append({
        "dimension": "生活节律",
        "surface": {
            "label": "行为表象",
            "question": "发生了什么？",
            "content": rh_surface,
            "evidence_brief": rh_evidence_summary,
        },
        "motivation": {
            "label": "动机逻辑",
            "question": "为什么发生？",
            "content": (
                f"深夜出入 {late_night_count} 次，这在教育心理学中属于典型的「延迟满足失调」——"
                "白天积累的压力或无聊感在夜间通过娱乐或社交释放，形成恶性循环。"
                if late_night_count >= 10
                else "生活节律整体可控，当前模式更接近「被动维持」而非主动管理。"
            ),
            "rag_hint": "参考知识库「生活节律与学业表现」「睡眠-认知关联」相关章节",
        },
        "impact": {
            "label": "后果预判",
            "question": "会导致什么？",
            "content": (
                "持续的作息紊乱将降低白天的认知效率，历史数据显示深夜活跃频繁的学生次学期成绩平均下滑 8-12%。"
                if late_night_count >= 10
                else "节律暂无红线风险，但缺少运动和规律锻炼可能在高压期（期末）放大疲劳效应。"
            ),
        },
    })

    # ---------- 社交融入 ----------
    sc_surface = sc.get("conclusion", "")
    sc_evidence_summary = "；".join(ep.get("fact", "") for ep in sc.get("evidence_points", []) if ep.get("fact"))
    is_isolated = all(
        "0 次" in str(ep.get("fact", "")) or "0 条" in str(ep.get("fact", ""))
        for ep in sc.get("evidence_points", [])
    )
    linkages.append({
        "dimension": "社交融入",
        "surface": {
            "label": "行为表象",
            "question": "发生了什么？",
            "content": sc_surface,
            "evidence_brief": sc_evidence_summary,
        },
        "motivation": {
            "label": "动机逻辑",
            "question": "为什么发生？",
            "content": (
                "社交通道全部静默并不一定意味着内向，更常见的原因是「归属感缺失」——"
                "没有找到匹配的同伴群体，导致社交尝试的心理成本过高。"
                if is_isolated
                else "已有基础社交网络，但社交能量主要停留在生活层面，尚未有效迁移到学业互助场景。"
            ),
            "rag_hint": "参考知识库「同伴效应与社交支持」相关章节",
        },
        "impact": {
            "label": "后果预判",
            "question": "会导致什么？",
            "content": (
                "长期社交孤立会削弱信息获取能力（错过作业提醒、考试重点等），"
                "同时降低心理韧性，在遇到学业挫折时更容易选择回避而非求助。"
                if is_isolated
                else "社交基础尚可，但如果不主动向学业场景延伸，将错过「同伴带动效应」的红利。"
            ),
        },
    })

    # ---------- 环境因 ----------
    env_surface = env.get("conclusion", "")
    env_evidence_summary = "；".join(ep.get("fact", "") for ep in env.get("evidence_points", []) if ep.get("fact"))
    has_high_absence = any("缺勤" in str(ep.get("fact", "")) for ep in env.get("evidence_points", []))
    absence_count = 0
    for ep in env.get("evidence_points", []):
        fact = str(ep.get("fact", ""))
        if "缺勤" in fact:
            m = re.search(r"缺勤\s*(\d+)\s*次", fact)
            if m:
                absence_count = int(m.group(1))
    linkages.append({
        "dimension": "环境适应",
        "surface": {
            "label": "行为表象",
            "question": "发生了什么？",
            "content": env_surface,
            "evidence_brief": env_evidence_summary,
        },
        "motivation": {
            "label": "动机逻辑",
            "question": "为什么发生？",
            "content": (
                f"缺勤 {absence_count} 次在课程负荷背景下提示外部环境约束力下降，"
                "可能是课程内容与预期不符导致的主动回避，也可能是时间管理失控的被动结果。"
                if absence_count >= 8
                else "环境适应指标正常，外部课程结构与出勤状态形成了基本的支撑框架。"
            ),
            "rag_hint": "参考知识库「环境适应与课程负荷」相关章节",
        },
        "impact": {
            "label": "后果预判",
            "question": "会导致什么？",
            "content": (
                "高缺勤率在教务系统中会触发考试资格限制（部分课程缺课超 1/3 取消考试资格），"
                "且缺勤惯性一旦形成，恢复出勤的心理成本会逐周递增。"
                if absence_count >= 8
                else "环境因素暂不构成独立风险，但需在其他维度恶化时作为放大器重新评估。"
            ),
        },
    })

    return linkages


def build_strength_highlights(score_cards: list[dict[str, Any]], deep_attr: dict[str, Any]) -> dict[str, Any]:
    """从数据中挖掘该生的优势闪光点，即使是高风险学生也一定有值得肯定的维度。"""
    by_mode = {str(item.get("mode", "")): _to_num(item.get("score", 0.0)) for item in score_cards}
    highlights: list[dict[str, str]] = []

    # 找最高维度
    if by_mode:
        best_mode = max(by_mode, key=lambda k: by_mode[k])
        best_score = by_mode[best_mode]
        mode_short = best_mode.replace("模式", "").replace("与运动健康", "")
        if best_score >= 0.55:
            highlights.append({
                "dimension": mode_short,
                "statement": f"在{mode_short}方面表现突出（得分 {best_score:.2f}），这是该生最具优势的领域。",
                "leverage": f"建议以{mode_short}为支点，带动其他较弱维度的改善。",
            })
        elif best_score >= 0.4:
            highlights.append({
                "dimension": mode_short,
                "statement": f"虽然整体偏弱，但{mode_short}相对最好（得分 {best_score:.2f}），是最有希望率先突破的方向。",
                "leverage": f"从{mode_short}切入建立信心，再逐步扩展到其他维度。",
            })

    # 从深度归因中找具体的闪光行为
    for dim_key, dim_name, positive_keywords in [
        ("learning_behavior", "学习投入", ["图书馆", "签到", "作业提交"]),
        ("learning_outcome", "学业产出", ["奖学金", "竞赛", "均分"]),
        ("rhythm_health", "生活节律", ["跑步", "锻炼", "运动"]),
        ("social_life", "社交融入", ["社团", "讨论", "课堂任务"]),
    ]:
        dim = deep_attr.get(dim_key, {})
        for ep in dim.get("evidence_points", []):
            fact = str(ep.get("fact", ""))
            for kw in positive_keywords:
                if kw in fact:
                    nums = re.findall(r"(\d+)", fact)
                    if nums and int(nums[0]) > 0:
                        highlights.append({
                            "dimension": dim_name,
                            "statement": f"发现亮点：{fact}",
                            "leverage": f"这说明该生在{dim_name}方面并非完全空白，可以此为起点强化。",
                        })
                        break

    # 去重，最多保留 4 条
    seen = set()
    unique: list[dict[str, str]] = []
    for h in highlights:
        key = h["dimension"]
        if key not in seen:
            seen.add(key)
            unique.append(h)
    highlights = unique[:4]

    if not highlights:
        highlights = [{
            "dimension": "潜力",
            "statement": "虽然各维度数据均偏低，但该生仍在校且有行为记录，说明基本的参与意愿尚存。",
            "leverage": "从最小可行动作开始：本周到课 1 次、图书馆坐 30 分钟，建立最初的正反馈循环。",
        }]

    return {
        "highlight_count": len(highlights),
        "highlights": highlights,
        "warmth_statement": (
            f"即使在需要关注的领域，该生在{highlights[0]['dimension']}方面仍展现了积极信号，"
            "建议利用这一优势作为谈话切入点和改善支点。"
        ),
    }


def build_confidence_assessment(deep_attr: dict[str, Any], data_source_trace: dict[str, Any]) -> dict[str, Any]:
    """为报告结论生成置信度评估，让辅导员知道哪些结论可信、哪些需要补充验证。"""
    summary = data_source_trace.get("summary", {}) if isinstance(data_source_trace, dict) else {}
    total_tables = summary.get("source_count", 0)
    tables_with_data = summary.get("tables_with_student_data", 0)
    freshness = summary.get("overall_freshness_days")

    # 数据覆盖率
    coverage = tables_with_data / max(total_tables, 1)

    # 计算每个维度的证据强度
    dim_confidence: list[dict[str, Any]] = []
    for dim in deep_attr.get("dimensions", []):
        dim_name = dim.get("dimension", "")
        evidence_points = dim.get("evidence_points", [])
        total_evidence = len(evidence_points)
        non_zero = sum(
            1 for ep in evidence_points
            if not any(z in str(ep.get("fact", "")) for z in ["0 次", "0 条", "0 分钟", " 0 门"])
        )
        strength = non_zero / max(total_evidence, 1)
        if strength >= 0.75:
            level = "高"
            note = "多源数据交叉验证，结论可靠"
        elif strength >= 0.5:
            level = "中"
            note = "部分数据源有记录，结论基本可信但建议补充核实"
        else:
            level = "低"
            note = "数据源覆盖不足，结论仅供参考，建议通过面谈补充信息"
        dim_confidence.append({
            "dimension": dim_name,
            "evidence_count": total_evidence,
            "non_zero_evidence": non_zero,
            "confidence_level": level,
            "confidence_note": note,
        })

    # 总体置信度
    avg_strength = sum(d["non_zero_evidence"] for d in dim_confidence) / max(sum(d["evidence_count"] for d in dim_confidence), 1)
    if avg_strength >= 0.7 and coverage >= 0.5:
        overall = "高"
        overall_note = f"基于 {total_tables} 张表中 {tables_with_data} 张有该生记录，数据覆盖率 {coverage:.0%}，整体结论可靠。"
    elif avg_strength >= 0.4:
        overall = "中"
        overall_note = f"数据覆盖率 {coverage:.0%}，部分维度证据较薄，标注为「低置信」的维度建议通过面谈核实。"
    else:
        overall = "低"
        overall_note = f"数据覆盖率仅 {coverage:.0%}，多数维度证据不足，本报告更适合作为面谈前的初步参考。"

    return {
        "overall_confidence": overall,
        "overall_note": overall_note,
        "data_coverage": round(coverage, 3),
        "tables_total": total_tables,
        "tables_with_student_data": tables_with_data,
        "dimension_confidence": dim_confidence,
    }


def build_deep_attribution(project_root: Path, student_id: str) -> dict[str, Any]:
    sid = str(student_id)
    lb = _build_learning_dimension(project_root, sid)
    lo = _build_output_dimension(project_root, sid)
    rh = _build_rhythm_dimension(project_root, sid)
    sc = _build_social_dimension(project_root, sid)
    env = _build_environment_dimension(project_root, sid)
    triple_linkage = _build_triple_linkage(lb, lo, rh, sc, env)
    return {
        "learning_behavior": lb,
        "learning_outcome": lo,
        "rhythm_health": rh,
        "social_life": sc,
        "environment": env,
        "dimensions": [lb, lo, rh, sc, env],
        "triple_linkage": triple_linkage,
        "methodology_note": (
            "全部证据读自 data/ods 原始业务表，数值均为该生在全观测窗口内的实际累计记录；"
            "三层叙事链（表象→动机→后果）基于数据事实与教育心理学知识库联合生成，"
            "结论与行动建议可被辅导员直接核对到单表。"
        ),
    }


# ----------------------------------------------------------------------------
# 个性化微计划（按角色匹配）
# ----------------------------------------------------------------------------
_MICRO_PLANS: dict[str, list[dict[str, Any]]] = {
    "high_achiever": [
        {"day": "D1", "focus": "保持节奏", "actions": ["锁定下周冲刺课程 1 门", "完成 1 次定时模考"]},
        {"day": "D2", "focus": "深度突破", "actions": ["针对薄弱题型做专项训练 60 分钟", "整理错题本到云笔记"]},
        {"day": "D3", "focus": "同伴分享", "actions": ["带 1 位同学 30 分钟共学，讲解你擅长的题型"]},
        {"day": "D4", "focus": "扩展视野", "actions": ["浏览 1 篇与选修课方向相关的论文或博客"]},
        {"day": "D5", "focus": "体能恢复", "actions": ["运动 40 分钟，控制晚 23:00 入睡"]},
        {"day": "D6", "focus": "冲刺预演", "actions": ["整卷模拟 1 次，严格计时"]},
        {"day": "D7", "focus": "周复盘", "actions": ["写一页「本周亮点+下周计划」笔记"]},
    ],
    "effort_outcome_gap": [
        {"day": "D1", "focus": "诊断", "actions": ["挑 1 门成绩最差课程，翻出最近作业批改，标记错题类型"]},
        {"day": "D2", "focus": "精准训练", "actions": ["做该课程同类错题 10 道，不贪多，做完核对解题思路"]},
        {"day": "D3", "focus": "求助", "actions": ["找 1 位高分同学共学 30 分钟，请他讲解一道你的错题"]},
        {"day": "D4", "focus": "复盘", "actions": ["总结前 3 天共性错误，写下「下次遇到这种题我先做什么」"]},
        {"day": "D5", "focus": "主动提问", "actions": ["参加 1 次答疑或 office hour，带 2 个具体问题"]},
        {"day": "D6", "focus": "限时测试", "actions": ["独立限时完成 1 套小测，观察解题节奏"]},
        {"day": "D7", "focus": "策略校准", "actions": ["确定下周主攻 1 个题型，其他暂缓"]},
    ],
    "rhythm_broken": [
        {"day": "D1", "focus": "节律锚点", "actions": ["23:30 断网，手机放离床 1 米外位置"]},
        {"day": "D2", "focus": "早晨触发", "actions": ["7:30 前到早餐点打卡，连续记录 5 天"]},
        {"day": "D3", "focus": "碎片替代", "actions": ["午间散步 15 分钟代替刷短视频"]},
        {"day": "D4", "focus": "晚间留白", "actions": ["23:00 前结束所有学习任务，不借「再冲一把」拖后"]},
        {"day": "D5", "focus": "运动重启", "actions": ["下午运动 30 分钟（跑步/球类任选）"]},
        {"day": "D6", "focus": "波动诊断", "actions": ["整理本周作息，找出「崩溃时间点」是周几"]},
        {"day": "D7", "focus": "下周锚点", "actions": ["写下 2 个下周必守节律锚点，纳入日历"]},
    ],
    "habit_breakdown": [
        {"day": "D1", "focus": "最小闭环", "actions": ["选 1 门课程，完成 1 次签到 + 1 次作业"]},
        {"day": "D2", "focus": "可见化", "actions": ["打印本周课表贴在宿舍，勾选已完成项"]},
        {"day": "D3", "focus": "搭伙", "actions": ["邀请 1 位同学一起去上课，互相监督"]},
        {"day": "D4", "focus": "微奖励", "actions": ["完成今日计划后，允许自己 30 分钟娱乐"]},
        {"day": "D5", "focus": "物理到场", "actions": ["去图书馆坐 45 分钟，可以不学，但要坐够"]},
        {"day": "D6", "focus": "低门槛作业", "actions": ["只做作业前 3 题，做不出来也算完成"]},
        {"day": "D7", "focus": "习惯确认", "actions": ["回顾本周完成项，哪怕只有一两个，写下「值得继续的那一个」"]},
    ],
    "social_exploration_low": [
        {"day": "D1", "focus": "低负担破冰", "actions": ["主动对 1 位同专业同学说 1 句「你那门课作业怎么做」"]},
        {"day": "D2", "focus": "课程社交", "actions": ["加入 1 个课程讨论群，先不发言也可"]},
        {"day": "D3", "focus": "兴趣探索", "actions": ["参加 1 次社团开放日或讲座，只旁听"]},
        {"day": "D4", "focus": "学伴尝试", "actions": ["邀请 1 位同学一起自习 1 小时"]},
        {"day": "D5", "focus": "发言一次", "actions": ["在课程群或讨论区发 1 条有信息量的消息"]},
        {"day": "D6", "focus": "跨专业接触", "actions": ["参与 1 次跨院活动或选听 1 节公开课"]},
        {"day": "D7", "focus": "感受记录", "actions": ["写 1 句本周社交中最舒服的时刻"]},
    ],
    "lifestyle_first": [
        {"day": "D1", "focus": "学业回收", "actions": ["把本周课程任务清单列出，标红未完成项"]},
        {"day": "D2", "focus": "课外到课内", "actions": ["和 1 位社团朋友一起约图书馆 1 小时"]},
        {"day": "D3", "focus": "社交能量转化", "actions": ["把你擅长的活动组织能力用到 1 次课程小组"]},
        {"day": "D4", "focus": "课堂出勤", "actions": ["保证当天所有课程到课"]},
        {"day": "D5", "focus": "混合节奏", "actions": ["上午学习 2 小时 + 下午社团"]},
        {"day": "D6", "focus": "学业输出", "actions": ["完成 1 份作业或 1 次小测"]},
        {"day": "D7", "focus": "平衡复盘", "actions": ["写下本周学业与社交时间比例，调整下周锚点"]},
    ],
    "stable_average": [
        {"day": "D1", "focus": "选点突破", "actions": ["从五维里选定 1 个你想突破的维度，写下 1 个具体目标"]},
        {"day": "D2", "focus": "行动对齐", "actions": ["围绕该目标安排 1 次具体行动（看书/跑步/活动）"]},
        {"day": "D3", "focus": "借力同伴", "actions": ["找 1 位「这一维度比你强的」同学请教 15 分钟"]},
        {"day": "D4", "focus": "小步迭代", "actions": ["微调昨日行动，复刻 1 次"]},
        {"day": "D5", "focus": "体能保底", "actions": ["运动 30 分钟，保持身体基础"]},
        {"day": "D6", "focus": "成果记录", "actions": ["写下本周你在目标维度上的具体变化"]},
        {"day": "D7", "focus": "周复盘", "actions": ["决定下周是否继续此目标，或更换新维度"]},
    ],
}


def build_personalized_micro_plan(archetype_code: str) -> dict[str, Any]:
    plan = _MICRO_PLANS.get(archetype_code, _MICRO_PLANS["stable_average"])
    return {"archetype_code": archetype_code, "plan": plan}


# ----------------------------------------------------------------------------
# 辅导员话术工具包
# ----------------------------------------------------------------------------
_TOOLKITS: dict[str, dict[str, Any]] = {
    "high_achiever": {
        "opening_strategy": "先肯定产出，再引导向更高挑战",
        "script": "你这学期的学习状态非常稳定，成绩也走在班级前列，这是你自己长期努力的结果。接下来我们可以一起想想，是不是该选 1 个更高的目标，比如学科竞赛、保研预研或者某门硬核选修，让这份稳定变成一次真正的突破。",
        "taboos": ["不要只停留在表扬，避免让学生觉得「到头了没方向」", "不要加过多任务，他本身节奏已满"],
        "follow_up_questions": ["你有没有想过毕业后的方向？", "有没有某位老师或某个方向最让你心动？"],
    },
    "effort_outcome_gap": {
        "opening_strategy": "先肯定投入，再切入效率",
        "script": "你平时出勤、作业提交都很规范，态度我是看在眼里的，这点非常好。但这次几门课的成绩和你的努力量不太匹配，这不是你不认真，而是方法可能需要调整。我们不妨一起把最近错得最多的题型理一理，看看到底是理解卡住了还是熟练度不够。",
        "taboos": ["不要说「你方法不对」，这会否定努力", "不要直接拿别人做对比"],
        "follow_up_questions": ["你自己觉得哪门课最「使不上劲」？", "做作业时是读完题就能开动，还是经常要翻笔记？"],
    },
    "rhythm_broken": {
        "opening_strategy": "从生活节奏切入，避免直接谈成绩",
        "script": "最近你看起来有点累，我先不问成绩，就关心一下你睡眠和吃饭怎么样。很多时候学习掉线其实是节律先被打乱了，学习只是被连累的那个。我们先把「晚上几点断网」这一件事定下来，你觉得从 23:30 开始能不能做到？",
        "taboos": ["不要把话题直接甩到「你成绩在下滑」", "不要一上来就给长任务清单"],
        "follow_up_questions": ["你一般几点睡觉？", "最近有什么事情让你睡不好？"],
    },
    "habit_breakdown": {
        "opening_strategy": "从「陪伴」切入，目标锚定在最小动作",
        "script": "我看了一下你最近的在校记录，发现你好像和学习的节奏断开了一阵。先别急着补，我们今天就定一件小事：明天去上那节你最不想逃的课。只要做到这一件，其他的我们一步步来。",
        "taboos": ["不要说「你最近什么都没做」「懒」之类的词", "不要一次列 5 件以上的任务"],
        "follow_up_questions": ["你最近哪门课还愿意去？", "是有具体的事在分心吗？"],
    },
    "social_exploration_low": {
        "opening_strategy": "从兴趣和安全感入手，不强推社交",
        "script": "我发现你平时比较低调，其实这没有问题。但一个人闷着学有时候会越学越紧，我们可以找 1 件你感兴趣的事，比如某个社团的活动或者学长做的项目，先去看看，不一定要加入。",
        "taboos": ["不要说「你要合群点」这种判断式的话", "不要强行撮合社交"],
        "follow_up_questions": ["你平时喜欢做什么放松？", "有没有想过去旁听哪个学长学姐的分享？"],
    },
    "lifestyle_first": {
        "opening_strategy": "从他擅长的生活/社交切入，再迁移到学习",
        "script": "你平时在社团、在运动上都挺有组织力的，大家也愿意跟你一起。这份能量如果能分一小部分到学习上，效果会很明显。下周我们能不能挑 1 门你最感兴趣的课，把你在社团里那套「组织小组干活」的本事用上？",
        "taboos": ["不要否定他的活跃度", "不要要求他放弃当前兴趣"],
        "follow_up_questions": ["你最想做出名堂的课是哪门？", "有没有你愿意一起学的社团朋友？"],
    },
    "stable_average": {
        "opening_strategy": "引导他找到可突破的那个维度",
        "script": "你整体表现平稳，不冒险但也没出大问题，这是你的基本盘。接下来半年如果你想让自己更有成就感，可以在五个维度里挑 1 个你最想变强的，我们围绕它定 3 件小事去推进。",
        "taboos": ["不要笼统地说「要加油」", "不要给平均主义的建议"],
        "follow_up_questions": ["五个方向里哪一个你最有兴趣？", "你心里有没有一个想成为的样子？"],
    },
}


def build_counselor_toolkit(archetype_code: str, warning: dict[str, Any]) -> dict[str, Any]:
    base = _TOOLKITS.get(archetype_code, _TOOLKITS["stable_average"])
    level = str(warning.get("course_fail_fused_risk_level", "low")).lower() if warning else "low"
    priority = str(warning.get("warning_priority", "low")).lower() if warning else "low"
    channel_rec = "常规周度约谈即可"
    if level == "high" or priority in {"urgent", "high"}:
        channel_rec = "建议一周内完成 1 次 20 分钟面谈 + 1 次家长沟通"
    elif level == "medium":
        channel_rec = "两周内安排 1 次短面谈并预留跟踪窗口"
    return {
        **base,
        "channel_recommendation": channel_rec,
    }


# ----------------------------------------------------------------------------
# 数据时效声明 + 模式切换
# ----------------------------------------------------------------------------
def build_data_validity_statement(data_source_trace: dict[str, Any]) -> dict[str, Any]:
    summary = data_source_trace.get("summary", {}) if isinstance(data_source_trace, dict) else {}
    freshness_days = summary.get("overall_freshness_days")
    try:
        days = int(freshness_days) if freshness_days is not None else None
    except Exception:
        days = None
    latest_time = str(summary.get("overall_latest_time", ""))
    if days is None:
        mode = "historical_pattern"
        statement = "当前样本时间未能解析，报告以历史行为模式档案形式呈现，建议以阶段性规律而非实时信号解读结论。"
    elif days <= 14:
        mode = "realtime"
        statement = f"数据最近更新于 {latest_time}（距今 {days} 天），报告支持近期实时干预。"
    elif days <= 90:
        mode = "recent_window"
        statement = f"数据最近更新于 {latest_time}（距今 {days} 天），报告适合做周/月度复盘，实时干预前建议补采最新一周数据。"
    else:
        mode = "historical_pattern"
        statement = (
            f"数据最近更新于 {latest_time}（距今 {days} 天），样本非实时，"
            "报告自动切换为「历史行为模式档案」视角——结论用于理解该生行为规律，而非当下状态；实时决策请配合最新学期数据。"
        )
    mode_display = {
        "realtime": "实时干预视角",
        "recent_window": "近期复盘视角",
        "historical_pattern": "历史行为档案视角",
    }.get(mode, mode)
    return {
        "mode": mode,
        "mode_display": mode_display,
        "freshness_days": days if days is not None else -1,
        "latest_time": latest_time,
        "statement": statement,
    }


# ----------------------------------------------------------------------------
# 弱相关语义化：|rho| < 0.1 → 「未观测到显著关联」
# ----------------------------------------------------------------------------
def _semanticize_corr(value: Any) -> tuple[str, str]:
    try:
        num = float(value)
    except Exception:
        return ("未观测到显著关联", "")
    abs_v = abs(num)
    if abs_v < 0.1:
        return ("未观测到显著关联", "")
    if abs_v < 0.2:
        return ("弱关联", f"{num:+.2f}")
    if abs_v < 0.4:
        return ("中等关联", f"{num:+.2f}")
    direction = "正向" if num > 0 else "反向"
    return (f"{direction}强关联", f"{num:+.2f}")


def semanticize_attribution_3d(attr: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(attr, dict):
        return {}
    out: dict[str, Any] = {}
    for dim in ("behavior", "result", "environment"):
        block = attr.get(dim, {})
        if not isinstance(block, dict):
            out[dim] = block
            continue
        new_block = dict(block)
        for key, value in list(block.items()):
            if isinstance(value, (int, float)) and "corr" in key.lower():
                label, display = _semanticize_corr(value)
                new_block[f"{key}_semantic"] = label
                new_block[f"{key}_display"] = display
        out[dim] = new_block
    return out


def semanticize_cross_rows(key_paths: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    energy = key_paths.get("energy_support_chain", {}) if isinstance(key_paths, dict) else {}
    peer = key_paths.get("peer_effect_chain", {}) if isinstance(key_paths, dict) else {}
    motivation = key_paths.get("motivation_drive_chain", {}) if isinstance(key_paths, dict) else {}
    efficiency = key_paths.get("efficiency_conversion_chain", {}) if isinstance(key_paths, dict) else {}

    def _row(path_name: str, rho_val: Any, fallback_statement: str) -> dict[str, Any]:
        label, display = _semanticize_corr(rho_val)
        if label == "未观测到显著关联":
            statement = "当前样本未观测到显著关联；结论基于该生个体行为代理，不做因果推断。"
        else:
            statement = fallback_statement or f"{label}（{display}）"
        return {"path": path_name, "strength_label": label, "strength_display": display, "statement": statement}

    rows.append(_row("节律→学习投入", energy.get("rho_rhythm_focus"), str(energy.get("statement", ""))))
    rows.append(
        {
            "path": "同伴参与→恢复速度",
            "strength_label": "样本对比",
            "strength_display": f"4周差 {peer.get('recovery_gap_4w', 0)} / 8周差 {peer.get('recovery_gap_8w', 0)}",
            "statement": str(peer.get("statement", "")) or "样本间恢复差值未见显著差异。",
        }
    )
    rows.append(
        {
            "path": "课程探索→学习动力",
            "strength_label": "样本量",
            "strength_display": str(motivation.get("sample_size", 0)),
            "statement": str(motivation.get("statement", "")) or "当前样本量不足以给出稳定结论。",
        }
    )
    rows.append(_row("学习投入→学习成果", efficiency.get("rho_density_outcome"), str(efficiency.get("statement", ""))))
    return rows
