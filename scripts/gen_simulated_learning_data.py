"""
为 A3 个性化学习系统生成 simulated_learning_data.json
- 10 个学生 × 30 天 (2026-06-01 ~ 2026-06-30)
- 学霸 / 普通 / 挣扎 三种类型
- 包含 daily_records / mastery_by_kp / mistake_history / learning_streak / summary_stats
"""
import json
import random
from datetime import date, timedelta
from collections import defaultdict

random.seed(20260708)

# 20 个知识点 (来自 chapter frontmatter 中的 kp_ids)
KP_POOL = [
    "transformer", "attention", "rag", "multi_agent", "cnn", "rnn",
    "nlp_basics", "mcp_protocol", "ai_agent", "multimodal_llm",
    "neural_networks", "supervised_learning", "unsupervised_learning",
    "decision_trees", "svm", "backpropagation", "ml_fundamentals",
    "math_foundations", "reinforcement_learning", "ai_overview"
]

# 中文 kp 名映射
KP_NAME = {
    "transformer": "Transformer", "attention": "注意力机制", "rag": "检索增强生成",
    "multi_agent": "多智能体系统", "cnn": "卷积神经网络", "rnn": "循环神经网络",
    "nlp_basics": "自然语言处理基础", "mcp_protocol": "MCP 模型上下文协议",
    "ai_agent": "AI Agent 智能体", "multimodal_llm": "多模态大模型",
    "neural_networks": "神经网络基础", "supervised_learning": "监督学习",
    "unsupervised_learning": "无监督学习", "decision_trees": "决策树与集成",
    "svm": "支持向量机", "backpropagation": "反向传播",
    "ml_fundamentals": "机器学习基础", "math_foundations": "数学基础",
    "reinforcement_learning": "强化学习", "ai_overview": "AI 概览"
}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 10 个学生画像
STUDENTS_DEF = [
    ("demo-student-1", "小明", "视觉型",   "中等",  "中等", 0.72, 28),  # 目标学生,中等偏上
    ("demo-student-2", "学霸小张", "视觉型", "快",   "高",   0.88, 30),
    ("demo-student-3", "努力小王", "读写型", "中等", "极高", 0.75, 30),
    ("demo-student-4", "聪明小李", "听觉型", "快",   "高",   0.85, 29),
    ("demo-student-5", "普通小陈", "视觉型", "中等", "中等", 0.65, 26),
    ("demo-student-6", "进步小赵", "动觉型", "中等", "高",   0.70, 28),
    ("demo-student-7", "挣扎小周", "视觉型", "慢",   "低",   0.45, 22),
    ("demo-student-8", "黑马小吴", "读写型", "中等", "中等", 0.55, 25),
    ("demo-student-9", "稳健小郑", "视觉型", "中等", "高",   0.68, 27),
    ("demo-student-10","学渣小钱", "听觉型", "慢",   "低",   0.42, 18),
]

# 学生类型 → (duration 区间, correct 区间)
TYPE_PROFILE = {
    "学霸": (60, 95, 0.80, 0.95),
    "普通": (30, 65, 0.58, 0.78),
    "挣扎": (15, 45, 0.38, 0.62),
}

def get_type(correct_rate):
    if correct_rate >= 0.80:
        return "学霸"
    if correct_rate >= 0.60:
        return "普通"
    return "挣扎"

RESOURCE_POOL = ["video", "ppt", "article", "code", "mindmap", "audio", "quiz"]
RESOURCE_TYPE_NAME = {
    "video": "视频", "ppt": "PPT", "article": "文章",
    "code": "代码", "mindmap": "思维导图", "audio": "音频", "quiz": "测验"
}

ERROR_TYPES = ["概念误解", "计算错误", "审题不清", "粗心", "公式记错"]

def gen_resources(num=2):
    types = random.sample(RESOURCE_POOL, min(num, len(RESOURCE_POOL)))
    out = []
    for t in types:
        rid = f"r-{random.randint(100, 999)}"
        if t == "video":
            out.append({"type": t, "id": rid, "duration": random.randint(8, 25)})
        elif t == "ppt":
            out.append({"type": t, "id": rid, "pages_viewed": random.randint(6, 20)})
        else:
            out.append({"type": t, "id": rid})
    return out

def gen_kp_studied(num):
    return random.sample(KP_POOL, num)

def gen_day_record(d, stype, target_rate, kp_progress):
    """生成一天学习记录"""
    dur_min, dur_max, rate_min, rate_max = TYPE_PROFILE[stype]
    duration = random.randint(dur_min, dur_max)
    if d.weekday() >= 5:  # 周末可能更长
        duration = int(duration * random.uniform(1.0, 1.3))
    sessions = random.randint(1, 3)
    kps = gen_kp_studied(random.randint(2, 4))
    resources = gen_resources(random.randint(2, 3))
    questions = random.randint(5, 15)
    correct = max(0, min(questions, int(questions * random.uniform(rate_min, rate_max))))
    correct_rate = round(correct / questions, 2) if questions else 0
    new_mistakes = max(0, questions - correct - random.randint(0, 2))
    reviewed = random.randint(0, 3) if d.day > 5 else 0
    return {
        "date": d.strftime("%Y-%m-%d"),
        "weekday": WEEKDAY_CN[d.weekday()],
        "duration_minutes": duration,
        "sessions_count": sessions,
        "kp_studied": kps,
        "resources_accessed": resources,
        "questions_attempted": questions,
        "correct_count": correct,
        "correct_rate": correct_rate,
        "new_mistakes": new_mistakes,
        "reviewed_mistakes": reviewed,
    }

def gen_mastery(stype, covered_kps):
    """生成各知识点掌握度"""
    mastery = {}
    for kp in covered_kps:
        initial = round(random.uniform(0.05, 0.25), 2)
        if stype == "学霸":
            current = round(min(0.95, initial + random.uniform(0.4, 0.7)), 2)
        elif stype == "普通":
            current = round(min(0.85, initial + random.uniform(0.25, 0.55)), 2)
        else:
            current = round(min(0.70, initial + random.uniform(0.10, 0.35)), 2)
        trend = "improving" if current - initial > 0.15 else ("stable" if current - initial > 0.05 else "declining")
        mastery[kp] = {
            "current": current,
            "initial": initial,
            "trend": trend,
            "last_updated": "2026-06-30"
        }
    return mastery

def gen_mistakes(stype, covered_kps, num_mistakes):
    """生成错题历史"""
    mistakes = []
    for i in range(num_mistakes):
        kp = random.choice(covered_kps)
        q_id = f"q-{kp}-" + str(random.randint(0, 9)).zfill(2)
        wrong_count = random.randint(1, 4)
        review_count = random.randint(0, wrong_count) if wrong_count > 1 else 0
        is_resolved = review_count >= wrong_count and random.random() < 0.5
        first_day = random.randint(1, 20)
        first_wrong = date(2026, 6, first_day)
        if review_count > 0:
            last_review_day = min(30, first_day + random.randint(2, 15))
            last_review = f"2026-06-{last_review_day:02d}"
        else:
            last_review = None
        correct_ans = random.choice(["A", "B", "C", "D"])
        wrong_ans = random.choice([x for x in ["A", "B", "C", "D"] if x != correct_ans])
        similar = [f"q-{kp}-" + str(random.randint(0, 9)).zfill(2) for _ in range(random.randint(1, 3))]
        m = {
            "mistake_id": f"m-{i+1:04d}",
            "question_id": q_id,
            "kp_id": kp,
            "kp_name": KP_NAME[kp],
            "wrong_answer": wrong_ans,
            "correct_answer": correct_ans,
            "error_type": random.choice(ERROR_TYPES),
            "error_detail": f"在 {KP_NAME[kp]} 知识点上出现 {random.choice(ERROR_TYPES)},影响理解",
            "first_wrong_at": f"{first_wrong.isoformat()}T{random.randint(8,22):02d}:{random.randint(0,59):02d}:00",
            "wrong_count": wrong_count,
            "review_count": review_count,
            "last_review_at": last_review,
            "is_resolved": is_resolved,
            "similar_questions": similar
        }
        mistakes.append(m)
    return mistakes

def gen_streak(daily_records):
    """根据 daily_records 算连续学习天数"""
    study_days = {r["date"] for r in daily_records}
    cur = 0
    max_s = 0
    d = date(2026, 6, 30)
    while d.strftime("%Y-%m-%d") in study_days:
        cur += 1
        d -= timedelta(days=1)
    # 算 max_streak
    sorted_days = sorted(study_days)
    if not sorted_days:
        return 0, 0, "2026-06-30"
    max_s = 1
    run = 1
    for i in range(1, len(sorted_days)):
        prev = date.fromisoformat(sorted_days[i-1])
        cur_d = date.fromisoformat(sorted_days[i])
        if (cur_d - prev).days == 1:
            run += 1
            max_s = max(max_s, run)
        else:
            run = 1
    last_study = sorted_days[-1]
    return cur, max_s, last_study

def gen_summary(daily_records, mastery, stype):
    total_minutes = sum(r["duration_minutes"] for r in daily_records)
    total_questions = sum(r["questions_attempted"] for r in daily_records)
    total_correct = sum(r["correct_count"] for r in daily_records)
    overall_rate = round(total_correct / total_questions, 2) if total_questions else 0
    mastered = sum(1 for v in mastery.values() if v["current"] >= 0.75)
    weak = sum(1 for v in mastery.values() if v["current"] < 0.5)
    learning = len(mastery) - mastered - weak
    return {
        "total_study_minutes": total_minutes,
        "total_questions": total_questions,
        "overall_correct_rate": overall_rate,
        "mastered_kps": mastered,
        "learning_kps": learning,
        "weak_kps": weak
    }

def gen_student(sid, nickname, style, pace, consistency, target_rate, study_days_target):
    stype = get_type(target_rate)
    # 选择 8-12 个覆盖的知识点
    n_kp = random.randint(8, 12)
    covered = random.sample(KP_POOL, n_kp)
    # 30 天记录 (可能某些天没学习,挣扎型缺失更多)
    daily = []
    skip_prob = {"学霸": 0.0, "普通": 0.05, "挣扎": 0.18}[stype]
    for i in range(30):
        d = date(2026, 6, 1) + timedelta(days=i)
        if random.random() < skip_prob:
            continue
        daily.append(gen_day_record(d, stype, target_rate, covered))
    # 错题数
    n_mistakes = {"学霸": random.randint(8, 16), "普通": random.randint(18, 32), "挣扎": random.randint(25, 45)}[stype]
    mistakes = gen_mistakes(stype, covered, n_mistakes)
    mastery = gen_mastery(stype, covered)
    cur, max_s, last = gen_streak(daily)
    summary = gen_summary(daily, mastery, stype)
    return {
        "student_id": sid,
        "nickname": nickname,
        "profile_summary": {
            "learning_style": style,
            "pace": pace,
            "consistency": consistency
        },
        "daily_records": daily,
        "mastery_by_kp": mastery,
        "mistake_history": mistakes,
        "learning_streak": {
            "current_streak": cur,
            "max_streak": max_s,
            "last_study_date": last
        },
        "summary_stats": summary
    }

# 生成所有学生
students = []
for sid, nick, style, pace, cons, rate, _ in STUDENTS_DEF:
    students.append(gen_student(sid, nick, style, pace, cons, rate, 30))

meta = {
    "_meta": {
        "version": "1.0",
        "generated_at": "2026-07-08",
        "student_count": len(students),
        "days": 30,
        "total_records": sum(len(s["daily_records"]) for s in students)
    },
    "students": students
}

with open(r"F:\比赛\中软杯\A3\data\simulated_learning_data.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print("Wrote simulated_learning_data.json")
print(f"  students: {len(students)}")
print(f"  total daily_records: {sum(len(s['daily_records']) for s in students)}")
print(f"  total mistakes: {sum(len(s['mistake_history']) for s in students)}")
