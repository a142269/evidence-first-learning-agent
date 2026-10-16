"""One phase per process for real PostgreSQL unfinished-node recovery."""
import asyncio
import json
import os
from pathlib import Path
import sys


class Runtime:
    def __init__(self, phase):
        self.phase = phase
        self.searches = 0
        self.generations = 0

    def retrieve(self, _message, _course):
        if self.phase != "fail":
            raise AssertionError("committed retrieval replayed")
        self.searches += 1
        return [{"chunk_id": "c1", "source": "course.md", "content": "RAG evidence"}]

    async def generate(self, _message, _evidence, _user):
        self.generations += 1
        if self.phase == "fail":
            raise RuntimeError("injected_model_failure")
        return "Verified RAG answer"

    def citations(self, evidence):
        return [{"chunk_id": item["chunk_id"], "source": item["source"],
                 "label": item["source"], "score": 0} for item in evidence]


async def main(phase, run_id=""):
    url = os.environ["TEST_V2_POSTGRES_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
    os.environ.update({"DATABASE_URL": url, "V2_REQUIRE_CHECKPOINTER": "true",
                       "A3_OFFLINE_DEMO": "1", "OTEL_SDK_DISABLED": "true"})
    if phase == "migrate":
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "head")
        print(json.dumps({"migrated": True}))
        return
    from backend.app.agent_runtime import checkpointing
    from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph

    assert await checkpointing.initialize_checkpointer()
    try:
        if phase == "cleanup":
            await checkpointing.get_checkpointer().adelete_thread(run_id)
            print(json.dumps({"deleted": True}))
            return
        runtime = Runtime(phase)
        graph = EvidenceFirstGraph(runtime)
        if phase == "fail":
            state = {"run_id": run_id, "thread_id": run_id, "execution_id": "first",
                     "message": "RAG 是什么", "user_id": "pg-student",
                     "course_id": "artificial_intelligence", "require_approval": False}
            try:
                await graph.invoke(state)
            except RuntimeError as exc:
                assert str(exc) == "injected_model_failure"
            else:
                raise AssertionError("failure injection did not fire")
            saved = await graph.unfinished_checkpoint(run_id)
            assert saved["execution_id"] == "first" and runtime.searches == 1
            print(json.dumps({"run_id": run_id, "failed": True}))
            return
        assert phase == "recover"
        result = await graph.continue_unfinished(run_id, previous_execution_id="first",
                                                 execution_id="second")
        assert result["answer"].startswith("Verified RAG answer")
        assert runtime.searches == 0 and runtime.generations == 1
        print(json.dumps({"recovered": True}))
    finally:
        await checkpointing.shutdown_checkpointer()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(*sys.argv[1:]))
