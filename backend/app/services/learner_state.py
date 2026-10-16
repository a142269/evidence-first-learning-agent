"""Plan P1-7：LearnerState 中台 — 统一学习者状态聚合

聚合多源数据：
  - 画像（profile_repo + profile snapshot history）
  - 掌握度（BKT + DINA 平均）
  - 错因（mistakes 分类分布）
  - 复习计划（SM2 schedule，按 due_at 排序）
  - 资源使用（resources 表按 type 统计）
  - 策略历史（learning_paths.metadata.adjustments）
  - 评估汇总（assessments 计数 + 最近 N 条）

API:
  GET /api/v1/learner-state/{user_id}      → 当前快照 + 推荐解释
  GET /api/v1/learner-state/{user_id}/timeline → 事件流

设计取舍：
  - 全模块懒加载，避免循环导入
  - 单字段 fetch 失败不破坏整体（用空 dict 占位 + error 字段）
  - version 取自 profile.version 与 snapshot.count 的复合值
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 单字段抓取：每个函数独立 try/except，单点失败不破坏整体
# ============================================================
def _fetch_profile(user_id: str) -> Dict[str, Any]:
    from backend.app.repositories.profile_repo import ProfileRepository

    repo = ProfileRepository()
    profile = repo.get(user_id) or {}
    history = repo.history(user_id, limit=20)
    return {
        "profile": profile,
        "version": (profile.get("__version__") or 0),
        "snapshot_count": len(history),
        "snapshots": history[:5],
    }


def _fetch_mastery(user_id: str) -> Dict[str, Any]:
    """聚合 BKT + DINA：每个 KP 取 BKT p_learned 和 DINA mastery 的平均。"""
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import BktStateRecord, DinaStateRecord

    out: Dict[str, Dict[str, float]] = {}
    try:
        with SessionLocal() as db:
            for row in db.query(BktStateRecord).filter(BktStateRecord.user_id == user_id).all():
                out.setdefault(row.knowledge_point_id, {})["bkt_p_learned"] = float(row.p_learned or 0.0)
            for row in db.query(DinaStateRecord).filter(DinaStateRecord.user_id == user_id).all():
                out.setdefault(row.knowledge_point_id, {})["dina_mastery"] = float(row.mastery or 0.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner-state] mastery fetch failed: %s", exc)

    aggregate: List[Dict[str, Any]] = []
    for kp_id, scores in out.items():
        bkt = scores.get("bkt_p_learned")
        dina = scores.get("dina_mastery")
        if bkt is None:
            avg = dina
        elif dina is None:
            avg = bkt
        else:
            avg = (bkt + dina) / 2.0
        aggregate.append({
            "kp_id": kp_id,
            "bkt_p_learned": round(bkt, 3) if bkt is not None else None,
            "dina_mastery": round(dina, 3) if dina is not None else None,
            "average": round(avg, 3) if avg is not None else None,
        })
    aggregate.sort(key=lambda x: x.get("average") or 0.0, reverse=True)
    return {"items": aggregate, "total": len(aggregate)}


def _fetch_mistake_attribution(user_id: str, limit: int = 10) -> Dict[str, Any]:
    try:
        from backend.app.api.v1.mistakes import _gather_user_records
        records = _gather_user_records(user_id) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner-state] mistakes fetch failed: %s", exc)
        return {"total": 0, "category_distribution": {}, "latest": [], "error": str(exc)}
    dist = Counter((r.get("error_type") or "unknown") for r in records)
    latest = [
        {
            "id": r.get("id"),
            "kp_id": r.get("kp_id") or r.get("knowledge_point_id") or "",
            "question": (r.get("question") or "")[:120],
            "student_answer": (r.get("student_answer") or "")[:80],
            "correct_answer": (r.get("correct_answer") or "")[:80],
            "error_type": r.get("error_type") or "unknown",
            "created_at": r.get("created_at") or 0,
            "resolved_at": r.get("resolved_at") or 0,
            "resolved": bool(r.get("resolved")) or bool(r.get("resolved_at")),
        }
        for r in records[:limit]
    ]
    return {
        "total": len(records),
        "category_distribution": dict(dist),
        "latest": latest,
    }

def _fetch_review_schedule(user_id: str, limit: int = 10) -> Dict[str, Any]:
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import Sm2ScheduleRecord

    items: List[Dict[str, Any]] = []
    try:
        with SessionLocal() as db:
            rows = (
                db.query(Sm2ScheduleRecord)
                .filter(Sm2ScheduleRecord.user_id == user_id)
                .order_by(Sm2ScheduleRecord.due_at.asc())
                .limit(limit)
                .all()
            )
            for r in rows:
                items.append({
                    "item_id": r.item_id,
                    "item_type": r.item_type,
                    "repetitions": r.repetitions,
                    "interval_days": r.interval_days,
                    "easiness": r.easiness,
                    "due_at": r.due_at,
                    "overdue": bool(r.due_at and r.due_at < time.time()),
                })
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner-state] sm2 fetch failed: %s", exc)
        return {"items": [], "total": 0, "error": str(exc)}
    return {"items": items, "total": len(items)}


def _fetch_resource_usage(user_id: str) -> Dict[str, Any]:
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import ResourceRecord

        type_dist: Counter = Counter()
        recent: List[Dict[str, Any]] = []
        with SessionLocal() as db:
            rows = (
                db.query(ResourceRecord)
                .filter(ResourceRecord.user_id == user_id)
                .order_by(ResourceRecord.created_at.desc())
                .limit(20)
                .all()
            )
            for r in rows:
                type_dist[r.type] += 1
                recent.append({
                    "id": r.id,
                    "type": r.type,
                    "title": (r.title or "")[:80],
                    "agent_name": r.agent_name,
                    "created_at": r.created_at,
                    "tags": list(r.tags or []),
                })
        return {
            "type_distribution": dict(type_dist),
            "total_resources": sum(type_dist.values()),
            "recent": recent[:5],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner-state] resources fetch failed: %s", exc)
        return {"total_resources": 0, "type_distribution": {}, "recent": [], "error": str(exc)}


def _fetch_strategy_history(user_id: str) -> Dict[str, Any]:
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import LearningPathRecord

    paths: List[Dict[str, Any]] = []
    adjustments: List[Dict[str, Any]] = []
    try:
        with SessionLocal() as db:
            rows = db.query(LearningPathRecord).filter(LearningPathRecord.user_id == user_id).all()
            for r in rows:
                meta = dict(r.metadata_data or {})
                paths.append({
                    "id": r.id,
                    "title": r.title,
                    "current_stage": r.current_stage,
                    "progress": r.progress,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                })
                adjustments.extend(meta.get("adjustments") or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner-state] paths fetch failed: %s", exc)
        return {"paths": [], "adjustments": [], "error": str(exc)}
    return {"paths": paths, "adjustments": adjustments}


def _fetch_assessment_summary(user_id: str, limit: int = 5) -> Dict[str, Any]:
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import AssessmentRecord

    type_dist: Counter = Counter()
    recent: List[Dict[str, Any]] = []
    score_samples: List[float] = []
    try:
        with SessionLocal() as db:
            rows = (
                db.query(AssessmentRecord)
                .filter(AssessmentRecord.user_id == user_id)
                .order_by(AssessmentRecord.timestamp.desc())
                .limit(50)
                .all()
            )
            for r in rows:
                type_dist[r.record_type] += 1
                if isinstance(r.score, (int, float)):
                    score_samples.append(float(r.score))
                recent.append({
                    "id": r.id,
                    "external_id": r.external_id,
                    "record_type": r.record_type,
                    "score": r.score,
                    "topic": r.topic,
                    "timestamp": r.timestamp,
                })
    except Exception as exc:  # noqa: BLE001
        logger.warning("[learner-state] assessment fetch failed: %s", exc)
        return {"total": 0, "type_distribution": {}, "average_score": None, "recent": [], "error": str(exc)}
    return {
        "total": sum(type_dist.values()),
        "type_distribution": dict(type_dist),
        "average_score": round(sum(score_samples) / len(score_samples), 2) if score_samples else None,
        "recent": recent[:limit],
    }


# ============================================================
# 主服务
# ================================================================
class LearnerStateService:
    """统一学习者状态聚合 —— 单写入口记录版本。"""

    def snapshot(self, user_id: str) -> Dict[str, Any]:
        profile_block = _fetch_profile(user_id)
        mastery = _fetch_mastery(user_id)
        mistakes = _fetch_mistake_attribution(user_id)
        schedule = _fetch_review_schedule(user_id)
        resources = _fetch_resource_usage(user_id)
        strategy = _fetch_strategy_history(user_id)
        assessment = _fetch_assessment_summary(user_id)

        # 推荐解释：用一段简短的文字解释为什么这么推荐
        top_weak = [
            m for m in (mastery.get("items") or []) if (m.get("average") or 1.0) < 0.6
        ][:3]
        if not top_weak:
            top_weak = (mastery.get("items") or [])[-3:]
        due_count = sum(1 for it in schedule.get("items", []) if it.get("overdue"))
        recommendation = {
            "focus_kps": [
                {"kp_id": m.get("kp_id"), "average": m.get("average")} for m in top_weak
            ],
            "overdue_reviews": due_count,
            "primary_error_type": next(
                iter(mistakes.get("category_distribution", {}).items()), None,
            ),
            "resource_count": resources.get("total_resources", 0),
            "why": (
                "基于你最近 N 条答题的 BKT/DINA 状态，选出掌握度 < 0.6 的知识点优先复习；"
                "错题分类告诉你最常见的失误模式；SM-2 调度决定今天该复习哪些；"
                "近期生成的多模态资源会作为讲解材料。"
            ),
        }

        # 综合 version
        version = (
            int(profile_block.get("version") or 0)
            + mastery.get("total", 0)
            + mistakes.get("total", 0)
            + schedule.get("total", 0)
            + resources.get("total_resources", 0)
            + len(strategy.get("adjustments", []))
            + assessment.get("total", 0)
        )

        return {
            "user_id": user_id,
            "version": version,
            "generated_at": time.time(),
            "profile": profile_block,
            "mastery": mastery,
            "mistakes": mistakes,
            "review_schedule": schedule,
            "resources": resources,
            "strategy": strategy,
            "assessment": assessment,
            "recommendation": recommendation,
        }

    def timeline(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """事件流：合并画像快照 + 路径调整 + 错题 + 评估 + 资源生成，按时间倒序。"""
        events: List[Dict[str, Any]] = []
        errors: List[str] = []

        try:
            profile_block = _fetch_profile(user_id)
            for snap in profile_block.get("snapshots", []):
                events.append({
                    "type": "profile_snapshot",
                    "timestamp": snap.get("created_at", 0),
                    "version": snap.get("version"),
                    "source": snap.get("source"),
                    "changed_keys": snap.get("changed_keys", []),
                })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"profile_snapshots: {exc}")

        try:
            strategy = _fetch_strategy_history(user_id)
            for adj in strategy.get("adjustments", []):
                ts = adj.get("adjusted_at")
                events.append({
                    "type": "path_adjustment",
                    "timestamp": ts if isinstance(ts, (int, float)) else 0,
                    "id": adj.get("id"),
                    "reason": adj.get("reason", ""),
                    "before": adj.get("before"),
                    "after": adj.get("after"),
                    "added_kp_focus": adj.get("added_kp_focus", []),
                })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"path_adjustments: {exc}")

        try:
            mistakes = _fetch_mistake_attribution(user_id, limit=20)
            for m in mistakes.get("latest", []):
                # 丰富错题事件：添加题目摘要、学生答案、正确答案
                question = m.get("question") or ""
                question_short = question[:60] + ("…" if len(question) > 60 else "")
                student_ans = m.get("student_answer") or ""
                correct_ans = m.get("correct_answer") or ""
                error_type = m.get("error_type") or "未知"

                # 生成可读描述
                if m.get("resolved"):
                    desc = f"已攻克 [{m.get('kp_id', '?')}] {error_type} 错题"
                else:
                    desc = f"新增错题 [{m.get('kp_id', '?')}] {error_type}"

                events.append({
                    "type": "mistake_recorded",
                    "timestamp": m.get("resolved_at") or m.get("created_at") or 0,
                    "mistake_id": m.get("id"),
                    "kp_id": m.get("kp_id"),
                    "error_type": error_type,
                    "resolved": m.get("resolved"),
                    "question": question_short,
                    "student_answer": student_ans[:40],
                    "correct_answer": correct_ans[:40],
                    "description": desc,
                })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"mistakes: {exc}")

        try:
            assessment = _fetch_assessment_summary(user_id, limit=20)
            for r in assessment.get("recent", []):
                events.append({
                    "type": "assessment",
                    "timestamp": r.get("timestamp", 0),
                    "record_type": r.get("record_type"),
                    "score": r.get("score"),
                    "topic": r.get("topic"),
                })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"assessments: {exc}")

        try:
            resources = _fetch_resource_usage(user_id)
            for r in resources.get("recent", []):
                events.append({
                    "type": "resource_generated",
                    "timestamp": r.get("created_at", 0),
                    "resource_id": r.get("id"),
                    "resource_type": r.get("type"),
                    "agent": r.get("agent_name"),
                    "title": r.get("title"),
                })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"resources: {exc}")

        # 排序与截断
        events.sort(key=lambda e: e.get("timestamp") or 0, reverse=True)
        events = events[:limit]

        return {
            "user_id": user_id,
            "events": events,
            "total": len(events),
            "errors": errors,
        }


_service: Optional[LearnerStateService] = None


def get_learner_state_service() -> LearnerStateService:
    global _service
    if _service is None:
        _service = LearnerStateService()
    return _service
