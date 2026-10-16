"""Tests for AttributionEngine (T1.2-B) — 8 分类双通道归因。

覆盖：
- 8 分类各一个真实样例
- 规则通道置信度
- LLM 兜底（低置信度时触发，mock）
- AttributionResult 结构
- 单例
- API 端点
"""
from __future__ import annotations

from typing import List

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import configure_database, init_db
from backend.app.core import models  # noqa: F401
from backend.app.services.attribution_engine import (
    ATTRIBUTION_CATEGORIES,
    CATEGORY_LABELS,
    AttributionEngine,
    AttributionResult,
    get_attribution_engine,
)


# ─── 8 分类样例 ──────────────────────────────────────────

CASES = [
    ("input_error", "什么是 CNN？", "", "卷积神经网络", 0.9),
    ("careless", "2+3 等于多少？", "5.1", "5", 0.8),
    ("ambiguous_question", "损失函数可能的最优值大约是多少？", "0.3", "0.25", 0.7),
    ("boundary_unclear", "ReLU 在边界 x=0 处的导数是多少？", "0", "未定义", 0.6),
    ("procedural_slip", "写出 SGD 更新步骤", "步骤1:算梯度, 步骤2:错, 步骤3:对",
     "步骤1:算梯度, 步骤2:更新, 步骤3:校验", 0.6),
    ("prerequisite_missing", "CNN 的基本定义是什么？", "一种循环网络", "卷积神经网络", 0.55),
    ("concept_confusion", "Adam 和 SGD 的核心区别？", "都是激活函数", "学习率自适应 vs 固定", 0.7),
    ("unknown", "Q", "x", "y", 0.3),
]


# ─── 单元测试：8 分类 ────────────────────────────────────

class TestRuleClassification:
    @pytest.mark.parametrize("expected,question,ua,ca,min_conf", CASES)
    def test_each_category(self, expected, question, ua, ca, min_conf):
        eng = AttributionEngine(llm_client=None)  # 纯规则
        result = eng.attribute(question=question, user_answer=ua, correct_answer=ca)
        assert result.category == expected, (
            f"expected {expected}, got {result.category} (evidence={result.evidence})"
        )
        assert result.confidence >= min_conf - 0.1
        assert result.source in ("rule", "llm")

    def test_all_categories_covered(self):
        """8 分类样例覆盖全部类别。"""
        covered = {c[0] for c in CASES}
        assert covered == set(ATTRIBUTION_CATEGORIES)

    def test_category_labels_complete(self):
        for cat in ATTRIBUTION_CATEGORIES:
            assert cat in CATEGORY_LABELS
            assert len(CATEGORY_LABELS[cat]) > 0


# ─── AttributionResult 结构 ─────────────────────────────

class TestAttributionResult:
    def test_to_dict(self):
        r = AttributionResult(category="careless", confidence=0.8, evidence={"x": 1}, source="rule")
        d = r.to_dict()
        assert d["category"] == "careless"
        assert d["confidence"] == 0.8
        assert d["evidence"] == {"x": 1}
        assert d["source"] == "rule"
        assert d["category_label"] == "粗心失误"

    def test_evidence_default(self):
        r = AttributionResult(category="unknown", confidence=0.3)
        assert r.evidence == {}
        assert r.source == "rule"


# ─── LLM 兜底 ───────────────────────────────────────────

class _MockLLM:
    def __init__(self, response: str):
        self._response = response
        self.calls: List = []

    def chat(self, messages, temperature=None, max_tokens=None):
        self.calls.append(messages)
        return self._response

    def achat(self, messages, temperature=None, max_tokens=None):
        return self._response


class TestLLMFallback:
    def test_low_confidence_triggers_llm(self):
        """prerequisite_missing 置信度 0.58 < 0.6 → 触发 LLM。"""
        import json
        mock = _MockLLM(json.dumps({"category": "concept_confusion", "evidence": "llm 重新判断"}))
        eng = AttributionEngine(llm_client=mock)
        result = eng.attribute(
            question="CNN 的基本定义是什么？",
            user_answer="一种循环网络",
            correct_answer="卷积神经网络",
        )
        assert result.source == "llm"
        assert result.category == "concept_confusion"
        assert len(mock.calls) == 1

    def test_high_confidence_skips_llm(self):
        """input_error 置信度 0.92 → 不触发 LLM。"""
        mock = _MockLLM('{"category":"unknown"}')
        eng = AttributionEngine(llm_client=mock)
        result = eng.attribute(question="Q", user_answer="", correct_answer="A")
        assert result.source == "rule"
        assert result.category == "input_error"
        assert len(mock.calls) == 0

    def test_llm_failure_falls_back_to_rule(self):
        """LLM 抛异常 → 回退规则结果。"""
        class _BadLLM:
            def chat(self, *a, **k):
                raise RuntimeError("boom")
        eng = AttributionEngine(llm_client=_BadLLM())
        result = eng.attribute(
            question="CNN 的基本定义是什么？",
            user_answer="一种循环网络",
            correct_answer="卷积神经网络",
        )
        assert result.source == "rule"
        assert result.category == "prerequisite_missing"

    def test_llm_invalid_category_falls_back(self):
        """LLM 返回非 8 分类的值 → 回退规则。"""
        import json
        mock = _MockLLM(json.dumps({"category": "nonsense", "evidence": "x"}))
        eng = AttributionEngine(llm_client=mock)
        result = eng.attribute(
            question="CNN 的基本定义是什么？",
            user_answer="一种循环网络",
            correct_answer="卷积神经网络",
        )
        assert result.category == "prerequisite_missing"


# ─── 单例 ───────────────────────────────────────────────

class TestSingleton:
    def test_get_engine_returns_same_instance(self):
        a = get_attribution_engine()
        b = get_attribution_engine()
        assert a is b


# ─── API 端点 ───────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    init_db()
    yield


@pytest.fixture
def client(_isolated_db):
    from backend.app.main import app
    return TestClient(app)


class TestAttributionAPI:
    def _record(self, client, ua="提取特征", ca="降低维度、减少计算量"):
        resp = client.post(
            "/api/v1/mistakes/record",
            json={
                "user_id": "demo",
                "kp_id": "kp_cnn",
                "question": "CNN 的池化层作用是什么？",
                "student_answer": ua,
                "correct_answer": ca,
                "error_type": "概念混淆",
            },
        )
        assert resp.status_code == 200
        return resp.json()["mistake_id"]

    def test_attribution_returns_valid_category(self, client):
        mid = self._record(client)
        resp = client.get(f"/api/v1/mistakes/{mid}/attribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mistake_id"] == mid
        assert data["category"] in ATTRIBUTION_CATEGORIES
        assert 0.0 <= data["confidence"] <= 1.0
        assert "evidence" in data
        assert data["category_label"]
        assert data["recommended_bloom_level"] in (
            "remember", "understand", "apply", "analyze", "evaluate", "create"
        )
        assert len(data["remediation_advice"]) > 5
        assert data["all_categories"] == ATTRIBUTION_CATEGORIES

    def test_attribution_not_found(self, client):
        resp = client.get("/api/v1/mistakes/nonexistent/attribution")
        assert resp.status_code == 404
