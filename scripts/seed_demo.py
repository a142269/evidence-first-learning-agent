#!/usr/bin/env python3
"""
幂等种子数据导入脚本

* seed.json (B 拥有, 3 学生 baseline) → seed_database()
* seed_extended.json (A 拥有, 演示扩展) → seed_extended()
  额外补齐 2 学生 + 20 知识点 + 30 KG 边 + 94 答题 + BKT/DINA/SM-2 初始状态

重复运行安全：所有插入按 PK / UniqueConstraint / external_id 去重。

用法:
    python scripts/seed_demo.py                    # 导入 baseline + extended
    python scripts/seed_demo.py --check            # 仅检查数据库状态（不写入）
    python scripts/seed_demo.py --reset            # 先清空 B 拥有的表再导入
    python scripts/seed_demo.py --baseline-only    # 只跑 seed.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import configure_database, init_db, SessionLocal
from backend.app.core.models import (
    BktStateRecord,
    DinaStateRecord,
    KnowledgePointRecord,
    KnowledgeRelationRecord,
    Sm2ScheduleRecord,
)
from backend.app.repositories.profile_repo import ProfileRepository
from backend.app.repositories.path_repo import LearningPathRepository
from backend.app.repositories.assessment_repo import AssessmentRepository


SEED_PATH = PROJECT_ROOT / "data" / "seed.json"
SEED_EXTENDED_PATH = PROJECT_ROOT / "data" / "seed_extended.json"


def load_seed() -> dict:
    if not SEED_PATH.exists():
        print(f"[seed] 种子文件不存在: {SEED_PATH}")
        sys.exit(1)
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_database(session_factory=None, seed_path: str | None = None) -> dict:
    """幂等导入种子数据。返回统计信息。"""
    if session_factory is None:
        session_factory = SessionLocal

    profile_repo = ProfileRepository(session_factory)
    path_repo = LearningPathRepository(session_factory)
    assessment_repo = AssessmentRepository(session_factory)

    seed = load_seed() if seed_path is None else json.loads(
        Path(seed_path).read_text(encoding="utf-8")
    )

    stats = {"profiles": 0, "paths": 0, "assessments": 0, "skipped": 0}

    for student in seed.get("students", []):
        user_id = str(student["user_id"])

        # 画像：upsert 幂等
        existing_profile = profile_repo.get(user_id)
        if existing_profile:
            stats["skipped"] += 1
        else:
            profile_repo.upsert(user_id, student.get("profile", {}))
            stats["profiles"] += 1

        # 学习路径：如果已有同名路径则跳过
        for path in student.get("paths", []):
            existing = path_repo.get(str(path["id"]))
            if existing:
                stats["skipped"] += 1
                continue
            path.setdefault("created_at", time.time())
            path_repo.save(path)
            stats["paths"] += 1

        # 评估记录：使用 external_id 去重
        for i, assessment in enumerate(student.get("assessments", [])):
            external_id = f"seed-{user_id}-assessment-{i}"
            record = dict(assessment)
            record["timestamp"] = record.get("timestamp", time.time())
            record["external_id"] = external_id
            assessment_repo.add(user_id, record)
            stats["assessments"] += 1

    return stats


# ============================================================
# 扩展种子：A 拥有 —— 5 学生收口 / 20 KP / 30 KG 边 / 100 答题 / 算法初始状态
# ============================================================
_ASMT_TYPES_CYCLE = ("quiz", "quiz", "quiz", "resource_view", "question")


def _load_extended(seed_path: str | None) -> dict:
    path = Path(seed_path) if seed_path else SEED_EXTENDED_PATH
    if not path.exists():
        print(f"[seed-ext] 扩展种子文件不存在: {path}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_knowledge_graph(session_factory, data: dict, stats: dict) -> dict[str, int]:
    """插入 20 KP + 30 KG 边，PK / UniqueConstraint 兜底幂等。返回 KP difficulty 映射。"""
    difficulties: dict[str, int] = {}
    with session_factory() as db:
        for kp in data["knowledge_points"]:
            kp_id = str(kp["id"])
            difficulties[kp_id] = int(kp.get("difficulty", 2))
            if db.get(KnowledgePointRecord, kp_id) is not None:
                stats["skipped"] += 1
                continue
            db.add(
                KnowledgePointRecord(
                    id=kp_id,
                    course=str(kp.get("course", "AI")),
                    name=str(kp["name"]),
                    description=str(kp.get("description", "")),
                    metadata_data={
                        "bloom": kp.get("bloom", "Understand"),
                        "difficulty": difficulties[kp_id],
                    },
                )
            )
            stats["knowledge_points"] += 1
        db.commit()

        for rel in data["knowledge_relations"]:
            src, tgt, rtype = str(rel["source"]), str(rel["target"]), str(rel["type"])
            existing = (
                db.query(KnowledgeRelationRecord)
                .filter(
                    KnowledgeRelationRecord.source_id == src,
                    KnowledgeRelationRecord.target_id == tgt,
                    KnowledgeRelationRecord.relation_type == rtype,
                )
                .one_or_none()
            )
            if existing:
                stats["skipped"] += 1
                continue
            db.add(
                KnowledgeRelationRecord(
                    source_id=src,
                    target_id=tgt,
                    relation_type=rtype,
                    weight=float(rel.get("weight", 1.0)),
                    metadata_data={},
                )
            )
            stats["kg_relations"] += 1
        db.commit()
    return difficulties


def _student_kp_mastery(
    user_id: str, mastery_bias: float, difficulties: dict[str, int], take: int
) -> list[tuple[str, float]]:
    """根据 mastery_bias 与 KP difficulty 派生每个学生覆盖的 KP 掌握度（确定性）。"""
    items: list[tuple[str, float]] = []
    seed = sum(ord(c) for c in user_id)
    kp_ids = list(difficulties.keys())
    for idx in range(take):
        kp_id = kp_ids[(seed + idx) % len(kp_ids)]
        diff = difficulties[kp_id]
        mastery = mastery_bias - 0.05 * (diff - 1) + 0.02 * (idx % 3 - 1)
        mastery = max(0.05, min(0.95, mastery))
        items.append((kp_id, round(mastery, 3)))
    return items


def _seed_algorithm_states(
    session_factory, data: dict, difficulties: dict[str, int], stats: dict
) -> None:
    """BKT / DINA / SM-2 初始状态：每学生 N 个 KP 覆盖，UniqueConstraint 兜底幂等。"""
    coverage = int(data["algorithm_seed_recipe"]["kp_coverage_per_student"])
    recipe = data["assessment_recipe"]["students"]
    now = time.time()

    with session_factory() as db:
        for user_id, cfg in recipe.items():
            mastery_pairs = _student_kp_mastery(
                user_id, float(cfg["mastery_bias"]), difficulties, coverage
            )
            for kp_id, mastery in mastery_pairs:
                if not db.query(BktStateRecord).filter(
                    BktStateRecord.user_id == user_id,
                    BktStateRecord.knowledge_point_id == kp_id,
                ).one_or_none():
                    db.add(
                        BktStateRecord(
                            user_id=user_id,
                            knowledge_point_id=kp_id,
                            p_learned=mastery,
                            p_transit=0.08,
                            p_slip=0.1,
                            p_guess=0.2,
                            history=[{"t": now - 86400 * 7, "correct": mastery > 0.5}],
                        )
                    )
                    stats["bkt_states"] += 1
                if not db.query(DinaStateRecord).filter(
                    DinaStateRecord.user_id == user_id,
                    DinaStateRecord.knowledge_point_id == kp_id,
                ).one_or_none():
                    db.add(
                        DinaStateRecord(
                            user_id=user_id,
                            knowledge_point_id=kp_id,
                            mastery=mastery,
                            slip=0.1,
                            guess=0.2,
                            evidence={"source": "seed"},
                        )
                    )
                    stats["dina_states"] += 1
            top = sorted(mastery_pairs, key=lambda x: -x[1])[:5]
            for offset_days, (kp_id, mastery) in enumerate(top):
                if not db.query(Sm2ScheduleRecord).filter(
                    Sm2ScheduleRecord.user_id == user_id,
                    Sm2ScheduleRecord.item_id == kp_id,
                ).one_or_none():
                    db.add(
                        Sm2ScheduleRecord(
                            user_id=user_id,
                            item_id=kp_id,
                            item_type="knowledge_point",
                            repetitions=2 + offset_days,
                            interval_days=3 + offset_days * 4,
                            easiness=round(2.3 + mastery * 0.4, 2),
                            due_at=now + 86400 * (offset_days + 1),
                        )
                    )
                    stats["sm2_schedules"] += 1
        db.commit()


def _seed_bulk_assessments(
    session_factory, data: dict, difficulties: dict[str, int], stats: dict
) -> None:
    """为 5 学生补齐 ~94 条额外答题，覆盖 quiz / resource_view / question。"""
    assessment_repo = AssessmentRepository(session_factory)
    kp_ids = list(difficulties.keys())
    now = time.time()
    for user_id, cfg in data["assessment_recipe"]["students"].items():
        bias = float(cfg["mastery_bias"])
        count = int(cfg["extra_count"])
        seed = sum(ord(c) for c in user_id)
        for i in range(count):
            external_id = f"ext-{user_id}-asmt-{i:03d}"
            kp_id = kp_ids[(seed + i) % len(kp_ids)]
            diff = difficulties[kp_id]
            kp_name = next(k["name"] for k in data["knowledge_points"] if k["id"] == kp_id)
            rec_type = _ASMT_TYPES_CYCLE[i % len(_ASMT_TYPES_CYCLE)]
            duration = 600 + (i % 12) * 180
            timestamp = now - 86400 * (count - i) * 1.5
            score: float | None
            if rec_type == "quiz":
                raw = bias * 100 - (diff - 1) * 6 + ((-1) ** i) * 5
                score = max(30.0, min(99.0, round(raw, 1)))
            else:
                score = None
            record = {
                "external_id": external_id,
                "type": rec_type,
                "score": score,
                "topic": kp_name,
                "duration": duration,
                "timestamp": timestamp,
                "metadata": {"kp_id": kp_id, "source": "seed-extended"},
            }
            from backend.app.core.models import AssessmentRecord
            with session_factory() as db:
                already = (
                    db.query(AssessmentRecord.id)
                    .filter(AssessmentRecord.external_id == external_id)
                    .one_or_none()
                )
            if already:
                stats["skipped"] += 1
                continue
            assessment_repo.add(user_id, record)
            stats["extra_assessments"] += 1


def seed_extended(session_factory=None, seed_path: str | None = None) -> dict:
    """A 拥有的演示扩展导入：2 学生 + 2 路径 + 20 KP + 30 边 + 94 答题 + 算法状态。"""
    if session_factory is None:
        session_factory = SessionLocal

    data = _load_extended(seed_path)
    profile_repo = ProfileRepository(session_factory)
    path_repo = LearningPathRepository(session_factory)

    stats = {
        "extra_profiles": 0,
        "extra_paths": 0,
        "extra_assessments": 0,
        "knowledge_points": 0,
        "kg_relations": 0,
        "bkt_states": 0,
        "dina_states": 0,
        "sm2_schedules": 0,
        "skipped": 0,
    }

    for student in data["extra_students"]:
        user_id = str(student["user_id"])
        profile = dict(student.get("profile", {}))
        nickname = str(student.get("nickname", "")).strip()
        if nickname:
            # 登录态和画像页都能稳定展示同一姓名，避免扩展学生只在登录态有昵称。
            profile.setdefault("display_name", nickname)
            profile.setdefault("nickname", nickname)

        existing = profile_repo.get(user_id)
        allow_identity_backfill = bool(student.get("backfill_identity", False))
        missing_identity = {
            key: value
            for key, value in profile.items()
            if key in {"display_name", "nickname"} and not existing.get(key)
        } if allow_identity_backfill else {}
        if existing and not missing_identity:
            stats["skipped"] += 1
        else:
            profile_repo.upsert(user_id, profile if not existing else missing_identity)
            stats["extra_profiles"] += 1

    for path in data["extra_paths"]:
        if path_repo.get(str(path["id"])):
            stats["skipped"] += 1
            continue
        record = dict(path)
        record.setdefault("created_at", time.time())
        path_repo.save(record)
        stats["extra_paths"] += 1

    difficulties = _seed_knowledge_graph(session_factory, data, stats)
    _seed_algorithm_states(session_factory, data, difficulties, stats)
    _seed_bulk_assessments(session_factory, data, difficulties, stats)

    return stats


# ============================================================
# 演示首屏非空保障 —— demo-student-1 的首屏"演示动线"数据补齐
# ------------------------------------------------------------
# Plan P0-4 要求：
#   一次种入画像快照、学习行为热力、错题、评估记录、路径调整、KG 2-hop、
#   Debate traces、CoV 案例、多模态产物，保证 demo-student-1 首屏不空。
# ============================================================
_DEMO_FIRST_SCREEN_USER = "demo-student-1"
_DEMO_FIRST_SCREEN_MISTAKES = [
    # (kp_id, question, error_type, analysis, resolved)
    ("attention_mechanism", "Self-Attention 中 Q/K/V 三个矩阵各自代表什么含义？", "概念混淆",
     "把 Q 当成 query 直接去匹配输入 token，忽略了 QKV 都是输入的线性投影；先回顾 Linear Projection 步骤。", False),
    ("transformer", "Transformer 解码时为什么要做 mask？", "知识缺漏",
     "未建立『因果语言模型只能看上文』的约束；用右上三角 mask 模拟。", False),
    ("backpropagation", "反向传播时链式法则在矩阵维度上的顺序如何判定？", "方法选择错",
     "使用 ∂L/∂W = ∂L/∂y · ∂y/∂W 时方向反了；先固定 forward 计算图再反向求导。", True),
    ("neural_networks", "激活函数 ReLU 在负半轴的梯度为何导致神经元死亡？", "概念混淆",
     "Relu'(x<0)=0，权重不再更新；可换 LeakyReLU 或初始化调整。", True),
    ("ml_basics", "训练集准确率 99%、测试集 60%，最先排查的方向是什么？", "审题不清",
     "未判断是否过拟合；先看 train/test 分布差异 + 模型容量 + 正则项。", False),
]
_DEMO_FIRST_SCREEN_DEBATE = [
    # (round, expert, draft, critic_score, passed, issues, verdict)
    (1, "Tutor Agent",
     "先回顾 Self-Attention 的 QKV 三投影，再让学生口述每一步。",
     0.86, True, [], "round1:passed"),
    (1, "Safety Agent",
     "Socratic 反问不能直接给答案；当前草稿已满足。",
     0.92, True, [], "round1:safety_ok"),
    (2, "Content Agent",
     "补充 Transformer 位置编码的两种实现：sinusoidal vs learned。",
     0.81, True, ["建议加上 RoPE 的简短对照"], "round2:minor_revision"),
    (2, "Evaluation Agent",
     "case-by-case 评估：草稿证据完整度 0.88，建议加入案例演示。",
     0.78, False, ["缺少 1 个错题回放"], "round2:needs_evidence"),
    (3, "Planner Agent",
     "把 attention 拆成两段任务：先 QKV 概念、再 mask 推演。",
     0.95, True, [], "round3:passed"),
]
_DEMO_FIRST_SCREEN_RESOURCES = [
    # (type, title, content, tags)
    ("pptx", "Self-Attention 速通", "# Self-Attention\n\n- Q/K/V 含义\n- 注意力分数 = QKᵀ/√d\n- 多头拼接",
     ["attention_mechanism", "transformer", "tutor"]),
    ("mermaid", "Self-Attention 数据流", "graph LR\nX-->QProj\nX-->KProj\nX-->VProj\nQProj-->Scores\nKProj-->Scores\nScores-->Softmax\nVProj-->Softmax\nSoftmax-->Out",
     ["attention_mechanism"]),
    ("code", "Self-Attention 最小实现",
     "import numpy as np\nQ, K, V = np.random.randn(3, 4, 8)\nscores = Q @ K.transpose(0, 2, 1) / np.sqrt(8)\nattn = np.exp(scores) / np.exp(scores).sum(-1, keepdims=True)\nout = attn @ V\nprint(out.shape)",
     ["attention_mechanism", "code", "python"]),
    ("document", "Transformer 解码 mask 笔记",
     "解码时使用上三角 mask 保证每个位置只能看到左侧历史；shape = (T, T)。",
     ["transformer"]),
]
_DEMO_FIRST_SCREEN_KG_EXTRA_EDGES = [
    # 2-hop 补强：让 demo-student-1 当前 KP (transformer) 有更密的 2-hop 邻居
    {"source": "transformer", "target": "cnn", "type": "contrast", "weight": 0.55},
    {"source": "transformer", "target": "decision_trees", "type": "contrast", "weight": 0.5},
    {"source": "attention_mechanism", "target": "cnn", "type": "related", "weight": 0.6},
]
_DEMO_FIRST_SCREEN_PATH_ADJUSTMENT = {
    "adjusted_at": "2026-07-01T08:30:00Z",
    "reason": "评估发现 attention_mechanism 薄弱 + 进度落后 1 周，自动下调 NLP/Transformer 阶段门槛并前置 attention 强化。",
    "before": {"current_stage": 3, "progress": 60.0},
    "after": {"current_stage": 2, "progress": 50.0},
    "added_kp_focus": ["attention_mechanism", "transformer"],
}


def _seed_demo_first_screen(session_factory=None, stats: dict | None = None) -> dict:
    """Plan P0-4：demo-student-1 首屏非空保障。

    一次性种入：错题（5）/ Debate traces（5）/ 多模态产物（4）/ KG 2-hop 补强（3 边）/
    路径调整（1 条）+ 同步一些热力数据落到 GamificationProfile。
    """
    if session_factory is None:
        session_factory = SessionLocal

    if stats is None:
        stats = {
            "first_screen_mistakes": 0,
            "first_screen_debates": 0,
            "first_screen_resources": 0,
            "first_screen_kg_extra_edges": 0,
            "first_screen_path_adjustments": 0,
            "first_screen_gamification": 0,
            "first_screen_skipped": 0,
        }

    user_id = _DEMO_FIRST_SCREEN_USER

    # 1) 错题 → MistakeRecord
    from backend.app.core.models import (
        MistakeRecord, DebateLogRecord, ResourceRecord,
        KnowledgeRelationRecord, LearningPathRecord,
        GamificationProfileRecord,
    )

    now = time.time()
    with session_factory() as db:
        for idx, (kp_id, question, err_type, analysis, resolved) in enumerate(_DEMO_FIRST_SCREEN_MISTAKES):
            mid = f"seed-first-screen-{user_id}-m{idx + 1}"
            if db.get(MistakeRecord, mid) is not None:
                stats["first_screen_skipped"] += 1
                continue
            db.add(MistakeRecord(
                id=mid,
                user_id=user_id,
                knowledge_point_id=kp_id,
                question_data={
                    "stem": question,
                    "options": [],
                    "metadata": {"source": "seed-first-screen"},
                },
                error_type=err_type,
                analysis=analysis,
                resolved_at=(now - 86400) if resolved else None,
            ))
            stats["first_screen_mistakes"] += 1
        db.commit()

    # 2) Debate traces → DebateLogRecord
    with session_factory() as db:
        for round_num, expert, draft, critic_score, passed, issues, verdict in _DEMO_FIRST_SCREEN_DEBATE:
            # 用 session_id + round_num + expert 三元组做幂等键
            existing = (
                db.query(DebateLogRecord)
                .filter(
                    DebateLogRecord.session_id == f"seed-first-screen-{user_id}",
                    DebateLogRecord.round_num == round_num,
                    DebateLogRecord.expert_name == expert,
                )
                .one_or_none()
            )
            if existing:
                stats["first_screen_skipped"] += 1
                continue
            db.add(DebateLogRecord(
                session_id=f"seed-first-screen-{user_id}",
                round_num=round_num,
                expert_name=expert,
                draft_preview=draft,
                critic_score=critic_score,
                critic_passed=1 if passed else 0,
                critic_issues=issues,
                verdict=verdict,
            ))
            stats["first_screen_debates"] += 1
        db.commit()

    # 3) 多模态产物 → ResourceRecord
    with session_factory() as db:
        for idx, (rtype, title, content, tags) in enumerate(_DEMO_FIRST_SCREEN_RESOURCES):
            rid = f"seed-first-screen-{user_id}-r{idx + 1}"
            if db.get(ResourceRecord, rid) is not None:
                stats["first_screen_skipped"] += 1
                continue
            db.add(ResourceRecord(
                id=rid,
                user_id=user_id,
                type=rtype,
                title=title,
                content=content,
                content_type="markdown" if rtype != "code" else "python",
                agent_name={"pptx": "content_agent",
                            "mermaid": "content_agent",
                            "code": "tutor_agent",
                            "document": "reviewer_agent"}.get(rtype, "content_agent"),
                metadata_data={
                    "source": "seed-first-screen",
                    "kp_ids": ["attention_mechanism", "transformer"] if rtype in {"pptx", "document"} else ["attention_mechanism"],
                    "bloom_level": "Understand" if rtype in {"document"} else "Apply",
                },
                tags=tags,
                created_at=now - 86400 * (idx + 1),
            ))
            stats["first_screen_resources"] += 1
        db.commit()

    # 4) KG 2-hop 补强边 → KnowledgeRelationRecord
    with session_factory() as db:
        for edge in _DEMO_FIRST_SCREEN_KG_EXTRA_EDGES:
            existing = (
                db.query(KnowledgeRelationRecord)
                .filter(
                    KnowledgeRelationRecord.source_id == edge["source"],
                    KnowledgeRelationRecord.target_id == edge["target"],
                    KnowledgeRelationRecord.relation_type == edge["type"],
                )
                .one_or_none()
            )
            if existing:
                stats["first_screen_skipped"] += 1
                continue
            db.add(KnowledgeRelationRecord(
                source_id=edge["source"],
                target_id=edge["target"],
                relation_type=edge["type"],
                weight=edge["weight"],
                metadata_data={"source": "seed-first-screen"},
            ))
            stats["first_screen_kg_extra_edges"] += 1
        db.commit()

    # 5) 路径调整 → 写入 LearningPathRecord.metadata_data（idempotent by metadata.adjustment_id）
    with session_factory() as db:
        path = (
            db.query(LearningPathRecord)
            .filter(LearningPathRecord.user_id == user_id)
            .first()
        )
        if path is not None:
            meta = dict(path.metadata_data or {})
            adjustments = list(meta.get("adjustments") or [])
            adj_id = "adj-2026-07-01"
            if not any(a.get("id") == adj_id for a in adjustments):
                adjustments.append({
                    "id": adj_id,
                    "adjusted_at": _DEMO_FIRST_SCREEN_PATH_ADJUSTMENT["adjusted_at"],
                    "reason": _DEMO_FIRST_SCREEN_PATH_ADJUSTMENT["reason"],
                    "before": _DEMO_FIRST_SCREEN_PATH_ADJUSTMENT["before"],
                    "after": _DEMO_FIRST_SCREEN_PATH_ADJUSTMENT["after"],
                    "added_kp_focus": _DEMO_FIRST_SCREEN_PATH_ADJUSTMENT["added_kp_focus"],
                })
                meta["adjustments"] = adjustments
                path.metadata_data = meta
                stats["first_screen_path_adjustments"] += 1
            else:
                stats["first_screen_skipped"] += 1
        db.commit()

    # 6) 学习行为热力 → GamificationProfileRecord（xp/level/achievements/streak）
    with session_factory() as db:
        gp = db.get(GamificationProfileRecord, user_id)
        if gp is None:
            db.add(GamificationProfileRecord(
                user_id=user_id,
                xp=1240,
                level=4,
                streak_days=12,
                achievements=[
                    {"code": "first_correct", "unlocked_at": now - 86400 * 21},
                    {"code": "streak_7d", "unlocked_at": now - 86400 * 7},
                    {"code": "tutor_socratic_3", "unlocked_at": now - 86400 * 2},
                ],
            ))
            stats["first_screen_gamification"] += 1
        else:
            stats["first_screen_skipped"] += 1
        db.commit()

    return stats


def reset_b_tables() -> None:
    """清空 B 拥有的所有表（用于 --reset）。"""
    from backend.app.core.models import (
        ProfileRecord,
        RealtimeStateRecord,
        LearnerArchetypeRecord,
        KnowledgePointRecord,
        KnowledgeRelationRecord,
        DinaStateRecord,
        BktStateRecord,
        Sm2ScheduleRecord,
        LearningPathRecord,
        AssessmentRecord,
        MistakeRecord,
        GamificationProfileRecord,
        ResourceRecord,
        DebateLogRecord,
    )

    models = [
        AssessmentRecord,
        LearningPathRecord,
        MistakeRecord,
        DinaStateRecord,
        BktStateRecord,
        Sm2ScheduleRecord,
        KnowledgeRelationRecord,
        KnowledgePointRecord,
        LearnerArchetypeRecord,
        RealtimeStateRecord,
        GamificationProfileRecord,
        ResourceRecord,
        DebateLogRecord,
        ProfileRecord,
    ]

    with SessionLocal() as db:
        for model in models:
            try:
                db.query(model).delete()
            except Exception:
                pass
        db.commit()
    print("[seed] B 拥有的表已清空")


def main() -> None:
    parser = argparse.ArgumentParser(description="幂等种子数据导入")
    parser.add_argument("--check", action="store_true", help="仅检查，不写入")
    parser.add_argument("--reset", action="store_true", help="先清空 B 表再导入")
    parser.add_argument("--baseline-only", action="store_true", help="只跑 seed.json，不跑 extended")
    parser.add_argument(
        "--db",
        default=None,
        help="数据库 URL（默认使用项目配置）",
    )
    args = parser.parse_args()

    if args.db:
        configure_database(args.db)
    init_db()

    if args.check:
        seed = load_seed()
        extended = _load_extended(None) if SEED_EXTENDED_PATH.exists() else {"extra_students": []}
        all_students = seed.get("students", []) + extended.get("extra_students", [])
        print(f"[seed] 共 {len(all_students)} 个演示账号（baseline {len(seed.get('students', []))} + extended {len(extended.get('extra_students', []))}）")
        profile_repo = ProfileRepository()
        for student in all_students:
            uid = student["user_id"]
            profile = profile_repo.get(uid)
            status = "已存在" if profile else "未导入"
            print(f"  {student.get('nickname', uid)} ({uid}): {status}")
        return

    if args.reset:
        reset_b_tables()

    stats = seed_database()
    print(
        f"[seed/base] 画像 {stats['profiles']} / 路径 {stats['paths']} / "
        f"评估 {stats['assessments']} / 跳过 {stats['skipped']}"
    )

    stats2 = seed_database()
    assert stats2["profiles"] == 0, "二次 baseline 导入不应创建新画像"
    assert stats2["paths"] == 0, "二次 baseline 导入不应创建新路径"
    print("[seed/base] 幂等性验证通过")

    if args.baseline_only:
        return

    ext = seed_extended()
    print(
        f"[seed/ext]  画像 {ext['extra_profiles']} / 路径 {ext['extra_paths']} / "
        f"评估 {ext['extra_assessments']} / KP {ext['knowledge_points']} / "
        f"KG边 {ext['kg_relations']} / BKT {ext['bkt_states']} / "
        f"DINA {ext['dina_states']} / SM2 {ext['sm2_schedules']} / "
        f"跳过 {ext['skipped']}"
    )

    ext2 = seed_extended()
    for key in (
        "extra_profiles", "extra_paths", "extra_assessments",
        "knowledge_points", "kg_relations", "bkt_states", "dina_states", "sm2_schedules",
    ):
        assert ext2[key] == 0, f"二次 extended 导入不应新增 {key}: {ext2}"
    print("[seed/ext]  幂等性验证通过 —— 二次导入零新增")

    # ============================================================
    # Plan P0-4：demo-student-1 首屏非空保障 —— 演示动线数据补齐
    # ============================================================
    fs = _seed_demo_first_screen()
    print(
        f"[seed/fs]   错题 {fs['first_screen_mistakes']} / "
        f"Debate {fs['first_screen_debates']} / "
        f"资源 {fs['first_screen_resources']} / "
        f"KG补边 {fs['first_screen_kg_extra_edges']} / "
        f"路径调整 {fs['first_screen_path_adjustments']} / "
        f"成就 {fs['first_screen_gamification']} / "
        f"跳过 {fs['first_screen_skipped']}"
    )

    fs2 = _seed_demo_first_screen()
    assert all(
        fs2[k] == 0 for k in fs2 if k != "first_screen_skipped"
    ), f"二次 first_screen 导入不应新增: {fs2}"
    print("[seed/fs]   幂等性验证通过 —— 二次导入零新增")


if __name__ == "__main__":
    main()
