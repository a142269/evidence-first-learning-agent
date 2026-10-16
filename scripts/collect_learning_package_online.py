"""Collect standard learning-package cases from an authenticated V2 SSE API."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evaluation.learning_package import load_cases, review_template, summarise


def _login(base_url: str) -> str:
    account = os.environ["V2_EVAL_LOGIN_ACCOUNT"]
    password = os.environ["V2_EVAL_LOGIN_PASSWORD"]
    response = requests.post(f"{base_url.rstrip('/')}/api/v1/auth/login",
                             json={"account": account, "password": password}, timeout=20)
    response.raise_for_status()
    token = response.json().get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("online_package_login_failed")
    return token


def _collect(base_url: str, token: str, case, timeout: int) -> dict:
    started = time.perf_counter()
    payload = {"message": case.question, "course_id": case.course_id,
               "session_id": f"package-{case.id}-{uuid.uuid4().hex[:8]}",
               "require_approval": case.require_approval, "mode": "learning_package"}
    events: list[str] = []
    result: dict = {}
    current = ""
    with requests.post(f"{base_url.rstrip('/')}/api/v2/learning-runs/stream", json=payload,
                       headers={"Authorization": f"Bearer {token}"}, stream=True,
                       timeout=timeout) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if line.startswith("event: "):
                current = line.removeprefix("event: ").strip()
                events.append(current)
            elif line.startswith("data: ") and current in {"run.completed", "run.failed", "review.required"}:
                value = json.loads(line.removeprefix("data: "))
                result = value if isinstance(value, dict) else {}
    if not events or events[-1] not in {"run.completed", "run.failed", "review.required"}:
        result = {"error": "stream_ended_without_terminal_event"}
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return {"id": case.id, "scenario": case.scenario, "events": events, "result": result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/learning_package_cases_v1.jsonl")
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--review-template", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args(argv)
    selected = [case for case in load_cases(args.cases) if case.scenario == "standard"]
    if args.case_id:
        unknown = set(args.case_id) - {case.id for case in selected}
        if unknown:
            raise SystemExit("online_package_case_not_standard")
        selected = [case for case in selected if case.id in set(args.case_id)]
    for path in (args.report, args.review_template):
        if path.exists():
            raise SystemExit("online_package_output_exists")
        path.parent.mkdir(parents=True, exist_ok=True)
    if args.progress.exists() != args.resume:
        raise SystemExit("online_package_resume_mismatch")
    args.progress.parent.mkdir(parents=True, exist_ok=True)
    predictions = {}
    if args.resume:
        for line in args.progress.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            predictions[row["id"]] = row
    remaining = [case for case in selected if case.id not in predictions]
    token = _login(args.base_url) if remaining else ""
    with args.progress.open("a" if args.resume else "x", encoding="utf-8") as stream:
        for case in remaining:
            prediction = _collect(args.base_url, token, case, args.timeout)
            predictions[case.id] = prediction
            stream.write(json.dumps(prediction, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    report = summarise(selected, predictions, prediction_kind="recorded")
    report.update(collection_mode="recorded_authenticated_sse", predictions=predictions)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    with args.review_template.open("x", encoding="utf-8") as stream:
        for row in review_template(selected, predictions):
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"summary": report["summary"], "report": str(args.report),
                      "review_template": str(args.review_template)}, ensure_ascii=False))
    return 0 if all(row["contract_passed"] for row in report["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
