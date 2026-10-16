"""Disposable local Celery process probe; never invokes model providers."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
RUN = Path(os.environ["CELERY_PROBE_ROOT"]).resolve()
BROKER_URL = os.environ.get("CELERY_PROBE_BROKER_URL", "filesystem://")
BROKER = RUN / "broker"
STAGING = RUN / "staging"
CALLS = RUN / "calls.txt"
BLOCK = RUN / "block"
DB = RUN / "ledger.sqlite"
DATABASE_URL = os.environ.get("CELERY_PROBE_DATABASE_URL", f"sqlite:///{DB.as_posix()}")


def configure() -> None:
    sys.path.insert(0, str(ROOT))
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["CELERY_BROKER_URL"] = BROKER_URL
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
    os.environ["A3_OFFLINE_DEMO"] = "1"


def app():
    from backend.app.worker import celery_app

    if BROKER_URL == "filesystem://":
        celery_app.conf.broker_transport_options = {
            "data_folder_in": str(BROKER),
            "data_folder_out": str(BROKER),
            "data_folder_processed": str(RUN / "processed"),
        }
    celery_app.conf.worker_prefetch_multiplier = 1
    return celery_app


def worker() -> None:
    configure()
    from backend.app.services import ingestion_staging, knowledge_ingest

    ingestion_staging.staging_root = lambda: STAGING

    async def fake_ingest_document(**kwargs):
        with CALLS.open("a", encoding="utf-8") as stream:
            stream.write(kwargs["task_id"] + "\n")
        while BLOCK.exists():
            await asyncio.sleep(0.05)
        return {"id": f"kbdoc-{kwargs['task_id']}", "status": "indexed"}

    knowledge_ingest.ingest_document = fake_ingest_document
    app().worker_main(["worker", "--pool=solo", "--concurrency=1", "--loglevel=INFO",
                       "--without-gossip", "--without-mingle", "--without-heartbeat"])


def wait_for(predicate, label: str, timeout: float = 25.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise TimeoutError(label)


def start_worker(label: str):
    log = (RUN / f"{label}.log").open("w", encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen([sys.executable, __file__, "worker"], cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=flags)
    return process, log


def stop_worker(process, log):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log.close()


def main() -> None:
    RUN.mkdir(parents=True, exist_ok=False)
    BROKER.mkdir()
    STAGING.mkdir()
    (RUN / "processed").mkdir()
    configure()
    from sqlalchemy import update

    from backend.app.core.database import engine, SessionLocal
    from backend.app.core.models import IngestionTaskRecord
    from backend.app.repositories.ingestion_tasks import IngestionTasks
    from backend.app.tasks.ingestion import ingest_staged_document

    IngestionTaskRecord.__table__.create(engine, checkfirst=True)
    ledger = IngestionTasks()
    app()
    process, log = start_worker("success")
    try:
        task, _ = ledger.create_or_get(uploader="teacher", course_id="course-a",
                                       filename="one.md", data=b"one", deep_audit=False,
                                       key="worker-probe-001")
        task_id = task["task_id"]
        staged = STAGING / f"{task_id}.upload"
        staged.write_bytes(b"one")
        kwargs = dict(course="course-a", filename="one.md", staging_path=str(staged),
                      uploaded_by="teacher", deep_audit=False)
        ingest_staged_document.apply_async(kwargs=kwargs, task_id=task_id)
        wait_for(lambda: ledger.get(task_id)["status"] == "completed", "first completion")
        assert not staged.exists()
        ingest_staged_document.apply_async(kwargs=kwargs, task_id=task_id)
        wait_for(lambda: (RUN / "success.log").read_text(encoding="utf-8")
                 .count(f"[{task_id}] succeeded") >= 2, "duplicate delivery finished")
        assert CALLS.read_text(encoding="utf-8").splitlines().count(task_id) == 1
        print("duplicate_delivery: completed once")
    finally:
        stop_worker(process, log)

    BLOCK.write_text("wait", encoding="utf-8")
    process, log = start_worker("crash")
    try:
        task, _ = ledger.create_or_get(uploader="teacher", course_id="course-a",
                                       filename="two.md", data=b"two", deep_audit=False,
                                       key="worker-probe-002")
        task_id = task["task_id"]
        staged = STAGING / f"{task_id}.upload"
        staged.write_bytes(b"two")
        kwargs = dict(course="course-a", filename="two.md", staging_path=str(staged),
                      uploaded_by="teacher", deep_audit=False)
        ingest_staged_document.apply_async(kwargs=kwargs, task_id=task_id)
        wait_for(lambda: ledger.get(task_id)["status"] == "processing", "first claim")
        wait_for(lambda: CALLS.exists() and CALLS.read_text(encoding="utf-8")
                 .splitlines().count(task_id) == 1, "first ingest started")
    finally:
        stop_worker(process, log)

    assert ledger.get(task_id)["status"] == "processing"
    with SessionLocal.begin() as session:
        session.execute(update(IngestionTaskRecord).where(IngestionTaskRecord.id == task_id)
                        .values(lease_expires_at=time.time() - 1))
    BLOCK.unlink()
    process, log = start_worker("recovery")
    try:
        ingest_staged_document.apply_async(kwargs=kwargs, task_id=task_id)
        wait_for(lambda: ledger.get(task_id)["status"] == "completed", "lease recovery")
        assert CALLS.read_text(encoding="utf-8").splitlines().count(task_id) == 2
        assert not staged.exists()
        print("process_crash: expired lease reclaimed; second ingest completed")
    finally:
        stop_worker(process, log)


if __name__ == "__main__":
    worker() if sys.argv[1:] == ["worker"] else main()
