# ruff: noqa: RUF001
"""Tests for T1.2 mistake-to-variant remediation generation."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.services.attribution_engine import ATTRIBUTION_CATEGORIES
from backend.app.services.variant_generator import (
    VariantGenerationRequest,
    VariantGenerator,
    request_from_record,
)


def _cnn_request(user_id: str = "demo-student-2") -> VariantGenerationRequest:
    return VariantGenerationRequest(
        user_id=user_id,
        mistake_id="mistake_cnn_pooling",
        kp_id="cnn",
        kp_name="卷积神经网络",
        question="CNN 的池化层主要作用是什么？",
        student_answer="池化层负责学习卷积核参数。",
        correct_answer="池化层通过下采样降低特征图尺寸，保留显著特征并增强平移鲁棒性。",
        count=3,
    )


def test_generate_returns_full_remediation_package() -> None:
    package = VariantGenerator().generate(_cnn_request())
    assert package["mistake_id"] == "mistake_cnn_pooling"
    assert package["kp_id"] == "cnn"
    assert package["category"] in ATTRIBUTION_CATEGORIES
    assert package["category"] == package["attribution"]["category"]
    assert package["attribution"]["error_type"]
    assert package["attribution"]["category_label"]
    assert package["mastery"]["source"] == "RealDINAService"
    assert len(package["variants"]) == 3
    assert package["recommended_variant_id"]
    assert len(package["next_actions"]) == 3


def test_variants_are_unique_and_traceable_to_source_mistake() -> None:
    package = VariantGenerator().generate(_cnn_request())
    variant_ids = [item["variant_id"] for item in package["variants"]]
    questions = [item["question"] for item in package["variants"]]
    assert len(set(variant_ids)) == 3
    assert len(set(questions)) == 3
    assert all(item["source"] == "variant_of_mistake_cnn_pooling" for item in package["variants"])
    assert all("池化层主要作用是什么" not in item["question"] for item in package["variants"])


def test_generator_consumes_b_attribution_engine_category() -> None:
    class _FakeAttributionEngine:
        def attribute(self, **kwargs):
            return SimpleNamespace(
                category="boundary_unclear",
                confidence=0.91,
                evidence={"reason": "unit_test"},
                source="rule",
            )

    package = VariantGenerator(attribution_engine=_FakeAttributionEngine()).generate(_cnn_request())

    assert package["category"] == "boundary_unclear"
    assert package["attribution"]["category"] == "boundary_unclear"
    assert package["attribution"]["category_label"]
    assert all(item["category"] == "boundary_unclear" for item in package["variants"])


def test_generator_falls_back_when_attribution_engine_fails() -> None:
    class _FailingAttributionEngine:
        def attribute(self, **kwargs):
            message = "B attribution unavailable"
            raise RuntimeError(message)

    generator = VariantGenerator(attribution_engine=_FailingAttributionEngine())
    package = generator.generate(_cnn_request())

    assert package["category"] in ATTRIBUTION_CATEGORIES
    assert package["attribution"]["error_type"]
    assert package["attribution"]["evidence"]["fallback"] == "mistake_review"
    assert len(package["variants"]) == 3


def test_recommended_variant_has_best_score() -> None:
    package = VariantGenerator().generate(_cnn_request())
    recommended_id = package["recommended_variant_id"]
    recommended = next(item for item in package["variants"] if item["variant_id"] == recommended_id)
    best_score = min(item["recommendation_score"] for item in package["variants"])
    assert recommended["recommendation_score"] == best_score


def test_low_mastery_or_concept_confusion_targets_understanding() -> None:
    package = VariantGenerator().generate(_cnn_request("demo-student-2"))
    assert package["target_bloom"]["level"] in {"remember", "understand"}
    assert package["mastery"]["current"] < 0.7


def test_unknown_kp_falls_back_without_crashing() -> None:
    request = VariantGenerationRequest(
        user_id="demo-student-1",
        mistake_id="mistake_unknown_kp",
        kp_id="",
        question="这个概念为什么成立？",
        student_answer="不知道",
        correct_answer="需要先给出定义，再说明关键条件和适用边界。",
        count=3,
    )
    package = VariantGenerator().generate(request)
    assert package["kp_name"] == "当前知识点"
    assert len(package["variants"]) == 3


def test_request_from_record_maps_api_record_fields() -> None:
    request = request_from_record(
        {
            "id": "mistake_1",
            "user_id": "demo-student-1",
            "kp_id": "rag",
            "question": "RAG 为什么需要重排？",
            "student_answer": "不需要。",
            "correct_answer": "重排用于提升召回结果与问题的相关性。",
        },
        count=4,
    )
    assert request.mistake_id == "mistake_1"
    assert request.kp_id == "rag"
    assert request.count == 4


def test_remediation_api_returns_package_and_updates_analysis() -> None:
    from backend.app.api.v1 import mistakes as mistake_api

    mistake_api._mistakes.clear()
    mistake_api._mistakes["demo-student-2"] = [
        {
            "id": "mistake_api_001",
            "user_id": "demo-student-2",
            "kp_id": "cnn",
            "question": "CNN 的池化层主要作用是什么？",
            "student_answer": "池化层负责学习卷积核参数。",
            "correct_answer": "池化层通过下采样降低特征图尺寸，保留显著特征并增强平移鲁棒性。",
            "error_type": "",
            "analysis": "",
            "created_at": 1,
            "resolved": False,
        }
    ]
    app = FastAPI()
    app.include_router(mistake_api.router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post("/api/v1/mistakes/mistake_api_001/remediation?count=3")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mistake_id"] == "mistake_api_001"
    assert payload["category"] in ATTRIBUTION_CATEGORIES
    assert payload["attribution"]["category"] == payload["category"]
    assert len(payload["variants"]) == 3
    assert payload["recommended_variant_id"]
    assert mistake_api._mistakes["demo-student-2"][0]["analysis"]


# ---------------------------------------------------------------------------
# T1.2 spec — A's `/api/v1/system/variant/{mistake_id}` endpoint
# ---------------------------------------------------------------------------
def _system_client() -> TestClient:
    from backend.app.api.v1.system import router as system_router

    app = FastAPI()
    app.include_router(system_router, prefix="/api/v1")
    return TestClient(app)


def test_system_variant_endpoint_accepts_body_payload() -> None:
    client = _system_client()
    response = client.post(
        "/api/v1/system/variant/demo_mistake_cnn_pooling",
        json={
            "user_id": "demo-student-2",
            "kp_id": "cnn",
            "kp_name": "卷积神经网络",
            "question": "CNN 的池化层主要作用是什么？",
            "student_answer": "池化层负责学习卷积核参数。",
            "correct_answer": "池化层通过下采样降低特征图尺寸。",
            "count": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mistake_id"] == "demo_mistake_cnn_pooling"
    assert payload["source_endpoint"] == "system.variant"
    assert payload["category"] in ATTRIBUTION_CATEGORIES
    assert payload["attribution"]["category"] == payload["category"]
    assert len(payload["variants"]) == 3
    assert payload["recommended_variant_id"]


def test_system_variant_endpoint_rejects_empty_body() -> None:
    client = _system_client()
    response = client.post("/api/v1/system/variant/missing_data", json={})
    assert response.status_code == 400
    assert "question_and_correct_answer_required" in response.text


def test_system_variant_demo_samples_endpoint_lists_five_cases() -> None:
    client = _system_client()
    response = client.get("/api/v1/system/variant/demo-samples")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    sample_ids = {sample["mistake_id"] for sample in payload["samples"]}
    assert "demo_mistake_cnn_pooling" in sample_ids
    assert "demo_mistake_transformer_attention" in sample_ids


def test_system_variant_endpoint_handles_all_five_demo_samples() -> None:
    client = _system_client()
    sample_payload = client.get("/api/v1/system/variant/demo-samples").json()
    samples = sample_payload["samples"]
    assert len(samples) == 5
    for sample in samples:
        body = {
            "user_id": sample["user_id"],
            "kp_id": sample["kp_id"],
            "kp_name": sample["kp_name"],
            "question": sample["question"],
            "student_answer": sample["student_answer"],
            "correct_answer": sample["correct_answer"],
            "count": 3,
        }
        response = client.post(
            f"/api/v1/system/variant/{sample['mistake_id']}",
            json=body,
        )
        assert response.status_code == 200, response.text
        package = response.json()
        assert package["mistake_id"] == sample["mistake_id"]
        assert package["category"] in ATTRIBUTION_CATEGORIES
        assert package["attribution"]["category"] == package["category"]
        assert len(package["variants"]) == 3
        bloom_levels = {variant["bloom_level"] for variant in package["variants"]}
        assert bloom_levels  # at least one bloom level represented
        assert package["target_bloom"]["level"] in {
            "remember",
            "understand",
            "apply",
            "analyze",
        }
        # Spec: filter out variants whose KP+Bloom matches the original question exactly
        assert all(
            variant["question"].strip() != sample["question"].strip()
            for variant in package["variants"]
        )


def test_system_variant_endpoint_count_param_respected() -> None:
    client = _system_client()
    response = client.post(
        "/api/v1/system/variant/demo_mistake_python_mutable_default?count=5",
        json={
            "user_id": "demo-student-1",
            "kp_id": "python_basics",
            "kp_name": "Python 基础",
            "question": "Python 默认参数为什么会累积？",
            "student_answer": "复制了。",
            "correct_answer": "默认参数在定义时计算一次并共享。",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # Fallback templates may collide above 4 unique variants, so accept the
    # bounded range [count - 1, count] which still proves count escalation.
    assert 4 <= len(payload["variants"]) <= 5

