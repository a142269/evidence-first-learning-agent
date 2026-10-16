"""教师管理端 API — 资源建设 / 学情分析 / Agent 配置 / 路径推荐 / 消息干预。

设计原则:
- 教师是课程群聊的真实成员：指派资源、推荐路径、发消息都会写入
  room_id = course:student_id 的群聊房间，学生刷新即可看到。
- 资源复用现有 ResourceRecord（persist_resource 双写内存+SQLite），
  metadata 标准化为 {course, scope, status, created_by, target_user_ids, kp_ids}。
- Agent 管理走配置型 Agent（AgentConfigService），不允许上传任意代码。
"""
from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from backend.app.api.v1.resources import delete_resource_record, get_resource_dict, persist_resource
from backend.app.repositories.group_chat_repo import build_room_id, get_group_chat_repo
from backend.app.services.agent_config_service import get_agent_config_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teacher", tags=["teacher"])

DEFAULT_COURSE = "artificial_intelligence"


class StudentAccountRecoveryRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)

# 教师资料原件单独落盘，资源表仅保存受控的相对 storage_key，避免把客户端
# 文件名或任意绝对路径直接用于下载。
_TEACHER_UPLOAD_ROOT = Path(__file__).resolve().parents[4] / "data" / "teacher_uploads"
_MAX_TEACHER_UPLOAD_BYTES = 20 * 1024 * 1024
_MAX_TEACHER_VIDEO_UPLOAD_BYTES = 200 * 1024 * 1024
_ALLOWED_TEACHER_UPLOAD_SUFFIXES = frozenset({
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".txt", ".md", ".csv", ".json", ".py", ".ipynb", ".zip",
    ".mp4", ".webm", ".mov", ".m4v",
})
_VIDEO_UPLOAD_SUFFIXES = frozenset({".mp4", ".webm", ".mov", ".m4v"})
_UPLOAD_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".py": "text/x-python; charset=utf-8",
    ".ipynb": "application/x-ipynb+json",
    ".zip": "application/zip",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
}
_TEXT_UPLOAD_SUFFIXES = frozenset({".txt", ".md", ".csv", ".json", ".py"})

# 非学生账号（教师端学生列表需要排除）
_NON_STUDENT_ACCOUNTS = frozenset({"teacher", "counselor", "admin", "smoke-adaptive-1", "u-smart-record"})


def _safe_upload_filename(filename: str) -> str:
    """返回去路径化后的文件名；Windows 反斜杠同样不能穿透存储目录。"""
    cleaned = Path(str(filename or "").replace("\\", "/")).name.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(status_code=400, detail="filename_required")
    return cleaned[:180]


def _resolve_teacher_upload(storage_key: str) -> Path | None:
    """仅允许由服务端生成的文件键映射到教师上传目录。"""
    filename = Path(str(storage_key or "")).name
    if not filename or filename != storage_key:
        return None
    root = _TEACHER_UPLOAD_ROOT.resolve()
    target = (root / filename).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _upload_size_limit(suffix: str) -> int:
    """课程视频单独放宽容量，其他教学资料保持较小、可控的上限。"""
    return _MAX_TEACHER_VIDEO_UPLOAD_BYTES if suffix in _VIDEO_UPLOAD_SUFFIXES else _MAX_TEACHER_UPLOAD_BYTES


def _delete_uploaded_attachment(resource: Dict[str, Any] | None) -> None:
    attachment = ((resource or {}).get("metadata") or {}).get("attachment") or {}
    target = _resolve_teacher_upload(str(attachment.get("storage_key", "")))
    if target is None:
        return
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("[teacher] delete uploaded attachment failed: %s", exc)


# ================================================================
# 学生列表 & 学情聚合
# ================================================================
def _collect_student_ids() -> List[str]:
    """从画像/评估/错题表聚合出现过的学生 ID。"""
    ids: set[str] = set()
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import (
            AssessmentRecord,
            BktStateRecord,
            MistakeRecord,
            ProfileRecord,
        )

        with SessionLocal() as db:
            for (uid,) in db.query(ProfileRecord.user_id).all():
                ids.add(uid)
            for (uid,) in db.query(AssessmentRecord.user_id).distinct().all():
                ids.add(uid)
            for (uid,) in db.query(MistakeRecord.user_id).distinct().all():
                ids.add(uid)
            for (uid,) in db.query(BktStateRecord.user_id).distinct().all():
                ids.add(uid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] collect students failed: %s", exc)

    ids.add("demo-student-1")  # 演示学生兜底
    return sorted(
        uid for uid in ids
        if uid and uid not in _NON_STUDENT_ACCOUNTS and not uid.startswith("sess_")
    )


def _student_brief(user_id: str) -> Dict[str, Any]:
    """学生列表行：掌握度均值 / 未解决错题数 / 最近活跃时间。"""
    mastery_avg = None
    mistakes_open = 0
    last_active = 0.0
    display_name = user_id
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import (
            AssessmentRecord,
            BktStateRecord,
            MistakeRecord,
            ProfileRecord,
        )
        from sqlalchemy import func

        with SessionLocal() as db:
            profile = db.get(ProfileRecord, user_id)
            profile_data = dict(profile.profile_data or {}) if profile else {}
            display_name = str(
                profile_data.get("display_name")
                or profile_data.get("nickname")
                or user_id
            )
            avg = (
                db.query(func.avg(BktStateRecord.p_learned))
                .filter(BktStateRecord.user_id == user_id)
                .scalar()
            )
            mastery_avg = round(float(avg), 3) if avg is not None else None
            mistakes_open = (
                db.query(func.count(MistakeRecord.id))
                .filter(
                    MistakeRecord.user_id == user_id,
                    MistakeRecord.resolved_at.is_(None),
                )
                .scalar()
                or 0
            )
            ts = (
                db.query(func.max(AssessmentRecord.timestamp))
                .filter(AssessmentRecord.user_id == user_id)
                .scalar()
            )
            last_active = float(ts) if ts else 0.0
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] student brief failed for %s: %s", user_id, exc)

    return {
        "user_id": user_id,
        "display_name": display_name,
        "course": DEFAULT_COURSE,
        "mastery_avg": mastery_avg,
        "mistakes_open": int(mistakes_open),
        "last_active": last_active,
    }


def _unified_student_brief(user_id: str) -> Dict[str, Any]:
    """Build teacher-facing student facts from the shared overview service."""
    try:
        from backend.app.api.v1.auth import is_default_account
        from backend.app.services.student_overview import build_student_overview

        overview = build_student_overview(user_id)
        summary = overview.get("summary") or {}
        profile = overview.get("profile") or {}
        recent = (overview.get("assessment") or {}).get("recent") or []
        mastery_pct = summary.get("average_mastery_pct")
        return {
            "user_id": user_id,
            "display_name": str(profile.get("display_name") or user_id),
            "course": DEFAULT_COURSE,
            "mastery_avg": (
                round(float(mastery_pct) / 100, 3)
                if mastery_pct is not None
                else None
            ),
            "mistakes_open": int(summary.get("unresolved_mistake_count") or 0),
            "last_active": float(recent[0].get("timestamp") or 0) if recent else 0.0,
            "profile_completeness_pct": float(
                summary.get("profile_completeness_pct") or 0
            ),
            "deletable": not is_default_account(user_id),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] unified student brief failed for %s: %s", user_id, exc)
        fallback = _student_brief(user_id)
        fallback["profile_completeness_pct"] = 0.0
        from backend.app.api.v1.auth import is_default_account
        fallback["deletable"] = not is_default_account(user_id)
        return fallback


def _activity_level(last_active: float, now: float) -> str:
    if not last_active:
        return "inactive"
    idle = now - last_active
    if idle <= 7 * _DAY_SECONDS:
        return "active"
    if idle <= 30 * _DAY_SECONDS:
        return "dormant"
    return "inactive"


def _unified_risk_assessment(brief: Dict[str, Any], now: float) -> Dict[str, Any]:
    mastery = brief.get("mastery_avg")
    mistakes = int(brief.get("mistakes_open") or 0)
    activity_level = _activity_level(float(brief.get("last_active") or 0), now)
    mastery_score = (1.0 - float(mastery)) * 55 if mastery is not None else 28.0
    mistake_score = min(float(mistakes) * 3.0, 25.0)
    inactivity_score = {"active": 0.0, "dormant": 15.0, "inactive": 30.0}[activity_level]
    risk_score_pct = round(min(100.0, mastery_score + mistake_score + inactivity_score), 1)
    level = "high" if risk_score_pct >= 65 else "medium" if risk_score_pct >= 40 else "low"

    reasons: List[str] = []
    if mastery is not None and mastery < 0.55:
        reasons.append(f"平均掌握度偏低（{mastery:.0%}）")
    if mistakes >= 10:
        reasons.append(f"未解决错题积压 {mistakes} 道")
    elif mistakes >= 5:
        reasons.append(f"仍有 {mistakes} 道错题待复习")
    if activity_level == "dormant":
        reasons.append("已停学 8–30 天")
    elif activity_level == "inactive":
        reasons.append("超过 30 天未活跃")
    if not reasons:
        reasons.append("近期学习状态稳定，保持当前节奏并持续复盘")

    return {
        "user_id": brief["user_id"],
        "display_name": brief.get("display_name") or brief["user_id"],
        "level": level,
        "risk_score_pct": risk_score_pct,
        "activity_level": activity_level,
        "mastery_avg": mastery,
        "mistakes_open": mistakes,
        "last_active": float(brief.get("last_active") or 0),
        "reasons": reasons,
    }


@router.get("/students")
def list_students() -> Dict[str, Any]:
    """学生列表与简要学情。"""
    students = [_unified_student_brief(uid) for uid in _collect_student_ids()]
    return {"students": students, "total": len(students)}


@router.post("/students/{user_id}/restore-account")
def restore_student_login(
    user_id: str,
    payload: StudentAccountRecoveryRequest,
) -> Dict[str, str]:
    """教师为已有学习数据、但登录凭据缺失的学生重新建立登录账号。"""
    from backend.app.api.v1.auth import is_default_account, restore_student_account

    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id_required")
    if is_default_account(user_id):
        raise HTTPException(status_code=409, detail="protected_demo_account")

    try:
        record = restore_student_account(user_id, payload.new_password)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "student_data_not_found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[teacher] restore student account failed for %s", user_id)
        raise HTTPException(status_code=500, detail="account_restore_failed") from exc

    return {
        "status": "restored",
        "user_id": record.account,
        "display_name": record.display_name,
    }


@router.delete("/students/{user_id}")
def delete_student(user_id: str) -> Dict[str, Any]:
    """Delete one test student's account sessions and private learning records."""
    from backend.app.api.v1.auth import (
        is_default_account,
        remove_registered_student_account,
    )
    from backend.app.services.student_data_deletion import delete_student_data

    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id_required")
    if is_default_account(user_id):
        raise HTTPException(status_code=409, detail="protected_demo_account")

    try:
        result = delete_student_data(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[teacher] delete student failed for %s", user_id)
        raise HTTPException(
            status_code=500,
            detail="student_data_delete_failed",
        ) from exc

    result["account_removed"] = remove_registered_student_account(user_id)
    result["status"] = "deleted"
    return result


@router.get("/students/{user_id}/summary")
def student_summary(user_id: str, course: str = Query(default=DEFAULT_COURSE)) -> Dict[str, Any]:
    """学情分析聚合：画像 / 掌握度 / 错题 / 学习路径 / 资源使用 / 风险提示。"""
    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id_required")

    summary: Dict[str, Any] = {
        "user_id": user_id,
        "course": course,
        "profile": {},
        "mastery": {"average": None, "weakest": [], "strongest": []},
        "mistakes": {"open_count": 0, "recent": []},
        "paths": [],
        "resources": {"total": 0, "recent": []},
        "risks": [],
    }

    # 画像
    try:
        from backend.app.repositories.profile_repo import ProfileRepository
        summary["profile"] = ProfileRepository().get(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] profile failed: %s", exc)

    # 掌握度（BKT p_learned）
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import BktStateRecord, KnowledgePointRecord

        with SessionLocal() as db:
            rows = (
                db.query(BktStateRecord)
                .filter(BktStateRecord.user_id == user_id)
                .all()
            )
            kp_names = {
                kp.id: kp.name
                for kp in db.query(KnowledgePointRecord).all()
            }
        if rows:
            items = sorted(rows, key=lambda r: r.p_learned)
            def _kp(r):
                return {
                    "kp_id": r.knowledge_point_id,
                    "kp_name": kp_names.get(r.knowledge_point_id, r.knowledge_point_id),
                    "mastery": round(float(r.p_learned), 3),
                }
            summary["mastery"] = {
                "average": round(sum(r.p_learned for r in rows) / len(rows), 3),
                "weakest": [_kp(r) for r in items[:5]],
                "strongest": [_kp(r) for r in reversed(items[-5:])],
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] mastery failed: %s", exc)

    # 错题
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import MistakeRecord

        with SessionLocal() as db:
            open_rows = (
                db.query(MistakeRecord)
                .filter(
                    MistakeRecord.user_id == user_id,
                    MistakeRecord.resolved_at.is_(None),
                )
                .order_by(MistakeRecord.created_at.desc())
                .limit(50)
                .all()
            )
        summary["mistakes"] = {
            "open_count": len(open_rows),
            "recent": [
                {
                    "id": r.id,
                    "kp_id": r.knowledge_point_id,
                    "error_type": r.error_type,
                    "question": (r.question_data or {}).get("question", "")[:120],
                    "created_at": r.created_at,
                }
                for r in open_rows[:8]
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] mistakes failed: %s", exc)

    # 学习路径
    try:
        from backend.app.repositories.path_repo import LearningPathRepository
        paths = LearningPathRepository().list(user_id=user_id)
        summary["paths"] = [
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "progress": p.get("progress", 0),
                "stages_count": len(p.get("stages") or []),
                "created_at": p.get("created_at", 0),
                "recommended_by": (p.get("metadata") or {}).get("recommended_by", ""),
            }
            for p in paths[:10]
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] paths failed: %s", exc)

    # 资源使用（该学生可见的个人资源）
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import ResourceRecord

        with SessionLocal() as db:
            rows = (
                db.query(ResourceRecord)
                .filter(ResourceRecord.user_id == user_id)
                .order_by(ResourceRecord.created_at.desc())
                .limit(20)
                .all()
            )
        summary["resources"] = {
            "total": len(rows),
            "recent": [
                {
                    "id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "created_at": r.created_at,
                }
                for r in rows[:8]
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] resources failed: %s", exc)

    # 风险提示（规则驱动，不依赖 LLM）
    risks: List[Dict[str, str]] = []
    mastery_avg = summary["mastery"].get("average")
    if mastery_avg is not None and mastery_avg < 0.4:
        risks.append({
            "level": "high",
            "message": f"整体掌握度偏低（{mastery_avg:.0%}），建议优先补基础知识点。",
        })
    if summary["mistakes"]["open_count"] >= 10:
        risks.append({
            "level": "high",
            "message": f"未解决错题积压 {summary['mistakes']['open_count']} 道，建议指派针对性练习资源。",
        })
    elif summary["mistakes"]["open_count"] >= 5:
        risks.append({
            "level": "medium",
            "message": f"未解决错题 {summary['mistakes']['open_count']} 道，可安排错题回顾。",
        })
    if not summary["profile"]:
        risks.append({
            "level": "low",
            "message": "尚未建立学习画像，建议引导学生先与 Agent 对话完成画像构建。",
        })
    if not summary["paths"]:
        risks.append({
            "level": "medium",
            "message": "该学生暂无学习路径，可在「路径推荐」页签为其生成并推送。",
        })
    summary["risks"] = risks
    return summary


# ================================================================
# 班级学情看板
# ================================================================
_DAY_SECONDS = 24 * 3600

_MASTERY_BUCKETS = (
    ("0-20", 0.0, 0.2),
    ("20-40", 0.2, 0.4),
    ("40-60", 0.4, 0.6),
    ("60-80", 0.6, 0.8),
    ("80-100", 0.8, 1.01),
)


def _normalize_score(value: float) -> float:
    """assessments.score 历史上混有 0-1 与 0-100 两种量纲，统一到 0-1。"""
    score = float(value)
    if score > 1.0:
        score /= 100.0
    return min(max(score, 0.0), 1.0)


def _risk_assessment(brief: Dict[str, Any], now: float) -> Dict[str, Any] | None:
    """规则版风险评级：≥2 项硬指标 high；1 项或掌握度<55% medium；55-70% 且错题 5-9 low。"""
    mastery = brief["mastery_avg"]
    mistakes = brief["mistakes_open"]
    last_active = brief["last_active"]

    reasons: List[str] = []
    if mastery is not None and mastery < 0.4:
        reasons.append(f"掌握度偏低（{mastery:.0%}）")
    if mistakes >= 10:
        reasons.append(f"未解决错题积压 {mistakes} 道")
    if not last_active:
        reasons.append("尚无学习活动记录")
    elif now - last_active > 30 * _DAY_SECONDS:
        reasons.append("超过 30 天未活跃")
    hard_hits = len(reasons)

    if hard_hits >= 2:
        level = "high"
    elif hard_hits == 1 or (mastery is not None and mastery < 0.55):
        level = "medium"
    elif mastery is not None and mastery < 0.7 and 5 <= mistakes <= 9:
        level = "low"
    else:
        return None

    if not reasons:
        reasons.append(f"掌握度中等偏弱（{mastery:.0%}），需持续关注")
    return {
        "user_id": brief["user_id"],
        "level": level,
        "mastery_avg": mastery,
        "mistakes_open": mistakes,
        "last_active": last_active,
        "reasons": reasons,
    }


@router.get("/analytics/class")
def class_analytics(
    course: str = Query(default=DEFAULT_COURSE),
    days: int = Query(default=30, ge=7, le=180),
    weak_top: int = Query(default=5, ge=1, le=20),
    risk_top: int = Query(default=6, ge=1, le=50),
) -> Dict[str, Any]:
    """班级学情看板聚合：KPI / 掌握度分布 / 薄弱知识点 / 错因分布 / 活跃度 / 风险学生。

    全部规则聚合不依赖 LLM；BKT/错题/活动三段查询相互独立，单段失败不影响整体。
    """
    # 直接调用时（如 _teaching_snapshot）Query 对象未被路由解析为标量
    if not isinstance(days, int):
        days = 30
    if not isinstance(weak_top, int):
        weak_top = 5
    if not isinstance(risk_top, int):
        risk_top = 6
    now = time.time()
    student_ids = _collect_student_ids()
    briefs = [_unified_student_brief(uid) for uid in student_ids]

    # ---- KPI 与活跃度分桶 ----
    mastery_values = [b["mastery_avg"] for b in briefs if b["mastery_avg"] is not None]
    active_7d: List[str] = []
    dormant_7_30: List[str] = []
    inactive_30p: List[str] = []
    for b in briefs:
        idle = (now - b["last_active"]) if b["last_active"] else None
        if idle is not None and idle <= 7 * _DAY_SECONDS:
            active_7d.append(b["user_id"])
        elif idle is not None and idle <= 30 * _DAY_SECONDS:
            dormant_7_30.append(b["user_id"])
        else:
            inactive_30p.append(b["user_id"])

    student_rows = [
        {
            "user_id": b["user_id"],
            "display_name": b.get("display_name") or b["user_id"],
            "activity_level": _activity_level(float(b.get("last_active") or 0), now),
            "mastery_pct": round(float(b.get("mastery_avg") or 0) * 100, 1),
            "mistakes_open": int(b.get("mistakes_open") or 0),
            "last_active": float(b.get("last_active") or 0),
            "profile_completeness_pct": float(
                b.get("profile_completeness_pct") or 0
            ),
        }
        for b in briefs
    ]

    distribution = [{"bucket": label, "count": 0} for label, _, _ in _MASTERY_BUCKETS]
    for value in mastery_values:
        for i, (_, lo, hi) in enumerate(_MASTERY_BUCKETS):
            if lo <= value < hi:
                distribution[i]["count"] += 1
                break

    result: Dict[str, Any] = {
        "course": course,
        "generated_at": now,
        "student_count": len(briefs),
        "students": student_rows,
        "active_7d": len(active_7d),
        "active_30d": len(active_7d) + len(dormant_7_30),
        "mistakes_open_total": sum(b["mistakes_open"] for b in briefs),
        "mastery": {
            "overall_avg": round(sum(mastery_values) / len(mastery_values), 3) if mastery_values else None,
            "no_data_count": len(briefs) - len(mastery_values),
            "distribution": distribution,
            "trend": [],
        },
        "weak_kps": [],
        "error_distribution": [],
        "activity": {
            "active_7d": active_7d,
            "dormant_7_30": dormant_7_30,
            "inactive_30p": inactive_30p,
        },
        "risk_students": [],
    }

    # ---- 风险学生（复用 brief 三指标） ----
    risks = [_unified_risk_assessment(b, now) for b in briefs]
    level_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda r: (
        level_order[r["level"]],
        r["mastery_avg"] if r["mastery_avg"] is not None else 1.0,
    ))
    result["risk_students"] = risks[:risk_top]

    student_set = set(student_ids)

    # ---- 薄弱知识点（BKT 按 kp 聚合） + 错因分布 ----
    kp_open_mistakes: Dict[str, int] = {}
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import (
            BktStateRecord,
            KnowledgePointRecord,
            MistakeRecord,
        )

        with SessionLocal() as db:
            kp_names = {kp.id: kp.name for kp in db.query(KnowledgePointRecord).all()}
            course_kp_ids = {
                kp_id
                for (kp_id,) in db.query(KnowledgePointRecord.id)
                .filter(KnowledgePointRecord.course == course)
                .all()
            }
            bkt_rows = (
                db.query(BktStateRecord.knowledge_point_id, BktStateRecord.p_learned)
                .filter(BktStateRecord.user_id.in_(student_set))
                .all()
            )
            mistake_rows = (
                db.query(
                    MistakeRecord.knowledge_point_id,
                    MistakeRecord.error_type,
                    MistakeRecord.resolved_at,
                )
                .filter(MistakeRecord.user_id.in_(student_set))
                .all()
            )

        error_counter: Dict[str, int] = {}
        open_total = 0
        for kp_id, error_type, resolved_at in mistake_rows:
            if resolved_at is not None:
                continue
            open_total += 1
            error_counter[error_type or "unknown"] = error_counter.get(error_type or "unknown", 0) + 1
            if kp_id:
                kp_open_mistakes[kp_id] = kp_open_mistakes.get(kp_id, 0) + 1
        from backend.app.services.student_overview import error_type_label

        result["error_distribution"] = [
            {
                "code": cat,
                "label": error_type_label(cat),
                "category": error_type_label(cat),
                "count": n,
                "ratio": round(n / open_total, 3),
                "ratio_pct": round(n / open_total * 100, 1),
            }
            for cat, n in sorted(error_counter.items(), key=lambda kv: -kv[1])[:8]
        ] if open_total else []

        per_kp: Dict[str, Dict[str, Any]] = {}
        for kp_id, p_learned in bkt_rows:
            # 该课程没配 KP 白名单时不过滤（兼容 kp 未标 course 的演示数据）
            if course_kp_ids and kp_id not in course_kp_ids:
                continue
            slot = per_kp.setdefault(kp_id, {"sum": 0.0, "count": 0, "below": 0})
            slot["sum"] += float(p_learned)
            slot["count"] += 1
            if float(p_learned) < 0.6:
                slot["below"] += 1
        weak = [
            {
                "kp_id": kp_id,
                "kp_name": kp_names.get(kp_id, kp_id),
                "avg_mastery": round(s["sum"] / s["count"], 3),
                "students_tracked": s["count"],
                "students_below_60": s["below"],
                "mistake_count": kp_open_mistakes.get(kp_id, 0),
            }
            for kp_id, s in per_kp.items()
        ]
        weak.sort(key=lambda x: x["avg_mastery"])
        result["weak_kps"] = weak[:weak_top]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] class analytics kp/mistake aggregation failed: %s", exc)

    # ---- 近 N 天活动趋势（assessments 按天分桶：次数 + 归一化均分） ----
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import AssessmentRecord

        since = now - days * _DAY_SECONDS
        with SessionLocal() as db:
            rows = (
                db.query(AssessmentRecord.timestamp, AssessmentRecord.score)
                .filter(
                    AssessmentRecord.user_id.in_(student_set),
                    AssessmentRecord.timestamp >= since,
                )
                .all()
            )
        daily: Dict[str, Dict[str, Any]] = {}
        for ts, score in rows:
            day = time.strftime("%Y-%m-%d", time.localtime(float(ts)))
            slot = daily.setdefault(day, {"activity": 0, "scores": []})
            slot["activity"] += 1
            if score is not None:
                slot["scores"].append(_normalize_score(score))
        result["mastery"]["trend"] = [
            {
                "date": day,
                "activity_count": slot["activity"],
                "avg_score": round(sum(slot["scores"]) / len(slot["scores"]), 3) if slot["scores"] else None,
            }
            for day, slot in sorted(daily.items())
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] class analytics trend failed: %s", exc)

    return result


# ================================================================
# 教学共创：教师数据快照 → 既有多 Agent 编排
# ================================================================
# 这里不新造一套 Agent。教师工作台调用的仍是学生端正在使用的
# AgentOrchestrator / 安全校验 / 复盘流水线，只是为其补充教学数据上下文。
_COPILOT_ACTIONS: Dict[str, Dict[str, str]] = {
    "class_diagnosis": {
        "label": "班级学情诊断",
        "collaborative_prompt": (
            "@团团 先依据学情快照完成班级诊断，明确优先干预对象与证据；"
            "@智狐 再据此给出分层教学与资源投放顺序。"
        ),
        "single_prompt": "请依据学情快照完成班级诊断，并给出按优先级排序的分层教学建议。",
    },
    "learning_path": {
        "label": "分层学习路径",
        "collaborative_prompt": (
            "@团团 先诊断学习短板和风险；"
            "@智狐 再生成可执行的分层学习路径，包含阶段目标、资源类型和复查节点。"
        ),
        "single_prompt": "请依据学情快照生成可执行的分层学习路径，包含阶段目标、资源类型和复查节点。",
    },
    "student_intervention": {
        "label": "个体干预建议",
        "collaborative_prompt": (
            "@团团 先诊断该学生的掌握度、错题和活跃风险；"
            "@智灵 再拟定一份鼓励且具体的个体辅导建议与沟通话术。"
        ),
        "single_prompt": "请依据学情快照拟定一份鼓励且具体的个体辅导建议与沟通话术。",
    },
}


def _teaching_snapshot(scope: str, user_id: str, course: str) -> Dict[str, Any]:
    """将原始教学数据压缩为 Agent 需要的最小事实快照。

    不把完整画像、题干或聊天记录送入模型；只保留当前教学决策所需的
    聚合指标与前几项风险/薄弱点，既控制上下文长度，也减少不必要的数据暴露。
    """
    if scope == "student":
        summary = student_summary(user_id=user_id, course=course)
        mastery = summary.get("mastery") or {}
        mistakes = summary.get("mistakes") or {}
        return {
            "scope": "student",
            "student_id": user_id,
            "course": course,
            "mastery_average": mastery.get("average"),
            "weak_knowledge_points": (mastery.get("weakest") or [])[:5],
            "open_mistakes": mistakes.get("open_count", 0),
            "mistake_types": list({
                str(item.get("error_type") or "未分类")
                for item in (mistakes.get("recent") or [])[:8]
            }),
            "learning_paths": [
                {
                    "title": item.get("title"),
                    "progress": item.get("progress", 0),
                }
                for item in (summary.get("paths") or [])[:5]
            ],
            "risks": (summary.get("risks") or [])[:5],
        }

    overview = class_analytics(course=course)
    mastery = overview.get("mastery") or {}
    return {
        "scope": "class",
        "course": course,
        "student_count": overview.get("student_count", 0),
        "students_with_mastery_data": max(
            0,
            int(overview.get("student_count", 0))
            - int(mastery.get("no_data_count", 0)),
        ),
        "active_7d": overview.get("active_7d", 0),
        "mastery_average": mastery.get("overall_avg"),
        "open_mistakes": overview.get("mistakes_open_total", 0),
        "weak_knowledge_points": (overview.get("weak_kps") or [])[:5],
        "error_distribution": (overview.get("error_distribution") or [])[:5],
        "risk_students": (overview.get("risk_students") or [])[:8],
    }


@router.post("/copilot/consult")
async def consult_teaching_copilot(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """以教师数据为依据调用既有 Agent 编排，返回待教师审核的建议。

    产物默认不会自动发布、推送或覆盖学生数据；教师可在前端审核后再转为
    资源草稿、学习路径或师生消息。
    """
    action = str(payload.get("action", "class_diagnosis")).strip()
    if action not in _COPILOT_ACTIONS:
        raise HTTPException(status_code=400, detail="invalid_copilot_action")

    scope = str(payload.get("scope", "class")).strip().lower()
    if scope not in {"class", "student"}:
        raise HTTPException(status_code=400, detail="invalid_copilot_scope")

    user_id = str(payload.get("user_id", "")).strip()
    if scope == "student" and not user_id:
        raise HTTPException(status_code=400, detail="student_id_required")

    course = str(payload.get("course", DEFAULT_COURSE)).strip() or DEFAULT_COURSE
    instruction = str(payload.get("instruction", "")).strip()[:1200]
    agent_name = str(payload.get("agent_name", "")).strip()[:80]

    selected_agent: Dict[str, Any] | None = None
    if agent_name:
        # find_mentioned 只识别配置型 Agent；教学共创同时允许教师定向
        # 调用内置 Agent，因此这里从完整注册表按名称精确查找。
        selected_agent = next(
            (
                item for item in get_agent_config_service().list(
                    include_disabled=True,
                )
                if item.get("name") == agent_name
            ),
            None,
        )
        if selected_agent is None:
            raise HTTPException(status_code=400, detail="agent_not_found")
        if not selected_agent.get("enabled", True):
            raise HTTPException(status_code=400, detail="agent_disabled")

    snapshot = _teaching_snapshot(scope=scope, user_id=user_id, course=course)
    action_config = _COPILOT_ACTIONS[action]
    task_instruction = (
        f"@{selected_agent['name']} {action_config['single_prompt']}"
        if selected_agent is not None
        else action_config["collaborative_prompt"]
    )
    prompt = (
        "你正在教师教学共创工作台中协助制定教学方案。"
        "所有结论必须以给出的数据快照为依据；数据不足时明确说明，"
        "不要臆造学生表现或资源。输出应便于教师审核和后续执行。\n\n"
        f"任务：{task_instruction}\n"
        f"数据快照：{json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'))}"
    )
    if instruction:
        prompt += f"\n教师补充要求：{instruction}"

    # 复用 chat 的完整流水线（编排、辩论/反思、内容安全和质量评分），
    # 但使用独立的教师会话，且禁止画像更新污染学生数据。
    from backend.app.api.v1.chat import _process_turn
    from backend.app.api.v1.chat_pipeline.session import get_session_store

    requested_session_id = f"teacher-copilot:{scope}:{user_id or 'class'}:{action}"
    store = get_session_store()
    session_id, session = store.get_or_create(requested_session_id)
    session["user_id"] = "teacher"
    session["role_view"] = "teacher"
    session["teacher_context"] = snapshot

    result = await _process_turn(session_id, session, prompt, course)
    return {
        "action": action,
        "action_label": action_config["label"],
        "scope": scope,
        "student_id": user_id if scope == "student" else "",
        "snapshot": snapshot,
        **result,
    }


# ================================================================
# 课程资源管理
# ================================================================
def _normalize_resource_metadata(payload: Dict[str, Any], created_by: str) -> Dict[str, Any]:
    scope = str(payload.get("scope", "course"))
    if scope not in ("course", "student"):
        scope = "course"
    status = str(payload.get("status", "published"))
    if status not in ("draft", "published", "archived"):
        status = "published"
    return {
        **dict(payload.get("metadata") or {}),
        "course": str(payload.get("course", DEFAULT_COURSE)) or DEFAULT_COURSE,
        "scope": scope,
        "status": status,
        "created_by": created_by,
        "target_user_ids": [str(u) for u in (payload.get("target_user_ids") or [])],
        "kp_ids": [str(k) for k in (payload.get("kp_ids") or [])],
    }


@router.post("/resources/upload")
async def upload_teacher_resource(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    resource_type: str = Form(default="document"),
    course: str = Form(default=DEFAULT_COURSE),
    scope: str = Form(default="course"),
    status: str = Form(default="draft"),
    tags: str = Form(default=""),
    kp_ids: str = Form(default=""),
    target_user_ids: str = Form(default=""),
    created_by: str = Form(default="teacher"),
) -> Dict[str, Any]:
    """上传教师资料并纳入课程资源管理。

    文本型资料会保留正文预览，供教师编辑时查看；Office/PDF 和教师自录视频
    保留原件和附件元数据。视频可在学生端资源中心直接播放；默认保存为草稿，
    避免误发布。
    """
    filename = _safe_upload_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_TEACHER_UPLOAD_SUFFIXES:
        allowed = ", ".join(sorted(_ALLOWED_TEACHER_UPLOAD_SUFFIXES))
        raise HTTPException(status_code=400, detail=f"unsupported_file_type:{allowed}")

    _TEACHER_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4().hex}_{filename}"
    target = _resolve_teacher_upload(storage_key)
    if target is None:  # 理论上不会到达，保留为路径安全兜底
        raise HTTPException(status_code=400, detail="invalid_storage_key")
    max_bytes = _upload_size_limit(suffix)
    total_size = 0
    preview_bytes = bytearray()
    try:
        # 流式落盘，避免 200 MB 的课堂视频整段常驻进程内存。
        with target.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "file_too_large_max_200mb"
                            if suffix in _VIDEO_UPLOAD_SUFFIXES
                            else "file_too_large_max_20mb"
                        ),
                    )
                destination.write(chunk)
                if suffix in _TEXT_UPLOAD_SUFFIXES and len(preview_bytes) < 200_000:
                    remaining = 200_000 - len(preview_bytes)
                    preview_bytes.extend(chunk[:remaining])
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        logger.warning("[teacher] store uploaded attachment failed: %s", exc)
        raise HTTPException(status_code=500, detail="attachment_store_failed") from exc
    finally:
        await file.close()

    if not total_size:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="empty_file")

    try:
        tag_values = [item.strip() for item in tags.replace("，", ",").split(",") if item.strip()]
        kp_values = [item.strip() for item in kp_ids.replace("，", ",").split(",") if item.strip()]
        target_user_values = [
            item.strip() for item in target_user_ids.replace("，", ",").split(",") if item.strip()
        ]
        payload = {
            "course": course,
            "scope": scope,
            "status": status,
            "tags": tag_values,
            "kp_ids": kp_values,
            "target_user_ids": target_user_values,
        }
        owner = created_by.strip() or "teacher"
        metadata = _normalize_resource_metadata(payload, owner)
        metadata["attachment"] = {
            "filename": filename,
            "storage_key": storage_key,
            "size_bytes": total_size,
            "media_type": _UPLOAD_MEDIA_TYPES.get(suffix, "application/octet-stream"),
            "inline_preview": suffix in _VIDEO_UPLOAD_SUFFIXES,
        }

        text_preview = ""
        content_type = "video" if suffix in _VIDEO_UPLOAD_SUFFIXES else "attachment"
        if suffix in _TEXT_UPLOAD_SUFFIXES:
            text_preview = bytes(preview_bytes).decode("utf-8", errors="replace")
            content_type = "markdown" if suffix == ".md" else "text"

        resource_id = f"teacher_res_{uuid.uuid4().hex[:12]}"
        resource = {
            "id": resource_id,
            "user_id": "",
            "type": resource_type.strip() or "document",
            "title": title.strip() or Path(filename).stem,
            "content": text_preview,
            "content_type": content_type,
            "agent_name": "teacher_upload",
            "metadata": metadata,
            "tags": tag_values,
            "created_at": time.time(),
        }
        persist_resource(resource)
        return {"resource_id": resource_id, "resource": resource}
    except Exception:
        # 数据库写入失败时不遗留孤儿文件。
        target.unlink(missing_ok=True)
        raise


@router.get("/resources/{resource_id}/download")
def download_teacher_resource(resource_id: str) -> FileResponse:
    """下载教师上传的原始资料；仅教师路由可访问。"""
    resource = get_resource_dict(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="resource_not_found")
    attachment = (resource.get("metadata") or {}).get("attachment") or {}
    target = _resolve_teacher_upload(str(attachment.get("storage_key", "")))
    if target is None or not target.exists():
        raise HTTPException(status_code=404, detail="attachment_not_found")
    filename = _safe_upload_filename(str(attachment.get("filename", target.name)))
    media_type = str(attachment.get("media_type") or "application/octet-stream")
    return FileResponse(
        path=target,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline" if media_type.startswith(("video/", "audio/")) else "attachment",
    )


@router.post("/resources/from-artifact")
def create_teacher_resource_from_artifact(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """把已生成的真实 PPT/视频二进制纳入教师资源中心。

    Artifact registry 是服务端可信索引；导入时仍复制到受控的教师附件目录，
    避免把任意绝对路径写进资源记录，也保证后续下载、发布和删除行为一致。
    """
    artifact_id = str(payload.get("artifact_id", "")).strip()
    if not artifact_id:
        raise HTTPException(status_code=400, detail="artifact_id_required")

    from backend.app.api.v1.artifacts.registry import get_artifact_registry

    record = get_artifact_registry().get(artifact_id)
    if record is None:
        raise HTTPException(status_code=404, detail="artifact_not_found")
    source = Path(record.filepath).resolve() if record.filepath else None
    if source is None or not source.is_file() or source.stat().st_size <= 0:
        raise HTTPException(status_code=404, detail="artifact_file_not_ready")
    suffix = source.suffix.lower()
    allowed_binary_types = {
        ".pptx": {"pptx"},
        ".mp4": {"video", "manim_video"},
    }
    if suffix not in allowed_binary_types or record.type not in allowed_binary_types[suffix]:
        raise HTTPException(status_code=400, detail="artifact_file_type_not_publishable")
    size_bytes = source.stat().st_size
    if size_bytes > _upload_size_limit(suffix):
        raise HTTPException(status_code=400, detail="artifact_file_too_large")

    requested_title = str(payload.get("title", "")).strip()
    filename = _safe_upload_filename(
        f"{requested_title}{suffix}" if requested_title else source.name,
    )
    _TEACHER_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4().hex}_{filename}"
    target = _resolve_teacher_upload(storage_key)
    if target is None:
        raise HTTPException(status_code=400, detail="invalid_storage_key")
    try:
        shutil.copy2(source, target)
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="artifact_import_failed") from exc

    try:
        created_by = str(payload.get("created_by", "teacher")).strip() or "teacher"
        metadata = _normalize_resource_metadata(payload, created_by)
        metadata["attachment"] = {
            "filename": filename,
            "storage_key": storage_key,
            "size_bytes": size_bytes,
            "media_type": _UPLOAD_MEDIA_TYPES.get(suffix, "application/octet-stream"),
            "inline_preview": suffix in _VIDEO_UPLOAD_SUFFIXES,
        }
        metadata["generated_artifact"] = {
            "artifact_id": artifact_id,
            "artifact_type": record.type,
            "binary_generated": True,
            "source_metadata": dict(record.metadata or {}),
        }
        scope_user = ""
        if metadata["scope"] == "student" and metadata["target_user_ids"]:
            scope_user = metadata["target_user_ids"][0]
        resource_type = str(payload.get("type") or ("video" if suffix in _VIDEO_UPLOAD_SUFFIXES else "ppt"))
        resource_id = f"teacher_res_{uuid.uuid4().hex[:12]}"
        resource = {
            "id": resource_id,
            "user_id": scope_user,
            "type": resource_type,
            "title": requested_title or source.stem,
            "content": str(payload.get("content", "")),
            "content_type": "video" if suffix in _VIDEO_UPLOAD_SUFFIXES else "attachment",
            "agent_name": "teacher_studio_binary",
            "metadata": metadata,
            "tags": [str(t) for t in (payload.get("tags") or [])],
            "created_at": time.time(),
        }
        persist_resource(resource)
        return {"resource_id": resource_id, "resource": resource}
    except Exception:
        target.unlink(missing_ok=True)
        raise


@router.get("/resources")
def list_teacher_resources(
    course: str = Query(default=""),
    status: str = Query(default=""),
    q: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    """课程资源列表（教师视角：含草稿/已下架，全量可管理）。"""
    items: List[Dict[str, Any]] = []
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import ResourceRecord

        with SessionLocal() as db:
            rows = (
                db.query(ResourceRecord)
                .order_by(ResourceRecord.created_at.desc())
                .limit(1000)
                .all()
            )
        for r in rows:
            meta = dict(r.metadata_data or {})
            item = {
                "id": r.id,
                "user_id": r.user_id,
                "type": r.type,
                "title": r.title,
                "content": r.content,
                "content_type": r.content_type,
                "agent_name": r.agent_name,
                "metadata": meta,
                "tags": list(r.tags or []),
                "created_at": r.created_at,
            }
            if course and meta.get("course", DEFAULT_COURSE) != course:
                continue
            if status and meta.get("status", "") != status:
                continue
            if q and q not in (r.title or "") and q not in (r.content or "")[:2000]:
                continue
            items.append(item)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] list resources failed: %s", exc)

    return {"resources": items[:limit], "total": len(items)}


@router.post("/resources")
def create_teacher_resource(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """教师新增课程资源（上传/录入）。"""
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="title_required")

    created_by = str(payload.get("created_by", "teacher")).strip() or "teacher"
    metadata = _normalize_resource_metadata(payload, created_by)
    scope_user = ""
    if metadata["scope"] == "student" and metadata["target_user_ids"]:
        scope_user = metadata["target_user_ids"][0]

    resource = {
        "id": f"res_{uuid.uuid4().hex[:10]}",
        "user_id": scope_user,
        "type": str(payload.get("type", "document")),
        "title": title,
        "content": str(payload.get("content", "")),
        "content_type": str(payload.get("content_type", "markdown")),
        "agent_name": "teacher",
        "metadata": metadata,
        "tags": [str(t) for t in (payload.get("tags") or [])],
        "created_at": time.time(),
    }
    persist_resource(resource)
    return {"resource_id": resource["id"], "resource": resource}


@router.patch("/resources/{resource_id}")
def update_teacher_resource(
    resource_id: str, payload: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """编辑资源（标题/内容/标签/课程/可见范围/上下架状态）。"""
    resource = get_resource_dict(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="resource_not_found")

    for field in ("title", "content", "type", "content_type"):
        if field in payload:
            resource[field] = str(payload[field])
    if "tags" in payload:
        resource["tags"] = [str(t) for t in (payload.get("tags") or [])]

    meta = dict(resource.get("metadata") or {})
    for field in ("course", "scope", "status"):
        if field in payload:
            meta[field] = str(payload[field])
    if "target_user_ids" in payload:
        meta["target_user_ids"] = [str(u) for u in (payload.get("target_user_ids") or [])]
    if "kp_ids" in payload:
        meta["kp_ids"] = [str(k) for k in (payload.get("kp_ids") or [])]
    resource["metadata"] = meta

    persist_resource(resource)
    return {"resource": resource}


@router.delete("/resources/{resource_id}")
def delete_teacher_resource(resource_id: str) -> Dict[str, Any]:
    """删除课程资源。"""
    resource = get_resource_dict(resource_id)
    found = delete_resource_record(resource_id)
    if found:
        _delete_uploaded_attachment(resource)
    return {"status": "deleted" if found else "not_found"}


# ================================================================
# 指派 / 推荐（写入群聊）
# ================================================================
def _teacher_sender(payload: Dict[str, Any]) -> Dict[str, str]:
    return {
        "sender_id": str(payload.get("sender_id", "teacher")).strip() or "teacher",
        "sender_name": str(payload.get("sender_name", "王老师")).strip() or "王老师",
    }


@router.post("/assignments/resource")
def assign_resource(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """向学生指派资源：更新资源可见范围 + 在学生群聊写入资源卡片。"""
    resource_id = str(payload.get("resource_id", "")).strip()
    user_id = str(payload.get("user_id", "")).strip()
    if not resource_id or not user_id:
        raise HTTPException(status_code=400, detail="resource_id_and_user_id_required")

    resource = get_resource_dict(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="resource_not_found")

    meta = dict(resource.get("metadata") or {})
    targets = set(meta.get("target_user_ids") or [])
    targets.add(user_id)
    meta["target_user_ids"] = sorted(targets)
    meta.setdefault("course", DEFAULT_COURSE)
    meta.setdefault("scope", "student")
    meta.setdefault("status", "published")
    resource["metadata"] = meta
    persist_resource(resource)

    course = str(payload.get("course", meta.get("course", DEFAULT_COURSE)))
    note = str(payload.get("note", "")).strip()
    sender = _teacher_sender(payload)
    room_id = build_room_id(course, user_id)
    message = get_group_chat_repo().append(
        room_id=room_id,
        sender_role="teacher",
        content=note or f"给你推荐了学习资源《{resource['title']}》，记得查收。",
        message_type="resource_card",
        payload={
            "resource_id": resource_id,
            "title": resource["title"],
            "type": resource["type"],
            "course": course,
        },
        **sender,
    )
    return {"status": "ok", "resource": resource, "message": message, "room_id": room_id}


@router.post("/assignments/path")
def assign_path(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """教师为学生推荐学习路径：写入学生路径列表 + 群聊路径卡片。"""
    user_id = str(payload.get("user_id", "")).strip()
    title = str(payload.get("title", "")).strip() or "教师推荐学习路径"
    stages = payload.get("stages") or []
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id_required")
    if not isinstance(stages, list) or not stages:
        raise HTTPException(status_code=400, detail="stages_required")

    course = str(payload.get("course", DEFAULT_COURSE)).strip() or DEFAULT_COURSE
    normalized_stages = []
    for i, stage in enumerate(stages):
        if isinstance(stage, str):
            stage_title = stage.strip() or f"阶段 {i + 1}"
            normalized_stages.append({
                "id": f"teacher-stage-{i + 1}",
                "title": stage_title,
                "name": stage_title,
                "topics": [stage_title],
                "order": i + 1,
            })
        elif isinstance(stage, dict):
            stage_title = str(stage.get("title") or stage.get("name") or f"阶段 {i + 1}").strip()
            topics = stage.get("topics")
            normalized_stages.append({
                **stage,
                "id": stage.get("id") or f"teacher-stage-{i + 1}",
                "title": stage_title,
                "name": stage_title,
                "topics": topics if isinstance(topics, list) and topics else [stage_title],
                "order": stage.get("order", i + 1),
            })

    sender = _teacher_sender(payload)
    path_id = f"path_{uuid.uuid4().hex[:10]}"
    record = {
        "id": path_id,
        "user_id": user_id,
        "title": title,
        "stages": normalized_stages,
        "current_stage": 0,
        "progress": 0.0,
        # Keep metadata fields at the record's top level.  LearningPathRepository
        # persists those fields in its metadata column and exposes them directly
        # to the student's path page.
        "course": course,
        "recommended_by": sender["sender_name"],
        "recommended_role": "teacher",
        "created_at": time.time(),
    }
    try:
        from backend.app.repositories.path_repo import LearningPathRepository
        saved = LearningPathRepository().save(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] path save via repo failed: %s", exc)
        saved = record

    note = str(payload.get("note", "")).strip()
    room_id = build_room_id(course, user_id)
    message = get_group_chat_repo().append(
        room_id=room_id,
        sender_role="teacher",
        content=note or f"为你规划了学习路径「{title}」（共 {len(normalized_stages)} 个阶段），在学习路径页即可开始。",
        message_type="path_card",
        payload={
            "path_id": path_id,
            "title": title,
            "stages_count": len(normalized_stages),
            "stages_preview": [s.get("title", "") for s in normalized_stages[:4]],
            "course": course,
        },
        **sender,
    )
    return {"status": "ok", "path": saved, "message": message, "room_id": room_id}


# ================================================================
# Agent 配置管理
# ================================================================
@router.get("/agents")
def list_agents() -> Dict[str, Any]:
    configs = get_agent_config_service().list(include_disabled=True)
    return {"agents": configs, "total": len(configs)}


@router.post("/agents")
def create_agent(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        config = get_agent_config_service().create(
            payload, created_by=str(payload.get("created_by", "teacher")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", "agent": config}


@router.patch("/agents/{agent_key}")
def update_agent(agent_key: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        config = get_agent_config_service().update(agent_key, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="agent_not_found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok", "agent": config}


@router.delete("/agents/{agent_key}")
def delete_agent(agent_key: str) -> Dict[str, Any]:
    try:
        found = get_agent_config_service().delete(agent_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "deleted" if found else "not_found"}


# ================================================================
# 教师发消息
# ================================================================
@router.post("/messages")
def send_teacher_message(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """教师向指定学生的课程群聊发送消息（普通消息，不触发 LLM）。"""
    user_id = str(payload.get("user_id", "")).strip()
    content = str(payload.get("content", "")).strip()
    if not user_id or not content:
        raise HTTPException(status_code=400, detail="user_id_and_content_required")

    course = str(payload.get("course", DEFAULT_COURSE)) or DEFAULT_COURSE
    sender = _teacher_sender(payload)
    room_id = build_room_id(course, user_id)
    message = get_group_chat_repo().append(
        room_id=room_id,
        sender_role="teacher",
        content=content,
        message_type="teacher_message",
        payload=dict(payload.get("payload") or {}),
        **sender,
    )
    return {"status": "ok", "message": message, "room_id": room_id}


# ================================================================
# 增强 1：教师干预日志（Impact Loop）
# ================================================================
_INTERVENTION_TYPES = frozenset({"resource_card", "path_card", "teacher_message"})


@router.get("/interventions")
def list_interventions(
    user_id: str = Query(default=""),
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=200, ge=1, le=1000),
) -> Dict[str, Any]:
    """教师干预日志：按学生聚合教师操作（资源/路径/消息）+ 学生响应状态。

    数据来源：group_chat_messages 中 sender_role='teacher' 的非系统消息。
    响应判定：
    - resource_card / teacher_message → 学生是否在同房间有后续消息（已回复）
    - path_card → 关联 learning_paths 表查 progress > 0 视为已响应
    """
    now = time.time()
    since = now - days * _DAY_SECONDS
    student_ids = _collect_student_ids()
    target_filter = user_id.strip() if user_id.strip() else None

    result: Dict[str, Any] = {
        "generated_at": now,
        "days": days,
        "students": [],
    }

    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import (
            GroupChatMessageRecord,
            LearningPathRecord,
        )

        with SessionLocal() as db:
            # 拉取所有教师干预消息
            query = (
                db.query(GroupChatMessageRecord)
                .filter(
                    GroupChatMessageRecord.sender_role == "teacher",
                    GroupChatMessageRecord.message_type.in_(_INTERVENTION_TYPES),
                    GroupChatMessageRecord.created_at >= since,
                )
                .order_by(GroupChatMessageRecord.created_at.desc())
                .limit(limit)
            )
            rows = query.all()

            # 拉取学生回复（同房间、时间晚于干预、sender_role != teacher）
            room_ids = {r.room_id for r in rows}
            student_replies: Dict[str, List[Dict[str, Any]]] = {}
            if room_ids:
                reply_rows = (
                    db.query(GroupChatMessageRecord)
                    .filter(
                        GroupChatMessageRecord.room_id.in_(room_ids),
                        GroupChatMessageRecord.sender_role != "teacher",
                        GroupChatMessageRecord.created_at >= since,
                    )
                    .order_by(GroupChatMessageRecord.created_at.asc())
                    .all()
                )
                for rr in reply_rows:
                    student_replies.setdefault(rr.room_id, []).append({
                        "created_at": rr.created_at,
                        "sender_role": rr.sender_role,
                        "message_type": rr.message_type,
                    })

            # 路径进度
            path_ids = [
                (r.payload or {}).get("path_id")
                for r in rows
                if r.message_type == "path_card" and (r.payload or {}).get("path_id")
            ]
            path_progress: Dict[str, float] = {}
            if path_ids:
                path_rows = (
                    db.query(LearningPathRecord.id, LearningPathRecord.progress)
                    .filter(LearningPathRecord.id.in_(path_ids))
                    .all()
                )
                path_progress = {pid: float(prog) for pid, prog in path_rows}

        # 按学生聚合
        per_student: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            # room_id 格式: course:student_id
            parts = r.room_id.rsplit(":", 1)
            sid = parts[1] if len(parts) == 2 else r.room_id
            if sid not in student_ids:
                continue
            if target_filter and sid != target_filter:
                continue

            entry = per_student.setdefault(sid, {
                "user_id": sid,
                "total": 0,
                "resource_count": 0,
                "path_count": 0,
                "message_count": 0,
                "responded": 0,
                "not_responded": 0,
                "recent": [],
            })
            entry["total"] += 1
            if r.message_type == "resource_card":
                entry["resource_count"] += 1
            elif r.message_type == "path_card":
                entry["path_count"] += 1
            else:
                entry["message_count"] += 1

            # 判断学生是否已响应
            replied = False
            if r.message_type == "path_card":
                pid = (r.payload or {}).get("path_id", "")
                prog = path_progress.get(pid, 0.0)
                responded = prog > 0.0
            else:
                replies = student_replies.get(r.room_id, [])
                responded = any(rp["created_at"] > r.created_at for rp in replies)

            if responded:
                entry["responded"] += 1
                replied = True
            else:
                entry["not_responded"] += 1

            entry["recent"].append({
                "id": r.id,
                "type": r.message_type,
                "content": (r.content or "")[:100],
                "created_at": r.created_at,
                "responded": replied,
                "payload": dict(r.payload or {}),
            })

        # 每个学生只保留最近 10 条
        for entry in per_student.values():
            entry["recent"] = entry["recent"][:10]

        result["students"] = sorted(
            per_student.values(),
            key=lambda x: -x["total"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] interventions failed: %s", exc)

    result["total_interventions"] = sum(s["total"] for s in result["students"])
    result["total_responded"] = sum(s["responded"] for s in result["students"])
    return result


# ================================================================
# 增强 2：班级知识图谱热力图
# ================================================================
@router.get("/analytics/knowledge-map")
def knowledge_map(
    course: str = Query(default=DEFAULT_COURSE),
) -> Dict[str, Any]:
    """班级知识图谱热力图：返回全部知识点 + 班级平均掌握度 + 前置关系边。

    前端可用 nodes（热力着色）+ edges（前置依赖连线）渲染课程级知识图谱。
    """
    result: Dict[str, Any] = {
        "course": course,
        "nodes": [],
        "edges": [],
        "generated_at": time.time(),
    }
    student_ids = set(_collect_student_ids())

    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import (
            BktStateRecord,
            KnowledgePointRecord,
            KnowledgeRelationRecord,
            MistakeRecord,
        )

        with SessionLocal() as db:
            # 知识点
            kp_rows = (
                db.query(KnowledgePointRecord)
                .filter(KnowledgePointRecord.course == course)
                .all()
            )
            kp_meta = {kp.id: kp for kp in kp_rows}

            # BKT 按 kp 聚合
            bkt_rows = (
                db.query(
                    BktStateRecord.knowledge_point_id,
                    BktStateRecord.p_learned,
                )
                .filter(BktStateRecord.user_id.in_(student_ids))
                .all()
            )
            per_kp: Dict[str, Dict[str, Any]] = {}
            for kp_id, p_learned in bkt_rows:
                if kp_id not in kp_meta:
                    continue
                slot = per_kp.setdefault(kp_id, {"sum": 0.0, "count": 0, "below": 0})
                slot["sum"] += float(p_learned)
                slot["count"] += 1
                if float(p_learned) < 0.6:
                    slot["below"] += 1

            # 未解决错题按 kp 统计
            mistake_rows = (
                db.query(
                    MistakeRecord.knowledge_point_id,
                    MistakeRecord.resolved_at,
                )
                .filter(
                    MistakeRecord.user_id.in_(student_ids),
                    MistakeRecord.resolved_at.is_(None),
                )
                .all()
            )
            kp_mistakes: Dict[str, int] = {}
            for kp_id, _ in mistake_rows:
                if kp_id:
                    kp_mistakes[kp_id] = kp_mistakes.get(kp_id, 0) + 1

            # 知识点关系边
            kp_ids = set(kp_meta.keys())
            rel_rows = (
                db.query(KnowledgeRelationRecord)
                .filter(
                    KnowledgeRelationRecord.source_id.in_(kp_ids),
                    KnowledgeRelationRecord.target_id.in_(kp_ids),
                )
                .all()
            )

        # 构建节点
        for kp_id, kp in kp_meta.items():
            slot = per_kp.get(kp_id, {"sum": 0.0, "count": 0, "below": 0})
            avg = round(slot["sum"] / slot["count"], 3) if slot["count"] > 0 else None
            meta = dict(kp.metadata_data or {})
            result["nodes"].append({
                "id": kp.id,
                "name": kp.name,
                "description": kp.description or "",
                "avg_mastery": avg,
                "students_tracked": slot["count"],
                "students_below_60": slot["below"],
                "open_mistakes": kp_mistakes.get(kp.id, 0),
                "bloom_level": meta.get("bloom_level", ""),
                "difficulty": meta.get("difficulty", ""),
            })

        # 构建边
        for rel in rel_rows:
            result["edges"].append({
                "source": rel.source_id,
                "target": rel.target_id,
                "relation_type": rel.relation_type,
                "weight": float(rel.weight),
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] knowledge-map failed: %s", exc)

    return result


# ================================================================
# 增强 3：学生对比分析
# ================================================================
@router.get("/analytics/compare")
def compare_students(
    user_ids: str = Query(default="", description="逗号分隔的学生 ID 列表"),
    course: str = Query(default=DEFAULT_COURSE),
) -> Dict[str, Any]:
    """多学生横向对比：掌握度均值 + 全 KP 掌握度向量（雷达图）+ 错题/活跃度。"""
    ids = [uid.strip() for uid in user_ids.split(",") if uid.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="user_ids_required")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="max_10_students")

    now = time.time()
    result: Dict[str, Any] = {
        "course": course,
        "generated_at": now,
        "students": [],
        "kp_ids": [],
    }

    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import (
            AssessmentRecord,
            BktStateRecord,
            KnowledgePointRecord,
            MistakeRecord,
        )
        from sqlalchemy import func

        with SessionLocal() as db:
            # 全部课程知识点（用于对齐向量维度）
            kp_rows = (
                db.query(KnowledgePointRecord)
                .filter(KnowledgePointRecord.course == course)
                .all()
            )
            kp_names = {kp.id: kp.name for kp in kp_rows}
            all_kp_ids = [kp.id for kp in kp_rows]
            result["kp_ids"] = all_kp_ids

            id_set = set(ids)
            for uid in ids:
                # BKT 掌握度
                bkt_rows = (
                    db.query(BktStateRecord)
                    .filter(BktStateRecord.user_id == uid)
                    .all()
                )
                mastery_map = {r.knowledge_point_id: float(r.p_learned) for r in bkt_rows}
                mastery_avg = (
                    round(sum(mastery_map.values()) / len(mastery_map), 3)
                    if mastery_map else None
                )
                # 对齐到全课程 KP 向量
                mastery_vector = [
                    round(mastery_map.get(kp_id, 0.0), 3) for kp_id in all_kp_ids
                ]

                # 错题
                mistakes_open = (
                    db.query(func.count(MistakeRecord.id))
                    .filter(
                        MistakeRecord.user_id == uid,
                        MistakeRecord.resolved_at.is_(None),
                    )
                    .scalar() or 0
                )

                # 最近活跃
                last_ts = (
                    db.query(func.max(AssessmentRecord.timestamp))
                    .filter(AssessmentRecord.user_id == uid)
                    .scalar()
                )

                # 最弱 / 最强 KP
                sorted_kps = sorted(mastery_map.items(), key=lambda kv: kv[1])
                weakest = [
                    {"kp_id": k, "kp_name": kp_names.get(k, k), "mastery": round(v, 3)}
                    for k, v in sorted_kps[:3]
                ]
                strongest = [
                    {"kp_id": k, "kp_name": kp_names.get(k, k), "mastery": round(v, 3)}
                    for k, v in reversed(sorted_kps[-3:])
                ]

                result["students"].append({
                    "user_id": uid,
                    "mastery_avg": mastery_avg,
                    "mastery_vector": mastery_vector,
                    "mistakes_open": int(mistakes_open),
                    "last_active": float(last_ts) if last_ts else 0.0,
                    "weakest": weakest,
                    "strongest": strongest,
                })
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] compare students failed: %s", exc)

    return result


# ================================================================
# 增强 4：班级学情报告导出（Markdown）
# ================================================================
@router.get("/analytics/class/export")
def export_class_report(
    course: str = Query(default=DEFAULT_COURSE),
    days: int = Query(default=30, ge=7, le=180),
) -> Response:
    """导出班级学情 Markdown 报告，供教师下载或打印。"""
    data = class_analytics(course=course, days=days)
    now_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(data["generated_at"]))

    lines: List[str] = [
        f"# 班级学情报告 — {course}",
        f"",
        f"> 生成时间：{now_str}  ·  统计窗口：近 {days} 天",
        f"",
        f"---",
        f"",
        f"## 一、核心指标",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 学生总数 | {data['student_count']} |",
        f"| 7 日活跃 | {data['active_7d']} |",
        f"| 30 日活跃 | {data['active_30d']} |",
        f"| 未解决错题合计 | {data['mistakes_open_total']} |",
        f"| 班级平均掌握度 | {format(data['mastery']['overall_avg'], '.1%') if data['mastery']['overall_avg'] is not None else '暂无数据'} |",
        f"| 无掌握度数据人数 | {data['mastery']['no_data_count']} |",
        f"",
        f"## 二、掌握度分布",
        f"",
        f"| 区间 | 人数 |",
        f"|------|------|",
    ]
    for bucket in data["mastery"]["distribution"]:
        lines.append(f"| {bucket['bucket']}% | {bucket['count']} |")

    lines.extend([
        f"",
        f"## 三、薄弱知识点 TOP5",
        f"",
        f"| 知识点 | 平均掌握度 | 追踪人数 | 未达标人数 | 关联未解决错题 |",
        f"|--------|-----------|---------|-----------|--------------|",
    ])
    for kp in data["weak_kps"]:
        lines.append(
            f"| {kp['kp_name']} | {kp['avg_mastery']:.1%} | {kp['students_tracked']} | {kp['students_below_60']} | {kp['mistake_count']} |"
        )

    lines.extend([
        f"",
        f"## 四、错因分布 TOP5",
        f"",
        f"| 错因类型 | 数量 | 占比 |",
        f"|---------|------|------|",
    ])
    for e in data["error_distribution"]:
        lines.append(f"| {e['category']} | {e['count']} | {e['ratio']:.1%} |")

    lines.extend([
        f"",
        f"## 五、活跃度分布",
        f"",
        f"- 7 日内活跃（{len(data['activity']['active_7d'])} 人）：{', '.join(data['activity']['active_7d'][:20]) or '无'}",
        f"- 7-30 天未活跃（{len(data['activity']['dormant_7_30'])} 人）：{', '.join(data['activity']['dormant_7_30'][:20]) or '无'}",
        f"- 超 30 天未活跃（{len(data['activity']['inactive_30p'])} 人）：{', '.join(data['activity']['inactive_30p'][:20]) or '无'}",
        f"",
    ])

    if data["risk_students"]:
        lines.extend([
            f"## 六、优先干预名单",
            f"",
            f"| 学生 | 风险等级 | 掌握度 | 未解决错题 | 原因 |",
            f"|------|---------|--------|-----------|------|",
        ])
        risk_label = {"high": "高", "medium": "中", "low": "低"}
        for r in data["risk_students"]:
            mastery_str = f"{r['mastery_avg']:.1%}" if r["mastery_avg"] is not None else "—"
            lines.append(
                f"| {r['user_id']} | {risk_label.get(r['level'], r['level'])} | {mastery_str} | {r['mistakes_open']} | {'；'.join(r['reasons'])} |"
            )

    if data["mastery"]["trend"]:
        lines.extend([
            f"",
            f"## 七、近 {days} 天学习活动趋势",
            f"",
            f"| 日期 | 活动次数 | 平均得分 |",
            f"|------|---------|---------|",
        ])
        for t in data["mastery"]["trend"][-14:]:  # 最近 14 天
            score_str = f"{t['avg_score']:.1%}" if t["avg_score"] is not None else "—"
            lines.append(f"| {t['date']} | {t['activity_count']} | {score_str} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"*本报告由 A3 学习智能体系统自动生成，数据来源：BKT 知识追踪 × 错题归因 × 学习活动记录。*",
    ])

    markdown = "\n".join(lines)
    filename = f"class_report_{course}_{time.strftime('%Y%m%d_%H%M', time.localtime(data['generated_at']))}.md"
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ================================================================
# 增强 5：错题批量处理
# ================================================================
@router.post("/mistakes/batch-resolve")
def batch_resolve_mistakes(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """批量标记错题为已解决 / 重新打开。

    Body: { "mistake_ids": ["id1", "id2", ...], "action": "resolve" | "unresolve" }
    """
    mistake_ids = payload.get("mistake_ids") or []
    action = str(payload.get("action", "resolve")).strip().lower()

    if not isinstance(mistake_ids, list) or not mistake_ids:
        raise HTTPException(status_code=400, detail="mistake_ids_required")
    if action not in ("resolve", "unresolve"):
        raise HTTPException(status_code=400, detail="action_must_be_resolve_or_unresolve")
    if len(mistake_ids) > 500:
        raise HTTPException(status_code=400, detail="max_500_mistakes_per_batch")

    ids = [str(mid).strip() for mid in mistake_ids if str(mid).strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="mistake_ids_required")

    now = time.time()
    resolved_count = 0
    unresolved_count = 0

    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import MistakeRecord

        with SessionLocal() as db:
            rows = (
                db.query(MistakeRecord)
                .filter(MistakeRecord.id.in_(ids))
                .all()
            )
            for row in rows:
                if action == "resolve":
                    if row.resolved_at is None:
                        row.resolved_at = now
                        resolved_count += 1
                else:
                    if row.resolved_at is not None:
                        row.resolved_at = None
                        unresolved_count += 1
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[teacher] batch resolve mistakes failed: %s", exc)
        raise HTTPException(status_code=500, detail="batch_resolve_failed")

    action_label = "已解决" if action == "resolve" else "已重新打开"
    changed = resolved_count if action == "resolve" else unresolved_count
    return {
        "status": "ok",
        "action": action,
        "action_label": action_label,
        "requested": len(ids),
        "changed": changed,
        "skipped": len(ids) - changed,
    }
