"""Real PostgreSQL + in-process HTTP API probe; only model/identity are scripted."""
import asyncio
from contextlib import ExitStack, nullcontext
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


async def run(phase, scenario, run_id=""):
    url = os.environ["TEST_V2_POSTGRES_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    sqlalchemy_url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    os.environ.update({"DATABASE_URL": sqlalchemy_url, "A3_OFFLINE_DEMO": "1",
        "V2_AUTH_REQUIRED": "true", "V2_REQUIRE_CHECKPOINTER": "true", "APP_ENV": "development",
        "V2_STUDENT_COURSES": "artificial_intelligence", "V2_TEACHER_COURSES": "artificial_intelligence",
        "OTEL_SDK_DISABLED": "true", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"})
    from backend.app.core import config
    config._dotenv_loaded, config._config = True, config.AppConfig()
    if phase == "migrate":
        from alembic import command
        from alembic.config import Config
        migration = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        command.upgrade(migration, "head")
        command.downgrade(migration, "20261011_0006")
        command.upgrade(migration, "head")
        print(json.dumps({"migration_roundtrip": True}), flush=True)
        return

    from fastapi import FastAPI, HTTPException
    from httpx import AsyncClient, ASGITransport
    from sqlalchemy import delete, select
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import AgentRunRecord, AgentCheckpointRecord, RetrievalLogRecord
    from backend.app.agent_runtime import checkpointing, run_audit
    from backend.app.agent_runtime.learning_package import LearningPackageGraph
    from backend.app.api.v2 import access, learning_runs, run_lifecycle
    from backend.app.evaluation.package_collection import ScriptedRuntime, parse_sse
    from backend.app.evaluation.learning_package import load_cases
    from tests.helpers.checkpoint_restart_worker import ResumeRuntime

    assert await checkpointing.initialize_checkpointer()
    if phase == "cleanup":
        await checkpointing.get_checkpointer().adelete_thread(run_id)
        with SessionLocal() as db:
            for model in (AgentCheckpointRecord, RetrievalLogRecord):
                db.execute(delete(model).where(model.run_id == run_id))
            db.execute(delete(AgentRunRecord).where(AgentRunRecord.id == run_id))
            db.commit()
        await checkpointing.shutdown_checkpointer()
        print(json.dumps({"deleted": True}), flush=True)
        return

    def principal(header):
        if header == "Bearer pg-student":
            return access.V2Principal("pg-student", "student", True)
        if header == "Bearer pg-teacher":
            return access.V2Principal("pg-teacher", "teacher", True)
        raise HTTPException(401, "test_identity_required")

    with ExitStack() as stack:
        stack.enter_context(patch.object(access, "_principal_from_authorization", principal))
        stack.enter_context(patch.object(run_lifecycle, "_principal_from_authorization", principal))
        stack.enter_context(patch.object(learning_runs, "learning_run_span", lambda *_a, **_kw: nullcontext()))
        for target in ("httpx.HTTPTransport.handle_request", "httpx.AsyncHTTPTransport.handle_async_request",
                       "requests.sessions.Session.request"):
            stack.enter_context(patch(target, side_effect=AssertionError("HTTP network disabled")))
        if phase == "crash":
            cases = load_cases(Path(__file__).resolve().parents[2] / "evals/learning_package_cases_v1.jsonl")
            runtime = ScriptedRuntime(next(case for case in cases if case.scenario == "unused_evidence"), learning_runs.LearningRuntime.citations)
        else:
            runtime = ResumeRuntime()
        stack.enter_context(patch.object(learning_runs, "_runtime", runtime))
        stack.enter_context(patch.object(learning_runs, "_package_graph", LearningPackageGraph(runtime)))
        app = FastAPI()
        app.include_router(learning_runs.router)
        student, teacher = {"Authorization": "Bearer pg-student"}, {"Authorization": "Bearer pg-teacher"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            if phase == "crash":
                original = run_audit.finish_run
                terminal = "awaiting_approval" if scenario == "pending" else "rejected" if scenario == "reject" else "completed"
                def finish(**kwargs):
                    if kwargs["status"] == terminal:
                        print(json.dumps({"run_id": kwargs["run_id"], "pid": os.getpid()}), flush=True)
                        os._exit(74)  # Checkpoint committed, Run write never happened.
                    return original(**kwargs)
                stack.enter_context(patch.object(run_audit, "finish_run", finish))
                response = await client.post("/api/v2/learning-runs/stream", headers=student,
                    json={"message": "解释 RAG 并给我三道练习", "mode": "learning_package",
                          "require_approval": scenario != "completed"})
                assert response.status_code == 200
                run_id = parse_sse(response.text)[0]["data"]["run_id"]
                decision = {"approved": scenario != "reject"}
                if scenario == "edit":
                    decision["edited_answer"] = "教师替换后的内容"
                await client.post(f"/api/v2/learning-runs/{run_id}/resume", headers=teacher, json=decision)
                raise AssertionError("crash injection was not reached")

            assert phase == "recover"
            with SessionLocal() as db:
                row = db.get(AgentRunRecord, run_id)
                assert row.status in {"running", "reviewing"} and row.execution_id
                previous_token = row.execution_id
                row.lease_expires_at = 0  # Advance only this test's lease; no 45-second sleep.
                db.commit()
            repaired = await client.post(f"/api/v2/learning-runs/{run_id}/reconcile", headers=teacher)
            assert repaired.status_code == 200
            expected = "awaiting_approval" if scenario == "pending" else "rejected" if scenario == "reject" else "completed"
            assert repaired.json()["status"] == expected
            read = await client.get(f"/api/v2/learning-runs/{run_id}", headers=student)
            result = read.json()["result"]
            if scenario == "pending":
                assert result == {"review_required": True}
                finished = await client.post(f"/api/v2/learning-runs/{run_id}/resume", headers=teacher, json={"approved": True})
                result = parse_sse(finished.text)[-1]["data"]
                assert result["status"] == "completed"
            if scenario in {"pending", "completed", "approve"}:
                assert len(result["learning_package"]["exercises"]) == 3
                assert "unused" not in {item["chunk_id"] for item in result["citations"]}
                assert result["budget"]["model_calls"] == 6
            else:
                assert not result.get("learning_package") and result["citations"] == []
                if scenario == "edit":
                    assert result["answer"] == "教师替换后的内容"
                else:
                    assert result["evidence"] == []
            # Even after successful recovery, the stale process cannot publish.
            try:
                run_audit.finish_run(run_id=run_id, status="failed", result={}, started_at=0, execution_id=previous_token)
            except run_audit.RunStateConflict:
                pass
            else:
                raise AssertionError("stale executor overwrote recovered result")
            with SessionLocal() as db:
                audits = list(db.scalars(select(AgentCheckpointRecord.status).where(AgentCheckpointRecord.run_id == run_id)))
                assert audits.count("run.lease_expired") == audits.count("run.reconciled") == 1
            await checkpointing.shutdown_checkpointer()
            print(json.dumps({"pid": os.getpid(), "recovered": expected, "stale_writer_blocked": True}), flush=True)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run(*sys.argv[1:]))
    except Exception as exc:
        import traceback
        frames = traceback.extract_tb(exc.__traceback__)
        print(json.dumps({"error_type": type(exc).__name__, "locations": [(Path(f.filename).name, f.lineno) for f in frames]}), file=sys.stderr)
        sys.exit(1)
