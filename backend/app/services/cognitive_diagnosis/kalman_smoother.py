"""One-dimensional Kalman smoothing for noisy mastery observations."""

from __future__ import annotations

import math
from typing import Any


class KalmanSmoother:
    """Smooth bounded mastery observations while preserving their timestamps."""

    def __init__(
        self,
        process_variance: float = 0.02,
        observation_variance: float = 0.05,
        initial_variance: float = 0.1,
    ) -> None:
        if process_variance <= 0 or observation_variance <= 0:
            raise ValueError("Kalman variances must be positive")
        self.process_variance = process_variance
        self.observation_variance = observation_variance
        self.initial_variance = initial_variance

    def smooth(self, observations: list[dict[str, Any]]) -> list[dict[str, float | int]]:
        """Return smoothed mastery values and 90% confidence intervals."""
        if not observations:
            return []

        state = self._bounded(observations[0].get("p_learned", 0.3))
        variance = self.initial_variance
        output: list[dict[str, float | int]] = []

        for observation in observations:
            measured = self._bounded(observation.get("p_learned", state))
            predicted_variance = variance + self.process_variance
            gain = predicted_variance / (
                predicted_variance + self.observation_variance
            )
            state = self._bounded(state + gain * (measured - state))
            variance = (1.0 - gain) * predicted_variance
            radius = 1.645 * math.sqrt(max(variance, 1e-9))
            output.append(
                {
                    "day": int(observation.get("day", len(output))),
                    "p_learned": round(state, 4),
                    "ci_low": round(max(0.0, state - radius), 4),
                    "ci_high": round(min(1.0, state + radius), 4),
                }
            )
        return output

    @staticmethod
    def _bounded(value: Any) -> float:
        return max(0.0, min(1.0, float(value)))
