from __future__ import annotations


def test_daily_checkin_is_idempotent_within_same_day(monkeypatch):
    from backend.app.api.v1 import gamification

    monkeypatch.setattr(gamification, "_db_available", False)
    gamification._mem.clear()

    first = gamification.daily_checkin("u-checkin")
    second = gamification.daily_checkin("u-checkin")

    assert first["status"] == "checked_in"
    assert second["status"] == "already_checked_in"
    assert second["streak_days"] == first["streak_days"]
    assert second["total_xp"] == first["total_xp"]
    assert gamification.get_profile("u-checkin")["checked_in_today"] is True


def test_seeded_achievement_objects_are_returned_as_readable_labels(monkeypatch):
    from backend.app.api.v1 import gamification

    monkeypatch.setattr(gamification, "_db_available", False)
    gamification._mem.clear()
    gamification._mem["u-ach"] = {
        "xp": 30,
        "level": 1,
        "streak_days": 2,
        "achievements": [{"code": "first_correct", "unlocked_at": 1}],
    }

    result = gamification.get_profile("u-ach")

    assert result["achievements"] == ["首次答对"]
    assert result["achievements_earned"] == 1
