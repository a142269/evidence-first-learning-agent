"""Synthetic ASGI collection for the real learning-package workflow.

This developer-only harness patches process-global dependencies; run it in a
dedicated CLI process, never inside a live application or concurrently. It
does not test retrieval relevance, model quality or production authentication.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import patch
import uuid

from backend.app.evaluation.learning_package import PackageCase

COLLECTOR_VERSION = "offline-package-1.0"


class ScriptedRuntime:
    """Only provider boundaries are scripted; graph outputs are never fabricated."""

    def __init__(self, case: PackageCase, citations):
        self.case = case
        self.citations = citations
        self.trace = []
        self.search_count = 0
        sources = case.expected_sources or ("artificial_intelligence/chapters/09_rag.md",)
        self.hits = [{"chunk_id": f"c{i}", "source": source,
                      "content": "[离线检索桩] 用于工作流契约测试，不是课程事实质量验收。"}
                     for i, source in enumerate(sources, 1)]
        ids = [item["chunk_id"] for item in self.hits]
        if case.scenario == "same_source_chunks":
            self.hits.append({**self.hits[0], "chunk_id": "complement"})
            ids.append("complement")
        if case.scenario in {"unused_evidence", "review_changes_sources"}:
            self.hits.append({"chunk_id": "unused", "source": "fixtures/unused-evidence.md",
                              "content": "[离线注入] 未被最终学习包使用的资料。"})

        def artifacts(source_ids, revision=False):
            lesson = {"explanation": ("[离线测试桩·修订] " if revision else "[离线测试桩·初稿] ")
                      + case.question + "本段仅用于验证工作流，不代表模型生成质量。",
                      "source_ids": source_ids}
            practice = {"exercises": [{"question": f"[离线测试桩] 第 {i + 1} 道练习",
                         "answer": "修订后的模拟答案" if revision else "初始模拟答案",
                         "explanation": "[离线测试桩] 仅检验引用与依赖传递，不用于知识正确性评分。",
                         "source_ids": [source_ids[i % len(source_ids)]]} for i in range(3)]}
            return lesson, practice

        initial_ids = ["unused"] if case.scenario == "review_changes_sources" else ids
        lesson, practice = artifacts(initial_ids)
        revised_lesson, revised_practice = artifacts(ids, True)
        plan = {"steps": [
            {"id": "tutor", "role": "tutor", "goal": case.question[:500], "depends_on": []},
            {"id": "practice", "role": "practice", "goal": "三道递进练习", "depends_on": ["tutor"]},
        ]}
        search = {"action": "search_course", "query": "课程证据检索"}
        finish = {"action": "finish"}
        approve = {"approved": True, "issues": []}
        reject = {"approved": False, "issues": ["请修正讲解及题目，重新核对证据引用。"]}
        self.script = [("Planner", plan), ("Tutor", search)]
        if case.scenario == "invalid_model_output":
            self.script = [("Planner", "[离线注入] invalid JSON")]
        elif case.scenario == "model_budget_exhausted":
            pass  # Two permitted calls; the next call must fail before reaching this runtime.
        elif case.scenario == "no_evidence":
            self.script.append(("Tutor", finish))
        else:
            if case.scenario == "empty_then_evidence":
                self.script.append(("Tutor", {**search, "query": "补充课程证据检索"}))
            self.script.append(("Tutor", search if case.scenario == "repeated_search" else finish))
            if case.scenario == "fabricated_citation":
                self.script.append(("Tutor", {**lesson, "source_ids": ["fabricated"]}))
            else:
                self.script.extend([("Tutor", lesson), ("Practice", practice)])
                if case.scenario in {"review_once", "review_changes_sources", "review_twice"}:
                    self.script.extend([("Reviewer", reject), ("Tutor", revised_lesson),
                                        ("Practice", revised_practice),
                                        ("Reviewer", reject if case.scenario == "review_twice" else approve)])
                else:
                    self.script.append(("Reviewer", approve))

    @staticmethod
    def _profile_context(_user_id):
        return "[离线测试桩] 无真实学生画像，使用通用解释。"

    async def complete_structured(self, messages, *, max_tokens):
        if not self.script:
            raise RuntimeError("offline_unexpected_model_call")
        role, output = self.script.pop(0)
        if f" {role}。" not in messages[0]["content"] or max_tokens != 2048:
            raise RuntimeError("offline_model_contract_mismatch")
        payload = json.loads(messages[1]["content"])
        self.trace.append({"sequence": len(self.trace) + 1, "kind": "model", "role": role,
                           "output": deepcopy(output), "dependencies": payload.get("dependencies", {}),
                           "review_feedback": payload.get("review_feedback", [])})
        return output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)

    def retrieve(self, query, course_id):
        if course_id != self.case.course_id:
            raise RuntimeError("offline_course_scope_mismatch")
        self.search_count += 1
        empty = self.case.scenario == "no_evidence" or (self.case.scenario == "empty_then_evidence" and self.search_count == 1)
        hits = [] if empty else deepcopy(self.hits)
        self.trace.append({"sequence": len(self.trace) + 1, "kind": "retrieval", "query": query,
                           "course_id": course_id, "chunk_ids": [item["chunk_id"] for item in hits]})
        return hits

    def injection_checks(self):
        models = [item for item in self.trace if item["kind"] == "model"]
        searches = [item for item in self.trace if item["kind"] == "retrieval"]
        reviews = [item["output"] for item in models if item["role"] == "Reviewer"]
        # Guard rejection is evaluated by the real guard; no model output is supplied.
        guard_case = self.case.expected_outcome == "rejected"
        checks = {"script_consumed": not self.script if not guard_case else not self.trace,
                  "course_scope": all(item["course_id"] == self.case.course_id for item in searches)}
        scenario = self.case.scenario
        if scenario == "empty_then_evidence":
            checks["empty_then_evidence"] = len(searches) == 2 and not searches[0]["chunk_ids"] and bool(searches[1]["chunk_ids"])
        elif scenario in {"review_once", "review_changes_sources", "review_twice"}:
            checks["review_decisions"] = len(reviews) == 2 and reviews[0]["approved"] is False and reviews[1]["approved"] is (scenario != "review_twice")
            lessons = [item["output"] for item in models if isinstance(item["output"], dict) and "explanation" in item["output"]]
            practices = [item for item in models if item["role"] == "Practice"]
            checks["downstream_regenerated"] = len(lessons) == len(practices) == 2 and lessons[0] != lessons[1] and practices[1]["dependencies"] == {"tutor": lessons[1]}
            if scenario == "review_changes_sources":
                checks["sources_changed"] = len(lessons) == 2 and lessons[0]["source_ids"] != lessons[1]["source_ids"]
        elif scenario == "repeated_search":
            decisions = [item["output"] for item in models if isinstance(item["output"], dict) and item["output"].get("action") == "search_course"]
            checks["duplicate_not_executed"] = len(decisions) == 2 and decisions[0] == decisions[1] and len(searches) == 1
        elif scenario == "model_budget_exhausted":
            checks["stopped_before_third_call"] = len(models) == 2 and len(searches) == 1
        elif scenario == "no_evidence":
            checks["empty_retrieval"] = len(searches) == 1 and not searches[0]["chunk_ids"]
        elif scenario == "fabricated_citation":
            checks["fabricated_id_injected"] = bool(models) and models[-1]["output"].get("source_ids") == ["fabricated"]
        elif scenario == "invalid_model_output":
            checks["invalid_json_injected"] = len(models) == 1 and isinstance(models[0]["output"], str)
        elif scenario == "unused_evidence":
            checks["unused_evidence_injected"] = bool(searches) and "unused" in searches[0]["chunk_ids"]
        elif scenario == "same_source_chunks":
            checks["complement_injected"] = bool(searches) and "complement" in searches[0]["chunk_ids"]
        return checks


def parse_sse(text):
    """Preserve complete frames, including deltas, for independent replay."""
    frames = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = "", []
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].lstrip()
            elif line.startswith("data:"):
                data.append(line[5:].lstrip())
        if data:
            payload = json.loads("\n".join(data))
            if not name or not isinstance(payload, dict):
                raise ValueError("offline_invalid_sse_frame")
            frames.append({"name": name, "data": payload})
    return frames


@contextmanager
def offline_api(database_path: Path):
    """Isolate all production adapters; the real API, graph and run audit execute."""
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {
            "A3_OFFLINE_DEMO": "1", "DATABASE_URL": "sqlite:///:memory:", "APP_ENV": "development",
            "V2_AUTH_REQUIRED": "true", "V2_REQUIRE_CHECKPOINTER": "false",
            "V2_STUDENT_COURSES": "artificial_intelligence", "V2_TEACHER_COURSES": "artificial_intelligence",
            "OTEL_SDK_DISABLED": "true", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
        }))
        from backend.app.core import config
        # Use a credential-free config before importing API/database modules.
        stack.enter_context(patch.object(config, "_dotenv_loaded", True))
        stack.enter_context(patch.object(config, "_config", config.AppConfig()))
        from fastapi import FastAPI, HTTPException
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from backend.app.agent_runtime import run_audit
        from backend.app.api.v2 import access, learning_runs, run_lifecycle
        from backend.app.core.models import AgentRunRecord, AgentCheckpointRecord, RetrievalLogRecord

        engine = create_engine(f"sqlite:///{database_path.resolve().as_posix()}", connect_args={"check_same_thread": False})
        stack.callback(engine.dispose)
        for model in (AgentRunRecord, AgentCheckpointRecord, RetrievalLogRecord):
            model.__table__.create(engine)
        factory = sessionmaker(bind=engine)
        stack.enter_context(patch.object(run_audit, "SessionLocal", factory))
        stack.enter_context(patch.object(run_lifecycle, "SessionLocal", factory))
        stack.enter_context(patch.object(learning_runs, "learning_run_span", lambda *_a, **_kw: nullcontext()))

        def principal(header):
            if header != "Bearer offline-student":
                raise HTTPException(401, "offline_identity_required")
            return access.V2Principal("offline-student", "student", True)

        stack.enter_context(patch.object(access, "_principal_from_authorization", principal))
        stack.enter_context(patch.object(run_lifecycle, "_principal_from_authorization", principal))
        # ASGITransport never uses these network transports. Accidental real HTTP fails.
        stack.enter_context(patch("httpx.HTTPTransport.handle_request", side_effect=RuntimeError("offline_network_disabled")))
        stack.enter_context(patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=RuntimeError("offline_network_disabled")))
        stack.enter_context(patch("requests.sessions.Session.request", side_effect=RuntimeError("offline_network_disabled")))
        app = FastAPI()
        app.include_router(learning_runs.router)
        yield app, learning_runs


async def collect_case(client, case, learning_runs):
    from langgraph.checkpoint.memory import InMemorySaver
    from backend.app.agent_runtime import checkpointing
    from backend.app.agent_runtime.learning_package import LearningPackageGraph

    runtime = ScriptedRuntime(case, learning_runs.LearningRuntime.citations)
    graph = LearningPackageGraph(runtime)
    if not graph._builder_available:
        raise RuntimeError("offline_langgraph_unavailable")
    if case.scenario == "model_budget_exhausted":
        graph.MAX_MODEL_CALLS = 2
    saver = InMemorySaver()
    headers = {"Authorization": "Bearer offline-student"}
    with patch.object(learning_runs, "_runtime", runtime), patch.object(learning_runs, "_package_graph", graph), patch.object(checkpointing, "get_checkpointer", lambda: saver):
        response = await client.post("/api/v2/learning-runs/stream", headers=headers, json={
            "message": case.question, "course_id": case.course_id, "mode": "learning_package",
            "session_id": f"offline-{uuid.uuid4().hex}", "require_approval": case.require_approval,
        })
        if response.status_code != 200:
            raise RuntimeError("offline_api_request_failed")
        frames = parse_sse(response.text)
        names = [frame["name"] for frame in frames]
        terminal = [frame for frame in frames if frame["name"] in {"run.completed", "run.failed", "review.required"}]
        result = terminal[-1]["data"] if terminal else {"error": "stream_ended_without_terminal_event"}
        run_id = result.get("run_id")
        saved_response = await client.get(f"/api/v2/learning-runs/{run_id}", headers=headers)
        audits_response = await client.get(f"/api/v2/learning-runs/{run_id}/events", headers=headers)
        saved = saved_response.json() if saved_response.status_code == 200 else {}
        checks = runtime.injection_checks()
        if terminal and terminal[-1]["name"] == "review.required":
            checks["persisted_result_matches"] = saved.get("status") == "awaiting_approval" and saved.get("result") == {"review_required": True}
        elif terminal and terminal[-1]["name"] == "run.failed":
            checks["persisted_result_matches"] = saved.get("status") == "failed" and saved.get("result", {}).get("error") == result.get("error")
        else:
            checks["persisted_result_matches"] = saved.get("status") == result.get("status") and saved.get("result") == {key: value for key, value in result.items() if key not in {"status", "run_id", "event_sequence"}}
        checks["audit_readable"] = audits_response.status_code == 200 and bool(audits_response.json().get("events"))
        # Ensure this request did not consume history from another case.
        checks["session_isolated"] = not result.get("memory_run_ids")
        return {"id": case.id, "scenario": case.scenario, "events": names, "result": result,
                "collection": {"collector_version": COLLECTOR_VERSION, "mode": "synthetic_asgi", "checks": checks},
                "sse_frames": frames, "injection_trace": runtime.trace,
                "persisted_status": saved.get("status"),
                "node_audit": audits_response.json().get("events", []) if audits_response.status_code == 200 else []}


async def collect_cases(cases, database_path, on_prediction=None):
    import httpx

    predictions = {}
    with offline_api(database_path) as (app, learning_runs):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline.test") as client:
            for case in cases:
                prediction = await collect_case(client, case, learning_runs)
                predictions[case.id] = prediction
                if on_prediction:
                    on_prediction(prediction)
    return predictions
