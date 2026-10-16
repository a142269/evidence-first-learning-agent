from __future__ import annotations

from uuid import uuid4

from backend.app.services.onboarding_profile import build_initial_profile
from backend.app.services.profile_schema import calculate_profile_completeness


def _complete_answers() -> dict:
    return {
        "academic": {
            "major": "人工智能",
            "grade": "大二",
            "current_course": "机器学习",
        },
        "goal": {
            "target": "完成实践项目",
            "interests": ["机器学习", "计算机视觉"],
            "timeline": "3 个月",
            "motivation": "职业发展",
            "success_evidence": "做出可展示项目",
        },
        "foundation": {
            "level": "有一些基础",
            "known_topics": ["Python 基础"],
            "applied_experience": "独立完成过练习",
        },
        "errors": {
            "difficulty_stages": ["数学或公式推导", "调试与排错"],
            "error_patterns": ["忽略条件或边界", "缺少检查与验证"],
            "stuck_response": "向老师或 AI 求助",
        },
        "cognition": {
            "styles": ["图示与知识脉络", "边做边学的实践"],
            "explanation_depth": "先看全局，再拆细节",
            "information_density": "重点清楚，适量细节",
        },
        "resources": {
            "formats": ["图文讲义", "代码案例"],
            "practice_mode": "先给提示让我再试",
            "pace": "适中，讲练结合",
            "challenge_level": "保持一点难度，边学边试",
        },
        "habits": {
            "weekly_hours": 8,
            "session_length": "30–45 分钟",
            "best_time": "晚上",
            "schedule": "每天灵活安排一小段",
            "interruption_risks": ["手机与社交媒体"],
        },
        "autonomy": {
            "confidence": "有提示就能继续",
            "help_style": "先用问题引导我思考",
            "reflection_habit": "回顾错题和原因",
            "collaboration": "需要时找同伴讨论",
        },
    }


def test_onboarding_builds_all_standard_dimensions_with_self_report_evidence() -> None:
    profile = build_initial_profile(_complete_answers(), display_name="小林")

    filled, total, completeness = calculate_profile_completeness(profile)
    assert (filled, total, completeness) == (8, 8, 100.0)
    assert profile["profile_origin"] == "registration_conversation"
    assert profile["knowledge_base"]["level"] == "有一些基础"
    assert profile["knowledge_base"]["score"] == 0.48
    assert profile["knowledge_base"]["applied_experience"] == "独立完成过练习"
    assert profile["error_pattern"]["topics"] == ["数学或公式推导", "调试与排错"]
    assert profile["error_pattern"]["patterns"] == ["忽略条件或边界", "缺少检查与验证"]
    assert profile["error_pattern"]["stuck_response"] == "向老师或 AI 求助"
    assert profile["cognitive_style"]["primary"] == "图示与知识脉络"
    assert profile["cognitive_style"]["information_density"] == "重点清楚，适量细节"
    assert profile["resource_preference"]["preferred_formats"] == ["图文讲义", "代码案例"]
    assert profile["resource_preference"]["challenge_level"] == "保持一点难度，边学边试"
    assert profile["learning_habit"]["weekly_hours"] == 8.0
    assert profile["learning_habit"]["interruption_risks"] == ["手机与社交媒体"]
    assert profile["self_learning_ability"]["status"] == "initial_self_report"
    assert profile["self_learning_ability"]["reflection_habit"] == "回顾错题和原因"
    assert profile["interest_model"]["motivation"] == "职业发展"
    assert profile["learning_progress"]["success_evidence"] == "做出可展示项目"
    assert profile["onboarding"]["completed"] is True
    assert profile["onboarding"]["version"] == "registration-8-turn-v2"
    assert profile["onboarding"]["answer_count"] == 8


def test_onboarding_keeps_skipped_sections_unknown() -> None:
    profile = build_initial_profile(
        {"goal": {"target": "学好当前课程", "timeline": "一学期"}},
        display_name="小周",
    )

    filled, total, completeness = calculate_profile_completeness(profile)
    assert (filled, total, completeness) == (2, 8, 25.0)
    assert profile["knowledge_base"]["status"] == "unknown"
    assert profile["interest_model"]["target"] == "学好当前课程"
    assert profile["onboarding"]["completed"] is False


def test_register_persists_initial_profile_and_returns_completeness(monkeypatch) -> None:
    from backend.app.api.v1 import auth
    from backend.app.repositories import profile_repo

    captured: dict = {}

    class FakeProfileRepository:
        def replace(self, user_id, profile, source="chat"):
            captured.update({"user_id": user_id, "profile": profile, "source": source})
            return profile

    monkeypatch.setattr(profile_repo, "ProfileRepository", FakeProfileRepository)
    account = f"new-student-{uuid4().hex[:10]}"

    response = auth.register(
        auth.RegisterRequest(
            account=account,
            password="secure123",
            display_name="新同学",
            role="student",
            profile_answers=_complete_answers(),
        )
    )

    assert response.user.account == account
    assert response.profile_initialized is True
    assert response.profile_completeness == 100.0
    assert captured["user_id"] == account
    assert captured["source"] == "registration_onboarding"
    assert captured["profile"]["display_name"] == "新同学"

    auth._SESSIONS.pop(response.access_token, None)
    auth._REGISTERED_ACCOUNTS.pop(account, None)


def test_anonymous_register_request_reaches_registration_handler(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from backend.app.api.v1 import auth
    from backend.app.main import app
    from backend.app.repositories import profile_repo

    class FakeProfileRepository:
        def replace(self, user_id, profile, source="chat"):
            return profile

    monkeypatch.setattr(profile_repo, "ProfileRepository", FakeProfileRepository)
    account = f"anonymous-student-{uuid4().hex[:10]}"

    response = TestClient(app).post(
        "/api/v1/auth/register",
        json={
            "account": account,
            "password": "secure123",
            "display_name": "Anonymous Student",
            "role": "student",
            "profile_answers": _complete_answers(),
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["account"] == account
    assert payload["profile_initialized"] is True

    auth._SESSIONS.pop(payload["access_token"], None)
    auth._REGISTERED_ACCOUNTS.pop(account, None)
