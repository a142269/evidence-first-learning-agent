"""Celery application for slow, retryable enterprise ingestion jobs."""
from __future__ import annotations

import os

from celery import Celery


def _setting(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


celery_app = Celery(
    "triple_u",
    broker=_setting("CELERY_BROKER_URL", _setting("REDIS_URL", "redis://localhost:6379/0")),
    backend=_setting("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=["backend.app.tasks.ingestion"],
)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_time_limit=15 * 60,
    task_soft_time_limit=12 * 60,
)
