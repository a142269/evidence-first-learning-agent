from tests.a.test_learning_runs_v2_lifecycle import api as api, create


def test_learning_run_streams_citations(api):
    client, _ = api
    response = create(client, "What is a variable?")
    assert response.status_code == 200
    assert "event: run.started" in response.text
    assert "event: retrieval.completed" in response.text
    assert "event: answer.delta" in response.text
    assert "event: run.completed" in response.text
    assert "chapter.md" in response.text


def test_learning_run_requests_human_approval(api):
    client, _ = api
    response = create(client, "请解释 RAG，并请教师审核讲解内容", True)
    assert response.status_code == 200
    assert "event: review.required" in response.text
