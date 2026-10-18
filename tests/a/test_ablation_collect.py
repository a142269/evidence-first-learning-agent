import json
from types import SimpleNamespace

import pytest

from scripts import collect_ablation
from backend.app.core import config as config_module


@pytest.mark.asyncio
async def test_resume_preserves_results_and_retrieval_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(collect_ablation, "ROOT", tmp_path)
    runner = tmp_path / "backend/app/evaluation/ablation_runner.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("runner", encoding="utf-8")
    cases = tmp_path / "cases.jsonl"
    cases.write_text('\n'.join(json.dumps({"id": id, "question": id, "course_id": "c"}) for id in ("ok", "bad")), encoding="utf-8")
    calls = []

    class Runtime:
        def retrieve(self, question, course):
            calls.append(("retrieve", question))
            if question == "bad":
                raise ValueError("unavailable")
            return [{"chunk_id": "c", "source": "s", "content": "evidence"}]

    async def run_arm(runtime, case, evidence, arm):
        calls.append(("model", case["id"], arm))
        return {"completed": True, "budget": {}, "latency_ms": 1, "model_calls": 1}

    monkeypatch.setattr(config_module, "get_config", lambda: SimpleNamespace(llm=SimpleNamespace(provider="openai_compatible", openai_api_key="test", openai_model="m")))
    monkeypatch.setattr(collect_ablation, "LearningRuntime", Runtime)
    monkeypatch.setattr(collect_ablation, "run_arm", run_arm)
    args = SimpleNamespace(cases=cases, case_id=[], output_dir=tmp_path / "output" / "run", resume=False)
    await collect_ablation.collect(args)
    rows = [json.loads(line) for line in (args.output_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 6
    assert len([row for row in rows if not row["completed"]]) == 3
    before = list(calls)
    args.resume = True
    await collect_ablation.collect(args)
    assert calls == before
