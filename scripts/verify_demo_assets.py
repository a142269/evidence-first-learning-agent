"""演示资产健康检查 CLI（防演示翻车）.

跑一遍所有评委会触达的资产 + endpoint，任一失败立即报警 + 非零退出码。

Usage
-----
    python -m scripts.verify_demo_assets
    python -m scripts.verify_demo_assets --json    # 机器可读输出
"""
# ruff: noqa: RUF001
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force offline mode so we never hit external LLM during health checks.
os.environ.setdefault("A3_OFFLINE_DEMO", "1")

DEMO_USERS = ("demo-student-1", "demo-student-2", "demo-student-3", "demo-student-4", "demo-student-5")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    elapsed_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _run(name: str, fn: Callable[[], dict[str, Any]]) -> CheckResult:
    start = time.perf_counter()
    try:
        extra = fn() or {}
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult(name=name, ok=True, elapsed_ms=elapsed, extra=extra)
    except Exception as exc:  # noqa: BLE001
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult(
            name=name, ok=False, detail=f"{type(exc).__name__}: {exc}", elapsed_ms=elapsed
        )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
def check_seed_json() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "seed.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    students = {s["user_id"] for s in payload.get("students", [])}
    assert {"demo-student-1", "demo-student-2", "demo-student-3"} <= students
    return {"students": len(students)}


def check_seed_extended() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "seed_extended.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    kps = payload.get("knowledge_points", [])
    extra_students = payload.get("extra_students", [])
    assert len(kps) >= 20, f"expected >=20 KPs, got {len(kps)}"
    assert len(extra_students) >= 2, f"expected >=2 extra students, got {len(extra_students)}"
    return {"kps": len(kps), "extra_students": len(extra_students)}


def check_question_bank() -> dict[str, Any]:
    from backend.app.services.question_bank import get_question_bank

    bank = get_question_bank()
    assert bank.total >= 200, f"expected >=200 questions, got {bank.total}"
    return {"total": bank.total, "kps": len(bank.kp_ids)}


def check_chapters() -> dict[str, Any]:
    from backend.app.services.knowledge_index import get_knowledge_index

    index = get_knowledge_index()
    assert index.total >= 20, f"expected >=20 chapters, got {index.total}"
    return {"chapters": index.total, "kps": len(index.kp_ids_covered)}


def check_cov_demo_cases() -> dict[str, Any]:
    from backend.app.services.cov_demo_service import CoVDemoService

    cases = CoVDemoService().demo_cases()
    assert len(cases) == 5, f"expected 5 CoV demo cases, got {len(cases)}"
    axes = {c["axis"] for c in cases}
    assert axes == {"factual", "pedagogical", "bloom", "citation", "safety"}
    return {"cases": len(cases)}


def check_variant_demo_samples() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "variant_demo_samples.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = payload.get("samples", [])
    assert len(samples) == 5, f"expected 5 variant samples, got {len(samples)}"
    for s in samples:
        assert s["question"] and s["correct_answer"], f"sample {s.get('mistake_id')} missing fields"
    return {"samples": len(samples)}


def check_diagnosis_reporter_all_users() -> dict[str, Any]:
    from backend.app.services.diagnosis_reporter import (
        DiagnosisReporter,
        validate_report_json,
    )

    reporter = DiagnosisReporter()
    for user_id in DEMO_USERS:
        report = reporter.build_report(user_id)
        issues = validate_report_json(report.json_payload)
        assert not issues, f"{user_id}: JSON schema issues {issues}"
        assert len(report.mastery_rows) == 20
        assert len(report.recommendations.questions) == 5
    return {"users": len(DEMO_USERS)}


def check_variant_generator_all_samples() -> dict[str, Any]:
    from backend.app.services.variant_generator import (
        VariantGenerator,
        request_from_record,
    )

    path = PROJECT_ROOT / "data" / "variant_demo_samples.json"
    samples = json.loads(path.read_text(encoding="utf-8"))["samples"]
    generator = VariantGenerator()
    for sample in samples:
        package = generator.generate(request_from_record(sample, count=3))
        assert package["mistake_id"] == sample["mistake_id"]
        assert len(package["variants"]) == 3, (
            f"{sample['mistake_id']}: got {len(package['variants'])} variants"
        )
    return {"samples": len(samples)}


def check_cov_demo_service_all_axes() -> dict[str, Any]:
    from backend.app.services.cov_demo_service import CoVDemoRequest, CoVDemoService

    service = CoVDemoService()
    cases = service.demo_cases()
    for case in cases:
        result = service.run(
            CoVDemoRequest(
                text=case["text"],
                ground_truth=case.get("ground_truth", ""),
                axes=[case["axis"]],
            )
        )
        assert result["ok"] is True, f"{case['id']}: ok=False"
        assert result["axes"], f"{case['id']}: empty axes result"
    return {"cases": len(cases)}


def check_http_routes_registered() -> dict[str, Any]:
    from backend.app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    required = {
        "/api/v1/chat/with-cov",
        "/api/v1/chat/cov-demo-cases",
        "/api/v1/system/variant/{mistake_id}",
        "/api/v1/system/variant/demo-samples",
        "/api/v1/system/status",
        "/api/v1/cognitive/forecast",
        "/healthz",
    }
    missing = sorted(required - paths)
    assert not missing, f"missing routes: {missing}"
    return {"required_routes": len(required)}


def check_realdina_snapshots() -> dict[str, Any]:
    from backend.app.services.realdina_service import (
        get_realdina_service,
        reset_realdina_service,
    )

    reset_realdina_service()
    service = get_realdina_service()
    for user_id in DEMO_USERS:
        snap = service.snapshot_for(user_id)
        assert snap, f"empty RealDINA snapshot for {user_id}"
    return {"users": len(DEMO_USERS), "kp_universe": len(service.kp_universe)}


def check_pedagogical_safety_smoke() -> dict[str, Any]:
    """5 个典型 tutor 响应过 PedagogicalSafetyEvaluator，验证 4 字段都能返回。"""
    from backend.app.services.pedagogical_safety import (
        TutoringContext,
        get_pedagogical_safety_evaluator,
    )

    ev = get_pedagogical_safety_evaluator()
    cases = [
        ("safe_guidance", "你觉得这道题第一步应该怎么入手？想想已知量。", None),
        ("answer_leak", "正确答案是 x=2，过程: 2x=4, x=2",
         TutoringContext(correct_answer="x=2", bloom_level="apply")),
        ("misconception_echo", "你说得对，x=4 没错。",
         TutoringContext(student_answer="x=4", correct_answer="x=2")),
        ("mixed", "正确答案是 x=2，但你想想为什么？第一步应该做什么？",
         TutoringContext(correct_answer="x=2", bloom_level="apply")),
        ("empty_response", "", None),
    ]
    summary: dict[str, Any] = {"cases": []}
    for label, text, ctx in cases:
        r = ev.evaluate(text, ctx)
        d = r.to_dict()
        # 4 字段都必须有
        assert "scaffolding_score" in d, f"{label}: missing scaffolding_score"
        assert "answer_leak_risk" in d, f"{label}: missing answer_leak_risk"
        assert "misconception_reinforcement_risk" in d
        assert "student_uptake_prompt" in d
        summary["cases"].append({"label": label, "overall_risk": d["overall_risk"]})
    return {"cases": len(cases), "max_risk": max(c["overall_risk"] for c in summary["cases"])}


def check_cockpit_endpoint() -> dict[str, Any]:
    """Cockpit 聚合端点 smoke：调 get_cockpit 函数验证 8 块字段都在。

    2026-06-24: get_cockpit 改成 async（并发优化），需 asyncio.run 包装。
    """
    import asyncio
    from backend.app.api.v1.cockpit import get_cockpit

    result = asyncio.run(get_cockpit(
        user_id="demo-student-1",
        horizon_days=7,
        focus_kp="",
        sample_response="你觉得这道题该怎么入手？",
        sample_text="CNN 是卷积神经网络。",
    ))
    required = {
        "user_id", "generated_at", "profile", "kg",
        "forecast", "attribution", "cov", "debate",
        "safety", "ledger",
    }
    missing = required - set(result.keys())
    assert not missing, f"cockpit response missing keys: {missing}"
    # safety 4 字段
    safety = result.get("safety", {})
    for k in ("scaffolding_score", "answer_leak_risk",
              "misconception_reinforcement_risk", "student_uptake_prompt"):
        assert k in safety, f"safety missing {k}: {safety}"
    return {
        "blocks": len(required) - 2,  # 减去 user_id / generated_at meta
        "safety_overall_risk": safety.get("overall_risk"),
        "ledger_total_claims": result.get("ledger", {}).get("total_claims", 0),
    }


def check_claim_ledger_smoke() -> dict[str, Any]:
    """5 类 source 各放一条 demo claim 文本，验证 5 source type 全走通。

    每个 claim 完整子串匹配对应的 source，走 substring 路径，confidence ≥ 0.95。
    """
    from backend.app.services.claim_ledger import (
        EvidencePool,
        SOURCE_TYPES,
        get_claim_ledger,
    )

    ledger = get_claim_ledger()
    # 让每条 claim 是对应 source content 的完整子串
    pool = EvidencePool(
        textbook=[{"ref": "ai/04_cnn.md#L23",
                   "content": "教材记载: CNN 是卷积神经网络的简称, 处理图像数据。"}],
        kg=[{"ref": "kp:cnn",
             "content": "知识图谱节点: CNN 是图像处理的核心架构, 出现在第 4 章。"}],
        rag_chunk=[{"ref": "chunk-42",
                    "content": "RAG 召回片段: 卷积神经网络可应用于计算机视觉任务。"}],
        mistake=[{"ref": "mistake_id:m-12",
                  "content": "学生历史错题: 把 CNN 当成循环神经网络的简称。"}],
        history=[{"ref": "path:cnn-2026-06",
                  "content": "学习历史: 学生上周完成 CNN 章节 5 道练习题。"}],
    )
    text = (
        "CNN 是卷积神经网络的简称。"           # 命中 textbook
        "CNN 是图像处理的核心架构。"           # 命中 kg
        "卷积神经网络可应用于计算机视觉任务。"  # 命中 rag_chunk
        "把 CNN 当成循环神经网络的简称。"       # 命中 mistake
        "学生上周完成 CNN 章节 5 道练习题。"    # 命中 history
    )
    result = ledger.build(text, pool=pool)

    assert result.total_claims >= 5, f"too few claims: {result.total_claims}"
    types_covered = sum(1 for v in result.source_distribution.values() if v > 0)
    assert types_covered == 5, (
        f"expected all 5 source types hit, got {types_covered}: "
        f"{result.source_distribution}"
    )
    assert set(result.source_distribution.keys()) == set(SOURCE_TYPES)
    return {
        "claims": result.total_claims,
        "supported": result.supported_claims,
        "support_rate": round(result.support_rate, 2),
        "source_types_hit": types_covered,
    }


CHECKS: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    ("seed.json", check_seed_json),
    ("seed_extended.json", check_seed_extended),
    ("question_bank.json (>=200 题)", check_question_bank),
    ("knowledge_base/ (>=20 章)", check_chapters),
    ("cov_demo_cases.json (5 案例)", check_cov_demo_cases),
    ("variant_demo_samples.json (5 样例)", check_variant_demo_samples),
    ("RealDINA snapshots (5 demo)", check_realdina_snapshots),
    ("DiagnosisReporter × 5 demo users", check_diagnosis_reporter_all_users),
    ("VariantGenerator × 5 demo samples", check_variant_generator_all_samples),
    ("CoVDemoService × 5 axes", check_cov_demo_service_all_axes),
    ("PedagogicalSafety × 5 cases (P1.1)", check_pedagogical_safety_smoke),
    ("ClaimLedger × 5 source types (P1.2)", check_claim_ledger_smoke),
    ("Cockpit 聚合端点 (8 blocks)", check_cockpit_endpoint),
    ("FastAPI routes registered", check_http_routes_registered),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all() -> list[CheckResult]:
    results: list[CheckResult] = []
    for name, fn in CHECKS:
        results.append(_run(name, fn))
    return results


def render_text(results: list[CheckResult]) -> str:
    lines = ["=" * 70, " A3 Demo Assets Health Check", "=" * 70]
    for r in results:
        icon = "OK  " if r.ok else "FAIL"
        suffix = f"[{r.elapsed_ms:6.1f} ms]"
        line = f"  {icon} {r.name:<48} {suffix}"
        if r.extra:
            line += f"  {r.extra}"
        lines.append(line)
        if not r.ok:
            lines.append(f"       => {r.detail}")
    passed = sum(1 for r in results if r.ok)
    lines.append("-" * 70)
    total_ms = sum(r.elapsed_ms for r in results)
    lines.append(f"  {passed}/{len(results)} checks passed in {total_ms:.0f} ms")
    return "\n".join(lines)


def render_json(results: list[CheckResult]) -> str:
    payload = {
        "total": len(results),
        "passed": sum(1 for r in results if r.ok),
        "results": [
            {
                "name": r.name,
                "ok": r.ok,
                "detail": r.detail,
                "elapsed_ms": round(r.elapsed_ms, 2),
                "extra": r.extra,
            }
            for r in results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A3 demo asset health check")
    parser.add_argument("--json", action="store_true", help="output machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_all()
    if args.json:
        print(render_json(results))
    else:
        print(render_text(results))
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
