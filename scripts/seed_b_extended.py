#!/usr/bin/env python3
"""
B 侧演示扩展种子：错题本 + 游戏化 + 30 天 BKT 历史轨迹

v7 Day 4 要求：演示数据让 30 天 BKT 预测曲线有真实形状。
A 的 seed_extended.json 覆盖了 5 学生 + 20 KP + 30 KG 边 + 94 答题 + 算法初始状态，
但缺：
  - 错题本记录（MistakeRecord）— 让 /mistakes/heatmap 有数据
  - 游戏化档案（GamificationProfileRecord）— 让 /gamification 有数据
  - 30 天 BKT 历史轨迹 — 让 /cognitive/forecast 曲线有真实形状

本脚本幂等补充上述数据，依赖 seed_extended.json 已灌入的 5 学生 + 20 KP。

用法:
    python scripts/seed_b_extended.py             # 导入 B 扩展
    python scripts/seed_b_extended.py --check     # 仅检查
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import configure_database, init_db, SessionLocal
from backend.app.core.models import (
    MistakeRecord,
    GamificationProfileRecord,
    BktStateRecord,
    KnowledgePointRecord,
)


# ── 错题本：每学生 4-6 条，覆盖 8 种错因 ──────────────────────────
MISTAKE_TEMPLATES = [
    {"question": "计算 3.14 × 2.5 的结果", "student_answer": "7.85", "correct_answer": "7.85",
     "error_type": "计算粗心", "analysis": "数值正确但格式未保留小数位"},
    {"question": "什么是梯度消失？", "student_answer": "", "correct_answer": "深层网络中梯度趋近于零",
     "error_type": "知识缺漏", "analysis": "未作答，概念掌握不足"},
    {"question": "CNN 的池化层作用", "student_answer": "增加特征图数量", "correct_answer": "降维+平移不变性",
     "error_type": "概念混淆", "analysis": "混淆了池化与卷积的作用"},
    {"question": "求导 f(x)=x²sin(x)", "student_answer": "2x·cos(x)", "correct_answer": "2x·sin(x)+x²·cos(x)",
     "error_type": "计算失误", "analysis": "漏了乘积法则第二项"},
    {"question": "题干：下列哪个不是过拟合的表现（选非题）", "student_answer": "训练集准确率高",
     "correct_answer": "测试集准确率高", "error_type": "审题不清", "analysis": "忽略了'选非'要求"},
    {"question": "用 Python 实现快速排序", "student_answer": "sorted(arr)",
     "correct_answer": "手写 partition + 递归", "error_type": "方法选择错", "analysis": "直接调库未体现算法"},
    {"question": "解释 BatchNorm 的原理", "student_answer": "归一化", "correct_answer": "对每 batch 做零均值单位方差+可学习缩放平移",
     "error_type": "概念边界混淆", "analysis": "仅说'归一化'过于笼统"},
    {"question": "阅读以下代码后输出结果", "student_answer": "[1,2,3]", "correct_answer": "[3,2,1]",
     "error_type": "阅读理解", "analysis": "未注意 reverse=True 参数"},
]

# ── 游戏化：5 学生差异化档案 ──────────────────────────────────────
GAMIFICATION_PROFILES = [
    {"user_id": "demo-student-1", "xp": 2850, "level": 12, "streak_days": 23,
     "achievements": ["七日连续打卡", "Python入门通关", "ML概念达人", "首批探索者"]},
    {"user_id": "demo-student-2", "xp": 980, "level": 5, "streak_days": 4,
     "achievements": ["首次答题", "七日连续打卡"]},
    {"user_id": "demo-student-3", "xp": 4200, "level": 18, "streak_days": 67,
     "achievements": ["深度学习专家", "论文阅读者", "辩论高手", "百题斩", "坚持六十天"]},
    {"user_id": "demo-student-4", "xp": 1650, "level": 8, "streak_days": 12,
     "achievements": ["协作学习", "七日连续打卡", "错题本收集者"]},
    {"user_id": "demo-student-5", "xp": 2310, "level": 10, "streak_days": 18,
     "achievements": ["实操项目完成", "代码审查员", "七日连续打卡"]},
]


def _seed_mistakes(session_factory, stats: dict) -> None:
    """每学生灌入错题记录，幂等（按 mistake id 去重）。"""
    now = time.time()
    with session_factory() as db:
        kp_ids = [r.id for r in db.query(KnowledgePointRecord).all()]
        if not kp_ids:
            print("[seed-b-ext] 无知识点，跳过错题灌入（请先跑 seed_demo.py）")
            return
        for i, student in enumerate(GAMIFICATION_PROFILES):
            uid = student["user_id"]
            # 每学生 4-6 条错题，循环覆盖 8 种错因
            count = 4 + (i % 3)
            for j in range(count):
                tpl = MISTAKE_TEMPLATES[(i + j) % len(MISTAKE_TEMPLATES)]
                mid = f"seed-mistake-{uid}-{j}"
                if db.get(MistakeRecord, mid) is not None:
                    stats["skipped"] += 1
                    continue
                db.add(MistakeRecord(
                    id=mid,
                    user_id=uid,
                    knowledge_point_id=kp_ids[(i + j) % len(kp_ids)],
                    question_data={
                        "question": tpl["question"],
                        "student_answer": tpl["student_answer"],
                        "correct_answer": tpl["correct_answer"],
                    },
                    error_type=tpl["error_type"],
                    analysis=tpl["analysis"],
                    created_at=now - 86400 * (count - j),
                ))
                stats["mistakes"] += 1
        db.commit()


def _seed_gamification(session_factory, stats: dict) -> None:
    """灌入游戏化档案，幂等（按 user_id PK 去重）。"""
    with session_factory() as db:
        for prof in GAMIFICATION_PROFILES:
            uid = prof["user_id"]
            if db.get(GamificationProfileRecord, uid) is not None:
                stats["skipped"] += 1
                continue
            db.add(GamificationProfileRecord(
                user_id=uid,
                xp=prof["xp"],
                level=prof["level"],
                streak_days=prof["streak_days"],
                achievements=prof["achievements"],
            ))
            stats["gamification"] += 1
        db.commit()


def _seed_bkt_history(session_factory, stats: dict) -> None:
    """给已有 BKT 状态补 30 天历史轨迹，让预测曲线有真实形状。

    每条 BktStateRecord 的 history 字段追加 20 个时间点（过去 30 天），
    按 mastery 趋势生成 correct 序列（掌握度高的多答对）。
    """
    now = time.time()
    with session_factory() as db:
        records = db.query(BktStateRecord).all()
        for rec in records:
            if rec.history and len(rec.history) >= 15:
                stats["skipped"] += 1  # 已有充足历史，跳过
                continue
            mastery = rec.p_learned
            # 生成 20 个历史点：mastery 越高，正确率越高
            history = []
            for t in range(20):
                day_offset = 30 - t
                # 正确概率随时间递增（学习进步）
                p_correct = min(0.95, mastery * 0.7 + 0.1 * t / 20)
                correct = (hash((rec.user_id, rec.knowledge_point_id, t)) % 100) / 100 < p_correct
                history.append({
                    "day": -day_offset,
                    "correct": bool(correct),
                    "p_learned": round(max(0.05, min(0.95, mastery - 0.3 + 0.015 * t)), 3),
                })
            rec.history = history
            stats["bkt_history"] += 1
        db.commit()


def seed_b_extended(session_factory=None) -> dict:
    if session_factory is None:
        session_factory = SessionLocal
    stats = {
        "mistakes": 0, "gamification": 0, "bkt_history": 0, "skipped": 0,
    }
    _seed_mistakes(session_factory, stats)
    _seed_gamification(session_factory, stats)
    _seed_bkt_history(session_factory, stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="B 侧演示扩展种子")
    parser.add_argument("--check", action="store_true", help="仅检查")
    parser.add_argument("--db", default=None, help="数据库 URL")
    args = parser.parse_args()

    if args.db:
        configure_database(args.db)
    init_db()

    if args.check:
        with SessionLocal() as db:
            from backend.app.core.models import ProfileRecord
            students = db.query(ProfileRecord).count()
            mistakes = db.query(MistakeRecord).count()
            games = db.query(GamificationProfileRecord).count()
            bkt = db.query(BktStateRecord).count()
            bkt_with_history = sum(1 for r in db.query(BktStateRecord).all()
                                   if r.history and len(r.history) >= 15)
        print(f"[seed-b-ext] 学生 {students} / 错题 {mistakes} / 游戏化 {games} / "
              f"BKT {bkt}（含历史 {bkt_with_history}）")
        return

    stats = seed_b_extended()
    print(
        f"[seed-b/ext] 错题 {stats['mistakes']} / 游戏化 {stats['gamification']} / "
        f"BKT历史 {stats['bkt_history']} / 跳过 {stats['skipped']}"
    )

    # 幂等验证
    stats2 = seed_b_extended()
    for key in ("mistakes", "gamification", "bkt_history"):
        assert stats2[key] == 0, f"二次导入不应新增 {key}: {stats2}"
    print("[seed-b/ext] 幂等性验证通过 —— 二次导入零新增")


if __name__ == "__main__":
    main()
