"""Subprocess queue-worker probe for QWEN-301: claim and execute one queued run.

argv: <sqlite-file-path> <mode: hang|quick>

The database URL is set before any backend import so this process binds to the
caller's isolated SQLite file.  Only offline stubs are used: no model, no
network, no ``.env``.  ``hang`` blocks inside generation so the parent test can
kill the process mid-run; ``quick`` completes the run.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


def citations(evidence):
    return [{"source": item["source"], "chunk_id": item["chunk_id"], "label": item["source"]}
            for item in evidence]


class StubRuntime:
    citations = staticmethod(citations)

    def retrieve(self, *_args):
        return [{"source": "queue.md", "chunk_id": "c1", "content": "队列 worker 探针的测试证据"}]

    async def generate(self, *_args):
        if os.environ["RUN_QUEUE_PROBE_MODE"] == "hang":
            await asyncio.sleep(600)
        return "队列 worker 探针的测试回答"


def main():
    db_path, mode = sys.argv[1], sys.argv[2]
    os.environ["DATABASE_URL"] = "sqlite:///" + Path(db_path).resolve().as_posix()
    os.environ["RUN_QUEUE_PROBE_MODE"] = mode
    os.environ.update({"A3_OFFLINE_DEMO": "true", "LLM_PROVIDER": "none", "APP_ENV": "development",
                       "V2_AUTH_REQUIRED": "true", "V2_REQUIRE_CHECKPOINTER": "false",
                       "V2_STUDENT_COURSES": "artificial_intelligence",
                       "V2_TEACHER_COURSES": "artificial_intelligence",
                       "OTEL_SDK_DISABLED": "true", "LANGSMITH_TRACING": "false",
                       "LANGCHAIN_TRACING_V2": "false"})
    from backend.app.core import config
    config._dotenv_loaded, config._config = True, config.AppConfig()
    from backend.app.agent_runtime import run_worker
    from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph
    from backend.app.api.v2 import learning_runs

    learning_runs._graph = EvidenceFirstGraph(StubRuntime())
    outcome = run_worker.work_once(f"probe-{mode}")
    print(json.dumps({"outcome": outcome, "pid": os.getpid()}), flush=True)


if __name__ == "__main__":
    try:
        with patch("httpx.HTTPTransport.handle_request", side_effect=AssertionError("HTTP disabled")), \
             patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=AssertionError("HTTP disabled")), \
             patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP disabled")):
            main()
    except Exception as exc:
        import traceback
        frames = traceback.extract_tb(exc.__traceback__)
        print(type(exc).__name__ + ": " + ", ".join(f"{Path(f.filename).name}:{f.lineno}" for f in frames), file=sys.stderr)
        sys.exit(1)
