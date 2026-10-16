"""Docker 端到端冒烟测试

用户跑完 `docker-compose up -d` 后调用本脚本，验证：
    1. backend container 起来（/api/v1/system/status 200）
    2. cockpit 聚合端点 200 + 8 块字段
    3. cockpit 字段都不是 error
    4. profile / kg / forecast 三个零散端点可用
    5. frontend container 起来（http://localhost:5173 返回 HTML）

依赖：仅标准库（urllib），不需额外 pip install。

用法:
    python -m scripts.docker_smoke
    python -m scripts.docker_smoke --host http://192.168.1.100   # 远程容器
    python -m scripts.docker_smoke --json                          # CI 用
    python -m scripts.docker_smoke --skip-frontend                 # 只测后端
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    elapsed_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _http_get(url: str, timeout: float = 10.0) -> tuple[int, str, dict[str, Any] | None]:
    """返回 (status_code, raw_text, parsed_json or None)。"""
    req = Request(url, headers={"User-Agent": "docker_smoke/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, raw, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw, None
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body, None
    except (URLError, TimeoutError) as e:
        return 0, str(e), None


def _run(name: str, fn: Callable[[], dict[str, Any]]) -> CheckResult:
    start = time.perf_counter()
    try:
        extra = fn() or {}
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult(name=name, ok=True, elapsed_ms=elapsed, extra=extra)
    except AssertionError as e:
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult(name=name, ok=False, detail=str(e), elapsed_ms=elapsed)
    except Exception as e:  # noqa: BLE001
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult(name=name, ok=False,
                           detail=f"{type(e).__name__}: {e}", elapsed_ms=elapsed)


# ================================================================
# Checks
# ================================================================
def make_backend_checks(api_base: str) -> list[tuple[str, Callable[[], dict[str, Any]]]]:
    def check_backend_status() -> dict[str, Any]:
        status, _, data = _http_get(f"{api_base}/system/status", timeout=15)
        assert status == 200, f"system/status returned {status}"
        return {"status_code": status}

    def check_cockpit_endpoint() -> dict[str, Any]:
        status, _, data = _http_get(
            f"{api_base}/cockpit/student/demo-student-1", timeout=20,
        )
        assert status == 200, f"cockpit returned {status}"
        assert data is not None, "cockpit returned non-JSON"
        required = {"user_id", "profile", "kg", "forecast", "attribution",
                    "cov", "debate", "safety", "ledger"}
        missing = required - set(data.keys())
        assert not missing, f"cockpit missing keys: {missing}"
        return {"blocks": len(required), "user_id": data.get("user_id")}

    def check_cockpit_no_block_errors() -> dict[str, Any]:
        status, _, data = _http_get(
            f"{api_base}/cockpit/student/demo-student-1", timeout=20,
        )
        assert status == 200 and data is not None
        # 允许 1 块以下报错（如 debate 表为空）；超 1 块报错则失败
        errored_blocks = [
            k for k, v in data.items()
            if isinstance(v, dict) and v.get("error")
        ]
        assert len(errored_blocks) <= 1, (
            f"too many errored blocks: {errored_blocks}"
        )
        return {"errored_blocks": errored_blocks}

    def check_cockpit_schema() -> dict[str, Any]:
        status, _, data = _http_get(f"{api_base}/cockpit/schema", timeout=10)
        assert status == 200, f"schema returned {status}"
        assert data is not None
        assert "response_fields" in data
        return {"fields": len(data.get("response_fields", {}))}

    def check_profile_endpoint() -> dict[str, Any]:
        status, _, data = _http_get(
            f"{api_base}/profile/demo-student-1", timeout=10,
        )
        assert status == 200, f"profile returned {status}"
        return {"status_code": status}

    def check_kg_stats() -> dict[str, Any]:
        status, _, data = _http_get(f"{api_base}/knowledge-graph/stats", timeout=10)
        assert status == 200
        return data or {}

    def check_forecast_endpoint() -> dict[str, Any]:
        status, _, data = _http_get(
            f"{api_base}/cognitive/forecast?user_id=demo-student-1&horizon_days=7",
            timeout=15,
        )
        assert status == 200, f"forecast returned {status}"
        return {"status_code": status}

    return [
        ("backend /system/status 200", check_backend_status),
        ("cockpit 8 blocks present", check_cockpit_endpoint),
        ("cockpit no widespread block errors", check_cockpit_no_block_errors),
        ("/cockpit/schema 200", check_cockpit_schema),
        ("/profile/{user_id} 200", check_profile_endpoint),
        ("/knowledge-graph/stats 200", check_kg_stats),
        ("/cognitive/forecast?... 200", check_forecast_endpoint),
    ]


def make_frontend_checks(frontend_host: str) -> list[tuple[str, Callable[[], dict[str, Any]]]]:
    def check_frontend_html() -> dict[str, Any]:
        status, raw, _ = _http_get(frontend_host, timeout=10)
        assert status == 200, f"frontend root returned {status}"
        # 检查是否含 SPA 标志
        assert ("<!DOCTYPE html>" in raw or "<!doctype html>" in raw.lower()), \
            f"frontend root not HTML: {raw[:80]!r}"
        return {"len": len(raw)}

    def check_frontend_api_proxy() -> dict[str, Any]:
        # 通过前端 nginx 反代调后端 API
        # 严格性：必须返回 JSON（容器 nginx 反代真后端）
        # 防伪：Vite dev SPA fallback 也会返回 200 + index.html，但 content 是 HTML 不是 JSON
        status, raw, data = _http_get(
            f"{frontend_host.rstrip('/')}/api/v1/system/status", timeout=10,
        )
        assert status == 200, f"frontend nginx proxy returned {status}"
        if data is None:
            head = raw[:120].replace("\n", " ")
            raise AssertionError(
                "frontend /api/* 返回非 JSON（疑似 Vite dev SPA fallback 而非 nginx 反代）。"
                f" 前 120 字节: {head!r}"
            )
        return {"status_code": status, "content": "json"}

    return [
        ("frontend root 200 + HTML", check_frontend_html),
        ("frontend nginx → backend /api/v1/system/status", check_frontend_api_proxy),
    ]


# ================================================================
# Render
# ================================================================
def render_text(results: list[CheckResult]) -> str:
    lines = ["=" * 78, " Docker Smoke Test", "=" * 78]
    for r in results:
        icon = "OK  " if r.ok else "FAIL"
        line = f"  {icon} {r.name:<48} [{r.elapsed_ms:7.1f} ms]"
        if r.extra:
            line += f"  {r.extra}"
        lines.append(line)
        if not r.ok:
            lines.append(f"       => {r.detail}")
    passed = sum(1 for r in results if r.ok)
    lines.append("-" * 78)
    lines.append(f"  {passed}/{len(results)} checks passed")
    return "\n".join(lines)


def render_json(results: list[CheckResult]) -> str:
    payload = {
        "total": len(results),
        "passed": sum(1 for r in results if r.ok),
        "results": [
            {"name": r.name, "ok": r.ok, "detail": r.detail,
             "elapsed_ms": round(r.elapsed_ms, 2), "extra": r.extra}
            for r in results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ================================================================
# Main
# ================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Docker 端到端冒烟（用户跑 docker-compose up 后调用）"
    )
    parser.add_argument("--host", type=str, default="http://localhost:8000",
                        help="backend 容器地址（默认 http://localhost:8000）")
    parser.add_argument("--frontend", type=str, default="http://localhost:5173",
                        help="frontend 容器地址（默认 http://localhost:5173）")
    parser.add_argument("--skip-frontend", action="store_true",
                        help="只测后端（前端没起时用）")
    parser.add_argument("--json", action="store_true", help="JSON 输出（CI 用）")
    parser.add_argument("--wait", type=int, default=0,
                        help="启动前等待 N 秒（给容器初始化时间）")
    args = parser.parse_args(argv)

    if args.wait:
        if not args.json:
            print(f"  waiting {args.wait}s for containers to warm up ...",
                  flush=True)
        time.sleep(args.wait)

    api_base = f"{args.host.rstrip('/')}/api/v1"
    checks = make_backend_checks(api_base)
    if not args.skip_frontend:
        checks += make_frontend_checks(args.frontend)

    results: list[CheckResult] = []
    for name, fn in checks:
        if not args.json:
            print(f"  running {name} ...", flush=True)
        results.append(_run(name, fn))

    if args.json:
        print(render_json(results))
    else:
        print(render_text(results))

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
