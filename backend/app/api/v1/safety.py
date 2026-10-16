"""Plan P1-3：安全红队 API

POST /api/v1/safety/adversarial-leakage
  body:
    {
      "question": "2x + 3 = 7，求 x",
      "correct_answer": "x = 2",
      "tutor_responses": {              // 可选：每种诱导的 tutor 回复
         "direct_demand": "...",
         "spoof_teacher": "..."
      },
      "extra_inducers": [               // 可选：自定义诱导
         {"strategy": "...", "inducer": "..."}
      ],
      "kp_ids": ["linear_algebra"],     // 可选
      "bloom_level": "apply"            // 可选
    }

  output: AdversarialLeakageReport.to_dict()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.safety.adversarial_leakage import (
    AdversarialLeakageTester,
    get_adversarial_leakage_tester,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/safety", tags=["safety"])


class AdversarialLeakageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=2000, description="题目原文")
    correct_answer: str = Field(..., min_length=1, max_length=1000, description="正确答案")
    tutor_responses: Optional[Dict[str, str]] = Field(
        default=None, description="可选：strategy → tutor 回复映射，缺省用 baseline placeholder"
    )
    extra_inducers: Optional[List[Dict[str, str]]] = Field(
        default=None, description="可选：自定义诱导策略，{strategy, inducer}"
    )
    kp_ids: Optional[List[str]] = Field(default=None)
    bloom_level: Optional[str] = Field(default=None)


class AdversarialLeakageResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    passed: bool
    leakage_score: float
    scaffolding_score: float
    misconception_risk: float
    overall_risk: float
    scenarios: List[Dict[str, Any]]
    recommendation: str
    ind_count: int = 0


@router.post("/adversarial-leakage", response_model=AdversarialLeakageResponse)
def run_adversarial_leakage(payload: AdversarialLeakageRequest = Body(...)) -> AdversarialLeakageResponse:
    """运行答案泄露对抗测试 — Plan P1-3 红队入口。

    返回：5 类诱导策略下的评分 / 修订版回复 / 综合风险。"""
    tester: AdversarialLeakageTester = get_adversarial_leakage_tester()
    try:
        report = tester.run(
            question=payload.question,
            correct_answer=payload.correct_answer,
            tutor_responses=payload.tutor_responses,
            extra_inducers=payload.extra_inducers,
            kp_ids=payload.kp_ids,
            bloom_level=payload.bloom_level,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[safety] adversarial leakage run failed")
        raise HTTPException(status_code=500, detail=f"adversarial_run_failed: {exc}") from exc
    payload_out = report.to_dict()
    return AdversarialLeakageResponse(
        **payload_out,
        ind_count=len(payload_out.get("scenarios", [])),
    )


@router.get("/adversarial-leakage/strategies")
def list_inducer_strategies() -> Dict[str, Any]:
    """返回默认的 5 类诱导策略，方便前端展示 + 测试做断言。"""
    from backend.app.services.safety.adversarial_leakage import DEFAULT_INDUCERS
    return {"strategies": DEFAULT_INDUCERS}
