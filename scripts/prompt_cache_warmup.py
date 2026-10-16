"""PromptCache 预热脚本 — 演示日前 cron 触发

把 demo-student-1..5 在演示路径上会触发的 prompt 全部预算一遍，落到
SQLite cache 里。这样真正演示时 LLM 调用 100% 命中本地，避免：

    * 评委网络环境弱时延迟巨大
    * 演示当天 LLM 配额超限
    * 演示当天 LLM 返回结果不稳定（同 prompt 不同输出）

预热范围:
    1. 5 个 demo student × Cockpit 全字段（profile/kg/forecast/cov/...）
    2. 5 个 demo student × P1.4 反事实
    3. 5 个 demo student × COV 验证（cov_demo_cases × axes）
    4. 5 个 variant 错题归因

用法:
    python -m scripts.prompt_cache_warmup
    python -m scripts.prompt_cache_warmup --json     # CI 用
    python -m scripts.prompt_cache_warmup --dry-run  # 列出会预热什么但不执行

演示日前 cron 示例:
    0 8 * * *  cd /app && python -m scripts.prompt_cache_warmup --json >> logs/warmup.log
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Offline 模式：让 LLM 走 mock 不打外网；mock 输出会被 PromptCache 缓存
os.environ.setdefault("A3_OFFLINE_DEMO", "1")
os.environ.setdefault("PROMPT_CACHE_ENABLED", "1")

DEMO_USERS = ("demo-student-1", "demo-student-2", "demo-student-3",
              "demo-student-4", "demo-student-5")


@dataclass
class WarmupTask:
    """一次预热任务的执行结果。"""
    name: str
    ok: bool
    detail: str = ""
    elapsed_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _run(name: str, fn: Callable[[], dict[str, Any]]) -> WarmupTask:
    start = time.perf_counter()
    try:
        extra = fn() or {}
        elapsed = (time.perf_counter() - start) * 1000
        return WarmupTask(name=name, ok=True, elapsed_ms=elapsed, extra=extra)
    except Exception as exc:  # noqa: BLE001
        elapsed = (time.perf_counter() - start) * 1000
        return WarmupTask(
            name=name, ok=False,
            detail=f"{type(exc).__name__}: {exc}",
            elapsed_ms=elapsed,
        )


# ================================================================
# Warm-up 任务
# ================================================================
def warmup_cockpit_all_demo_users() -> dict[str, Any]:
    """5 个 demo student × Cockpit 全字段（含 forecast / kg / safety / ledger）。"""
    from backend.app.api.v1.cockpit import get_cockpit

    async def _warm():
        results = []
        for user_id in DEMO_USERS:
            r = await get_cockpit(
                user_id=user_id, horizon_days=7, focus_kp="",
                sample_response="你觉得这道题该怎么入手？",
                sample_text="CNN 是卷积神经网络的简称。",
            )
            results.append({
                "user": user_id,
                "blocks": len([k for k in r if k not in ("user_id", "generated_at")]),
                "errored": sum(1 for v in r.values()
                               if isinstance(v, dict) and v.get("error")),
            })
        return results

    results = asyncio.run(_warm())
    total_errored = sum(r["errored"] for r in results)
    return {"users": len(DEMO_USERS), "total_errored_blocks": total_errored}


def warmup_counterfactual() -> dict[str, Any]:
    """5 个 demo student × P1.4 反事实（需先有 BKT 历史）。"""
    from backend.app.services.cognitive_diagnosis.bkt import get_bkt
    from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster

    fc = BKTForecaster()
    bkt = get_bkt()
    results = []
    for user_id in DEMO_USERS:
        masteries = bkt.get_all_masteries(user_id) or {}
        if not masteries:
            results.append({"user": user_id, "skipped": "no BKT history"})
            continue
        kp_id = min(masteries, key=masteries.get)
        try:
            cf = fc.counterfactual(user_id=user_id, kp_id=kp_id, horizon_days=14)
            results.append({"user": user_id, "expected_gain": cf.get("expected_gain")})
        except Exception as exc:  # noqa: BLE001
            results.append({"user": user_id, "error": str(exc)})
    return {"users": len(DEMO_USERS),
            "with_data": sum(1 for r in results if "expected_gain" in r)}


def warmup_cov_demo() -> dict[str, Any]:
    """CoV demo 5 axes (factual / pedagogical / bloom / citation / safety)。"""
    from backend.app.services.cov_demo_service import CoVDemoRequest, CoVDemoService

    svc = CoVDemoService()
    sample_text = ("CNN 是卷积神经网络的简称。"
                   "它通过卷积核共享权重，参数量比全连接少。")
    req = CoVDemoRequest(
        axes=["factual", "pedagogical", "bloom", "citation", "safety"],
        text=sample_text,
        ground_truth=sample_text,
    )
    try:
        result = svc.run(req)
        return {"axes": 5, "ok": True,
                "claims": len(result.get("axes", [])) if isinstance(result, dict) else 0}
    except Exception as exc:  # noqa: BLE001
        return {"axes": 5, "ok": False, "error": str(exc)}


def warmup_variant_generation() -> dict[str, Any]:
    """5 个 demo variant 样例预生成。"""
    from backend.app.services.variant_generator import (
        VariantGenerator,
        request_from_record,
    )

    gen = VariantGenerator()
    # 直接从 data/variant_demo_samples.json 加载
    path = PROJECT_ROOT / "data" / "variant_demo_samples.json"
    if not path.exists():
        return {"samples": 0, "note": "demo file missing"}

    samples = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(samples, dict):
        samples = samples.get("samples", [])
    success = 0
    for sample in (samples or [])[:5]:
        try:
            req = request_from_record(sample, count=3)
            gen.generate(req)
            success += 1
        except Exception:
            pass
    return {"samples": len(samples) if samples else 0, "succeeded": success}


def warmup_diagnosis_reporter() -> dict[str, Any]:
    """5 个 demo student × DiagnosisReporter（最常被前端 Cockpit 调用）。"""
    from backend.app.services.diagnosis_reporter import DiagnosisReporter

    reporter = DiagnosisReporter()
    success = 0
    for user_id in DEMO_USERS:
        try:
            reporter.build_report(user_id)
            success += 1
        except Exception:
            pass
    return {"users": len(DEMO_USERS), "succeeded": success}


WARMUP_TASKS: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    ("Cockpit × 5 demo users (8 blocks each)", warmup_cockpit_all_demo_users),
    ("Counterfactual × 5 demo users (P1.4)", warmup_counterfactual),
    ("CoV demo cases × 5 axes", warmup_cov_demo),
    ("Variant generation × 5 samples", warmup_variant_generation),
    ("DiagnosisReporter × 5 demo users", warmup_diagnosis_reporter),
]


# ================================================================
# Render
# ================================================================
def render_text(tasks: list[WarmupTask], cache_stats: dict[str, Any]) -> str:
    lines = ["=" * 78, " PromptCache Warmup Report", "=" * 78]
    for t in tasks:
        icon = "OK  " if t.ok else "FAIL"
        line = f"  {icon} {t.name:<48} [{t.elapsed_ms:8.1f} ms]"
        if t.extra:
            line += f"  {t.extra}"
        lines.append(line)
        if not t.ok:
            lines.append(f"       => {t.detail}")
    passed = sum(1 for t in tasks if t.ok)
    total_ms = sum(t.elapsed_ms for t in tasks)
    lines.append("-" * 78)
    lines.append(f"  {passed}/{len(tasks)} tasks passed in {total_ms:.0f} ms")
    lines.append("")
    lines.append("Cache stats:")
    lines.append(f"  entries     : {cache_stats.get('total_entries', 0)}")
    lines.append(f"  hits so far : {cache_stats.get('total_hits', 0)}")
    lines.append(f"  hit rate    : {cache_stats.get('hit_rate', 0) * 100:.1f}%")
    lines.append("=" * 78)
    return "\n".join(lines)


def render_json(tasks: list[WarmupTask], cache_stats: dict[str, Any]) -> str:
    payload = {
        "total": len(tasks),
        "passed": sum(1 for t in tasks if t.ok),
        "tasks": [asdict(t) for t in tasks],
        "cache_stats": cache_stats,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ================================================================
# Main
# ================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PromptCache 预热脚本（演示日前 cron 触发）"
    )
    parser.add_argument("--json", action="store_true",
                        help="JSON 输出（CI 用）")
    parser.add_argument("--dry-run", action="store_true",
                        help="列出会预热什么但不执行")
    args = parser.parse_args(argv)

    if args.dry_run:
        for name, _ in WARMUP_TASKS:
            print(f"  would run: {name}")
        return 0

    tasks: list[WarmupTask] = []
    for name, fn in WARMUP_TASKS:
        if not args.json:
            print(f"  warming up {name} ...", flush=True)
        tasks.append(_run(name, fn))

    # Cache 命中统计（即使本轮全 miss，至少入库了）
    cache_stats: dict[str, Any] = {}
    try:
        from backend.app.services.prompt_cache import get_default_cache
        stats = get_default_cache().stats()
        cache_stats = {
            "total_entries": stats.total_entries,
            "total_hits": stats.total_hits,
            "hit_rate": stats.hit_rate,
        }
    except Exception:
        pass

    if args.json:
        print(render_json(tasks, cache_stats))
    else:
        print(render_text(tasks, cache_stats))

    return 0 if all(t.ok for t in tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
