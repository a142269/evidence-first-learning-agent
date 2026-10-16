import pytest

from backend.app.agent_runtime import checkpointing
from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph
from backend.app.api.v2 import learning_runs
from tests.a.test_learning_runs_v2_lifecycle import api as api, events


class FailOnceRuntime:
    def __init__(self):
        self.searches = 0
        self.generations = 0

    def retrieve(self, _message, _course):
        self.searches += 1
        return [{"chunk_id": "c1", "source": "chapter.md", "content": "RAG evidence"}]

    async def generate(self, _message, _evidence, _user):
        self.generations += 1
        if self.generations == 1:
            raise RuntimeError("transient failure after retrieve checkpoint")
        return "RAG uses retrieval"

    def citations(self, evidence):
        return [{"chunk_id": item["chunk_id"], "source": item["source"],
                 "label": item["source"], "score": 0} for item in evidence]


@pytest.mark.asyncio
async def test_unfinished_run_resumes_pending_node_without_retrieval_replay(monkeypatch):
    from langgraph.checkpoint.memory import InMemorySaver

    saver = InMemorySaver()
    monkeypatch.setattr(checkpointing, "get_checkpointer", lambda: saver)
    runtime = FailOnceRuntime()
    graph = EvidenceFirstGraph(runtime)
    state = {"run_id": "run-1", "thread_id": "run-1", "execution_id": "old-execution",
             "message": "RAG 是什么", "user_id": "alice", "course_id": "artificial_intelligence",
             "require_approval": False}
    with pytest.raises(RuntimeError, match="transient failure"):
        await graph.invoke(state)
    checkpoint = await graph.unfinished_checkpoint("run-1")
    assert checkpoint["execution_id"] == "old-execution"
    resumed = await graph.continue_unfinished("run-1", previous_execution_id="old-execution",
                                              execution_id="new-execution")
    assert resumed["answer"].startswith("RAG uses retrieval")
    assert runtime.searches == 1 and runtime.generations == 2
    with pytest.raises(ValueError, match="checkpoint_not_unfinished"):
        await graph.unfinished_checkpoint("run-1")


def test_api_continues_failed_node_with_new_lease(api, monkeypatch):
    client, _factory = api
    calls = {"retrieve": 0, "generate": 0}

    def retrieve(_message, _course):
        calls["retrieve"] += 1
        return [{"chunk_id": "c1", "source": "chapter.md", "content": "evidence"}]

    async def generate(_message, _evidence, _user):
        calls["generate"] += 1
        if calls["generate"] == 1:
            raise RuntimeError("transient failure")
        return "Verified answer"

    monkeypatch.setattr(learning_runs._runtime, "retrieve", retrieve)
    monkeypatch.setattr(learning_runs._runtime, "generate", generate)
    headers = {"Authorization": "Bearer alice"}
    first = events(client.post("/api/v2/learning-runs/stream", headers=headers,
        json={"message": "RAG 是什么", "course_id": "artificial_intelligence"}))
    assert first[-1][0] == "run.failed"
    run_id = first[0][1]["run_id"]
    continued = events(client.post(f"/api/v2/learning-runs/{run_id}/continue", headers=headers))
    assert continued[0][1]["resumed"] is True
    assert continued[-1][0] == "run.completed"
    assert calls == {"retrieve": 1, "generate": 2}
    again = client.post(f"/api/v2/learning-runs/{run_id}/continue", headers=headers)
    assert again.status_code == 409
