from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster


def test_forecast_uncertainty_does_not_shrink_over_horizon():
    forecast = BKTForecaster().forecast(0.35, horizon_days=20, n_effective=8)
    widths = [round(point.ci_high - point.ci_low, 4) for point in forecast]

    assert widths == sorted(widths)


def test_kalman_smoother_returns_bounded_state_sequence():
    from backend.app.services.cognitive_diagnosis.kalman_smoother import KalmanSmoother

    result = KalmanSmoother().smooth(
        [
            {"day": -3, "p_learned": 0.2},
            {"day": -2, "p_learned": 0.8},
            {"day": -1, "p_learned": 0.3},
        ]
    )

    assert [point["day"] for point in result] == [-3, -2, -1]
    assert all(0.0 <= point["p_learned"] <= 1.0 for point in result)
    assert result[1]["p_learned"] != 0.8


def test_reverse_plan_finds_minimum_practice_rate():
    plan = BKTForecaster().reverse_plan(
        current_mastery=0.2,
        target_mastery=0.8,
        horizon_days=30,
        questions_per_full_practice_day=10,
    )

    assert plan["status"] == "achievable"
    assert 0.0 <= plan["daily_practice_rate"] <= 1.0
    assert plan["daily_questions"] >= 1
    assert plan["projected_mastery"] >= 0.8


def test_reverse_plan_reports_unreachable_target():
    plan = BKTForecaster(p_transit=0.0).reverse_plan(
        current_mastery=0.1,
        target_mastery=0.99,
        horizon_days=1,
        questions_per_full_practice_day=1,
    )

    assert plan["status"] == "unreachable"
    assert plan["daily_practice_rate"] is None
    assert plan["projected_mastery"] < 0.99


def test_reverse_plan_api_uses_validated_models():
    from backend.app.api.v1.cognitive import ReversePlanRequest, reverse_plan

    response = reverse_plan(
        ReversePlanRequest(
            current_mastery=0.3,
            target_mastery=0.85,
            horizon_days=30,
            questions_per_full_practice_day=12,
        )
    )

    assert response.status in {"achievable", "unreachable"}
    assert response.target_mastery == 0.85


def test_cognitive_openapi_exposes_reverse_plan():
    from backend.app.main import app

    operation = app.openapi()["paths"]["/api/v1/cognitive/reverse-plan"]["post"]

    assert operation["summary"]
    assert "requestBody" in operation
    assert "200" in operation["responses"]
