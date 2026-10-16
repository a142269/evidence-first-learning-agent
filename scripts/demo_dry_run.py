"""演示日 Dry-Run 脚本 — 7 步评委演示路径完整跑一遍

按 docs/06-演示视频脚本.md 的 7 分钟视频时间轴顺序，把评委会看到的所有
功能挨个触发一次。任一步失败立即报警 + 非零退出。

7 步顺序:
    1. 健康检查 (verify_demo_assets 14/14)
    2. 登录 counselor/123456 → 拿 token
    3. 画像 GET /profile/demo-student-1
    4. Cockpit 聚合 GET /cockpit/student/demo-student-1 (8 块字段)
    5. 学习时光机 GET /cognitive/forecast (+ counterfactual)
    6. 错题归因 GET /mistakes/demo-student-1
    7. KG 邻居 GET /knowledge-graph/neighbors?kp=cnn

用法:
    python -m scripts.demo_dry_run                       # 默认 localhost:8000
    python -m scripts.demo_dry_run --host http://x.y.z:8000
    python -m scripts.demo_dry_run --json                # CI 用
    python -m scripts.demo_dry_run --skip-health         # 跳过预检

演示日前 cron 示例:
    */30 8-18 * * *  python -m scripts.demo_dry_run --json >> logs/dry_run.log
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""
    elapsed_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _request(
    method: str, url: str,
    *, headers: dict[str, str] | None = None,
    body: bytes | None = None, timeout: float = 15.0,
) -> tuple[int, str, dict[str, Any] | None]:
    req = Request(url, data=body, method=method,
                  headers=headers or {"User-Agent": "demo_dry_run/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, raw, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw, None
    except HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body_text, None
    except (URLError, TimeoutError) as e:
        return 0, str(e), None


# ================================================================
# 7 步
# ================================================================
def step_1_verify_demo_assets(host: str) -> dict[str, Any]:
    """跑 verify_demo_assets 一遍 (本地 import 调用，不走 HTTP)。"""
    from scripts.verify_demo_assets import run_all
    results = run_all()
    failed = [r.name for r in results if not r.ok]
    assert not failed, f"verify_demo_assets failed: {failed}"
    return {"total": len(results), "passed": sum(1 for r in results if r.ok)}


def step_2_login(host: str) -> tuple[dict[str, Any], str]:
    """counselor / 123456 登录拿 token。"""
    url = f"{host}/api/v1/auth/login"
    payload = json.dumps({"account": "counselor", "password": "123456"}).encode()
    status, raw, data = _request(
        "POST", url, headers={"Content-Type": "application/json"}, body=payload,
    )
    assert status == 200, f"login {status}: {raw[:80]}"
    assert data and "access_token" in data, f"no access_token: {data}"
    return ({"token_len": len(data["access_token"])}, data["access_token"])


def step_3_profile(host: str, token: str) -> dict[str, Any]:
    url = f"{host}/api/v1/profile/demo-student-1"
    status, raw, data = _request("GET", url,
                                  headers={"Authorization": f"Bearer {token}"})
    assert status == 200, f"profile {status}: {raw[:80]}"
    return {"user_id": (data or {}).get("user_id")}


def step_4_cockpit(host: str, token: str) -> dict[str, Any]:
    url = f"{host}/api/v1/cockpit/student/demo-student-1"
    status, raw, data = _request("GET", url,
                                  headers={"Authorization": f"Bearer {token}"},
                                  timeout=30)
    assert status == 200, f"cockpit {status}: {raw[:80]}"
    required = {"profile", "kg", "forecast", "attribution",
                "cov", "debate", "safety", "ledger"}
    missing = required - set((data or {}).keys())
    assert not missing, f"cockpit missing: {missing}"
    errored = [k for k, v in (data or {}).items()
               if isinstance(v, dict) and v.get("error")]
    assert len(errored) <= 1, f"too many errored blocks: {errored}"
    return {"blocks": 8, "errored": errored}


def step_5_forecast(host: str, token: str) -> dict[str, Any]:
    url = (
        f"{host}/api/v1/cognitive/forecast"
        f"?user_id=demo-student-1&horizon_days=14"
    )
    status, raw, data = _request("GET", url,
                                  headers={"Authorization": f"Bearer {token}"})
    assert status == 200, f"forecast {status}: {raw[:80]}"
    return {"horizon_days": (data or {}).get("horizon_days", 0)}


def step_6_mistakes(host: str, token: str) -> dict[str, Any]:
    url = f"{host}/api/v1/mistakes/demo-student-1"
    status, raw, data = _request("GET", url,
                                  headers={"Authorization": f"Bearer {token}"})
    assert status == 200, f"mistakes {status}: {raw[:80]}"
    return {"count": len((data or {}).get("mistakes", [])) if isinstance(data, dict) else 0}


def step_7_kg_neighbors(host: str, token: str) -> dict[str, Any]:
    url = f"{host}/api/v1/knowledge-graph/neighbors?kp=cnn&direction=both"
    status, raw, data = _request("GET", url,
                                  headers={"Authorization": f"Bearer {token}"})
    assert status == 200, f"kg/neighbors {status}: {raw[:80]}"
    return {"has_data": data is not None}


# ================================================================
# Render
# ================================================================
def render_text(steps: list[Step]) -> str:
    lines = ["=" * 78, " A3 Demo Dry-Run (7 steps)", "=" * 78]
    for i, s in enumerate(steps, 1):
        icon = "OK  " if s.ok else "FAIL"
        line = f"  {icon} Step {i}: {s.name:<40} [{s.elapsed_ms:7.1f} ms]"
        if s.extra:
            line += f"  {s.extra}"
        lines.append(line)
        if not s.ok:
            lines.append(f"       => {s.detail}")
    passed = sum(1 for s in steps if s.ok)
    total_ms = sum(s.elapsed_ms for s in steps)
    lines.append("-" * 78)
    lines.append(f"  {passed}/{len(steps)} steps passed in {total_ms:.0f} ms")
    return "\n".join(lines)


def render_json(steps: list[Step]) -> str:
    payload = {
        "total": len(steps),
        "passed": sum(1 for s in steps if s.ok),
        "steps": [asdict(s) for s in steps],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ================================================================
# Main
# ================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="演示日 Dry-Run：7 步评委演示路径完整跑一遍"
    )
    parser.add_argument("--host", type=str, default="http://localhost:8000",
                        help="后端服务地址（默认 http://localhost:8000）")
    parser.add_argument("--skip-health", action="store_true",
                        help="跳过 step 1 健康检查（如已在 windows_start 跑过）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    steps: list[Step] = []

    # Step 1
    if not args.skip_health:
        start = time.perf_counter()
        try:
            extra = step_1_verify_demo_assets(args.host)
            steps.append(Step(name="verify_demo_assets 14/14", ok=True,
                              elapsed_ms=(time.perf_counter() - start) * 1000,
                              extra=extra))
        except Exception as exc:  # noqa: BLE001
            steps.append(Step(name="verify_demo_assets 14/14", ok=False,
                              detail=f"{type(exc).__name__}: {exc}",
                              elapsed_ms=(time.perf_counter() - start) * 1000))
            if not args.json:
                print(render_text(steps))
            else:
                print(render_json(steps))
            return 1

    # Step 2: login
    start = time.perf_counter()
    token = ""
    try:
        extra, token = step_2_login(args.host)
        steps.append(Step(name="login counselor/123456", ok=True,
                          elapsed_ms=(time.perf_counter() - start) * 1000,
                          extra=extra))
    except Exception as exc:  # noqa: BLE001
        steps.append(Step(name="login counselor/123456", ok=False,
                          detail=f"{type(exc).__name__}: {exc}",
                          elapsed_ms=(time.perf_counter() - start) * 1000))
        if not args.json:
            print(render_text(steps))
        else:
            print(render_json(steps))
        return 1

    # Step 3-7
    for fn, name in [
        (step_3_profile, "profile (8 维画像)"),
        (step_4_cockpit, "cockpit 聚合 (8 块)"),
        (step_5_forecast, "学习时光机 forecast"),
        (step_6_mistakes, "错题归因"),
        (step_7_kg_neighbors, "KG 邻居推荐"),
    ]:
        start = time.perf_counter()
        try:
            extra = fn(args.host, token)
            steps.append(Step(name=name, ok=True,
                              elapsed_ms=(time.perf_counter() - start) * 1000,
                              extra=extra))
        except Exception as exc:  # noqa: BLE001
            steps.append(Step(name=name, ok=False,
                              detail=f"{type(exc).__name__}: {exc}",
                              elapsed_ms=(time.perf_counter() - start) * 1000))

    if args.json:
        print(render_json(steps))
    else:
        print(render_text(steps))

    return 0 if all(s.ok for s in steps) else 1


if __name__ == "__main__":
    sys.exit(main())
