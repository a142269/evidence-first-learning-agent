"""
BKT Forecaster 测试
"""
import pytest
from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster, ForecastPoint


class TestBKTForecaster:
    def test_basic_growth(self):
        f = BKTForecaster(p_transit=0.15)
        forecast = f.forecast(0.2, horizon_days=30)
        assert len(forecast) == 31
        assert forecast[-1].p_learned > forecast[0].p_learned

    def test_milestone_80pct(self):
        f = BKTForecaster(p_transit=0.20)
        forecast = f.forecast(0.3, horizon_days=30)
        ms = f.find_milestones(forecast)
        assert any(m["target"] == 0.80 for m in ms)

    def test_ci_widens_with_low_n(self):
        f = BKTForecaster()
        fc_low = f.forecast(0.5, horizon_days=10, n_effective=2)
        fc_high = f.forecast(0.5, horizon_days=10, n_effective=20)
        w_low = fc_low[5].ci_high - fc_low[5].ci_low
        w_high = fc_high[5].ci_high - fc_high[5].ci_low
        assert w_low > w_high

    def test_zero_transit_no_growth(self):
        f = BKTForecaster(p_transit=0.0, daily_practice_rate=0.0)
        forecast = f.forecast(0.4, horizon_days=10)
        assert abs(forecast[-1].p_learned - 0.4) < 0.05

    def test_full_forecast_structure(self):
        f = BKTForecaster()
        forecast = f.forecast(0.5, horizon_days=7)
        for fp in forecast:
            assert hasattr(fp, "day")
            assert hasattr(fp, "p_learned")
            assert hasattr(fp, "ci_low")
            assert hasattr(fp, "ci_high")
            assert fp.ci_low <= fp.p_learned <= fp.ci_high
