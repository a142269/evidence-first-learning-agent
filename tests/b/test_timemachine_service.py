"""
TimeMachine Service 测试 — B 竞赛增强计划 T1.3

验证真实 BKT 历史接入 + Kalman 平滑 + ASCII 可视化 + 反事实分析。
"""
import pytest
from backend.app.services.timemachine_service import TimeMachineService
from backend.app.services.cognitive_diagnosis.state_repository import StateRepository


class FakeStateRepo(StateRepository):
    """内存状态仓库，用于测试。"""

    def __init__(self):
        self._data: dict = {}

    def save_bkt_state(self, user_id: str, kp_id: str, state: dict) -> None:
        self._data.setdefault(user_id, {}).setdefault(kp_id, state)

    def load_bkt_state(self, user_id: str, kp_id: str) -> dict | None:
        return self._data.get(user_id, {}).get(kp_id)


class TestTimeMachineService:
    def test_forecast_with_empty_history(self):
        """无历史时返回默认起点 + 预测。"""
        repo = FakeStateRepo()
        svc = TimeMachineService(state_repo=repo)
        result = svc.forecast("u1", "kp1", horizon_days=10)

        assert result["user_id"] == "u1"
        assert result["kp_id"] == "kp1"
        assert "forecast" in result
        assert len(result["forecast"]) == 11
        assert result["current_mastery"] == 0.3  # 默认起点
        assert "ascii_chart" in result
        assert "milestones" in result

    def test_forecast_with_history(self):
        """有历史时预测应基于最后历史值（平滑后可能在原值附近）。"""
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u2",
            "kp2",
            {
                "p_learned": 0.6,
                "p_transit": 0.15,
                "p_slip": 0.1,
                "p_guess": 0.2,
                "history": [
                    {"day": 0, "p_learned": 0.2},
                    {"day": 1, "p_learned": 0.4},
                    {"day": 2, "p_learned": 0.6},
                ],
            },
        )
        svc = TimeMachineService(state_repo=repo)
        result = svc.forecast("u2", "kp2", horizon_days=10, use_kalman=False)

        assert result["current_mastery"] == 0.6
        forecast = result["forecast"]
        assert len(forecast) == 11
        # 预测应单调递增（练习带来提升）
        assert forecast[-1]["p_learned"] > forecast[0]["p_learned"]

    def test_forecast_accepts_timestamped_bkt_history(self):
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u2",
            "kp-structured",
            {
                "p_learned": 0.61,
                "history": [
                    {"ts": 1_720_000_000, "p_before": 0.3, "p_after": 0.45, "correct": True},
                    {"ts": 1_720_086_400, "p_before": 0.45, "p_after": 0.61, "correct": True},
                ],
            },
        )

        result = TimeMachineService(state_repo=repo).forecast(
            "u2", "kp-structured", horizon_days=5, use_kalman=False
        )

        assert result["current_mastery"] == 0.61
        assert [point["p_learned"] for point in result["history"]] == [0.45, 0.61]

    def test_forecast_accepts_seed_history_with_correct_only(self):
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u-seed",
            "kp-seed",
            {"p_learned": 0.57, "history": [{"t": 1_720_000_000, "correct": True}]},
        )

        result = TimeMachineService(state_repo=repo).counterfactual(
            "u-seed", "kp-seed", horizon_days=5
        )

        assert len(result["scenarios"]) == 4
        assert all(0 <= item["final_mastery"] <= 1 for item in result["scenarios"])

    def test_kalman_smooth_reduces_noise(self):
        """Kalman 平滑应降低噪声波动。"""
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u3",
            "kp3",
            {
                "p_learned": 0.5,
                "history": [
                    {"day": 0, "p_learned": 0.2},
                    {"day": 1, "p_learned": 0.9},  # 噪声 spike
                    {"day": 2, "p_learned": 0.5},
                ],
            },
        )
        svc = TimeMachineService(state_repo=repo)
        result = svc.forecast("u3", "kp3", horizon_days=5, use_kalman=True)

        history = result["history"]
        # 平滑后的中间值应远离原始 0.9
        assert history[1]["p_learned"] < 0.85

    def test_counterfactual_returns_scenarios(self):
        """反事实分析应返回多场景对比。"""
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u4",
            "kp4",
            {"p_learned": 0.3, "history": [{"day": 0, "p_learned": 0.3}]},
        )
        svc = TimeMachineService(state_repo=repo)
        result = svc.counterfactual("u4", "kp4", horizon_days=10)

        assert "scenarios" in result
        assert len(result["scenarios"]) >= 2
        # 高强度练习应优于低强度
        rates = [s["daily_practice_rate"] for s in result["scenarios"]]
        finals = [s["final_mastery"] for s in result["scenarios"]]
        assert finals == sorted(finals) or finals[0] <= finals[-1]
        assert "recommendation" in result

    def test_reverse_plan_achievable(self):
        """反向规划：可达目标应返回有效练习率。"""
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u5",
            "kp5",
            {"p_learned": 0.2, "history": [{"day": 0, "p_learned": 0.2}]},
        )
        svc = TimeMachineService(state_repo=repo)
        result = svc.reverse_plan(
            "u5", "kp5", target_mastery=0.8, horizon_days=30
        )

        assert result["status"] == "achievable"
        assert 0.0 < result["daily_practice_rate"] <= 1.0
        assert result["daily_questions"] >= 1
        assert result["projected_mastery"] >= 0.8

    def test_reverse_plan_unreachable(self):
        """反向规划：不可达目标应返回 unreachable。"""
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u6",
            "kp6",
            {"p_learned": 0.1, "history": [{"day": 0, "p_learned": 0.1}]},
        )
        svc = TimeMachineService(state_repo=repo)
        result = svc.reverse_plan(
            "u6", "kp6", target_mastery=0.99, horizon_days=1
        )

        assert result["status"] == "unreachable"
        assert result["daily_practice_rate"] is None

    def test_ascii_chart_format(self):
        """ASCII 图表应包含关键标签和条形。"""
        repo = FakeStateRepo()
        repo.save_bkt_state(
            "u7",
            "kp7",
            {"p_learned": 0.5, "history": [{"day": 0, "p_learned": 0.5}]},
        )
        svc = TimeMachineService(state_repo=repo)
        result = svc.forecast("u7", "kp7", horizon_days=10)
        chart = result["ascii_chart"]

        assert "Day" in chart
        assert "Mastery" in chart
        assert "█" in chart  # 条形块
        assert "%" in chart
