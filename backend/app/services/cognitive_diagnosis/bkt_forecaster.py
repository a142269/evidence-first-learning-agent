# ruff: noqa: RUF001
"""
BKT learning time-machine forecaster - Innovation #4

Multi-step BKT projection + CI + milestones + Kalman smoothing + counterfactual.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass
class ForecastPoint:
    day: int
    p_learned: float
    ci_low: float
    ci_high: float
    practice_count_expected: int = 0


class BKTForecaster:
    def __init__(
        self,
        p_transit: float = 0.15,
        p_slip: float = 0.10,
        p_guess: float = 0.20,
        daily_practice_rate: float = 0.7,
    ) -> None:
        self.p_transit = p_transit
        self.p_slip = p_slip
        self.p_guess = p_guess
        self.daily_practice_rate = daily_practice_rate

    def forecast(
        self,
        current_mastery: float,
        horizon_days: int = 30,
        practice_history: list[bool] | None = None,
        n_effective: float = 5.0,
    ) -> list[ForecastPoint]:
        n_eff = n_effective + (len(practice_history) if practice_history else 0)
        p = max(0.01, min(0.99, current_mastery))
        points = [self._point(0, p, n_eff, 0)]
        initial_width = points[0].ci_high - points[0].ci_low
        for day in range(1, horizon_days + 1):
            p_after_no = p
            p_correct = p * (1 - self.p_slip) + (1 - p) * self.p_guess
            pa_c = self._posterior(p, True)
            pa_w = self._posterior(p, False)
            posterior_after_practice = p_correct * pa_c + (1 - p_correct) * pa_w
            p_after_practice = (
                posterior_after_practice
                + (1 - posterior_after_practice) * self.p_transit
            )
            p = (
                self.daily_practice_rate * p_after_practice
                + (1 - self.daily_practice_rate) * p_after_no
            )
            p = max(0.01, min(0.99, p))
            n_eff += self.daily_practice_rate
            uncertainty_floor = min(1.0, initial_width + 0.01 * math.sqrt(day))
            points.append(
                self._point(
                    day,
                    p,
                    n_eff,
                    math.ceil(self.daily_practice_rate * day),
                    minimum_width=uncertainty_floor,
                )
            )
        return points

    def _posterior(self, p: float, correct: bool) -> float:
        if correct:
            num = p * (1 - self.p_slip)
            denom = p * (1 - self.p_slip) + (1 - p) * self.p_guess
        else:
            num = p * self.p_slip
            denom = p * self.p_slip + (1 - p) * (1 - self.p_guess)
        return num / max(denom, 1e-9)

    def _point(
        self,
        day: int,
        p: float,
        n_eff: float,
        n_practice: int,
        minimum_width: float = 0.0,
    ) -> ForecastPoint:
        z_90 = 1.645
        std = math.sqrt(max(p * (1 - p) / max(n_eff + 1.0, 1.0), 1e-9))
        ci = (max(0.0, p - z_90 * std), min(1.0, p + z_90 * std))
        width = min(1.0, max(ci[1] - ci[0], minimum_width))
        low = min(max(p - width / 2, 0.0), 1.0 - width)
        high = low + width
        return ForecastPoint(
            day=day,
            p_learned=round(p, 4),
            ci_low=round(low, 4),
            ci_high=round(high, 4),
            practice_count_expected=n_practice,
        )

    def find_milestones(self, forecast: list[ForecastPoint]) -> list[dict[str, Any]]:
        ms = []
        for target, label in [(0.80, "80%"), (0.90, "90%"), (0.95, "95%")]:
            for fp in forecast:
                if fp.p_learned >= target:
                    ms.append(
                        {
                            "day": fp.day,
                            "target": target,
                            "label": label,
                            "p_at_day": fp.p_learned,
                            "ci_at_day": [fp.ci_low, fp.ci_high],
                        }
                    )
                    break
        return ms

    def forecast_with_kalman(
        self,
        history: list[dict[str, Any]],
        horizon_days: int = 30,
    ) -> list[ForecastPoint]:
        if not history or len(history) < 2:
            current = history[-1].get("p_learned", 0.3) if history else 0.3
            return self.forecast(current, horizon_days)
        from backend.app.services.cognitive_diagnosis.kalman_smoother import KalmanSmoother

        smoothed_rows = KalmanSmoother().smooth(history)
        smoothed = [ForecastPoint(**row) for row in smoothed_rows]
        current = float(smoothed_rows[-1]["p_learned"])
        return smoothed + self.forecast(current, horizon_days)

    def reverse_plan(
        self,
        current_mastery: float,
        target_mastery: float,
        horizon_days: int = 30,
        questions_per_full_practice_day: int = 10,
    ) -> dict[str, Any]:
        """Find the minimum daily practice rate that reaches a target mastery."""
        current = max(0.0, min(1.0, current_mastery))
        target = max(0.0, min(1.0, target_mastery))
        if target <= current:
            return {
                "status": "achievable",
                "daily_practice_rate": 0.0,
                "daily_questions": 0,
                "projected_mastery": round(current, 4),
                "target_mastery": target,
                "horizon_days": horizon_days,
            }

        full_practice = BKTForecaster(
            p_transit=self.p_transit,
            p_slip=self.p_slip,
            p_guess=self.p_guess,
            daily_practice_rate=1.0,
        ).forecast(current, horizon_days)[-1].p_learned
        if full_practice < target:
            return {
                "status": "unreachable",
                "daily_practice_rate": None,
                "daily_questions": None,
                "projected_mastery": full_practice,
                "target_mastery": target,
                "horizon_days": horizon_days,
            }

        low, high = 0.0, 1.0
        for _ in range(24):
            middle = (low + high) / 2
            projected = BKTForecaster(
                p_transit=self.p_transit,
                p_slip=self.p_slip,
                p_guess=self.p_guess,
                daily_practice_rate=middle,
            ).forecast(current, horizon_days)[-1].p_learned
            if projected >= target:
                high = middle
            else:
                low = middle

        rate = math.ceil(high * 10_000) / 10_000
        projected = BKTForecaster(
            p_transit=self.p_transit,
            p_slip=self.p_slip,
            p_guess=self.p_guess,
            daily_practice_rate=rate,
        ).forecast(current, horizon_days)[-1].p_learned
        return {
            "status": "achievable",
            "daily_practice_rate": rate,
            "daily_questions": max(
                1, math.ceil(rate * questions_per_full_practice_day)
            ),
            "projected_mastery": projected,
            "target_mastery": target,
            "horizon_days": horizon_days,
        }

    def counterfactual(
        self,
        current_mastery: float,
        horizon_days: int = 30,
        daily_rates: list[float] | None = None,
    ) -> dict[str, Any]:
        if daily_rates is None:
            daily_rates = [0.3, 0.5, 0.7, 0.9]
        scenarios = []
        for rate in daily_rates:
            f = BKTForecaster(
                p_transit=self.p_transit,
                p_slip=self.p_slip,
                p_guess=self.p_guess,
                daily_practice_rate=rate,
            )
            fc = f.forecast(current_mastery, horizon_days)
            scenarios.append(
                {
                    "daily_practice_rate": rate,
                    "label": f"每天{rate * 100:.0f}%练习",
                    "forecast": [fp.__dict__ for fp in fc],
                    "milestones": f.find_milestones(fc),
                    "final_mastery": fc[-1].p_learned,
                }
            )
        base = scenarios[2] if len(scenarios) > 2 else scenarios[-1]
        rec = (
            f"当前节奏（{base['daily_practice_rate'] * 100:.0f}%）下，"
            f"30天后预计掌握{base['final_mastery'] * 100:.0f}%。"
        )
        if (
            len(scenarios) >= 2
            and scenarios[-1]["final_mastery"] > base["final_mastery"] + 0.1
        ):
            rec += (
                f" 若提高到每天{daily_rates[-1] * 100:.0f}%练习，"
                f"可达{scenarios[-1]['final_mastery'] * 100:.0f}%。"
            )

        # ── P1.4: 反事实学习收益 ──
        baseline = scenarios[0]  # lowest practice rate
        recommended = scenarios[-1] if len(scenarios) >= 2 else scenarios[0]  # highest
        expected_gain = round(recommended["final_mastery"] - baseline["final_mastery"], 4)

        # Risk warning: if student practices at baseline rate for 7 more days, what drops?
        risk_warning = ""
        if baseline["daily_practice_rate"] < 0.4:
            risk_warning = (
                f"若连续 7 天不练习（当前 {baseline['daily_practice_rate'] * 100:.0f}% "
                f"练习率仅维持），预计掌握度回落至 {max(0.0, current_mastery - 0.15) * 100:.0f}% 以下"
            )

        return {
            "scenarios": scenarios,
            "recommendation": rec,
            "baseline_curve": baseline,
            "recommended_curve": recommended,
            "expected_gain": expected_gain,
            "risk_warning": risk_warning,
        }


def _build_summary_text(
    current: float,
    forecast: list[ForecastPoint],
    milestones: list[dict[str, Any]],
) -> str:
    parts = [f"当前掌握度 {current * 100:.0f}%。"]
    for m in milestones[:2]:
        parts.append(f"预计第 {m['day']} 天达到 {m['label']}。")
    last = forecast[-1]
    parts.append(
        f"30天后预测掌握度 {last.p_learned * 100:.0f}%"
        f"（90%CI {last.ci_low * 100:.0f}-{last.ci_high * 100:.0f}%）。"
    )
    return " ".join(parts)
