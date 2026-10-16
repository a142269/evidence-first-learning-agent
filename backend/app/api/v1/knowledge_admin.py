"""知识库管理 API（教师/管理员）—— 建课 / 上传 / 文档管理 / 重建索引 / 命中测试。

挂载在 /api/v1/teacher/knowledge 前缀下：main.py 的鉴权中间件对
/api/v1/teacher/* 统一要求 teacher（含合并后的 admin）角色，无需逐接口校验。

对标产品设计（docs/08-知识库平台化改造方案.md）：
* Dify 的"知识库=一等实体 + 召回测试"
* RAGFlow 的"文档状态机 + 可干预"
* 星火知识库的"严格模式/信源定位"（命中测试返回 source + title_hint 供引用溯源）
"""
from __future__ import annotations

import logging
import asyncio
import os
import re
from typing import Any, Dict, Optional
import uuid

from fastapi import APIRouter, Body, File, Header, HTTPException, Query, UploadFile

from backend.app.services.course_registry import (
    CourseRegistryError,
    get_course_registry,
)
from backend.app.services.knowledge_ingest import (
    ALLOWED_SUFFIXES,
    KnowledgeIngestError,
    delete_document,
    ingest_document,
    list_documents,
)
from backend.app.services.ingestion_staging import staging_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teacher/knowledge", tags=["teacher-knowledge"])


def _celery_ingestion_enabled() -> bool:
    return os.getenv("CELERY_INGEST_ENABLED", "").lower() in {"1", "true", "yes"}


def _current_account(authorization: Optional[str]) -> str:
    """best-effort 取当前登录账号做 uploaded_by 追踪（中间件已保证 token 有效）。"""
    try:
        from backend.app.api.v1.auth import _get_session, _parse_bearer_token

        return _get_session(_parse_bearer_token(authorization)).account
    except Exception:  # noqa: BLE001 — 测试/内网直连场景无 token 时不阻塞
        return ""


# ================================================================
# 课程 CRUD
# ================================================================
@router.get("/courses")
def list_courses_admin() -> Dict[str, Any]:
    """教师视角课程清单（含草稿、文档统计）。"""
    registry = get_course_registry()
    courses = registry.list_courses(include_draft=True)
    doc_stats: Dict[str, Dict[str, int]] = {}
    for doc in list_documents():
        stat = doc_stats.setdefault(
            doc["course"], {"total": 0, "indexed": 0, "rejected": 0, "failed": 0}
        )
        stat["total"] += 1
        if doc["status"] in stat:
            stat[doc["status"]] += 1
    for course in courses:
        course["documents"] = doc_stats.get(
            course["id"], {"total": 0, "indexed": 0, "rejected": 0, "failed": 0}
        )
    return {"courses": courses, "total": len(courses)}


@router.post("/courses")
def create_course(
    payload: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """新建课程：目录 + course.yaml，立即出现在全端课程下拉中。"""
    try:
        course = get_course_registry().create_course(
            slug=str(payload.get("slug") or payload.get("id") or ""),
            display_name=str(payload.get("display_name") or ""),
            description=str(payload.get("description") or ""),
            owner=_current_account(authorization),
            status=str(payload.get("status") or "published"),
        )
    except CourseRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "created", "course": course}


@router.patch("/courses/{slug}")
def update_course(slug: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        course = get_course_registry().update_course(
            slug,
            display_name=payload.get("display_name"),
            description=payload.get("description"),
            status=payload.get("status"),
        )
    except CourseRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "updated", "course": course}


@router.post("/courses/{slug}/archive")
def archive_course(slug: str) -> Dict[str, Any]:
    """归档自建课程；学生端和常规课程选择器不再展示，课程数据保留。"""
    try:
        course = get_course_registry().archive_course(slug)
    except CourseRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "archived", "course": course}


@router.post("/courses/{slug}/restore")
def restore_course(slug: str) -> Dict[str, Any]:
    """将已归档课程恢复为教师可审核的草稿状态。"""
    try:
        course = get_course_registry().restore_course(slug)
    except CourseRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "restored_to_draft", "course": course}


@router.delete("/courses/{slug}")
def delete_course_permanently(
    slug: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """永久删除已归档的自建课程及其知识库文件、索引和课程级图谱。"""
    normalized = str(slug or "").strip().lower()
    if str(payload.get("confirm_slug") or "").strip().lower() != normalized:
        raise HTTPException(status_code=400, detail="confirm_slug_mismatch")

    registry = get_course_registry()
    course = registry.get_course(normalized)
    if course is None:
        raise HTTPException(status_code=404, detail=f"课程不存在: {normalized}")
    if course.get("builtin"):
        raise HTTPException(status_code=409, detail="builtin_course_protected")
    if course.get("status") != "archived":
        raise HTTPException(status_code=409, detail="archive_required_before_delete")

    try:
        from backend.app.services.knowledge_ingest import purge_course_records

        deleted = purge_course_records(normalized)
        registry.delete_course(normalized)
        try:
            from backend.app.services.rag_service import get_rag_service

            get_rag_service().refresh()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[knowledge-admin] course delete index refresh failed: %s", exc)
    except CourseRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[knowledge-admin] permanent course delete failed for %s", normalized)
        raise HTTPException(status_code=500, detail="course_delete_failed") from exc

    return {
        "status": "deleted",
        "course": normalized,
        "deleted": deleted,
        "student_records_preserved": True,
    }


# ================================================================
# 文档上传 / 列表 / 删除
# ================================================================
@router.post("/courses/{slug}/documents")
async def upload_document(
    slug: str,
    file: UploadFile = File(...),
    deep_audit: bool = Query(default=False, description="是否调用 LLM 深度审查"),
    authorization: Optional[str] = Header(default=None),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> Dict[str, Any]:
    """上传知识库文档，走完整摄取流水线（解析→审核→索引）。"""
    data = await file.read()
    filename = file.filename or "untitled.md"
    uploaded_by = _current_account(authorization)
    key = (idempotency_key or "").strip()
    if key and not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
        raise HTTPException(status_code=422, detail="invalid_idempotency_key")
    use_ledger = bool(key) or _celery_ingestion_enabled()
    task = None
    if use_ledger:
        from backend.app.repositories.ingestion_tasks import IngestionTasks

        try:
            task, created = await asyncio.to_thread(IngestionTasks().create_or_get,
                uploader=uploaded_by, course_id=slug.lower(), filename=filename,
                data=data, deep_audit=deep_audit, key=key)
        except ValueError:
            raise HTTPException(status_code=409, detail="idempotency_key_conflict") from None
        except Exception:
            raise HTTPException(status_code=503, detail="ingestion_storage_unavailable") from None
        if not created and task["status"] == "completed":
            document = task["result"]
            return {"status": document.get("status", "completed"),
                    "document": document, "task_id": task["task_id"]}
        if not created and task["status"] in {"queued", "processing"}:
            return {"status": task["status"], "task_id": task["task_id"],
                    "filename": filename,
                    "next": f"/api/v1/teacher/knowledge/ingestion-tasks/{task['task_id']}"}
    if _celery_ingestion_enabled():
        task_id = task["task_id"]
        staged = staging_path(task_id)
        staged.write_bytes(data)
        try:
            from backend.app.tasks.ingestion import ingest_staged_document

            ingest_staged_document.apply_async(
                kwargs={
                    "course": slug,
                    "filename": filename,
                    "staging_path": str(staged),
                    "uploaded_by": uploaded_by,
                    "deep_audit": deep_audit,
                },
                task_id=task_id,
            )
        except Exception as exc:  # noqa: BLE001
            staged.unlink(missing_ok=True)
            from backend.app.repositories.ingestion_tasks import IngestionTasks
            IngestionTasks().fail(task_id, code="ingestion_queue_unavailable")
            logger.exception("[knowledge-admin] unable to enqueue document ingestion")
            raise HTTPException(status_code=503, detail="ingestion_queue_unavailable") from exc
        return {
            "status": "queued",
            "task_id": task_id,
            "filename": filename,
            "next": f"/api/v1/teacher/knowledge/ingestion-tasks/{task_id}",
        }
    owner = uuid.uuid4().hex
    if task:
        from backend.app.repositories.ingestion_tasks import IngestionTasks
        if not await asyncio.to_thread(IngestionTasks().claim, task["task_id"], owner):
            raise HTTPException(status_code=409, detail="ingestion_task_busy")
    try:
        document = await ingest_document(
            course=slug,
            filename=filename,
            data=data,
            uploaded_by=uploaded_by,
            deep_audit=deep_audit,
            **({"task_id": task["task_id"]} if task else {}),
        )
    except KnowledgeIngestError as exc:
        if task:
            IngestionTasks().fail(task["task_id"], owner)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        if task:
            IngestionTasks().fail(task["task_id"], owner)
        raise
    if task:
        if not await asyncio.to_thread(IngestionTasks().complete, task["task_id"], owner, document):
            raise HTTPException(status_code=409, detail="ingestion_lease_lost")
    return {"status": document["status"], "document": document,
            **({"task_id": task["task_id"]} if task else {})}


@router.get("/ingestion-tasks/{task_id}")
def ingestion_task_status(task_id: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Expose Celery state without leaking broker internals to the frontend."""
    from backend.app.repositories.ingestion_tasks import IngestionTasks

    saved = IngestionTasks().get(task_id)
    if saved:
        account = _current_account(authorization)
        if saved["uploader"] and account != saved["uploader"]:
            raise HTTPException(status_code=403, detail="ingestion_task_access_denied")
        response = {"task_id": task_id, "status": saved["status"]}
        if saved["status"] == "completed":
            response["document"] = saved["result"]
        elif saved["status"] == "failed":
            response["error"] = saved["result"].get("error", "ingestion_failed")
        return response
    try:
        from backend.app.worker import celery_app

        task = celery_app.AsyncResult(task_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="ingestion_queue_unavailable") from exc
    response: Dict[str, Any] = {"task_id": task_id, "status": task.status.lower()}
    if task.successful():
        response["document"] = task.result
    elif task.failed():
        response["error"] = str(task.result)
    return response


@router.get("/courses/{slug}/documents")
def course_documents(slug: str) -> Dict[str, Any]:
    return {
        "course": str(slug).lower(),
        "documents": list_documents(course=slug),
        "allowed_suffixes": sorted(ALLOWED_SUFFIXES),
    }


@router.delete("/documents/{doc_id}")
def remove_document(doc_id: str) -> Dict[str, Any]:
    try:
        info = delete_document(doc_id)
    except KnowledgeIngestError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted", "document": info}


# ================================================================
# 索引运维
# ================================================================
@router.post("/courses/{slug}/reindex")
def reindex_course(
    slug: str,
    force: bool = Query(default=False, description="true=全库重建，false=增量刷新"),
) -> Dict[str, Any]:
    from backend.app.services.rag_service import get_rag_service

    registry = get_course_registry()
    if registry.get_course(slug) is None:
        raise HTTPException(status_code=404, detail=f"课程不存在: {slug}")
    stats = get_rag_service().refresh(force_rebuild=force)
    return {"status": "reindexed", "course": str(slug).lower(), "rag": stats}


@router.post("/hit-test")
def hit_test(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """命中测试（对标 Dify 召回测试）：输入问题，返回召回分段+得分+来源。"""
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query_required")
    course = str(payload.get("course") or "").strip().lower() or None
    top_k = max(1, min(int(payload.get("top_k") or 5), 20))

    from backend.app.services.rag_service import get_rag_service

    chunks = get_rag_service().retrieve(query, top_k=top_k, course_filter=course)
    return {
        "query": query,
        "course": course,
        "total": len(chunks),
        "chunks": [
            {
                "content": c["content"][:600],
                "source": c["source"],
                "course": c["course"],
                "score": round(float(c.get("score") or 0.0), 4),
                "title_hint": c.get("title_hint") or "",
            }
            for c in chunks
        ],
    }


# ================================================================
# 知识点图谱：自动生成（新课程零配置获得图谱）
# ================================================================
@router.post("/courses/{slug}/generate-map")
def generate_course_map(slug: str) -> Dict[str, Any]:
    """从课程 Markdown 的标题结构启发式生成知识点图谱并灌入图谱库。

    产出 knowledge_base/<slug>/knowledge_map.yaml；
    已有课程级图谱文件时会被覆盖（存量 AI/PY 走旧全局文件，不受影响）。
    """
    registry = get_course_registry()
    course = registry.get_course(slug)
    if course is None:
        raise HTTPException(status_code=404, detail=f"课程不存在: {slug}")

    nodes = _heuristic_map_nodes(str(slug).lower())
    if not nodes:
        raise HTTPException(
            status_code=422,
            detail="课程内没有可提取标题的 Markdown 文档，请先上传知识文档",
        )
    registry.write_course_map(str(slug).lower(), nodes)

    seeded = _seed_kg_store(str(slug).lower(), nodes)
    return {
        "status": "generated",
        "course": str(slug).lower(),
        "node_count": len(nodes),
        "kg_seeded": seeded,
        "nodes": list(nodes.keys()),
    }


def _heuristic_map_nodes(slug: str) -> Dict[str, Dict[str, Any]]:
    """H1/H2 标题 → 知识点节点；按文档顺序串联先修关系。"""
    import re as _re

    registry = get_course_registry()
    course_dir = registry.root / slug
    prefix = "".join(part[0] for part in slug.split("_") if part)[:4].upper() or "KP"

    titles: list[str] = []
    seen: set[str] = set()
    for md_path in sorted(course_dir.glob("**/*.md")):
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _re.finditer(r"^#{1,2}\s+(.+?)\s*$", text, flags=_re.M):
            title = _re.sub(r"[#*`]|\d+[\.、]\s*", "", match.group(1)).strip()
            if 2 <= len(title) <= 40 and title not in seen:
                seen.add(title)
                titles.append(title)
        if len(titles) >= 40:
            break

    nodes: Dict[str, Dict[str, Any]] = {}
    prev_id: Optional[str] = None
    for index, title in enumerate(titles[:40], start=1):
        kp_id = f"{prefix}_{index:03d}"
        nodes[kp_id] = {
            "name": title,
            "difficulty": min(1 + index // 8, 5),
            "prerequisites": [prev_id] if prev_id else [],
            "keywords": [title],
            "estimated_hours": 2,
        }
        prev_id = kp_id
    return nodes


def _seed_kg_store(slug: str, nodes: Dict[str, Dict[str, Any]]) -> int:
    """把生成的节点灌入知识图谱库（与 insights.seed-from-map 同款逻辑）。"""
    try:
        from backend.app.services.knowledge_graph.store import get_kg_store

        store = get_kg_store()
        count = 0
        for kp_id, meta in nodes.items():
            store.upsert_kp(
                kp_id,
                name=str(meta.get("name", kp_id)),
                course=slug,
                description="",
                bloom_level="understand",
                metadata={"difficulty": meta.get("difficulty", 2)},
            )
            count += 1
        for kp_id, meta in nodes.items():
            for pre in meta.get("prerequisites") or []:
                if pre in nodes:
                    store.add_relation(str(pre), kp_id, "prerequisite", weight=1.0)
        return count
    except Exception as exc:  # noqa: BLE001 — 图谱库不可用不阻塞图谱文件生成
        logger.warning("[knowledge-admin] 图谱库灌入失败: %s", exc)
        return 0
