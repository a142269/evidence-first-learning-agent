"""Tests for Bloom 6×3 sub-level classification (T2.4).

覆盖场景：
- 子层级关键词匹配
- 知识维度判断（factual / conceptual / procedural / metacognitive）
- API 端点 /bloom/detail
- 示例与反例返回
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.services.cognitive_diagnosis.bloom_6x3 import (
    Bloom6x3Config,
    get_bloom6x3_config,
    _default_config,
)
from backend.app.core.database import configure_database, init_db
from backend.app.core import models  # noqa: F401


# ─── Unit tests ────────────────────────────────────────

def test_default_config_structure():
    """默认配置应包含 6 个认知层级 + 4 个知识维度。"""
    cfg = _default_config()
    cognitive = cfg["cognitive_dimensions"]
    assert len(cognitive) == 6
    assert "remember" in cognitive
    assert "create" in cognitive
    # remember 有 2 个子层级
    assert len(cognitive["remember"]["sub_levels"]) == 2
    # understand 有 7 个子层级
    assert len(cognitive["understand"]["sub_levels"]) == 7
    # apply 有 2 个子层级
    assert len(cognitive["apply"]["sub_levels"]) == 2
    # analyze 有 3 个子层级
    assert len(cognitive["analyze"]["sub_levels"]) == 3
    # evaluate 有 2 个子层级
    assert len(cognitive["evaluate"]["sub_levels"]) == 2
    # create 有 3 个子层级
    assert len(cognitive["create"]["sub_levels"]) == 3

    knowledge = cfg["knowledge_dimensions"]
    assert len(knowledge) == 4


def test_classify_text_remember():
    """纯记忆类文本应归类为 remember / recalling。"""
    cfg = Bloom6x3Config()
    result = cfg.classify_text("回忆卷积核的定义并列举 5 种优化算法")
    assert result["level"] == "remember"
    assert result["sub_level"] in ["recognizing", "recalling"]


def test_classify_text_apply():
    """含"实现""编码"的文本应归类为 apply / implementing。"""
    cfg = Bloom6x3Config()
    result = cfg.classify_text("用 PyTorch 实现一个注意力机制")
    assert result["level"] == "apply"
    assert result["sub_level"] in ["executing", "implementing"]
    assert result["knowledge_dim"] == "procedural"


def test_classify_text_analyze():
    """含"分析""归因"的文本应归类为 analyze。"""
    cfg = Bloom6x3Config()
    result = cfg.classify_text("分析 Adam 与 SGD 的收敛差异并归因于学习率")
    assert result["level"] == "analyze"
    assert result["sub_level"] in ["differentiating", "organizing", "attributing"]


def test_classify_text_metacognitive():
    """含"策略""反思"的文本应标记为元认知。"""
    cfg = Bloom6x3Config()
    result = cfg.classify_text("反思当前学习策略的效果并调整计划")
    assert result["knowledge_dim"] == "metacognitive"


def test_sub_level_info():
    """get_sub_level 应返回定义、关键词和示例。"""
    cfg = Bloom6x3Config()
    info = cfg.get_sub_level("understand", "interpreting")
    assert "definition" in info
    assert "keywords" in info
    assert "examples" in info
    assert "anti_examples" in info


# ─── API tests ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_db():
    configure_database("sqlite:///:memory:")
    init_db()
    yield


@pytest.fixture(scope="module")
def client():
    from backend.app.main import app
    return TestClient(app)


class TestBloomDetailAPI:
    def test_bloom_detail_remember(self, client):
        resp = client.get("/api/v1/cognitive/bloom/detail?text=回忆卷积核的定义")
        assert resp.status_code == 200
        data = resp.json()
        assert data["level"] == "remember"
        assert data["sub_level"] in ["recognizing", "recalling"]
        assert data["level_label"] == "记忆"
        assert "definition" in data
        assert len(data["examples"]) > 0

    def test_bloom_detail_apply(self, client):
        resp = client.get("/api/v1/cognitive/bloom/detail?text=用 PyTorch 实现注意力机制")
        assert resp.status_code == 200
        data = resp.json()
        assert data["level"] == "apply"
        assert data["knowledge_dimension"] == "procedural"
        assert data["knowledge_dim_label"] == "程序性"

    def test_bloom_detail_missing_text(self, client):
        resp = client.get("/api/v1/cognitive/bloom/detail")
        assert resp.status_code == 422  # FastAPI validation error
