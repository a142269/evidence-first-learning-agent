"""
为 A3 生成 class_comparison_data.json
- 1 目标学生 (demo-student-1, 中等偏上) + 19 对比学生 = 20 人
- 包含 rankings / kp_percentiles / class_stats / top_performers / all_students
"""
import json
import random
from collections import defaultdict

random.seed(20260708)

# 20 个学生 (含目标学生 demo-student-1)
NAMES = [
    ("demo-student-1",  "小明",       0.78, 1500, 0.80, 29, 12),  # 目标学生,中等偏上(掌握度 0.78,学时 1500)
    ("demo-student-2",  "学霸小张",   0.93, 1720, 0.92, 30, 19),
    ("demo-student-3",  "努力小王",   0.88, 1500, 0.85, 30, 17),
    ("demo-student-4",  "聪明小李",   0.85, 1300, 0.86, 29, 16),
    ("demo-student-5",  "普通小陈",   0.64, 980,  0.67, 26, 9),
    ("demo-student-6",  "进步小赵",   0.72, 1180, 0.75, 28, 11),
    ("demo-student-7",  "挣扎小周",   0.44, 480,  0.50, 22, 5),
    ("demo-student-8",  "黑马小吴",   0.55, 850,  0.61, 25, 7),
    ("demo-student-9",  "稳健小郑",   0.68, 1020, 0.70, 27, 10),
    ("demo-student-10", "学渣小钱",   0.40, 400,  0.46, 18, 4),
    ("demo-student-11", "勤奋小孙",   0.79, 1320, 0.78, 28, 13),
    ("demo-student-12", "内敛小周",   0.62, 760,  0.66, 25, 8),
    ("demo-student-13", "高效小吴",   0.81, 950,  0.84, 24, 12),
    ("demo-student-14", "踏实小郑",   0.75, 1410, 0.77, 29, 12),
    ("demo-student-15", "随意小冯",   0.58, 600,  0.60, 20, 6),
    ("demo-student-16", "细品小陈",   0.77, 1200, 0.79, 27, 11),
    ("demo-student-17", "新秀小褚",   0.66, 1080, 0.69, 26, 9),
    ("demo-student-18", "老练小卫",   0.82, 1280, 0.83, 28, 14),
    ("demo-student-19", "稳重小蒋",   0.72, 1120, 0.73, 27, 10),
    ("demo-student-20", "开窍小沈",   0.60, 850,  0.63, 23, 7),
]

# 知识点百分位 (目标学生 demo-student-1)
# 2-3 个优势 (排名前 30% → 百分位 ≥ 70)
# 2-3 个薄弱 (排名后 40% → 百分位 ≤ 40)
# 其他中等 (40-70)
KP_PERCENTILES_TARGET = {
    "transformer": 85,        # 优势
    "attention":   78,        # 优势
    "cnn":         70,        # 中等偏上
    "rag":         45,        # 薄弱
    "multi_agent": 60,        # 中等
    "ai_agent":    55,        # 中等
    "mcp_protocol":32,        # 薄弱
    "nlp_basics":  68,        # 中等
    "multimodal_llm":62,      # 中等
    "neural_networks":72,     # 优势
    "backpropagation":50,     # 中等
    "reinforcement_learning": 38,  # 薄弱
}

def percentile_to_rank(pct, total=20):
    """百分位 → 排名 (1-indexed)"""
    if pct >= 99: return 1
    if pct <= 1:  return total
    return max(1, round(total * (1 - pct/100)))

# 计算 all_students
all_students = []
for sid, nick, mastery, study_min, correct_rate, study_days, mastered_kps in NAMES:
    all_students.append({
        "student_id": sid,
        "nickname": nick,
        "study_minutes": study_min,
        "mastery_avg": round(mastery, 2),
        "correct_rate": round(correct_rate, 2),
        "study_days": study_days,
        "mastered_kps": mastered_kps
    })

# 排名计算
def rank_by(key, reverse=True):
    sorted_s = sorted(all_students, key=lambda x: x[key], reverse=reverse)
    ranks = {}
    for i, s in enumerate(sorted_s):
        ranks[s["student_id"]] = i + 1
    return ranks, sorted_s

rank_mastery, sorted_by_mastery = rank_by("mastery_avg")
rank_study, sorted_by_study = rank_by("study_minutes")
rank_correct, sorted_by_correct = rank_by("correct_rate")
rank_days, sorted_by_days = rank_by("study_days")

# 综合排名:加权 (mastery 0.4 + study 0.2 + correct 0.3 + days 0.1)
def composite(s):
    s["composite_score"] = (
        s["mastery_avg"] * 0.4
        + (s["study_minutes"] / 1700) * 0.2
        + s["correct_rate"] * 0.3
        + (s["study_days"] / 30) * 0.1
    )
    return s
all_students_scored = sorted([composite(s) for s in all_students], key=lambda x: x["composite_score"], reverse=True)
rank_overall = {s["student_id"]: i+1 for i, s in enumerate(all_students_scored)}

def percentile_from_rank(rank, total=20):
    """排名 → 百分位 (rank 1 → 95, rank 20 → 5)"""
    return round((1 - (rank-1)/total) * 100) if total > 1 else 50

target = all_students[0]
ts = {
    "student_id": target["student_id"],
    "nickname": target["nickname"],
    "rankings": {
        "overall": {
            "rank": rank_overall[target["student_id"]],
            "total": 20,
            "percentile": percentile_from_rank(rank_overall[target["student_id"]])
        },
        "study_time": {
            "rank": rank_study[target["student_id"]],
            "total": 20,
            "percentile": percentile_from_rank(rank_study[target["student_id"]]),
            "value": target["study_minutes"],
            "unit": "分钟"
        },
        "mastery": {
            "rank": rank_mastery[target["student_id"]],
            "total": 20,
            "percentile": percentile_from_rank(rank_mastery[target["student_id"]]),
            "value": target["mastery_avg"],
            "unit": "平均掌握度"
        },
        "correct_rate": {
            "rank": rank_correct[target["student_id"]],
            "total": 20,
            "percentile": percentile_from_rank(rank_correct[target["student_id"]]),
            "value": target["correct_rate"],
            "unit": "正确率"
        },
        "consistency": {
            "rank": rank_days[target["student_id"]],
            "total": 20,
            "percentile": percentile_from_rank(rank_days[target["student_id"]]),
            "value": target["study_days"],
            "unit": "学习天数"
        }
    },
    "kp_percentiles": KP_PERCENTILES_TARGET
}

# 班级统计
total_students = len(all_students)
avg_study = round(sum(s["study_minutes"] for s in all_students) / total_students, 1)
avg_mastery = round(sum(s["mastery_avg"] for s in all_students) / total_students, 2)
avg_correct = round(sum(s["correct_rate"] for s in all_students) / total_students, 2)
avg_days = round(sum(s["study_days"] for s in all_students) / total_students, 1)

# 分布
excellent = sum(1 for s in all_students if s["mastery_avg"] >= 0.85)
good = sum(1 for s in all_students if 0.75 <= s["mastery_avg"] < 0.85)
average = sum(1 for s in all_students if 0.60 <= s["mastery_avg"] < 0.75)
below = sum(1 for s in all_students if s["mastery_avg"] < 0.60)

class_stats = {
    "avg_study_minutes": avg_study,
    "avg_mastery": avg_mastery,
    "avg_correct_rate": avg_correct,
    "avg_study_days": avg_days,
    "distribution": {
        "excellent": excellent,
        "good": good,
        "average": average,
        "below_average": below
    }
}

# Top 3
AVATARS = ["🥇", "🥈", "🥉"]
top_performers = []
for i, s in enumerate(all_students_scored[:3]):
    top_performers.append({
        "rank": i+1,
        "nickname": s["nickname"],
        "avatar": AVATARS[i],
        "mastery": s["mastery_avg"],
        "study_time": s["study_minutes"]
    })

result = {
    "_meta": {
        "version": "1.0",
        "class_id": "class-ai-2026",
        "total_students": 20,
        "generated_at": "2026-07-08"
    },
    "target_student": ts,
    "class_stats": class_stats,
    "top_performers": top_performers,
    "all_students": all_students
}

with open(r"F:\比赛\中软杯\A3\data\class_comparison_data.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("Wrote class_comparison_data.json")
print(f"  target_student rank_overall: {ts['rankings']['overall']['rank']}")
print(f"  target mastery: {ts['rankings']['mastery']['value']} rank {ts['rankings']['mastery']['rank']}")
print(f"  target study: {ts['rankings']['study_time']['value']} min rank {ts['rankings']['study_time']['rank']}")
print(f"  class avg mastery: {avg_mastery}, distribution: {class_stats['distribution']}")
print(f"  top 3: {[t['nickname'] for t in top_performers]}")
