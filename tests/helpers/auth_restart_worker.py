"""Disposable auth API probe: real identities, no model or network calls."""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


def main():
    payload = json.load(sys.stdin)
    url = os.environ["TEST_AUTH_DATABASE_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
    os.environ.update(DATABASE_URL=url, APP_ENV="production", A3_OFFLINE_DEMO="1",
        V2_AUTH_REQUIRED="true", V2_COURSE_AUTH_MODE="database", OTEL_SDK_DISABLED="true",
        LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    from backend.app.core import config
    config._dotenv_loaded, config._config = True, config.AppConfig()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import delete
    from backend.app.api.v1 import auth
    from backend.app.api.v2 import learning_runs
    from backend.app.api.v2.run_lifecycle import WORKFLOW_VERSION
    from backend.app.core.database import SessionLocal, init_db
    from backend.app.core.models import AgentRunRecord
    from backend.app.core.passwords import hash_password
    from backend.app.repositories.account_repo import AccountRepository, StoredAccount
    from backend.app.repositories.auth_repo import AuthRepository

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(learning_runs.router)
    client = TestClient(app)
    phase, account, run_id = payload["phase"], payload["account"], payload["run_id"]
    if phase == "issue":
        if url.startswith("postgresql"):
            from alembic import command
            from alembic.config import Config
            command.upgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "head")
        else:
            init_db()
        AccountRepository().upsert(StoredAccount(account, hash_password("test-only-password"), "student", "Test"), create_only=True)
        AuthRepository().grant_course(account, "ai")
        with SessionLocal.begin() as db:
            db.add(AgentRunRecord(id=run_id, user_id=account, status="completed",
                workflow_type="evidence_first_learning", metadata_data={
                    "request": {"message": "test", "course_id": "ai", "user_id": account},
                    "workflow_version": WORKFLOW_VERSION, "thread_id": run_id,
                    "result": {"answer": "test-only saved result", "citations": []}}))
        response = client.post("/api/v1/auth/login", json={"account": account, "password": "test-only-password"})
        assert response.status_code == 200
        return {"token": response.json()["access_token"], "pid": os.getpid()}
    if phase == "cleanup":
        AccountRepository().delete(account)
        with SessionLocal.begin() as db:
            db.execute(delete(AgentRunRecord).where(AgentRunRecord.id == run_id))
        return {"cleaned": True}
    token = payload["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.get(f"/api/v2/learning-runs/{run_id}").status_code == 200
    AuthRepository().revoke_course(account, "ai")
    assert client.get(f"/api/v2/learning-runs/{run_id}").status_code == 403
    AuthRepository().grant_course(account, "ai")
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get(f"/api/v2/learning-runs/{run_id}").status_code == 401
    return {"pid": os.getpid(), "session_survived_restart": True, "revocation_verified": True}


if __name__ == "__main__":
    try:
        # ASGITransport/TestClient remain usable; outbound model/provider HTTP is blocked.
        with patch("httpx.HTTPTransport.handle_request", side_effect=AssertionError("HTTP disabled")), \
             patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=AssertionError("HTTP disabled")), \
             patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP disabled")):
            print(json.dumps(main()), flush=True)
    except Exception as exc:
        import traceback
        frames = traceback.extract_tb(exc.__traceback__)
        print(type(exc).__name__ + ": " + ", ".join(f"{Path(f.filename).name}:{f.lineno}" for f in frames), file=sys.stderr)
        sys.exit(1)
