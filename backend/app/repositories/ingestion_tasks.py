"""Durable ingestion task ownership, idempotency and worker fencing."""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from backend.app.core.database import SessionLocal
from backend.app.core.models import IngestionTaskRecord


def _public(row: IngestionTaskRecord) -> dict:
    return {"task_id": row.id, "status": row.status, "course_id": row.course_id,
            "uploader": row.uploader, "document_id": row.document_id,
            "result": row.result or {}}


class IngestionTasks:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def create_or_get(self, *, uploader: str, course_id: str, filename: str,
                      data: bytes, deep_audit: bool, key: str = "") -> tuple[dict, bool]:
        digest = hashlib.sha256(key.encode()).hexdigest() if key else None
        fingerprint = hashlib.sha256(json.dumps({
            "uploader": uploader, "course_id": course_id, "filename": filename,
            "deep_audit": deep_audit, "content_hash": hashlib.sha256(data).hexdigest(),
        }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if digest:
            existing = self.find_by_key(uploader, digest)
            if existing:
                if existing["request_fingerprint"] != fingerprint:
                    raise ValueError("idempotency_key_conflict")
                return existing, False
        task_id = str(uuid.uuid4())
        try:
            with self.session_factory.begin() as db:
                db.add(IngestionTaskRecord(id=task_id, uploader=uploader, course_id=course_id,
                    idempotency_digest=digest, request_fingerprint=fingerprint,
                    status="queued", document_id=f"kbdoc-{task_id.replace('-', '')}",
                    result={}, created_at=time.time(), updated_at=time.time()))
        except IntegrityError:
            existing = self.find_by_key(uploader, digest) if digest else None
            if existing and existing["request_fingerprint"] == fingerprint:
                return existing, False
            raise ValueError("idempotency_key_conflict") from None
        return self.get(task_id), True

    def find_by_key(self, uploader: str, digest: str) -> dict | None:
        with self.session_factory() as db:
            row = db.scalars(select(IngestionTaskRecord).where(
                IngestionTaskRecord.uploader == uploader,
                IngestionTaskRecord.idempotency_digest == digest)).first()
            if row is None:
                return None
            return {**_public(row), "request_fingerprint": row.request_fingerprint}

    def get(self, task_id: str) -> dict | None:
        with self.session_factory() as db:
            row = db.get(IngestionTaskRecord, task_id)
            return _public(row) if row else None

    def claim(self, task_id: str, owner: str, *, lease_seconds: int = 900) -> bool:
        now = time.time()
        with self.session_factory.begin() as db:
            changed = db.execute(update(IngestionTaskRecord).where(
                IngestionTaskRecord.id == task_id,
                or_(IngestionTaskRecord.status.in_(("queued", "failed")),
                    and_(IngestionTaskRecord.status == "processing",
                         IngestionTaskRecord.lease_expires_at < now)),
            ).values(status="processing", lease_owner=owner,
                     lease_expires_at=now + lease_seconds, updated_at=now)).rowcount
            return changed == 1

    def complete(self, task_id: str, owner: str, value: dict) -> bool:
        with self.session_factory.begin() as db:
            changed = db.execute(update(IngestionTaskRecord).where(
                IngestionTaskRecord.id == task_id,
                IngestionTaskRecord.status == "processing",
                IngestionTaskRecord.lease_owner == owner,
            ).values(status="completed", result=value, lease_owner=None,
                     lease_expires_at=None, updated_at=time.time())).rowcount
            return changed == 1

    def fail(self, task_id: str, owner: str | None = None, code: str = "ingestion_failed") -> None:
        with self.session_factory.begin() as db:
            condition = [IngestionTaskRecord.id == task_id]
            if owner:
                condition.extend((IngestionTaskRecord.status == "processing",
                                  IngestionTaskRecord.lease_owner == owner))
            db.execute(update(IngestionTaskRecord).where(*condition).values(
                status="failed", result={"error": code}, lease_owner=None,
                lease_expires_at=None, updated_at=time.time()))
