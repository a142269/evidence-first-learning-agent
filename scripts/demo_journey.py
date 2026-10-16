# ruff: noqa: RUF001
"""CLI 演示串联脚本 (T1.6).

按 demo-student-1 / demo-student-2 / demo-student-3 等用户一键跑：
登录 → 画像 → 多智能体辩论 SSE → 时光机预测 → 错题→变式题闭环 → 诊断报告。

默认离线（mock LLM）模式以保证 < 30 秒，断网友好。

Examples
--------
    python -m scripts.demo_journey demo-student-1
    python -m scripts.demo_journey demo-student-2 --skip-stream
    python -m scripts.demo_journey demo-student-3 --no-offline
"""
from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def _set_offline_env(offline: bool) -> None:
    if offline:
        os.environ["A3_OFFLINE_DEMO"] = "1"


def _step_profile(client: Any, user_id: str) -> None:
    print_header("1. 登录与学情画像获取")
    # 优先用独立的 /profile/{user_id}（从 repository 读取，常含持久化画像），
    # 再回退到 chat session 内的 profile 快照。
    resp = client.get(f"/api/v1/profile/{user_id}")
    if resp.status_code != 200:
        resp = client.get(f"/api/v1/chat/profile/{user_id}")
    if resp.status_code == 200:
        body = resp.json()
        profile = body.get("profile", {}) or {}
        print(f"OK 画像字段数: {len(profile)}")
        if "knowledge_states" in profile:
            print(f"   掌握度: {len(profile['knowledge_states'])} 个知识点")
        if "completeness" in body:
            print(f"   完整度: {body['completeness']}% ({body.get('filled_dimensions', 0)}/{body.get('total_dimensions', 0)})")
    else:
        print(f"WARN 画像获取失败 status={resp.status_code}")


def _step_chat_stream(client: Any, user_id: str, course: str) -> None:
    print_header("2. 多 Agent 辩论 SSE 流")
    payload = {
        "message": "讲解 CNN 并给出 1 个例子和 1 道练习题。",
        "session_id": user_id,
        "course": course,
    }
    t0 = time.time()
    seen_events: set[str] = set()
    last_event = ""
    with client.stream("POST", "/api/v1/chat/stream", json=payload) as response:
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                last_event = line.split("event:", 1)[1].strip()
                seen_events.add(last_event)
            elif line.startswith("data:") and last_event in {
                "debate_round_start",
                "expert_draft",
                "critic_score",
                "debate_converged",
            }:
                payload_str = line.split("data:", 1)[1].strip()
                print(f"[辩论] {last_event}: {payload_str[:120]}...")
    print(f"OK SSE 事件种类: {sorted(seen_events)}")
    print(f"   耗时: {time.time() - t0:.2f}s")


def _step_forecast(client: Any, user_id: str) -> None:
    print_header("3. 学习时光机 (B 的 forecast)")
    # 注意：端点参数为 kp_id / horizon_days，曾误用 kp / days 导致 422。
    resp = client.get(f"/api/v1/cognitive/forecast?user_id={user_id}&kp_id=cnn&horizon_days=30")
    if resp.status_code == 200:
        data = resp.json()
        points = data.get("forecast") or data.get("points") or []
        print(f"OK 预测点数: {len(points)}")
    else:
        print(f"WARN 时光机不可用 status={resp.status_code} (B 的 T1.3 可能未启动)")


def _step_variant(client: Any, user_id: str) -> None:
    print_header("4. 错题 → 变式题 (A 的 /system/variant/*)")
    samples_resp = client.get("/api/v1/system/variant/demo-samples")
    if samples_resp.status_code != 200:
        print(f"WARN 样例端点不可用 status={samples_resp.status_code}")
        return
    samples = samples_resp.json().get("samples", [])
    if not samples:
        print("WARN 没有 demo 样例")
        return
    sample = next(
        (s for s in samples if s.get("user_id") == user_id),
        samples[0],
    )
    body = {
        "user_id": sample.get("user_id", user_id),
        "kp_id": sample.get("kp_id", ""),
        "kp_name": sample.get("kp_name", ""),
        "question": sample.get("question", ""),
        "student_answer": sample.get("student_answer", ""),
        "correct_answer": sample.get("correct_answer", ""),
        "count": 3,
    }
    resp = client.post(
        f"/api/v1/system/variant/{sample['mistake_id']}",
        json=body,
    )
    if resp.status_code == 200:
        package = resp.json()
        print(f"OK 错因: {package['attribution']['error_type']}")
        print(f"   推荐 Bloom: {package['target_bloom']['label']}")
        print(f"   变式数量: {len(package['variants'])}")
        for idx, variant in enumerate(package["variants"][:3], start=1):
            print(f"   {idx}. [{variant['bloom_label']}] {variant['question'][:50]}...")
    else:
        print(f"WARN 变式生成失败 status={resp.status_code} body={resp.text[:120]}")


def _step_diagnosis_report(user_id: str, tmp_dir: Path) -> None:
    print_header("5. 学习诊断报告 (T1.1)")
    cmd = [
        sys.executable,
        "-m",
        "scripts.generate_diagnosis_report",
        "--user",
        user_id,
        "--format",
        "both",
        "--out-dir",
        str(tmp_dir),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=20
        )
        print("OK")
        for line in result.stdout.splitlines()[-3:]:
            print(f"   {line}")
    except subprocess.CalledProcessError as exc:
        print(f"WARN 诊断报告失败: {exc.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("WARN 诊断报告超时 (>20s)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A3 evaluator demo journey")
    parser.add_argument(
        "user_id",
        nargs="?",
        default="demo-student-1",
        help="Demo student id (default demo-student-1)",
    )
    parser.add_argument(
        "--course",
        default="artificial_intelligence",
        help="Course slug for the chat step",
    )
    parser.add_argument(
        "--no-offline",
        action="store_true",
        help="Disable A3_OFFLINE_DEMO (will hit real LLM if configured)",
    )
    parser.add_argument(
        "--skip-stream",
        action="store_true",
        help="Skip the multi-agent SSE stream step (faster for testing)",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip the subprocess diagnosis-report step",
    )
    parser.add_argument(
        "--report-dir",
        default=str(PROJECT_ROOT / "reports" / "diagnosis"),
        help="Where the diagnosis report files should be written",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _set_offline_env(offline=not args.no_offline)

    print_header(f"Demo Journey: {args.user_id} (offline={'no' if args.no_offline else 'yes'})")
    t_start = time.time()

    # Import here so that A3_OFFLINE_DEMO is honoured before LLM init.
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with contextlib.suppress(KeyboardInterrupt), TestClient(app) as client:
        _step_profile(client, args.user_id)
        if not args.skip_stream:
            _step_chat_stream(client, args.user_id, args.course)
        else:
            print_header("2. 多 Agent 辩论 SSE 流（已跳过）")
        _step_forecast(client, args.user_id)
        _step_variant(client, args.user_id)
        if not args.skip_report:
            _step_diagnosis_report(args.user_id, Path(args.report_dir))
        else:
            print_header("5. 学习诊断报告（已跳过）")

    print_header(f"Demo 完成 | 总耗时: {time.time() - t_start:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
