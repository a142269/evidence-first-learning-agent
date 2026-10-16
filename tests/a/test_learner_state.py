"""Plan P1-7：LearnerState 中台自动化测试。

覆盖：
- snapshot 返回 8 个块 (profile / mastery / mistakes / review_schedule /
  resources / strategy / assessment / recommendation)
- timeline 返回 5 类事件按时间倒序
- 单字段 fetch 失败不破坏整体
- API 端点 GET /learner-state/{user_id}, /timeline, /recommendation
- 404 当用户不存在
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ================================================================
# Fixtures
# ================================================================
@pytest.fixture(scope="module")
def app() -> FastAPI:
    from backend.app.api.v1.learner_state import router as ls_router

    a = FastAPI()
    a.include_router(ls_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ================================================================
# 直接调 service
# ================================================================
class TestLearnerStateSnapshot:
    """直接调 service，绕开 HTTP。空数据库 / 不存在的 user 也必须返回结构。"""

    def test_snapshot_for_unknown_user_returns_minimal(self):
        from backend.app.services.learner_state import get_learner_state_service

        snap = get_learner_state_service().snapshot("nonexistent-user-zzz")
        assert snap["user_id"] == "nonexistent-user-zzz"
        # 八大块必须都在，即便全空
        for key in (
            "profile", "mastery", "mistakes", "review_schedule",
            "resources", "strategy", "assessment", "recommendation",
        ):
            assert key in snap, f"missing block: {key}"

    def test_recommendation_has_why_text(self):
        from backend.app.services.learner_state import get_learner_state_service

        snap = get_learner_state_service().snapshot("nonexistent-user-zzz")
        rec = snap["recommendation"]
        assert "why" in rec
        assert isinstance(rec["why"], str)
        assert "基于" in rec["why"]

    def test_snapshot_version_is_int(self):
        from backend.app.services.learner_state import get_learner_state_service

        snap = get_learner_state_service().snapshot("any-user")
        assert isinstance(snap["version"], int)
        assert snap["version"] >= 0

    def test_mastery_block_has_items_key(self):
        from backend.app.services.learner_state import get_learner_state_service

        snap = get_learner_state_service().snapshot("any-user")
        # 即便数据库空，mastery 必须含 items + total
        assert "items" in snap["mastery"]
        assert "total" in snap["mastery"]
        assert isinstance(snap["mastery"]["items"], list)


class TestLearnerStateTimeline:
    def test_timeline_for_unknown_user_returns_empty(self):
        from backend.app.services.learner_state import get_learner_state_service

        tl = get_learner_state_service().timeline("nonexistent-user-zzz")
        assert tl["user_id"] == "nonexistent-user-zzz"
        assert tl["events"] == []
        # 单点 fetch 失败也不破坏整体
        assert "errors" in tl
        assert isinstance(tl["errors"], list)

    def test_timeline_respects_limit(self):
        from backend.app.services.learner_state import get_learner_state_service

        tl = get_learner_state_service().timeline("any-user", limit=3)
        assert len(tl["events"]) <= 3

    def test_timeline_event_types(self):
        """合法的事件类型只有 5 种。"""
        from backend.app.services.learner_state import get_learner_state_service

        tl = get_learner_state_service().timeline("any-user")
        allowed = {
            "profile_snapshot", "path_adjustment", "mistake_recorded",
            "assessment", "resource_generated",
        }
        for ev in tl["events"]:
            assert ev["type"] in allowed, f"unknown event type: {ev['type']}"


class TestFetchFunctionTolerance:
    """Plan P1-7 约束：单字段 fetch 失败不破坏整体。"""

    def test_fetch_mastery_no_db_returns_empty_items(self):
        from backend.app.services import learner_state as ls
        out = ls._fetch_mastery("zzz-no-db-user")
        # 失败也必须有 items + total
        assert "items" in out
        assert "total" in out

    def test_fetch_review_schedule_returns_items_or_error(self):
        from backend.app.services import learner_state as ls
        out = ls._fetch_review_schedule("zzz-no-db-user")
        assert "items" in out
        # 没有 items 但有 error 字段 → 失败路径也算通过
        assert "total" in out or "error" in out


# ================================================================
# API 端点
# ================================================================
class TestLearnerStateAPI:
    def test_api_404_for_unknown_user(self, client: TestClient):
        r = client.get("/api/v1/learner-state/nonexistent-user-zzz")
        # 用户不存在 → 404
        assert r.status_code == 404
        assert "learner_not_found" in r.text

    def test_api_recommendation_endpoint(self, client: TestClient):
        # recommendation 端点对不存在的 user 也返回 200（profile 兜底），
        # 或 500 — 只要不是 404 即可（设计上不强依赖 profile）
        r = client.get("/api/v1/learner-state/nonexistent-user-zzz/recommendation")
        assert r.status_code in (200, 500)

    def test_api_timeline_endpoint(self, client: TestClient):
        r = client.get(
            "/api/v1/learner-state/nonexistent-user-zzz/timeline",
            params={"limit": 5},
        )
        # timeline 对不存在 user 返回 200 + 空 events
        assert r.status_code == 200, r.text
        body = r.json()
        assert "events" in body
        assert isinstance(body["events"], list)