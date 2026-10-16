"""知识库文档摄取流水线 —— 教师上传 → 解析 → 审核 → 入索引。

流水线（对标 Dify/RAGFlow 的知识库 ingestion 设计，见 docs/08）：

    上传原件 → 存 uploads/_raw/ → 提取正文(md/txt/pdf/docx)
      → KnowledgeGuardAgent 审核（内容安全/注入检测/质量）
      → 通过：写 uploads/<name>.md（RAG 扫描目录）→ 增量刷新索引
      → 拒绝：原件保留备查，不产出 .md，状态 rejected

状态机（KnowledgeDocumentRecord.status）：
    uploaded → parsing → indexed | failed | rejected

约定：
* 只有 .md 文件会被 rag_service 扫描入索引；上传原件一律放 uploads/_raw/
  （非 .md 后缀天然不入索引，.md 原件直接晋升为正文文件）
* storage_key / raw_storage_key 存 knowledge_base 相对路径，防路径穿透
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from backend.app.agents.knowledge_guard import get_knowledge_guard
from backend.app.core.database import SessionLocal
from backend.app.core.models import (
    DocumentChunkRecord,
    DocumentVersionRecord,
    KnowledgeDocumentRecord,
)
from backend.app.services.course_registry import get_course_registry

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = frozenset({".md", ".txt", ".pdf", ".docx"})
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ENTERPRISE_CHUNK_SIZE = 1200
ENTERPRISE_CHUNK_OVERLAP = 160


class KnowledgeIngestError(RuntimeError):
    """摄取入参非法（后缀/大小/课程不存在等），映射为 HTTP 400。"""


def _safe_filename(filename: str) -> str:
    cleaned = Path(str(filename or "").replace("\\", "/")).name.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise KnowledgeIngestError("文件名非法")
    return cleaned[:180]


def _unique_stem(stem: str, directory: Path, suffix: str) -> str:
    """同名文件自动追加短哈希，避免覆盖已有知识文档。"""
    candidate = stem
    counter = 0
    while (directory / f"{candidate}{suffix}").exists():
        counter += 1
        candidate = f"{stem}-{uuid.uuid4().hex[:6]}"
        if counter > 5:  # 理论上一次就够
            break
    return candidate


# ---------------------------------------------------------------------------
# 正文提取
# ---------------------------------------------------------------------------
def extract_text(data: bytes, suffix: str, filename: str = "") -> str:
    suffix = suffix.lower()
    if suffix in {".md", ".txt"}:
        for encoding in ("utf-8", "gbk", "utf-16"):
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, ValueError):
                continue
        raise KnowledgeIngestError("文本编码无法识别（请使用 UTF-8）")

    if suffix == ".pdf":
        try:
            from io import BytesIO

            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:
            raise KnowledgeIngestError(
                "服务器未安装 pypdf，无法解析 PDF；请上传 Markdown/TXT 或联系管理员安装"
            ) from exc
        try:
            reader = PdfReader(BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # noqa: BLE001
            raise KnowledgeIngestError(f"PDF 解析失败: {exc}") from exc
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        if not text.strip():
            raise KnowledgeIngestError("PDF 中未提取到文本（可能是扫描件，请先 OCR）")
        return text

    if suffix == ".docx":
        try:
            from io import BytesIO

            from docx import Document  # type: ignore
        except ImportError as exc:
            raise KnowledgeIngestError(
                "服务器未安装 python-docx，无法解析 Word；请上传 Markdown/TXT 或联系管理员安装"
            ) from exc
        try:
            document = Document(BytesIO(data))
            paragraphs = [p.text for p in document.paragraphs]
        except Exception as exc:  # noqa: BLE001
            raise KnowledgeIngestError(f"Word 解析失败: {exc}") from exc
        text = "\n\n".join(p.strip() for p in paragraphs if p.strip())
        if not text.strip():
            raise KnowledgeIngestError("Word 文档中未提取到文本")
        return text

    raise KnowledgeIngestError(
        f"暂不支持 {suffix} 格式，请上传 {'/'.join(sorted(ALLOWED_SUFFIXES))}"
    )


def _ensure_title(text: str, fallback_title: str) -> str:
    """正文若无一级/二级标题，补一个 H1，保证 RAG 分块的 title_hint 可用。"""
    if re.search(r"^#{1,2}\s+\S", text, flags=re.M):
        return text
    return f"# {fallback_title}\n\n{text}"


def _enterprise_chunks(text: str) -> list[str]:
    """Split text deterministically for versioned cloud-embedding ingestion."""
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    cursor = 0
    while cursor < len(normalized):
        end = min(len(normalized), cursor + ENTERPRISE_CHUNK_SIZE)
        if end < len(normalized):
            boundary = normalized.rfind("\n", cursor + ENTERPRISE_CHUNK_SIZE // 2, end)
            if boundary > cursor:
                end = boundary
        chunk = normalized[cursor:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        cursor = max(end - ENTERPRISE_CHUNK_OVERLAP, cursor + 1)
    return chunks


def _persist_enterprise_version(
    *,
    document_id: str,
    content_hash: str,
    text: str,
    status: str,
    filename: str,
    force_reembed: bool = False,
) -> dict[str, Any]:
    """Persist parse/version/chunk provenance without making cloud calls mandatory."""
    with SessionLocal() as session:
        latest = (
            session.query(DocumentVersionRecord)
            .filter(DocumentVersionRecord.document_id == document_id)
            .order_by(DocumentVersionRecord.version.desc())
            .first()
        )
        if latest and latest.content_hash == content_hash and latest.status == status and not force_reembed:
            return {"id": latest.id, "version": latest.version,
                    "chunk_count": session.query(DocumentChunkRecord).filter(
                        DocumentChunkRecord.document_version_id == latest.id).count(),
                    "embedding": (latest.metadata_data or {}).get("embedding", {})}
        next_version = int(latest.version) + 1 if latest else 1

    chunks = _enterprise_chunks(text) if status == "indexed" else []
    embeddings: list[list[float] | None] = [None] * len(chunks)
    embedding_meta: dict[str, Any] = {"status": "not_requested"}
    if chunks:
        from backend.app.services.embedding_provider import (
            EmbeddingProviderError,
            get_embedding_provider,
        )

        provider = get_embedding_provider()
        if provider.available:
            try:
                vectors: list[list[float]] = []
                for start in range(0, len(chunks), provider.batch_size):
                    vectors.extend(
                        provider.embed_documents(chunks[start : start + provider.batch_size])
                    )
                embeddings = vectors
                embedding_meta = {
                    "status": "embedded",
                    "provider": provider.provider_name,
                    "model": provider.model,
                    "dimension": provider.dimension,
                }
            except EmbeddingProviderError as exc:
                # Preserve the parsed version and legacy RAG availability.  The
                # status makes the missing vector index visible to operators.
                embedding_meta = {"status": "failed", "reason": str(exc)}
                logger.warning("[knowledge-ingest] cloud embedding skipped: %s", exc)
        else:
            embedding_meta = {"status": "not_configured"}

    version_id = f"docver-{uuid.uuid4().hex[:16]}"
    with SessionLocal() as session:
        version = DocumentVersionRecord(
            id=version_id,
            document_id=document_id,
            version=next_version,
            content_hash=content_hash,
            status=status,
            parser_name=Path(filename).suffix.lower().lstrip(".") or "text",
            metadata_data={
                "filename": filename,
                "chunk_size": ENTERPRISE_CHUNK_SIZE,
                "chunk_overlap": ENTERPRISE_CHUNK_OVERLAP,
                "embedding": embedding_meta,
            },
        )
        session.add(version)
        # ``DocumentChunkRecord`` does not declare an ORM relationship back to
        # its parent.  Flush the parent explicitly before adding children so
        # PostgreSQL always satisfies document_chunks.document_version_id's
        # foreign key, regardless of SQLAlchemy's table ordering.
        session.flush()
        for ordinal, chunk in enumerate(chunks):
            session.add(
                DocumentChunkRecord(
                    id=f"docchunk-{uuid.uuid4().hex[:18]}",
                    document_version_id=version_id,
                    ordinal=ordinal,
                    content=chunk,
                    content_hash=hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:16],
                    embedding=embeddings[ordinal],
                    metadata_data={"filename": filename},
                )
            )
        session.commit()
    return {
        "id": version_id,
        "version": next_version,
        "chunk_count": len(chunks),
        "embedding": embedding_meta,
    }


# ---------------------------------------------------------------------------
# 摄取主流程
# ---------------------------------------------------------------------------
async def ingest_document(
    course: str,
    filename: str,
    data: bytes,
    uploaded_by: str = "",
    deep_audit: bool = False,
    task_id: str = "",
) -> Dict[str, Any]:
    """完整摄取一份教师上传文档，返回文档记录 dict（含审核报告）。"""
    registry = get_course_registry()
    course = str(course or "").strip().lower()
    course_info = registry.get_course(course)
    if course_info is None:
        raise KnowledgeIngestError(f"课程不存在: {course}")

    filename = _safe_filename(filename)
    if task_id and not re.fullmatch(r"[0-9a-fA-F-]{36}", task_id):
        raise KnowledgeIngestError("非法摄取任务标识")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise KnowledgeIngestError(
            f"暂不支持 {suffix or '无后缀'} 文件，允许: {', '.join(sorted(ALLOWED_SUFFIXES))}"
        )
    if not data:
        raise KnowledgeIngestError("文件内容为空")
    if len(data) > MAX_UPLOAD_BYTES:
        raise KnowledgeIngestError("文件超过 20MB 上限")

    kb_root = registry.root
    uploads_dir = kb_root / course / "uploads"
    raw_dir = uploads_dir / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    doc_id = f"kbdoc-{task_id.replace('-', '')}" if task_id else f"kbdoc-{uuid.uuid4().hex[:12]}"
    if task_id:
        existing_result = None
        missing_version_hash = ""
        existing_status = ""
        with SessionLocal() as session:
            existing = session.get(KnowledgeDocumentRecord, doc_id)
            if existing is not None:
                existing_result = _record_to_dict(existing)
                latest = session.query(DocumentVersionRecord).filter(
                    DocumentVersionRecord.document_id == doc_id,
                ).order_by(DocumentVersionRecord.version.desc()).first()
                if latest is not None:
                    existing_result["version"] = {"id": latest.id, "version": latest.version,
                                                  "embedding": (latest.metadata_data or {}).get("embedding", {}),
                                                  "chunk_count": existing.chunk_count}
                else:
                    missing_version_hash = existing.content_hash
                    existing_status = existing.status
        if existing_result is not None:
            if "version" not in existing_result:
                # The prior worker committed the logical document but exited
                # before the enterprise version. Rebuild only the missing part.
                existing_result["version"] = _persist_enterprise_version(
                    document_id=doc_id, content_hash=missing_version_hash,
                    text=extract_text(data, suffix, filename),
                    status=existing_status, filename=filename)
            return existing_result
    record = KnowledgeDocumentRecord(
        id=doc_id,
        course=course,
        filename=filename,
        file_type=suffix.lstrip("."),
        size_bytes=len(data),
        status="parsing",
        uploaded_by=uploaded_by or "",
    )

    # 1. 原件落盘。RAG 会扫描 knowledge_base/**/*.md，因此 .md 原件必须改存
    #    为 .md.orig，避免与 uploads/<stem>.md 正文重复入索引。
    stem = f"upload-{task_id.replace('-', '')}" if task_id else _unique_stem(Path(filename).stem, uploads_dir, ".md")
    raw_suffix = f"{suffix}.orig" if suffix == ".md" else suffix
    raw_path = raw_dir / f"{stem}{raw_suffix}"
    raw_path.write_bytes(data)
    record.raw_storage_key = str(raw_path.relative_to(kb_root)).replace("\\", "/")

    guard = get_knowledge_guard()
    extracted_text = ""
    try:
        # 2. 正文提取
        text = extract_text(data, suffix, filename)
        extracted_text = text
        record.content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        # 3. KnowledgeGuard 审核（防幻觉源头防线）
        if deep_audit:
            audit = await guard.audit_with_llm(text, filename=filename, course=course)
        else:
            audit = guard.audit_document(text, filename=filename, course=course)
        record.audit = audit

        if audit["verdict"] == "rejected":
            record.status = "rejected"
            record.error_msg = "；".join(
                i["detail"] for i in audit["issues"] if i["level"] == "error"
            )[:500]
        else:
            # 4. 写入正文 .md（RAG 扫描目录）
            md_path = uploads_dir / f"{stem}.md"
            md_path.write_text(
                _ensure_title(text, Path(filename).stem), encoding="utf-8"
            )
            record.storage_key = str(md_path.relative_to(kb_root)).replace("\\", "/")

            # 5. 增量刷新索引，并统计本文档产出的 chunk 数
            from backend.app.services.rag_service import get_rag_service

            rag = get_rag_service()
            rag.refresh()
            record.chunk_count = rag.count_source_chunks(record.storage_key)
            record.status = "indexed"
    except KnowledgeIngestError as exc:
        record.status = "failed"
        record.error_msg = str(exc)[:500]
    except Exception as exc:  # noqa: BLE001 — 任何未知异常都要落到记录里，不能丢文档状态
        logger.exception("[knowledge-ingest] %s 摄取失败", filename)
        record.status = "failed"
        record.error_msg = f"内部错误: {exc}"[:500]

    with SessionLocal() as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        result = _record_to_dict(record)

    if extracted_text:
        try:
            result["version"] = _persist_enterprise_version(
                document_id=record.id,
                content_hash=record.content_hash,
                text=extracted_text,
                status=record.status,
                filename=filename,
            )
        except Exception as exc:  # noqa: BLE001 - legacy indexed doc remains usable
            logger.exception("[knowledge-ingest] enterprise version persistence failed")
            result["version"] = {"status": "failed", "error": str(exc)[:300]}

    registry.invalidate()
    return result


def backfill_curated_markdown(
    *, course: str, storage_key: str, text: str
) -> Dict[str, Any]:
    """Version and embed one bundled course Markdown file without re-uploading it.

    The initial enterprise implementation only vectorised teacher uploads.
    That makes pgvector technically present but leaves the curated curriculum
    on the legacy TF-IDF path.  This idempotent backfill is the migration path
    for trusted, repository-managed course material.  It deliberately refuses
    ``uploads/``: those documents must retain their normal teacher-ingestion
    audit trail.
    """
    normalized_course = str(course or "").strip().lower()
    normalized_key = str(storage_key or "").replace("\\", "/").lstrip("/")
    normalized_text = str(text or "").strip()
    if not normalized_course or not normalized_key or not normalized_text:
        raise KnowledgeIngestError("课程、资料路径和正文均不能为空")
    if "/uploads/" in f"/{normalized_key}" or normalized_key.startswith("uploads/"):
        raise KnowledgeIngestError("教师上传资料必须通过正式摄取流水线处理")

    content_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()[:16]
    filename = Path(normalized_key).name
    with SessionLocal() as session:
        document = (
            session.query(KnowledgeDocumentRecord)
            .filter(
                KnowledgeDocumentRecord.course == normalized_course,
                KnowledgeDocumentRecord.storage_key == normalized_key,
            )
            .first()
        )
        if document is None:
            document = KnowledgeDocumentRecord(
                id=f"seed-doc-{hashlib.sha256(normalized_key.encode('utf-8')).hexdigest()[:16]}",
                course=normalized_course,
                filename=filename,
                storage_key=normalized_key,
                file_type="md",
                size_bytes=len(normalized_text.encode("utf-8")),
                status="indexed",
                content_hash=content_hash,
                uploaded_by="system:curated-corpus",
                audit={"verdict": "trusted", "origin": "repository_curated"},
            )
            session.add(document)
            session.commit()
        else:
            latest = (
                session.query(DocumentVersionRecord)
                .filter(DocumentVersionRecord.document_id == document.id)
                .order_by(DocumentVersionRecord.version.desc())
                .first()
            )
            provider = None
            try:
                from backend.app.services.embedding_provider import get_embedding_provider

                provider = get_embedding_provider()
            except Exception:  # pragma: no cover - handled by persistence metadata
                pass
            latest_embedding = (latest.metadata_data or {}).get("embedding", {}) if latest else {}
            is_current = (
                latest is not None
                and latest.content_hash == content_hash
                and latest.status == "indexed"
                and latest_embedding.get("status") == "embedded"
                and (provider is None or (
                    latest_embedding.get("dimension") == provider.dimension
                    and latest_embedding.get("model") == provider.model
                ))
            )
            if is_current:
                return {
                    "storage_key": normalized_key,
                    "status": "unchanged",
                    "version": latest.version,
                    "chunk_count": document.chunk_count,
                }
            document.filename = filename
            document.size_bytes = len(normalized_text.encode("utf-8"))
            document.status = "indexed"
            document.content_hash = content_hash
            session.commit()
        document_id = document.id

    version = _persist_enterprise_version(
        document_id=document_id,
        content_hash=content_hash,
        text=normalized_text,
        status="indexed",
        filename=filename,
        force_reembed=True,
    )
    with SessionLocal() as session:
        document = session.get(KnowledgeDocumentRecord, document_id)
        if document is not None:
            document.chunk_count = int(version["chunk_count"])
            document.status = "indexed"
            session.commit()
    return {"storage_key": normalized_key, "status": "indexed", **version}


# ---------------------------------------------------------------------------
# 查询 / 删除
# ---------------------------------------------------------------------------
def list_documents(course: Optional[str] = None) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        query = session.query(KnowledgeDocumentRecord)
        if course:
            query = query.filter(KnowledgeDocumentRecord.course == str(course).lower())
        rows = query.order_by(KnowledgeDocumentRecord.created_at.desc()).all()
        return [_record_to_dict(row) for row in rows]


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    with SessionLocal() as session:
        row = session.get(KnowledgeDocumentRecord, str(doc_id))
        return _record_to_dict(row) if row else None


def delete_document(doc_id: str) -> Dict[str, Any]:
    """删除文档：正文 .md + 原件 + DB 记录，随后增量刷新索引清孤儿 chunk。"""
    registry = get_course_registry()
    kb_root = registry.root

    with SessionLocal() as session:
        row = session.get(KnowledgeDocumentRecord, str(doc_id))
        if row is None:
            raise KnowledgeIngestError(f"文档不存在: {doc_id}")
        info = _record_to_dict(row)
        session.delete(row)
        session.commit()

    for key in (info.get("storage_key"), info.get("raw_storage_key")):
        target = _resolve_kb_path(kb_root, key)
        if target is not None:
            try:
                target.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("[knowledge-ingest] 删除文件失败 %s: %s", target, exc)

    if info.get("storage_key"):
        try:
            from backend.app.services.rag_service import get_rag_service

            get_rag_service().refresh()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[knowledge-ingest] 删除后索引刷新失败: %s", exc)

    registry.invalidate()
    return info


def purge_course_records(course: str) -> Dict[str, int]:
    """清除某课程的知识库索引与课程级图谱记录。

    不触碰学生画像、学习路径、错题或个人资源：删除课程内容不应顺带
    擦除学生的历史学习证据。
    """
    from backend.app.core.models import (
        ChunkVectorRecord,
        KnowledgeChunkRecord,
        KnowledgeDocumentRecord,
        KnowledgePointRecord,
        KnowledgeRelationRecord,
    )

    normalized = str(course or "").strip().lower()
    counts = {
        "documents": 0,
        "knowledge_chunks": 0,
        "chunk_vectors": 0,
        "knowledge_points": 0,
        "knowledge_relations": 0,
    }
    with SessionLocal() as session:
        try:
            chunk_ids = [
                row[0]
                for row in session.query(KnowledgeChunkRecord.chunk_id)
                .filter(KnowledgeChunkRecord.course == normalized)
                .all()
            ]
            if chunk_ids:
                counts["chunk_vectors"] = int(
                    session.query(ChunkVectorRecord)
                    .filter(ChunkVectorRecord.chunk_id.in_(chunk_ids))
                    .delete(synchronize_session=False)
                )
            counts["knowledge_chunks"] = int(
                session.query(KnowledgeChunkRecord)
                .filter(KnowledgeChunkRecord.course == normalized)
                .delete(synchronize_session=False)
            )
            counts["documents"] = int(
                session.query(KnowledgeDocumentRecord)
                .filter(KnowledgeDocumentRecord.course == normalized)
                .delete(synchronize_session=False)
            )

            point_ids = [
                row[0]
                for row in session.query(KnowledgePointRecord.id)
                .filter(KnowledgePointRecord.course == normalized)
                .all()
            ]
            if point_ids:
                counts["knowledge_relations"] = int(
                    session.query(KnowledgeRelationRecord)
                    .filter(
                        (KnowledgeRelationRecord.source_id.in_(point_ids))
                        | (KnowledgeRelationRecord.target_id.in_(point_ids))
                    )
                    .delete(synchronize_session=False)
                )
            counts["knowledge_points"] = int(
                session.query(KnowledgePointRecord)
                .filter(KnowledgePointRecord.course == normalized)
                .delete(synchronize_session=False)
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
    return counts


def _resolve_kb_path(kb_root: Path, storage_key: Any) -> Optional[Path]:
    key = str(storage_key or "").strip()
    if not key:
        return None
    target = (kb_root / key).resolve()
    try:
        target.relative_to(kb_root.resolve())
    except ValueError:
        logger.warning("[knowledge-ingest] 拒绝越界路径: %s", key)
        return None
    return target


def _record_to_dict(record: KnowledgeDocumentRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "course": record.course,
        "filename": record.filename,
        "storage_key": record.storage_key,
        "raw_storage_key": record.raw_storage_key,
        "file_type": record.file_type,
        "size_bytes": record.size_bytes,
        "status": record.status,
        "chunk_count": record.chunk_count,
        "audit": record.audit or {},
        "error_msg": record.error_msg,
        "uploaded_by": record.uploaded_by,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
