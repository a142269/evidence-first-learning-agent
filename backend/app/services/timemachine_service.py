"""
TimeMachine Service — B owns

包装 BKT forecaster + Kalman smoother，接入真实 BKT 历史数据，
提供学习时光机的统一数据接口：历史平滑、未来预测、里程碑、反事实分析。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.app.services.cognitive_diagnosis.bkt_forecaster import (
    BKTForecaster,
    ForecastPoint,
    _build_summary_text,
)
from backend.app.services.cognitive_diagnosis.kalman_smoother import KalmanSmoother
from backend.app.services.cognitive_diagnosis.state_repository import (
    StateRepository,
    get_state_repo,
)

logger = logging.getLogger(__name__)

HistoryPoint = Dict[str, Any]
PlotPoint = tuple[int, float]


class TimeMachineService:
    """学习时光机：基于真实 BKT 历史数据的 mastery 预测服务。"""

    def __init__(
        self,
        state_repo: Optional[StateRepository] = None,
        forecaster: Optional[BKTForecaster] = None,
    ):
        self.state_repo = state_repo or get_state_repo()
        self.forecaster = forecaster or BKTForecaster()
        self.smoother = KalmanSmoother()

    # ── 历史数据加载 ──────────────────────────────────────────

    def _load_history(self, user_id: str, kp_id: str) -> List[HistoryPoint]:
        """从 StateRepository 加载某用户某 KP 的真实 BKT 历史记录。

        返回按时间排序的 mastery 观测列表，每个元素含 day 和 p_learned。
        如果没有历史，则返回一个默认起点。
        """
        state = self.state_repo.load_bkt_state(user_id, kp_id)
        if state is None:
            return []

        history_raw = state.get("history", [])
        if not history_raw:
            # 只有当前状态，构造一个单点历史
            return [
                {
                    "day": 0,
                    "p_learned": max(0.01, min(0.99, state.get("p_learned", 0.3))),
                }
            ]

        # history_raw 可能是 [(timestamp, correct_bool), ...] 或 [{day, p_learned}, ...]
        parsed: List[HistoryPoint] = []
        for i, entry in enumerate(history_raw):
            if isinstance(entry, dict) and "p_learned" in entry:
                parsed.append(
                    {
                        "day": entry.get("day", i),
                        "p_learned": max(
                            0.01, min(0.99, float(entry["p_learned"]))
                        ),
                    }
                )
            elif isinstance(entry, dict) and "p_after" in entry:
                parsed.append(
                    {
                        "day": entry.get("day", i),
                        "p_learned": max(
                            0.01, min(0.99, float(entry["p_after"]))
                        ),
                    }
                )
            elif isinstance(entry, dict) and "correct" in entry:
                # 早期种子只记录 {t, correct}。这类事件没有逐步概率，使用
                # 当前持久化 BKT 掌握度作为有证据的观测，避免把 dict 强转
                # float 导致整个反事实/时光机接口 500。
                parsed.append({
                    "day": entry.get("day", i),
                    "p_learned": max(
                        0.01, min(0.99, float(state.get("p_learned", 0.3)))
                    ),
                })
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                # (timestamp, correct) → 简单映射到 mastery 波动
                correct = bool(entry[1])
                p = 0.8 if correct else 0.2
                parsed.append({"day": i, "p_learned": p})
            elif isinstance(entry, (int, float)):
                # 兜底：按索引递增
                parsed.append(
                    {"day": i, "p_learned": max(0.01, min(0.99, float(entry or 0.3)))}
                )
            else:
                logger.debug("[timemachine] ignore unsupported history entry: %r", entry)
        return parsed

    # ── 核心预测接口 ──────────────────────────────────────────

    def forecast(
        self,
        user_id: str,
        kp_id: str,
        horizon_days: int = 30,
        use_kalman: bool = True,
    ) -> Dict[str, Any]:
        """返回学习时光机完整数据：历史 + 预测 + 里程碑 + 摘要文本。

        Args:
            user_id: 学生 ID
            kp_id: 知识点 ID
            horizon_days: 预测天数（1-90）
            use_kalman: 是否对历史做 Kalman 平滑

        Returns:
            {
                "user_id": str,
                "kp_id": str,
                "current_mastery": float,
                "history": [{day, p_learned, ci_low, ci_high}, ...],
                "forecast": [{day, p_learned, ci_low, ci_high}, ...],
                "milestones": [{day, target, label, p_at_day, ci_at_day}, ...],
                "summary_text": str,
                "ascii_chart": str,
            }
        """
        history = self._load_history(user_id, kp_id)

        if use_kalman and len(history) >= 2:
            smoothed = self.smoother.smooth(history)
            current = float(smoothed[-1]["p_learned"])
            history_out = smoothed
        else:
            current = (
                float(history[-1]["p_learned"]) if history else 0.3
            )
            history_out = history

        # 使用 BKT 参数（如有）
        state = self.state_repo.load_bkt_state(user_id, kp_id)
        p_transit = state.get("p_transit", 0.15) if state else 0.15
        p_slip = state.get("p_slip", 0.10) if state else 0.10
        p_guess = state.get("p_guess", 0.20) if state else 0.20

        f = BKTForecaster(
            p_transit=p_transit,
            p_slip=p_slip,
            p_guess=p_guess,
        )
        forecast_pts = f.forecast(current, horizon_days)
        milestones = f.find_milestones(forecast_pts)

        ascii_chart = self._render_ascii(history_out, forecast_pts)
        svg_chart = self._render_svg(history_out, forecast_pts)

        return {
            "user_id": user_id,
            "kp_id": kp_id,
            "current_mastery": round(current, 4),
            "history": history_out,
            "forecast": [fp.__dict__ for fp in forecast_pts],
            "milestones": milestones,
            "summary_text": _build_summary_text(current, forecast_pts, milestones),
            "ascii_chart": ascii_chart,
            "svg": svg_chart,
        }


    def counterfactual(
        self,
        user_id: str,
        kp_id: str,
        horizon_days: int = 30,
        daily_rates: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """反事实分析：不同每日练习强度下的 mastery 预测对比。"""
        history = self._load_history(user_id, kp_id)
        current = (
            float(history[-1]["p_learned"]) if history else 0.3
        )
        return self.forecaster.counterfactual(
            current_mastery=current,
            horizon_days=horizon_days,
            daily_rates=daily_rates,
        )

    def reverse_plan(
        self,
        user_id: str,
        kp_id: str,
        target_mastery: float,
        horizon_days: int = 30,
        questions_per_full_practice_day: int = 10,
    ) -> Dict[str, Any]:
        """反向规划：从目标掌握度倒推每日练习强度。"""
        history = self._load_history(user_id, kp_id)
        current = (
            float(history[-1]["p_learned"]) if history else 0.3
        )
        state = self.state_repo.load_bkt_state(user_id, kp_id)
        p_transit = state.get("p_transit", 0.15) if state else 0.15
        p_slip = state.get("p_slip", 0.10) if state else 0.10
        p_guess = state.get("p_guess", 0.20) if state else 0.20

        f = BKTForecaster(
            p_transit=p_transit,
            p_slip=p_slip,
            p_guess=p_guess,
        )
        result = f.reverse_plan(
            current_mastery=current,
            target_mastery=target_mastery,
            horizon_days=horizon_days,
            questions_per_full_practice_day=questions_per_full_practice_day,
        )
        result["user_id"] = user_id
        result["kp_id"] = kp_id
        result["current_mastery"] = round(current, 4)
        return result

    # ── ASCII 可视化 ───────────────────────────────────────────

    @staticmethod
    def _render_ascii(
        history: List[HistoryPoint],
        forecast: List[ForecastPoint],
        width: int = 40,
    ) -> str:
        """渲染 ASCII 折线图（历史 + 预测），含不确定带。"""
        if not forecast:
            return "(no forecast data)"

        all_pts = []
        for h in history:
            all_pts.append(
                (int(h.get("day", 0)), float(h.get("p_learned", 0.3)))
            )
        for fp in forecast:
            all_pts.append((fp.day, fp.p_learned))

        if not all_pts:
            return "(empty)"

        max_day = max(d for d, _ in all_pts)
        min_p = min(p for _, p in all_pts)
        max_p = max(p for _, p in all_pts)
        p_range = max(0.01, max_p - min_p)

        lines: List[str] = []
        # 标题
        lines.append(f"{'Day':>4} | Mastery (90% CI)  {'Chart':<{width}}")
        lines.append("-" * (4 + 3 + 20 + 2 + width))

        # 选 5 个代表性点：起点、1/4、中、3/4、终点
        indices = [0]
        if len(forecast) > 1:
            indices.append(len(forecast) // 4)
            indices.append(len(forecast) // 2)
            indices.append(len(forecast) * 3 // 4)
        indices.append(len(forecast) - 1)
        indices = sorted(set(indices))

        for idx in indices:
            fp = forecast[idx]
            bar_len = int((fp.p_learned - min_p) / p_range * width)
            bar = "█" * bar_len + "░" * (width - bar_len)
            lines.append(
                f"{fp.day:>4} | {fp.p_learned*100:5.1f}% ({fp.ci_low*100:.0f}-{fp.ci_high*100:.0f}%) |{bar}"
            )

        return "\n".join(lines)

    @staticmethod
    def _render_svg(
        history: List[HistoryPoint],
        forecast: List[ForecastPoint],
        width: int = 480,
        height: int = 220,
    ) -> str:
        """渲染 SVG 折线图（历史 + 预测 + 90% CI 带）。"""
        if not forecast:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}"></svg>'.format(width, height)

        all_pts: List[PlotPoint] = []
        for h in history:
            all_pts.append((int(h.get("day", 0)), float(h.get("p_learned", 0.3))))
        for fp in forecast:
            all_pts.append((fp.day, fp.p_learned))

        max_day = max((d for d, _ in all_pts), default=1)
        margin_l, margin_b, margin_t, margin_r = 36, 24, 16, 12
        plot_w = width - margin_l - margin_r
        plot_h = height - margin_t - margin_b

        def x(d: float) -> float:
            return margin_l + (d / max(max_day, 1)) * plot_w

        def y(p: float) -> float:
            return margin_t + (1.0 - max(0.0, min(1.0, p))) * plot_h

        parts: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="10">',
        ]
        # 坐标轴
        parts.append(f'<line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t + plot_h}" stroke="#999"/>')
        parts.append(f'<line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{margin_l + plot_w}" y2="{margin_t + plot_h}" stroke="#999"/>')
        # Y 轴刻度
        for v in (0.0, 0.5, 1.0):
            yy = y(v)
            parts.append(f'<line x1="{margin_l - 3}" y1="{yy}" x2="{margin_l}" y2="{yy}" stroke="#999"/>')
            parts.append(f'<text x="{margin_l - 6}" y="{yy + 3}" text-anchor="end" fill="#666">{int(v * 100)}</text>')

        # CI 带（polygon）
        ci_upper = [(x(fp.day), y(fp.ci_high)) for fp in forecast]
        ci_lower = [(x(fp.day), y(fp.ci_low)) for fp in forecast]
        poly_pts = " ".join(f"{px},{py}" for px, py in ci_upper) + " " + " ".join(f"{px},{py}" for px, py in reversed(ci_lower))
        parts.append(f'<polygon points="{poly_pts}" fill="#4f8cff" fill-opacity="0.15"/>')

        # 预测中线
        line_pts = " ".join(f"{x(fp.day)},{y(fp.p_learned)}" for fp in forecast)
        parts.append(f'<polyline points="{line_pts}" fill="none" stroke="#2b6cb0" stroke-width="2"/>')

        # 历史散点
        for h in history:
            hx, hp = x(int(h.get("day", 0))), y(float(h.get("p_learned", 0.3)))
            parts.append(f'<circle cx="{hx}" cy="{hp}" r="2.5" fill="#ed8936"/>')

        # 里程碑
        for fp in forecast:
            if hasattr(fp, "is_milestone") and getattr(fp, "is_milestone", False):
                mx, my = x(fp.day), y(fp.p_learned)
                parts.append(f'<circle cx="{mx}" cy="{my}" r="4" fill="none" stroke="#2f855a" stroke-width="2"/>')

        parts.append("</svg>")
        return "".join(parts)



# ── 模块单例 ───────────────────────────────────────────────

_timemachine_service: Optional[TimeMachineService] = None


def get_timemachine_service() -> TimeMachineService:
    global _timemachine_service
    if _timemachine_service is None:
        _timemachine_service = TimeMachineService()
    return _timemachine_service
