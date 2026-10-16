"""Asynchronous document ingestion contract used by the enterprise worker.

The HTTP upload endpoint remains synchronous for backward compatibility.  New
callers can enqueue this task after persisting an uploaded file in shared
storage; the task then invokes the same guarded parser and index refresh used
by the legacy endpoint, so there are not two divergent ingestion pipelines.
"""
from __future__ import annotations

import asyncio
import uuid

from backend.app.services.ingestion_staging import resolve_staged_upload
from backend.app.worker import celery_app


@celery_app.task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def ingest_staged_document(
    self,
    *,
    course: str,
    filename: str,
    staging_path: str,
    uploaded_by: str = "",
    deep_audit: bool = False,
) -> dict:
    """Process a previously staged upload without exposing host file paths."""
    candidate = resolve_staged_upload(staging_path)
    from backend.app.repositories.ingestion_tasks import IngestionTasks

    ledger = IngestionTasks()
    task_id = str(getattr(self.request, "id", "") or "")
    existing = ledger.get(task_id) if task_id else None
    if existing and existing["status"] == "completed":
        return existing["result"]
    owner = uuid.uuid4().hex
    if existing and not ledger.claim(task_id, owner):
        current = ledger.get(task_id)
        return current["result"] if current and current["status"] == "completed" else {
            "status": "processing", "task_id": task_id}

    from backend.app.services.knowledge_ingest import ingest_document
    try:
        data = candidate.read_bytes()
        arguments = {"course": course, "filename": filename, "data": data,
                     "uploaded_by": uploaded_by, "deep_audit": deep_audit}
        if existing:
            arguments["task_id"] = task_id
        result = asyncio.run(ingest_document(**arguments))
        if existing and not ledger.complete(task_id, owner, result):
            raise RuntimeError("ingestion_lease_lost")
        candidate.unlink(missing_ok=True)
        return result
    except Exception:
        if existing:
            ledger.fail(task_id, owner)
        raise
