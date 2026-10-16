#!/usr/bin/env python3
"""Rebuild deterministic non-library business data for 20 demo students."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CLASS_DATA_PATH = ROOT / "data" / "class_comparison_data.json"
SOURCE = "demo-business-seed-v2"
COURSE = "artificial_intelligence"
PRIMARY_DEMO_USER_ID = "demo-student-1"
PRIMARY_DEMO_DISPLAY_NAME = "杜同学"
PRIMARY_DEMO_FOCUS_KPS = ("AI_015", "AI_006_03", "AI_008")
PRIMARY_DEMO_FOCUS_STAGE_TITLE = "多模态融合与专项补强"
PRIMARY_DEMO_FOCUS_MASTERIES = {
    "AI_015": 0.56,      # 多模态大模型：图文语义对齐尚不稳定
    "AI_006_03": 0.61,  # Transformer 与注意力机制：Q/K/V 维度推演待补强
    "AI_008": 0.66,     # 计算机视觉：为 CLIP 图文检索实践提供前置基础
}
PRIMARY_DEMO_MISTAKE_CASES = {
    "AI_015": {
        "error_type": "概念理解偏差",
        "question": "CLIP 为什么要把图像和文本映射到同一向量空间？它如何判断一组图文是否对齐？",
        "student_answer": "图像编码器和文本编码器各自分类，只要两个分类结果相同就说明对齐。",
        "correct_answer": "CLIP 将图像和文本编码为同一语义空间中的向量，用相似度与对比学习拉近匹配图文、拉远不匹配图文。",
        "analysis": "把跨模态语义对齐误解为两个独立分类器的一致性，需先建立图文共享向量空间的视觉表征。",
    },
    "AI_006_03": {
        "error_type": "计算错误",
        "question": "若 d_model=768、num_heads=12，Self-Attention 中每个头的 d_k 是多少？QKᵀ 后的最后两维代表什么？",
        "student_answer": "每个头维度是 768，QKᵀ 的最后两维仍是 (seq_len, 768)。",
        "correct_answer": "每个头 d_k=64；QKᵀ 的最后两维是 (query_len, key_len)，表示每个查询位置对各键位置的注意力分数。",
        "analysis": "没有把 d_model 按头数拆分，也没有把矩阵乘法后的维度变化与注意力分数矩阵对应起来。",
    },
    "AI_008": {
        "error_type": "迁移应用困难",
        "question": "为课程图片检索“包含反向传播计算图的示意图”时，为什么 CLIP 式图文检索通常比仅按文件名检索更适合？",
        "student_answer": "因为 CLIP 只识别图片中的文字，所以与关键词检索没有区别。",
        "correct_answer": "CLIP 能把图像内容和文本查询映射到共享语义空间，可根据图文语义相似度召回相关图片，而不只依赖文件名关键词。",
        "analysis": "尚未把跨模态对齐能力迁移到真实检索场景，需要通过图文检索小实验验证理解。",
    },
}
ERROR_TYPES = (
    ("conceptual_misunderstanding", "概念理解偏差"),
    ("calculation_error", "计算错误"),
    ("application_transfer", "迁移应用困难"),
    ("careless_error", "审题疏忽"),
    ("reading_comprehension", "题意理解偏差"),
    ("memory_gap", "知识记忆缺口"),
    ("strategy_error", "解题策略不当"),
    ("incomplete_answer", "作答不完整"),
)
QUESTION_TEMPLATES = (
    (
        "请解释 {kp_name} 的核心概念，并说明它适合解决什么问题。",
        "只写出了概念名称，没有说明适用场景。",
        "应同时给出核心定义、关键条件和典型应用场景。",
        "先明确概念边界，再用一个正例和一个反例验证理解。",
    ),
    (
        "围绕 {kp_name} 完成一次参数计算，并写出每一步推导。",
        "直接写出结果，部分中间计算有误。",
        "应列出公式、代入参数并逐步检查计算结果。",
        "将复杂计算拆成三个可校验步骤，可减少符号和数值错误。",
    ),
    (
        "在一个新的业务场景中选择并应用 {kp_name}，说明选择理由。",
        "沿用了示例结论，没有结合新场景约束。",
        "应分析场景特征、方法假设和预期结果后再做选择。",
        "先列出场景约束，再逐项核对方法的适用条件。",
    ),
    (
        "阅读关于 {kp_name} 的题目条件，找出两个关键限制并完成作答。",
        "遗漏了题目中的一个限制条件。",
        "应完整提取条件，并在结论中逐一回应。",
        "用条件清单复核答案，可避免审题疏忽和作答遗漏。",
    ),
    (
        "比较 {kp_name} 与相邻知识点的差异，给出判断依据。",
        "只描述了表面差异，判断依据不充分。",
        "应从目标、输入、过程和输出四个维度进行比较。",
        "建立对比表后再下结论，能够提升题意理解与辨析能力。",
    ),
    (
        "不查看资料，写出 {kp_name} 的关键步骤和一个注意事项。",
        "遗漏了关键步骤，注意事项表述模糊。",
        "应准确写出完整步骤，并指出最常见的错误位置。",
        "使用间隔复习和主动回忆巩固容易遗忘的步骤。",
    ),
    (
        "为 {kp_name} 设计两种解题方案，并选择更合适的一种。",
        "只给出一种方案，没有比较策略成本。",
        "应比较两种方案的正确性、复杂度和适用条件。",
        "先生成备选策略，再按评价标准选择，可改善解题策略。",
    ),
    (
        "完整回答 {kp_name} 综合题，结论中必须包含依据和验证。",
        "给出了结论，但缺少依据和结果验证。",
        "答案应包含结论、推理依据、计算或案例验证。",
        "提交前按结论、依据、验证三项检查作答完整性。",
    ),
)


@dataclass(frozen=True)
class Persona:
    code: str
    mastery: float
    activity_level: str
    last_active_days: int
    assessment_count: int
    collaboration_count: int
    risk_level: str


def _stable_unit(*parts: object) -> float:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16) / 0xFFFFFFFF


def _clamp(value: float, low: float = 0.05, high: float = 0.98) -> float:
    return max(low, min(high, value))


def _load_students() -> list[dict[str, Any]]:
    data = json.loads(CLASS_DATA_PATH.read_text(encoding="utf-8"))
    students = list(data.get("all_students") or [])
    if len(students) != 20:
        raise RuntimeError(f"expected 20 class students, got {len(students)}")
    return students


def _anchor_timestamp(anchor_date: str | date | datetime | None) -> float:
    if anchor_date is None:
        return time.time()
    if isinstance(anchor_date, datetime):
        value = anchor_date
    else:
        value = datetime.combine(
            date.fromisoformat(anchor_date) if isinstance(anchor_date, str) else anchor_date,
            datetime_time(hour=12),
            tzinfo=timezone.utc,
        )
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _persona(index: int) -> Persona:
    if index < 5:
        return Persona("high_active", 0.88 - index * 0.018, "active", index % 3, 34 - index, 8 + index % 5, "low")
    if index < 10:
        offset = index - 5
        return Persona("stable", 0.72 - offset * 0.018, "active", 2 + offset % 4, 25 - offset, 4 + offset, "low" if offset < 2 else "medium")
    if index < 14:
        offset = index - 10
        return Persona("active_low_mastery", 0.51 - offset * 0.025, "active", offset % 3, 32 - offset * 2, 9 + offset, "high")
    if index < 17:
        offset = index - 14
        return Persona("dormant", 0.62 - offset * 0.05, "dormant", (10, 18, 27)[offset], 18 - offset * 2, 2 - offset, "medium" if offset == 0 else "high")
    offset = index - 17
    return Persona("inactive", 0.57 - offset * 0.07, "inactive", (36, 48, 67)[offset], 14 - offset, 0, "high")


def _profile_data(student: dict[str, Any], persona: Persona, index: int, anchor_ts: float) -> dict[str, Any]:
    mastery = persona.mastery
    consistency = {"active": 0.86, "dormant": 0.42, "inactive": 0.2}[persona.activity_level]
    interaction = min(0.95, 0.25 + persona.collaboration_count * 0.055)
    display_name = (
        PRIMARY_DEMO_DISPLAY_NAME
        if str(student.get("student_id")) == PRIMARY_DEMO_USER_ID
        else student.get("nickname") or f"演示学生{index + 1}"
    )
    return {
        "display_name": display_name,
        "nickname": display_name,
        "class_id": "class-ai-2026",
        "registered_at": anchor_ts - (120 + index * 3) * 86400,
        "knowledge_base": {"score": round(mastery, 3), "status": "measured"},
        "learning_preference": {"score": round(0.58 + index % 4 * 0.08, 3), "mode": ("视觉", "读写", "动手", "听觉")[index % 4]},
        "weak_points": {"score": round(1 - mastery, 3), "patterns": ["概念辨析", "迁移应用"] if mastery < 0.65 else ["综合分析"]},
        "time_management": {"score": consistency, "best_time": ("上午", "下午", "晚间")[index % 3]},
        "self_efficacy": {"score": round(_clamp(mastery * 0.92), 3), "confidence": round(_clamp(mastery * 0.9), 3)},
        "cognitive_style": {"score": round(0.55 + index % 5 * 0.07, 3), "primary": ("图像化", "步骤化", "案例化")[index % 3]},
        "learning_goal": {"score": round(0.62 + index % 4 * 0.07, 3), "target": ("课程高分", "项目实战", "算法竞赛", "AI 工程")[index % 4]},
        "interaction_pattern": {"score": round(interaction, 3), "style": "协作讨论" if interaction >= 0.6 else "独立学习"},
        "learning_progress": {"score": round(mastery, 3), "study_days_30d": max(0, 30 - persona.last_active_days), "updated_at": anchor_ts},
        "interest_model": {"score": round(0.58 + index % 6 * 0.06, 3), "recent_interest": ("Transformer", "RAG", "多智能体", "计算机视觉")[index % 4]},
        "risk": {"level": persona.risk_level, "activity_level": persona.activity_level},
        "seed_metadata": {"source": SOURCE, "synthetic_demo": True, "persona": persona.code},
    }


def _delete_demo_business_data(db: Any) -> None:
    from backend.app.core.models import (
        AgentRunRecord, AssessmentRecord, BktStateRecord, ChatHistoryRecord,
        DinaStateRecord, GamificationProfileRecord, GroupChatMessageRecord,
        LearnerArchetypeRecord, LearningPathRecord, MistakeRecord, ProfileRecord,
        ProfileSnapshotRecord, RealtimeStateRecord, ReviewEventRecord,
        Sm2ScheduleRecord,
    )

    user_models = (
        AgentRunRecord, ReviewEventRecord, AssessmentRecord, BktStateRecord,
        DinaStateRecord, GamificationProfileRecord, LearnerArchetypeRecord,
        LearningPathRecord, MistakeRecord, ProfileSnapshotRecord,
        RealtimeStateRecord, Sm2ScheduleRecord, ChatHistoryRecord, ProfileRecord,
    )
    for model in user_models:
        db.query(model).filter(model.user_id.like("demo-student-%")).delete(synchronize_session=False)
    db.query(GroupChatMessageRecord).filter(
        GroupChatMessageRecord.room_id.like(f"{COURSE}:demo-student-%")
    ).delete(synchronize_session=False)


def _seed_profile(db: Any, student: dict[str, Any], persona: Persona, index: int, anchor_ts: float) -> dict[str, Any]:
    from backend.app.core.models import ProfileRecord, ProfileSnapshotRecord

    user_id = str(student["student_id"])
    profile = _profile_data(student, persona, index, anchor_ts)
    db.add(ProfileRecord(user_id=user_id, profile_data=profile, version=6, created_at=profile["registered_at"], updated_at=anchor_ts))
    snapshot_count = 4 + index % 3
    for snapshot_index in range(snapshot_count):
        snapshot = json.loads(json.dumps(profile, ensure_ascii=False))
        progress = _clamp(persona.mastery - (snapshot_count - snapshot_index - 1) * 0.025)
        snapshot["knowledge_base"]["score"] = round(progress, 3)
        snapshot["learning_progress"]["score"] = round(progress, 3)
        db.add(ProfileSnapshotRecord(user_id=user_id, version=snapshot_index + 1, profile_data=snapshot, changed_keys=["knowledge_base", "learning_progress", "time_management"], source=SOURCE, created_at=anchor_ts - (snapshot_count - snapshot_index) * 7 * 86400))
    return profile


def _seed_assessments(db: Any, user_id: str, persona: Persona, index: int, kp_names: list[str], anchor_ts: float) -> None:
    from backend.app.core.models import AssessmentRecord

    latest_ts = anchor_ts - persona.last_active_days * 86400 - (index % 6) * 1800
    for item in range(persona.assessment_count):
        age_days = item if persona.assessment_count <= 20 else round(item * 1.25)
        duration = round(5 + _stable_unit(user_id, item, "duration") * 40, 1)
        score = round(max(30, min(100, persona.mastery * 100 + (0.5 - _stable_unit(user_id, item, "score")) * 16)), 1)
        db.add(AssessmentRecord(external_id=f"{SOURCE}-{user_id}-a{item + 1:02d}", user_id=user_id, record_type="quiz", score=score, topic=kp_names[(index + item) % len(kp_names)], duration=duration, metadata_data={"source": SOURCE, "duration_unit": "minutes", "synthetic_demo": True}, timestamp=latest_ts - age_days * 86400))


def _seed_cognitive_data(db: Any, user_id: str, persona: Persona, index: int, kp_ids: list[str], anchor_ts: float) -> dict[str, float]:
    from backend.app.core.models import BktStateRecord, DinaStateRecord

    mastery_by_kp: dict[str, float] = {}
    for kp_index, kp_id in enumerate(kp_ids):
        current = round(_clamp(persona.mastery + (_stable_unit(user_id, kp_id) - 0.5) * 0.28), 3)
        mastery_by_kp[kp_id] = current
        start = _clamp(current - 0.12)
        history = []
        before = start
        for event_index in range(4):
            correct = _stable_unit(user_id, kp_id, event_index, "correct") < current
            after = _clamp(before + (0.035 if correct else -0.012))
            history.append({"ts": anchor_ts - (28 - event_index * 7 + persona.last_active_days) * 86400, "p_before": round(before, 3), "p_after": round(after, 3), "correct": bool(correct), "source": SOURCE})
            before = after
        history[-1]["p_after"] = current
        db.add(BktStateRecord(user_id=user_id, knowledge_point_id=kp_id, p_learned=current, p_transit=0.1, p_slip=0.1, p_guess=0.2, history=history, updated_at=history[-1]["ts"]))
        db.add(DinaStateRecord(user_id=user_id, knowledge_point_id=kp_id, mastery=round(_clamp(current + 0.015), 3), slip=0.1, guess=0.2, evidence={"source": SOURCE, "attempts": 8 + (index + kp_index) % 20}, updated_at=history[-1]["ts"]))
    return mastery_by_kp


def _target_mistake_count(persona: Persona, index: int) -> int:
    base = 15 + index % 6
    if persona.risk_level == "high":
        return min(20, base + 1)
    return base


def _top_up_user_mistakes(
    db: Any,
    user_id: str,
    persona: Persona,
    index: int,
    kp_rows: list[Any],
    anchor_ts: float,
) -> int:
    from backend.app.core.models import MistakeRecord, Sm2ScheduleRecord

    target = _target_mistake_count(persona, index)
    existing = db.query(MistakeRecord).filter_by(user_id=user_id).all()
    missing = max(0, target - len(existing))
    existing_ids = {row.id for row in existing}
    existing_unresolved = sum(row.resolved_at is None for row in existing)
    target_unresolved = round(target * 0.4)
    unresolved_to_add = max(0, min(missing, target_unresolved - existing_unresolved))
    inserted = 0
    candidate = 0

    while inserted < missing:
        mistake_id = f"{SOURCE}-{user_id}-m{candidate + 1:02d}"
        if mistake_id in existing_ids:
            candidate += 1
            continue

        kp_row = kp_rows[(index * 2 + candidate) % len(kp_rows)]
        code, label = ERROR_TYPES[(index + candidate) % len(ERROR_TYPES)]
        stem, student_answer, correct_answer, explanation = QUESTION_TEMPLATES[
            (index + candidate) % len(QUESTION_TEMPLATES)
        ]
        question = stem.format(kp_name=kp_row.name)
        created_at = anchor_ts - (persona.last_active_days + candidate + 2) * 86400
        unresolved = inserted >= missing - unresolved_to_add
        db.add(
            MistakeRecord(
                id=mistake_id,
                user_id=user_id,
                knowledge_point_id=kp_row.id,
                question_data={
                    "question": question,
                    "stem": question,
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "explanation": explanation,
                    "source": SOURCE,
                },
                error_type=code,
                analysis=f"错因：{label}。{explanation}",
                created_at=created_at,
                resolved_at=None if unresolved else created_at + 2 * 86400,
            )
        )
        existing_ids.add(mistake_id)
        inserted += 1
        candidate += 1

    db.flush()
    unresolved_kps = {
        kp_id
        for (kp_id,) in db.query(MistakeRecord.knowledge_point_id)
        .filter_by(user_id=user_id, resolved_at=None)
        .filter(MistakeRecord.knowledge_point_id.is_not(None))
        .distinct()
        .all()
    }
    scheduled = {
        item_id
        for (item_id,) in db.query(Sm2ScheduleRecord.item_id)
        .filter_by(user_id=user_id)
        .all()
    }
    for offset, kp_id in enumerate(sorted(unresolved_kps - scheduled)):
        db.add(
            Sm2ScheduleRecord(
                user_id=user_id,
                item_id=kp_id,
                item_type="knowledge_point",
                repetitions=0,
                interval_days=1,
                easiness=round(2.1 + persona.mastery * 0.5, 2),
                due_at=anchor_ts + (offset % 3) * 86400,
                updated_at=anchor_ts,
            )
        )
    return inserted


def _seed_mistakes_and_reviews(db: Any, user_id: str, persona: Persona, index: int, kp_ids: list[str], mastery_by_kp: dict[str, float], anchor_ts: float) -> None:
    from backend.app.core.models import KnowledgePointRecord, ReviewEventRecord

    kp_rows = (
        db.query(KnowledgePointRecord)
        .filter(KnowledgePointRecord.id.in_(kp_ids))
        .order_by(KnowledgePointRecord.id)
        .all()
    )
    _top_up_user_mistakes(db, user_id, persona, index, kp_rows, anchor_ts)

    review_count = 2 + index % 7 if persona.activity_level == "active" else 1 if persona.activity_level == "dormant" else 0
    for item in range(review_count):
        kp_id = kp_ids[(index + item * 2) % len(kp_ids)]
        before = mastery_by_kp[kp_id]
        after = _clamp(before + 0.02 + item * 0.003)
        db.add(ReviewEventRecord(user_id=user_id, item_id=kp_id, item_type="knowledge_point", rating=3 + item % 3, before_mastery=before, after_mastery=round(after, 3), duration_minutes=round(6 + _stable_unit(user_id, item, "review") * 14, 1), reviewed_at=anchor_ts - (persona.last_active_days + item) * 86400, metadata_data={"source": SOURCE, "algorithm": "sm2"}))


def _focus_video_path_stages(
    stages: list[dict[str, Any]],
    current_stage: int,
    mastery_by_kp: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Put the recording account's live weakest KPs into its active path stage."""
    normalized: list[dict[str, Any]] = []
    focus_set = set(PRIMARY_DEMO_FOCUS_KPS)
    for stage in stages:
        normalized.append({
            **stage,
            "kp_ids": [
                str(kp_id)
                for kp_id in (stage.get("kp_ids") or [])
                if str(kp_id) not in focus_set
            ],
        })
    if not normalized:
        return normalized

    target_index = max(0, min(int(current_stage), len(normalized) - 1))
    target = normalized[target_index]
    target["title"] = PRIMARY_DEMO_FOCUS_STAGE_TITLE
    target["kp_ids"] = list(PRIMARY_DEMO_FOCUS_KPS)
    target["status"] = "current"
    if mastery_by_kp:
        values = [
            float(mastery_by_kp[kp_id])
            for kp_id in PRIMARY_DEMO_FOCUS_KPS
            if kp_id in mastery_by_kp
        ]
        if values:
            target["mastery_pct"] = round(sum(values) / len(values) * 100, 1)
    normalized[target_index] = target
    return normalized


def _seed_path_and_game(db: Any, user_id: str, display_name: str, persona: Persona, index: int, kp_ids: list[str], kp_name_by_id: dict[str, str], mastery_by_kp: dict[str, float], anchor_ts: float) -> None:
    from backend.app.core.models import GamificationProfileRecord, LearningPathRecord

    labels = ("基础诊断与补齐", "核心概念构建", "模型方法训练", "系统综合实践", "迁移与复盘")
    stages = []
    chunk_size = max(1, (len(kp_ids) + len(labels) - 1) // len(labels))
    current_stage = min(4, int(persona.mastery * 5))
    for stage_index, label in enumerate(labels):
        selected = kp_ids[stage_index * chunk_size:(stage_index + 1) * chunk_size] or [kp_ids[stage_index % len(kp_ids)]]
        stage_mastery = round(sum(mastery_by_kp[kp] for kp in selected) / len(selected) * 100, 1)
        stages.append({"id": f"stage-{stage_index + 1}", "title": label, "kp_ids": selected, "mastery_pct": stage_mastery, "progress_pct": 100.0 if stage_index < current_stage else 45.0 if stage_index == current_stage else 0.0, "status": "completed" if stage_index < current_stage else "current" if stage_index == current_stage else "pending"})
    if user_id == PRIMARY_DEMO_USER_ID:
        stages = _focus_video_path_stages(stages, current_stage, mastery_by_kp)
    weakest = PRIMARY_DEMO_FOCUS_KPS[0] if user_id == PRIMARY_DEMO_USER_ID else min(mastery_by_kp, key=mastery_by_kp.get)
    weakest_name = kp_name_by_id.get(weakest, weakest)
    second_task_title = "完成多模态专项练习与图文复盘" if user_id == PRIMARY_DEMO_USER_ID else "完成阶段小测"
    db.add(LearningPathRecord(id=f"{SOURCE}-{user_id}-path", user_id=user_id, title=f"{display_name}的人工智能学习路径", stages=stages, current_stage=current_stage, progress=round(sum(stage["progress_pct"] for stage in stages) / len(stages), 1), metadata_data={"source": SOURCE, "focus_kps": list(PRIMARY_DEMO_FOCUS_KPS) if user_id == PRIMARY_DEMO_USER_ID else [], "today_tasks": [{"id": f"task-{user_id}-1", "title": f"复习薄弱知识点「{weakest_name}」", "kp_id": weakest, "kp_name": weakest_name, "duration_minutes": 25, "status": "pending"}, {"id": f"task-{user_id}-2", "title": second_task_title, "duration_minutes": 20, "status": "pending"}], "milestones": [{"title": "完成基础阶段", "achieved": current_stage > 0}, {"title": "平均掌握度达到 80%", "achieved": persona.mastery >= 0.8}]}, created_at=anchor_ts - 45 * 86400, updated_at=anchor_ts - persona.last_active_days * 86400))
    db.flush()
    path_record = db.get(LearningPathRecord, f"{SOURCE}-{user_id}-path")
    if path_record is not None:
        path_record.metadata_data = {
            **(path_record.metadata_data or {}),
            "course": COURSE,
        }
    streak = max(0, 8 - persona.last_active_days) if persona.activity_level != "inactive" else 0
    db.add(GamificationProfileRecord(user_id=user_id, xp=round(persona.assessment_count * 42 + persona.mastery * 1000), level=max(1, min(10, round(persona.mastery * 10))), streak_days=streak, achievements=[{"code": "first_quiz", "label": "首次测评", "unlocked": True}, {"code": "streak_7d", "label": "连续学习 7 天", "unlocked": streak >= 7}], updated_at=anchor_ts - persona.last_active_days * 86400))


def _seed_collaboration_state_and_runs(db: Any, user_id: str, display_name: str, profile: dict[str, Any], persona: Persona, index: int, anchor_ts: float) -> None:
    from backend.app.core.models import AgentRunRecord, ChatHistoryRecord, GroupChatMessageRecord, LearnerArchetypeRecord, RealtimeStateRecord

    room_id = f"{COURSE}:{user_id}"
    messages = ("我想梳理本周薄弱知识点。", "这个概念可以换一个例子解释吗？", "我完成练习后会回来复盘。", "能推荐一位相近阶段的同伴吗？")
    for item in range(persona.collaboration_count):
        sender_role = "student" if item % 3 != 1 else "agent"
        db.add(GroupChatMessageRecord(id=f"{SOURCE}-g-{index + 1:02d}-{item + 1:02d}", room_id=room_id, sender_id=user_id if sender_role == "student" else "learning-coach", sender_name=display_name if sender_role == "student" else "学习教练", sender_role=sender_role, content=messages[item % len(messages)], message_type="text" if sender_role == "student" else "agent_reply", payload={"source": SOURCE}, created_at=anchor_ts - (persona.last_active_days * 86400 + item * 3600)))
    if persona.activity_level == "active":
        db.add(ChatHistoryRecord(session_id=f"demo-session-{user_id}", user_id=user_id, role="user", content="请帮我总结今天的学习重点。", created_at=anchor_ts - index * 1800))
        db.add(ChatHistoryRecord(session_id=f"demo-session-{user_id}", user_id=user_id, role="assistant", agent_name="学习教练", content="已结合你的掌握度与错题整理了三项重点。", created_at=anchor_ts - index * 1800 + 20))
    archetype_code = "high_achiever" if persona.mastery >= 0.75 else "effort_chaser" if persona.code == "active_low_mastery" else "rhythm_broken" if persona.activity_level != "active" else "stable_average"
    db.add(LearnerArchetypeRecord(user_id=user_id, archetype_code=archetype_code, archetype_data={"code": archetype_code, "name": {"high_achiever": "自驱引领者", "effort_chaser": "努力追赶者", "rhythm_broken": "节律失控型", "stable_average": "稳态中游型"}[archetype_code]}, updated_at=anchor_ts))
    confusion = round(
        _clamp(
            max(1 - persona.mastery, 0.55 if index == 9 or persona.mastery < 0.6 else 0),
            0,
            1,
        ),
        3,
    )
    db.add(RealtimeStateRecord(session_id=f"demo-session-{user_id}", user_id=user_id, state_data={"emotion": "confused" if confusion >= 0.5 else "neutral", "confusion": confusion, "fatigue": 0.65 if persona.activity_level != "active" else 0.2, "cognitive_load": round(0.35 + confusion * 0.4, 3), "engagement": "high" if persona.activity_level == "active" else "low", "next_best_action": "先完成薄弱知识点的 20 分钟复习，再进行小测。", "summary": "根据近期掌握度和活跃度生成"}, updated_at=anchor_ts - persona.last_active_days * 86400))
    run_count = 1 + index % 4 if persona.activity_level == "active" else 1
    for item in range(run_count):
        agent_count = 2 + (index + item) % 3
        success = not (persona.risk_level == "high" and item == run_count - 1 and index % 2 == 0)
        db.add(AgentRunRecord(id=f"{SOURCE}-run-{index + 1:02d}-{item + 1:02d}", session_id=f"workflow-{user_id}-{item + 1}", user_id=user_id, workflow_type=("path_planning", "learning_chat", "resource_generation")[item % 3], agents=["diagnosis", "planner", "reviewer", "coach"][:agent_count], tool_calls=agent_count + 1 + item, artifact_count=1 + item % 3, success_count=agent_count if success else max(0, agent_count - 1), duration_ms=700 + index * 35 + item * 180, status="success" if success else "failed", metadata_data={"source": SOURCE}, created_at=anchor_ts - (persona.last_active_days + item) * 86400))


def seed_business_data(session_factory: Any, anchor_date: str | date | datetime | None = None) -> dict[str, Any]:
    from backend.app.core.models import KnowledgePointRecord

    students = _load_students()
    anchor_ts = _anchor_timestamp(anchor_date)
    with session_factory() as db:
        try:
            kp_rows = db.query(KnowledgePointRecord).order_by(KnowledgePointRecord.id).all()
            if not kp_rows:
                raise RuntimeError("knowledge points must be seeded before business demo data")
            kp_ids = [row.id for row in kp_rows]
            kp_names = [row.name for row in kp_rows]
            kp_name_by_id = {row.id: row.name for row in kp_rows}
            _delete_demo_business_data(db)
            for index, student in enumerate(students):
                user_id = str(student["student_id"])
                persona = _persona(index)
                profile = _seed_profile(db, student, persona, index, anchor_ts)
                _seed_assessments(db, user_id, persona, index, kp_names, anchor_ts)
                mastery_by_kp = _seed_cognitive_data(db, user_id, persona, index, kp_ids, anchor_ts)
                _seed_mistakes_and_reviews(db, user_id, persona, index, kp_ids, mastery_by_kp, anchor_ts)
                _seed_path_and_game(db, user_id, profile["display_name"], persona, index, kp_ids, kp_name_by_id, mastery_by_kp, anchor_ts)
                _seed_collaboration_state_and_runs(db, user_id, profile["display_name"], profile, persona, index, anchor_ts)
            db.commit()
        except Exception:
            db.rollback()
            raise
    return audit_business_data(session_factory, anchor_ts=anchor_ts)


def top_up_demo_mistakes(
    session_factory: Any,
    anchor_date: str | date | datetime | None = None,
) -> dict[str, Any]:
    from sqlalchemy import func

    from backend.app.core.models import KnowledgePointRecord, MistakeRecord

    students = _load_students()
    anchor_ts = _anchor_timestamp(anchor_date)
    with session_factory() as db:
        try:
            kp_rows = db.query(KnowledgePointRecord).order_by(KnowledgePointRecord.id).all()
            if not kp_rows:
                raise RuntimeError("knowledge points must be seeded before topping up mistakes")
            before_total = (
                db.query(MistakeRecord)
                .filter(MistakeRecord.user_id.like("demo-student-%"))
                .count()
            )
            inserted = 0
            for index, student in enumerate(students):
                inserted += _top_up_user_mistakes(
                    db,
                    str(student["student_id"]),
                    _persona(index),
                    index,
                    kp_rows,
                    anchor_ts,
                )
            db.commit()
        except Exception:
            db.rollback()
            raise

        per_student = dict(
            db.query(MistakeRecord.user_id, func.count(MistakeRecord.id))
            .filter(MistakeRecord.user_id.like("demo-student-%"))
            .group_by(MistakeRecord.user_id)
            .all()
        )
        after_total = sum(per_student.values())
        unresolved_total = (
            db.query(MistakeRecord)
            .filter(
                MistakeRecord.user_id.like("demo-student-%"),
                MistakeRecord.resolved_at.is_(None),
            )
            .count()
        )
        error_codes = sorted(
            code
            for (code,) in db.query(MistakeRecord.error_type)
            .filter(MistakeRecord.user_id.like("demo-student-%"))
            .distinct()
            .all()
        )
        expected_users = {str(student["student_id"]) for student in students}
        complete = set(per_student) == expected_users and all(
            _target_mistake_count(_persona(index), index)
            <= per_student[str(student["student_id"])]
            <= 20
            for index, student in enumerate(students)
        )
        return {
            "mode": "top_up_mistakes",
            "before_total": before_total,
            "after_total": after_total,
            "inserted": inserted,
            "unresolved_total": unresolved_total,
            "unresolved_ratio_pct": round(unresolved_total / after_total * 100, 1) if after_total else 0.0,
            "error_codes": error_codes,
            "per_student": per_student,
            "complete": complete,
            "anchor_ts": anchor_ts,
        }


def prepare_video_demo_account(
    session_factory: Any,
    user_id: str = PRIMARY_DEMO_USER_ID,
    display_name: str = PRIMARY_DEMO_DISPLAY_NAME,
    max_open_mistakes: int = 8,
) -> dict[str, Any]:
    """Normalize the primary synthetic learner into one coherent recording persona."""
    from backend.app.core.models import (
        BktStateRecord,
        GroupChatMessageRecord,
        LearningPathRecord,
        MistakeRecord,
        ProfileRecord,
        ProfileSnapshotRecord,
        ResourceRecord,
    )

    canonical_path_id = f"{SOURCE}-{user_id}-path"
    changed = 0
    removed_paths = 0
    resolved_mistakes = 0
    now = time.time()

    with session_factory() as db:
        try:
            profile = db.get(ProfileRecord, user_id)
            if profile is None:
                raise RuntimeError(f"profile_not_found: {user_id}")
            profile_data = dict(profile.profile_data or {})
            if (
                profile_data.get("display_name") != display_name
                or profile_data.get("nickname") != display_name
            ):
                profile.profile_data = {
                    **profile_data,
                    "display_name": display_name,
                    "nickname": display_name,
                }
                profile.version = max(1, int(profile.version or 0)) + 1
                profile.updated_at = now
                changed += 1

            for snapshot in (
                db.query(ProfileSnapshotRecord)
                .filter(ProfileSnapshotRecord.user_id == user_id)
                .all()
            ):
                data = dict(snapshot.profile_data or {})
                if data.get("display_name") != display_name or data.get("nickname") != display_name:
                    snapshot.profile_data = {
                        **data,
                        "display_name": display_name,
                        "nickname": display_name,
                    }
                    changed += 1

            canonical_path = db.get(LearningPathRecord, canonical_path_id)
            if canonical_path is None:
                raise RuntimeError(f"canonical_path_not_found: {canonical_path_id}")
            other_paths = (
                db.query(LearningPathRecord)
                .filter(
                    LearningPathRecord.user_id == user_id,
                    LearningPathRecord.id != canonical_path_id,
                )
                .all()
            )
            for path in other_paths:
                db.delete(path)
                removed_paths += 1
            canonical_path.title = f"{display_name}的人工智能学习路径"
            # 录制账号保持“基础较强、在多模态关键环节有明确短板”的可解释状态。
            # 其余基础知识点维持较高掌握度，避免大屏把无关的 RNN/NLP 排在首位。
            for state in (
                db.query(BktStateRecord)
                .filter(BktStateRecord.user_id == user_id)
                .all()
            ):
                target = PRIMARY_DEMO_FOCUS_MASTERIES.get(state.knowledge_point_id)
                desired = target if target is not None else max(float(state.p_learned), 0.82)
                if abs(float(state.p_learned) - desired) >= 0.001:
                    state.p_learned = desired
                    state.updated_at = now
                    changed += 1
            focus_masteries = {
                row.knowledge_point_id: float(row.p_learned)
                for row in (
                    db.query(BktStateRecord)
                    .filter(
                        BktStateRecord.user_id == user_id,
                        BktStateRecord.knowledge_point_id.in_(PRIMARY_DEMO_FOCUS_KPS),
                    )
                    .all()
                )
            }
            canonical_path.stages = _focus_video_path_stages(
                list(canonical_path.stages or []),
                int(canonical_path.current_stage or 0),
                focus_masteries,
            )
            canonical_path.metadata_data = {
                **(canonical_path.metadata_data or {}),
                "course": COURSE,
                "active": True,
                "demo_profile": display_name,
                "recording_ready": True,
                "focus_kps": list(PRIMARY_DEMO_FOCUS_KPS),
                "today_tasks": [
                    {
                        "id": f"task-{user_id}-1",
                        "title": "复习薄弱知识点「多模态大模型」",
                        "kp_id": PRIMARY_DEMO_FOCUS_KPS[0],
                        "kp_name": "多模态大模型",
                        "duration_minutes": 25,
                        "status": "pending",
                    },
                    {
                        "id": f"task-{user_id}-2",
                        "title": "完成多模态专项练习与图文复盘",
                        "kp_id": PRIMARY_DEMO_FOCUS_KPS[0],
                        "kp_name": "多模态大模型",
                        "duration_minutes": 20,
                        "status": "pending",
                    },
                ],
            }
            canonical_path.updated_at = now
            changed += 1

            unresolved = (
                db.query(MistakeRecord)
                .filter(
                    MistakeRecord.user_id == user_id,
                    MistakeRecord.resolved_at.is_(None),
                )
                .order_by(MistakeRecord.created_at.desc())
                .all()
            )
            existing_focus_mistakes = {}
            for mistake in unresolved:
                case = PRIMARY_DEMO_MISTAKE_CASES.get(mistake.knowledge_point_id or "")
                if case is None:
                    mistake.resolved_at = min(now, max(float(mistake.created_at) + 3600, now - 86400))
                    resolved_mistakes += 1
                    continue
                existing_focus_mistakes.setdefault(mistake.knowledge_point_id, mistake)

            for kp_id, case in PRIMARY_DEMO_MISTAKE_CASES.items():
                mistake = existing_focus_mistakes.get(kp_id)
                if mistake is None:
                    mistake = MistakeRecord(
                        id=f"{SOURCE}-{user_id}-multimodal-{kp_id}",
                        user_id=user_id,
                        knowledge_point_id=kp_id,
                        created_at=now,
                    )
                    db.add(mistake)
                question_data = {
                    "question": case["question"],
                    "stem": case["question"],
                    "student_answer": case["student_answer"],
                    "correct_answer": case["correct_answer"],
                    "topic": "多模态大模型与跨模态对齐",
                }
                if (
                    mistake.question_data != question_data
                    or mistake.error_type != case["error_type"]
                    or mistake.analysis != case["analysis"]
                    or mistake.resolved_at is not None
                ):
                    mistake.question_data = question_data
                    mistake.error_type = case["error_type"]
                    mistake.analysis = case["analysis"]
                    mistake.resolved_at = None
                    changed += 1

            for message in (
                db.query(GroupChatMessageRecord)
                .filter(GroupChatMessageRecord.sender_id == user_id)
                .all()
            ):
                if message.sender_name != display_name:
                    message.sender_name = display_name
                    changed += 1
            for message in (
                db.query(GroupChatMessageRecord)
                .filter(GroupChatMessageRecord.content.contains("@小明"))
                .all()
            ):
                message.content = message.content.replace("@小明", f"@{display_name}")
                changed += 1

            for resource in (
                db.query(ResourceRecord)
                .filter(ResourceRecord.user_id == user_id)
                .all()
            ):
                title = str(resource.title or "")
                normalized = title.replace("小明专属", f"{display_name}专属", 1)
                if normalized != title:
                    resource.title = normalized
                    changed += 1

            db.commit()
        except Exception:
            db.rollback()
            raise

    audit = audit_business_data(session_factory)
    with session_factory() as db:
        path_count = (
            db.query(LearningPathRecord)
            .filter(LearningPathRecord.user_id == user_id)
            .count()
        )
        open_mistakes = (
            db.query(MistakeRecord)
            .filter(
                MistakeRecord.user_id == user_id,
                MistakeRecord.resolved_at.is_(None),
            )
            .count()
        )
        profile = db.get(ProfileRecord, user_id)
        profile_data = dict(profile.profile_data or {}) if profile else {}

    complete = (
        bool(audit.get("complete"))
        and path_count == 1
        and open_mistakes <= max_open_mistakes
        and profile_data.get("display_name") == display_name
    )
    return {
        "mode": "prepare_video_account",
        "user_id": user_id,
        "display_name": profile_data.get("display_name", ""),
        "path_count": path_count,
        "open_mistakes": open_mistakes,
        "removed_paths": removed_paths,
        "resolved_mistakes": resolved_mistakes,
        "changed_records": changed,
        "complete": complete,
        "business_audit": audit,
    }


def audit_business_data(session_factory: Any, anchor_ts: float | None = None) -> dict[str, Any]:
    from backend.app.core.models import (
        AgentRunRecord, AssessmentRecord, BktStateRecord, DinaStateRecord,
        GamificationProfileRecord, GroupChatMessageRecord, LearnerArchetypeRecord,
        LearningPathRecord, MistakeRecord, ProfileRecord, ProfileSnapshotRecord,
        RealtimeStateRecord, ReviewEventRecord, Sm2ScheduleRecord,
    )

    models = {"profiles": ProfileRecord, "profile_snapshots": ProfileSnapshotRecord, "assessments": AssessmentRecord, "mistakes": MistakeRecord, "bkt_states": BktStateRecord, "dina_states": DinaStateRecord, "sm2_schedule": Sm2ScheduleRecord, "learning_paths": LearningPathRecord, "gamification_profiles": GamificationProfileRecord, "group_chat_messages": GroupChatMessageRecord, "learner_archetypes": LearnerArchetypeRecord, "realtime_states": RealtimeStateRecord, "review_events": ReviewEventRecord, "agent_runs": AgentRunRecord}
    user_models = {name: model for name, model in models.items() if hasattr(model, "user_id") and name != "profile_snapshots"}
    with session_factory() as db:
        demo_users = {row[0] for row in db.query(ProfileRecord.user_id).filter(ProfileRecord.user_id.like("demo-student-%")).all()}
        coverage = {}
        for name, model in user_models.items():
            coverage[name] = len({row[0] for row in db.query(model.user_id).filter(model.user_id.like("demo-student-%")).distinct().all()})
        path_counts = dict(db.query(LearningPathRecord.user_id, __import__("sqlalchemy").func.count(LearningPathRecord.id)).filter(LearningPathRecord.user_id.like("demo-student-%")).group_by(LearningPathRecord.user_id).all())
        required = ("assessments", "mistakes", "bkt_states", "dina_states", "sm2_schedule", "learning_paths", "gamification_profiles", "learner_archetypes", "realtime_states", "agent_runs")
        complete = len(demo_users) == 20 and all(coverage.get(name) == 20 for name in required) and all(count == 1 for count in path_counts.values())
        return {"demo_students": len(demo_users), "table_counts": {name: db.query(model).count() for name, model in models.items()}, "student_coverage": coverage, "complete": complete, "anchor_ts": anchor_ts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed non-library demo business data")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="audit only; do not write")
    mode.add_argument(
        "--top-up-mistakes",
        action="store_true",
        help="only add missing demo-student mistake records and review schedules",
    )
    mode.add_argument(
        "--prepare-video-account",
        action="store_true",
        help="normalize demo-student-1 for a coherent competition-video walkthrough",
    )
    parser.add_argument("--db", default="", help="optional SQLAlchemy database URL")
    parser.add_argument("--anchor-date", default="", help="deterministic anchor date in YYYY-MM-DD format")
    args = parser.parse_args()

    from backend.app.core.database import SessionLocal, configure_database, init_db

    if args.db:
        configure_database(args.db)
    init_db()
    if args.check:
        result = audit_business_data(SessionLocal)
    elif args.top_up_mistakes:
        result = top_up_demo_mistakes(SessionLocal, anchor_date=args.anchor_date or None)
    elif args.prepare_video_account:
        result = prepare_video_demo_account(SessionLocal)
    else:
        result = seed_business_data(SessionLocal, anchor_date=args.anchor_date or None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("complete") else 1


if __name__ == "__main__":
    raise SystemExit(main())
