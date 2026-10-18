"""
资源管理 API

管理 AI 生成的个性化学习资源（文档/思维导图/题库/代码案例/PPT等）
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse

from backend.app.core.deployment_policy import production_mode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["resources"])

_TEACHER_UPLOAD_ROOT = Path(__file__).resolve().parents[4] / "data" / "teacher_uploads"

# 资源存储：内存热缓存 + SQLite 持久化双写（重启不丢，A 2026-07-02 补全）
_resources: dict[str, dict] = {}  # resource_id -> resource

_db_available = True
try:
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import ResourceRecord
except ImportError:
    _db_available = False


def _row_to_dict(row: "ResourceRecord") -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "type": row.type,
        "title": row.title,
        "content": row.content,
        "content_type": row.content_type,
        "agent_name": row.agent_name,
        "metadata": dict(row.metadata_data or {}),
        "tags": list(row.tags or []),
        "created_at": row.created_at,
    }


def _load_from_db() -> None:
    if not _db_available:
        return
    try:
        with SessionLocal() as db:
            for row in db.query(ResourceRecord).all():
                _resources[row.id] = _row_to_dict(row)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[resources] DB load failed, memory only: %s", type(exc).__name__)


def persist_resource(record: dict[str, Any]) -> None:
    """双写：内存缓存 + SQLite。chat pipeline 与 save 端点统一走这里。"""
    rid = str(record.get("id", ""))
    if not rid:
        return
    _resources[rid] = record
    if not _db_available:
        return
    try:
        with SessionLocal() as db:
            row = db.get(ResourceRecord, rid)
            if row is None:
                row = ResourceRecord(id=rid)
                db.add(row)
            row.user_id = str(record.get("user_id", ""))
            row.type = str(record.get("type", "document"))
            row.title = str(record.get("title", ""))[:512]
            row.content = str(record.get("content", ""))
            row.content_type = str(record.get("content_type", "markdown"))
            row.agent_name = str(record.get("agent_name", ""))
            row.metadata_data = dict(record.get("metadata") or {})
            row.tags = list(record.get("tags") or [])
            row.created_at = float(record.get("created_at") or 0.0)
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[resources] DB persist failed for %s: %s", rid, type(exc).__name__)


def get_resource_dict(resource_id: str) -> dict[str, Any] | None:
    """按 ID 取资源 dict（内存缓存优先，DB 兜底）。teacher API 复用。"""
    cached = _resources.get(resource_id)
    if cached is not None:
        return cached
    if not _db_available:
        return None
    try:
        with SessionLocal() as db:
            row = db.get(ResourceRecord, resource_id)
            if row is not None:
                record = _row_to_dict(row)
                _resources[resource_id] = record
                return record
    except Exception as exc:  # noqa: BLE001
        logger.warning("[resources] DB get failed for %s: %s", resource_id, type(exc).__name__)
    return None


def delete_resource_record(resource_id: str) -> bool:
    """删除资源（内存 + DB 双删）。teacher API 复用。"""
    found = resource_id in _resources
    _resources.pop(resource_id, None)
    if _db_available:
        try:
            with SessionLocal() as db:
                row = db.get(ResourceRecord, resource_id)
                if row is not None:
                    db.delete(row)
                    db.commit()
                    found = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("[resources] DB delete failed for %s: %s", resource_id, type(exc).__name__)
    return found


def evict_resource_cache(resource_ids: list[str]) -> None:
    """Evict records already removed by another transactional DB service."""
    for resource_id in resource_ids:
        _resources.pop(resource_id, None)


def _visible_to_student(record: dict[str, Any], user_id: str) -> bool:
    """学生可见范围：
    1. 自己的资源（Agent 为其生成 / 指派到个人）
    2. 教师发布的课程级资源（scope=course 且 status=published）
    3. 指派给自己的资源（target_user_ids 含自己 且已发布）
    """
    meta = record.get("metadata") or {}
    status = meta.get("status")
    scope = meta.get("scope")
    # A teacher assignment may store its first target as user_id. Ownership
    # must not expose an unpublished teacher draft.
    if scope in {"course", "student"} and status != "published":
        return False
    if production_mode():
        course = str(meta.get("course") or "").strip()
        if not course and scope in {"course", "student"}:
            return False
        if course:
            from sqlalchemy.exc import SQLAlchemyError

            from backend.app.repositories.auth_repo import AuthRepository

            try:
                if not AuthRepository().has_course(user_id, course):
                    return False
            except SQLAlchemyError as exc:
                raise HTTPException(status_code=503, detail="course_auth_storage_unavailable") from exc
    if scope == "student":
        return bool(user_id) and user_id in (meta.get("target_user_ids") or [])
    if record.get("user_id") == user_id:
        return True
    if status and status != "published":
        return False
    if scope == "course" and status == "published":
        return True
    if user_id and user_id in (meta.get("target_user_ids") or []):
        return True
    return False


def _resolve_course_attachment(storage_key: str) -> Path | None:
    """Only resolve files that were stored by the teacher-resource upload flow."""
    if not storage_key:
        return None
    root = _TEACHER_UPLOAD_ROOT.resolve()
    candidate = (root / Path(storage_key).name).resolve()
    if candidate.parent != root or not candidate.is_file():
        return None
    return candidate


_load_from_db()


@router.get("/list")
def list_resources(
    request: Request,
    user_id: str = Query(default=""),
    resource_type: str = Query(default=""),
    course: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """获取资源列表（学生视角：本人资源 + 课程已发布资源 + 指派给本人的资源）"""
    from backend.app.api.v1.auth import _get_session, _parse_bearer_token

    token = _parse_bearer_token(request.headers.get("Authorization"))
    session = _get_session(token)
    requested_user_id = user_id.strip()
    if session.role == "student":
        if requested_user_id and requested_user_id != session.account:
            raise HTTPException(status_code=403, detail="student_resource_scope_required")
        user_id = session.account

    items = list(_resources.values())

    if user_id:
        items = [r for r in items if _visible_to_student(r, user_id)]
    if resource_type:
        items = [r for r in items if r.get("type") == resource_type]
    if course:
        items = [
            r for r in items
            if str((r.get("metadata") or {}).get("course", "")).strip() == course
        ]

    items.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    items = items[:limit]

    return {
        "resources": items,
        "total": len(items),
    }


@router.get("/types")
def get_resource_types() -> dict[str, Any]:
    """获取支持的资源类型（必须注册在 /{resource_id} 之前，否则被动态路由遮蔽）"""
    return {
        "types": [
            {"key": "prompt", "label": "教师学习提示", "icon": "✦", "agent": "teacher"},
            {"key": "video", "label": "教师课程视频", "icon": "▶", "agent": "teacher"},
            {"key": "document", "label": "课程讲解文档", "icon": "📄", "agent": "course_expert"},
            {"key": "mindmap", "label": "知识思维导图", "icon": "🗺️", "agent": "multimodal"},
            {"key": "quiz", "label": "练习题库", "icon": "📝", "agent": "quiz_generator"},
            {"key": "code", "label": "代码实操案例", "icon": "💻", "agent": "multimodal"},
            {"key": "ppt", "label": "教学PPT", "icon": "📊", "agent": "multimodal"},
            {"key": "reading", "label": "拓展阅读", "icon": "📖", "agent": "course_expert"},
        ]
    }


@router.get("/{resource_id}")
def get_resource(resource_id: str, request: Request) -> dict[str, Any]:
    """获取单个资源详情；学生只能读取本人可见且已发布的资源。"""
    resource = get_resource_dict(resource_id)
    if not resource:
        return {"error": "not_found"}
    from backend.app.api.v1.auth import _get_session, _parse_bearer_token

    token = _parse_bearer_token(request.headers.get("Authorization"))
    session = _get_session(token)
    if session.role == "student" and not _visible_to_student(resource, session.account):
        raise HTTPException(status_code=404, detail="resource_not_available")
    return {"resource": resource}


@router.get("/{resource_id}/download")
def download_course_resource(
    resource_id: str,
    request: Request,
    user_id: str = Query(default=""),
) -> FileResponse:
    """Serve published course-wide or explicitly assigned teacher attachments."""
    resource = get_resource_dict(resource_id)
    metadata = (resource or {}).get("metadata") or {}
    attachment = metadata.get("attachment") or {}
    scope = metadata.get("scope")
    target_user_ids = metadata.get("target_user_ids") or []
    visible = scope == "course"
    if production_mode():
        from backend.app.api.v1.auth import _get_session, _parse_bearer_token

        session = _get_session(_parse_bearer_token(request.headers.get("Authorization")))
        if session.role == "student":
            if user_id and user_id != session.account:
                raise HTTPException(status_code=404, detail="resource_not_available")
            visible = resource is not None and _visible_to_student(resource, session.account)
    if scope == "student":
        from backend.app.api.v1.auth import _get_session, _parse_bearer_token

        token = _parse_bearer_token(request.headers.get("Authorization"))
        session = _get_session(token)
        assigned = bool(user_id) and user_id == session.account and user_id in target_user_ids
        visible = visible and assigned if production_mode() else assigned
    if metadata.get("status") != "published" or not visible:
        raise HTTPException(status_code=404, detail="resource_not_available")

    path = _resolve_course_attachment(str(attachment.get("storage_key") or ""))
    if path is None:
        raise HTTPException(status_code=404, detail="attachment_not_found")

    media_type = str(attachment.get("media_type") or "application/octet-stream")
    return FileResponse(
        path,
        media_type=media_type,
        filename=str(attachment.get("filename") or path.name),
        content_disposition_type="inline" if media_type.startswith(("video/", "audio/")) else "attachment",
    )


@router.post("/save")
def save_resource(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """保存 Agent 生成的资源"""
    from backend.app.api.v1.auth import _get_session, _parse_bearer_token

    session = _get_session(_parse_bearer_token(request.headers.get("Authorization")))
    user_id = str(payload.get("user_id") or "").strip()
    metadata = dict(payload.get("metadata") or {})
    if session.role == "student":
        if user_id and user_id != session.account:
            raise HTTPException(status_code=403, detail="student_resource_scope_required")
        if metadata.get("scope") in {"course", "student"} or metadata.get("target_user_ids"):
            raise HTTPException(status_code=403, detail="student_resource_publish_forbidden")
        user_id = session.account
    resource_id = f"res_{uuid.uuid4().hex[:10]}"
    resource = {
        "id": resource_id,
        "user_id": user_id,
        "type": payload.get("type", "document"),  # document/mindmap/quiz/code/ppt
        "title": payload.get("title", "未命名资源"),
        "content": payload.get("content", ""),
        "content_type": payload.get("content_type", "markdown"),
        "agent_name": payload.get("agent_name", ""),
        "metadata": metadata,
        "created_at": time.time(),
        "tags": payload.get("tags", []),
    }
    persist_resource(resource)

    return {"resource_id": resource_id, "resource": resource}


@router.delete("/{resource_id}")
def delete_resource(resource_id: str, request: Request) -> dict[str, Any]:
    """删除资源（内存 + DB 双删）"""
    from backend.app.api.v1.auth import _get_session, _parse_bearer_token

    session = _get_session(_parse_bearer_token(request.headers.get("Authorization")))
    if session.role == "student":
        record = get_resource_dict(resource_id)
        metadata = (record or {}).get("metadata") or {}
        if record and (record.get("user_id") != session.account or
                       metadata.get("scope") in {"course", "student"}):
            raise HTTPException(status_code=404, detail="resource_not_available")
    found = delete_resource_record(resource_id)
    return {"status": "deleted" if found else "not_found"}
