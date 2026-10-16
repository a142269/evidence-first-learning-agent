from __future__ import annotations

import pytest

from backend.app.services import ingestion_staging


def test_upload_path_is_accepted_by_worker_and_escape_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "ingest_staging"
    monkeypatch.setattr(ingestion_staging, "staging_root", lambda: root)

    staged = ingestion_staging.staging_path("task-123")
    staged.write_bytes(b"lesson")
    assert ingestion_staging.resolve_staged_upload(str(staged)) == staged.resolve()

    outside = tmp_path / "other.upload"
    outside.write_bytes(b"other")
    with pytest.raises(ValueError, match="staging_path_outside_allowed_root"):
        ingestion_staging.resolve_staged_upload(str(outside))
    with pytest.raises(ValueError, match="staging_path_outside_allowed_root"):
        ingestion_staging.resolve_staged_upload(str(root / ".." / "other.upload"))
