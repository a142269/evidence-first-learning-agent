"""
/metrics - Prometheus 端点 + 资源使用统计

提供两类端点:
    GET /metrics              Prometheus exposition format (text/plain)
    GET /metrics/summary      JSON 摘要 (供前端 dashboard 展示)
    GET /metrics/health       健康检查 (含依赖状态)

所有指标走 backend.app.core.telemetry.get_telemetry()。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.app.api.v1.artifacts.registry import get_artifact_registry
from backend.app.core.telemetry import get_telemetry


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


# ================================================================
# 启动时间 - 计算 uptime
# ================================================================
_BOOT_TS = time.time()


# ================================================================
# /metrics — Prometheus exposition
# ================================================================
@router.get("", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    """Prometheus exposition format

    指标命名遵循 Prometheus 社区惯例:
      llm_calls_total{provider, status}
      llm_call_duration_seconds_{bucket,sum,count}
      pipeline_stage_duration_seconds{stage}
      artifact_generated_total{type}
      agent_failure_total{agent}
      session_active_count
      artifact_registry_size
    """
    tel = get_telemetry()
    # 实时刷新 gauge
    try:
        tel.gauge("artifact_registry_size").set(
            float(get_artifact_registry().size()),
        )
    except Exception:
        pass
    return tel.export_prometheus()


# ================================================================
# /metrics/summary — JSON for frontend dashboard
# ================================================================
@router.get("/summary")
def metrics_summary() -> Dict[str, Any]:
    """聚合摘要 - 适合前端实时显示"""
    tel = get_telemetry()
    artifact_registry = get_artifact_registry()

    artifact_count = artifact_registry.size()
    tel.gauge("artifact_registry_size").set(float(artifact_count))

    # 按 type 统计已生成的 artifact
    by_type: Dict[str, int] = {}
    for rec in artifact_registry.list(limit=500):
        by_type[rec.type] = by_type.get(rec.type, 0) + 1

    # 累计 LLM 调用 (无标签时累加所有)
    llm_total = sum(
        v for k, v in tel.counter("llm_calls_total")._values.items()
    )
    agent_fail_total = sum(
        v for k, v in tel.counter("agent_failure_total")._values.items()
    )
    artifact_gen_total = sum(
        v for k, v in tel.counter("artifact_generated_total")._values.items()
    )
    pipeline_stages_total = sum(
        v for k, v in tel.counter("pipeline_stages_total")._values.items()
    )

    from backend.app.core.database import SessionLocal
    from backend.app.core.models import AgentRunRecord

    with SessionLocal() as db:
        persisted_runs = db.query(AgentRunRecord).all()
    persisted_run_count = len(persisted_runs)
    successful_runs = sum(1 for row in persisted_runs if row.status == "success")
    persisted_tool_calls = sum(int(row.tool_calls or 0) for row in persisted_runs)
    persisted_artifacts = sum(int(row.artifact_count or 0) for row in persisted_runs)
    persisted_agent_calls = sum(len(row.agents or []) for row in persisted_runs)
    average_duration_ms = (
        sum(int(row.duration_ms or 0) for row in persisted_runs) / persisted_run_count
        if persisted_run_count
        else 0.0
    )
    runs_by_workflow: Dict[str, int] = {}
    for row in persisted_runs:
        runs_by_workflow[row.workflow_type] = runs_by_workflow.get(row.workflow_type, 0) + 1

    return {
        "uptime_seconds": round(time.time() - _BOOT_TS, 2),
        "artifacts": {
            "total": artifact_count,
            "by_type": by_type,
            "generated_total": int(artifact_gen_total),
            "persisted_total": persisted_artifacts,
        },
        "llm": {
            "calls_total": int(llm_total) + persisted_agent_calls,
            "live_calls_total": int(llm_total),
            "persisted_agent_calls_total": persisted_agent_calls,
        },
        "agents": {
            "failures_total": int(agent_fail_total),
            "runs_total": persisted_run_count,
            "successful_runs": successful_runs,
            "success_rate_pct": round(
                successful_runs / persisted_run_count * 100, 1
            ) if persisted_run_count else 0.0,
            "tool_calls_total": persisted_tool_calls,
            "average_duration_ms": round(average_duration_ms, 1),
            "runs_by_workflow": runs_by_workflow,
        },
        "pipeline": {
            "stages_total": int(pipeline_stages_total),
            "active_sessions": int(
                tel.gauge("session_active_count").value(),
            ),
        },
    }


# ================================================================
# /metrics/health — 健康检查
# ================================================================
@router.get("/health")
def health() -> Dict[str, Any]:
    """轻量健康检查 — 含关键依赖可用性"""
    checks: Dict[str, Dict[str, Any]] = {}

    # 1. Mermaid Studio 可初始化
    try:
        from backend.app.services.multimodal.mermaid import get_mermaid_studio
        get_mermaid_studio()
        checks["mermaid_studio"] = {"ok": True}
    except Exception as exc:
        checks["mermaid_studio"] = {"ok": False, "error": str(exc)}

    # 2. PPTX Builder 可初始化
    try:
        from backend.app.services.multimodal.pptx import get_slide_deck_builder
        get_slide_deck_builder()
        checks["pptx_builder"] = {"ok": True}
    except Exception as exc:
        checks["pptx_builder"] = {"ok": False, "error": str(exc)}

    # 3. Code Sandbox 可初始化
    try:
        from backend.app.services.multimodal.code_sandbox import get_code_sandbox
        sb = get_code_sandbox()
        checks["code_sandbox"] = {
            "ok": True,
            "restricted_available": sb.restricted_available,
        }
    except Exception as exc:
        checks["code_sandbox"] = {"ok": False, "error": str(exc)}

    # 4. TTS 服务可初始化
    try:
        from backend.app.services.multimodal.tts_xunfei import get_tts_service
        tts = get_tts_service()
        checks["tts_xunfei"] = {
            "ok": True, "xunfei_available": tts.available,
        }
    except Exception as exc:
        checks["tts_xunfei"] = {"ok": False, "error": str(exc)}

    # 5. 反思框架
    try:
        from backend.app.agents.reflection import get_reflector
        get_reflector()
        checks["reflector"] = {"ok": True}
    except Exception as exc:
        checks["reflector"] = {"ok": False, "error": str(exc)}

    healthy = all(c.get("ok") for c in checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "uptime_seconds": round(time.time() - _BOOT_TS, 2),
        "checks": checks,
    }
