"""Shared staging path contract for upload requests and ingestion workers."""
from __future__ import annotations

from pathlib import Path


def staging_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "ingest_staging"


def staging_path(task_id: str) -> Path:
    root = staging_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{task_id}.upload"


def resolve_staged_upload(path: str) -> Path:
    root = staging_root().resolve()
    candidate = Path(path).resolve()
    if root not in candidate.parents:
        raise ValueError("staging_path_outside_allowed_root")
    return candidate
