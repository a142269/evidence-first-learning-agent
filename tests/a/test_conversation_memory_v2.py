import time

from backend.app.agent_runtime.conversation_memory import load_conversation_memory
from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph
from backend.app.api.v2 import learning_runs
from backend.app.core.models import AgentRunRecord
from tests.a.test_learning_runs_v2_lifecycle import api as api, create, events


def test_memory_survives_graph_recreation_and_reaches_next_generation(api, monkeypatch):
    client, _ = api
    run_id = events(create(client, "我在学习 RAG"))[0][1]["run_id"]
    seen = []
    async def generate(message, evidence, user_id, history=None):
        seen.extend(history or [])
        return "这是基于上一轮内容的解释"
    monkeypatch.setattr(learning_runs._runtime, "generate", generate)
    monkeypatch.setattr(learning_runs, "_graph", EvidenceFirstGraph(learning_runs._runtime))
    response = create(client, "再解释一下刚才的流程")
    assert events(response)[-1][1]["memory_run_ids"] == [run_id]
    assert seen[0] == {"role": "user", "content": "我在学习 RAG"}
    assert "private-draft" in seen[1]["content"]


def test_memory_is_scoped_bounded_and_excludes_unreleased_or_demo_runs(api):
    _, factory = api
    now = time.time()
    def row(index, *, user="alice", course="artificial_intelligence", session="memory", status="completed", eligible=True):
        return AgentRunRecord(id=str(index), user_id=user, session_id=session, status=status,
            created_at=now - 100 + index, metadata_data={"memory_eligible": eligible,
                "request": {"course_id": course, "message": "q" * 3000},
                "result": {"answer": "a" * 3000}})
    with factory() as db:
        db.add_all([row(index) for index in range(5)])
        db.add_all([row(10, user="bob"), row(11, course="other"), row(12, session="other"),
                    row(13, status="awaiting_approval"), row(14, status="reviewing"),
                    row(15, status="failed"), row(16, status="rejected"), row(17, eligible=False)])
        db.commit()
    history, ids = load_conversation_memory(factory, user_id="alice", session_id="memory",
                                            course_id="artificial_intelligence", before=now)
    assert ids == ["2", "3", "4"]
    assert len(history) == 6 and sum(len(item["content"]) for item in history) == 12000


def test_pending_review_is_not_added_to_followup_memory(api):
    client, _ = api
    create(client, "还未审核的内容", review=True)
    final = events(create(client, "解释 RAG"))[-1][1]
    assert final["memory_run_ids"] == []
