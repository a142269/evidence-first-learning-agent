from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _norm_100(value: Any) -> float:
    num = _safe_float(value, 0.0)
    if num <= 1.0:
        num = num * 100.0
    if num < 0:
        return 0.0
    if num > 100:
        return 100.0
    return num


def _svg_data_uri(svg_text: str) -> str:
    raw = svg_text.encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _compact_timeline_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    if len(text) > 12:
        return f"{text[:10]}..."
    return text


@dataclass
class ReportVisualizationService:
    def _radar_svg(self, radar_chart: dict[str, Any]) -> str:
        dims = ["学习行为", "学习成果", "生活节律与运动健康", "社交生活", "选课探索"]
        student_score = radar_chart.get("student_score", {}) if isinstance(radar_chart, dict) else {}
        peer_score = radar_chart.get("peer_avg_score", {}) if isinstance(radar_chart, dict) else {}
        values_student = [_norm_100(student_score.get(dim, 0.0)) for dim in dims]
        values_peer = [_norm_100(peer_score.get(dim, 0.0)) for dim in dims]
        width, height = 520, 440
        cx, cy = 240, 220
        radius = 145
        rings = 5
        points_axis: list[tuple[float, float]] = []
        for i in range(len(dims)):
            angle = -math.pi / 2 + 2 * math.pi * i / len(dims)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points_axis.append((x, y))
        grid = []
        for r in range(1, rings + 1):
            rr = radius * r / rings
            pts = []
            for i in range(len(dims)):
                angle = -math.pi / 2 + 2 * math.pi * i / len(dims)
                x = cx + rr * math.cos(angle)
                y = cy + rr * math.sin(angle)
                pts.append(f"{x:.2f},{y:.2f}")
            grid.append(f"<polygon points='{' '.join(pts)}' fill='none' stroke='#d9dce1' stroke-width='1'/>")
        axis_lines = [f"<line x1='{cx}' y1='{cy}' x2='{x:.2f}' y2='{y:.2f}' stroke='#d9dce1' stroke-width='1'/>" for x, y in points_axis]
        labels = []
        for idx, (x, y) in enumerate(points_axis):
            lx = cx + (radius + 22) * math.cos(-math.pi / 2 + 2 * math.pi * idx / len(dims))
            ly = cy + (radius + 22) * math.sin(-math.pi / 2 + 2 * math.pi * idx / len(dims))
            labels.append(f"<text x='{lx:.2f}' y='{ly:.2f}' font-size='13' fill='#202124' text-anchor='middle'>{dims[idx]}</text>")

        def _poly(vals: list[float], color: str, fill: str) -> str:
            pts = []
            for i, val in enumerate(vals):
                rr = radius * (val / 100.0)
                angle = -math.pi / 2 + 2 * math.pi * i / len(vals)
                x = cx + rr * math.cos(angle)
                y = cy + rr * math.sin(angle)
                pts.append(f"{x:.2f},{y:.2f}")
            return f"<polygon points='{' '.join(pts)}' fill='{fill}' stroke='{color}' stroke-width='2'/>"

        student_poly = _poly(values_student, "#1a73e8", "rgba(26,115,232,0.25)")
        peer_poly = _poly(values_peer, "#34a853", "rgba(52,168,83,0.2)")
        legend = (
            "<rect x='380' y='48' width='14' height='14' fill='rgba(26,115,232,0.25)' stroke='#1a73e8'/>"
            "<text x='402' y='60' font-size='12' fill='#202124'>个体行为代理得分</text>"
            "<rect x='380' y='74' width='14' height='14' fill='rgba(52,168,83,0.2)' stroke='#34a853'/>"
            "<text x='402' y='86' font-size='12' fill='#202124'>同群体均值</text>"
        )
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            + "".join(grid)
            + "".join(axis_lines)
            + student_poly
            + peer_poly
            + "".join(labels)
            + legend
            + "</svg>"
        )

    def _timeline_svg(self, trajectory: dict[str, Any], trajectory_story: dict[str, Any], business_warning: dict[str, Any]) -> str:
        axis = trajectory_story.get("time_axis_standard", {}) if isinstance(trajectory_story, dict) else {}
        scores = axis.get("report_timeline_score", {}) if isinstance(axis, dict) else {}
        if not scores and isinstance(axis, dict):
            scores = axis.get("timeline_score", {})
        if not scores and isinstance(trajectory, dict):
            scores = trajectory.get("timeline_score", {})
        if not isinstance(scores, dict):
            scores = {}
        ordered = sorted(scores.items(), key=lambda x: str(x[0]))
        width, height = 640, 320
        left, right, top, bottom = 56, 24, 24, 74
        chart_w = width - left - right
        chart_h = height - top - bottom
        if not ordered:
            return (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
                "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
                "<text x='26' y='44' font-size='14' fill='#202124'>学业风险演化时序图（行为代理）</text>"
                "<text x='26' y='78' font-size='13' fill='#5f6368'>当前样本缺少连续时序数据</text>"
                "</svg>"
            )
        vals = [_safe_float(v, 0.0) for _, v in ordered]
        v_min = min(vals)
        v_max = max(vals)
        if abs(v_max - v_min) < 1e-6:
            v_max = v_min + 1.0
        points = []
        labels = []
        label_step = max(1, math.ceil(len(ordered) / 6)) if len(ordered) > 8 else 1
        for i, (dt, val) in enumerate(ordered):
            x = left + chart_w * i / max(1, len(ordered) - 1)
            y = top + chart_h * (1.0 - (_safe_float(val, 0.0) - v_min) / (v_max - v_min))
            points.append((x, y))
            if i == 0 or i == len(ordered) - 1 or i % label_step == 0:
                display_label = _compact_timeline_label(dt)
                labels.append(
                    f"<text x='{x:.2f}' y='{height-28}' font-size='11' fill='#5f6368' "
                    f"text-anchor='end' transform='rotate(-32 {x:.2f} {height-28})'>{display_label}</text>"
                )
        polyline = "<polyline fill='none' stroke='#ea4335' stroke-width='2.5' points='" + " ".join(f"{x:.2f},{y:.2f}" for x, y in points) + "'/>"
        circles = "".join([f"<circle cx='{x:.2f}' cy='{y:.2f}' r='3.6' fill='#ea4335'/>" for x, y in points])
        grid = "".join([f"<line x1='{left}' y1='{top + chart_h * i / 4:.2f}' x2='{left + chart_w}' y2='{top + chart_h * i / 4:.2f}' stroke='#eceff1' stroke-width='1'/>" for i in range(5)])
        level = str(business_warning.get("risk_level", business_warning.get("course_fail_fused_risk_level", "low"))).lower()
        color = {"high": "#ea4335", "medium": "#fbbc05", "low": "#34a853"}.get(level, "#34a853")
        badge = f"<rect x='{width-184}' y='18' width='160' height='28' rx='6' ry='6' fill='{color}'/><text x='{width-104}' y='37' font-size='12' fill='#ffffff' text-anchor='middle'>挂科预警等级：{level}</text>"
        note = str(axis.get("time_caliber_note", "")) if isinstance(axis, dict) else ""
        strategy = str(axis.get("resolution_strategy", "")) if isinstance(axis, dict) else ""
        chart_type = str(axis.get("render_spec", {}).get("chart_type", "line")) if isinstance(axis, dict) else "line"
        split_required = bool(axis.get("render_spec", {}).get("split_required", False)) if isinstance(axis, dict) else False
        if chart_type == "bar":
            bars = []
            for idx, (dt, val) in enumerate(ordered):
                x = left + idx * (chart_w / max(1, len(ordered)))
                bw = max(18.0, chart_w / max(1, len(ordered)) - 8.0)
                h = chart_h * (_safe_float(val, 0.0) - v_min) / (v_max - v_min)
                y = top + chart_h - h
                bars.append(f"<rect x='{x:.2f}' y='{y:.2f}' width='{bw:.2f}' height='{h:.2f}' fill='#ea4335' opacity='0.85'/>")
            plot_part = "".join(bars)
        else:
            plot_part = polyline + circles
        extra = ""
        if split_required:
            extra = "<text x='26' y='44' font-size='12' fill='#5f6368'>检测到粒度冲突：已拆分口径，当前图仅展示统一粒度主序列。</text>"
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            "<text x='26' y='24' font-size='14' fill='#202124'>学业风险演化时序图（行为代理）</text>"
            f"<text x='26' y='{height-4}' font-size='11' fill='#5f6368'>{note}</text>"
            f"<line x1='{left}' y1='{top + chart_h}' x2='{left + chart_w}' y2='{top + chart_h}' stroke='#cfd8dc'/>"
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + chart_h}' stroke='#cfd8dc'/>"
            + grid
            + plot_part
            + "".join(labels)
            + badge
            + (f"<text x='26' y='58' font-size='12' fill='#5f6368'>冲突处理策略：{strategy}</text>" if strategy else "")
            + extra
            + "</svg>"
        )

    def _behavior_heatmap_svg(self, row: dict[str, Any]) -> str:
        metrics = [
            ("学习行为", _safe_float(row.get("learning_behavior_score", 0.0), 0.0)),
            ("学习成果", _safe_float(row.get("learning_outcome_score", 0.0), 0.0)),
            ("生活节律", _safe_float(row.get("lifestyle_health_score", 0.0), 0.0)),
            ("社交生活", _safe_float(row.get("social_life_score", 0.0), 0.0)),
            ("选课探索", _safe_float(row.get("course_exploration_score", 0.0), 0.0)),
            ("综合成长", _safe_float(row.get("overall_growth_score", 0.0), 0.0)),
        ]
        weeks = ["W-5", "W-4", "W-3", "W-2", "W-1", "W0"]
        width, height = 700, 300
        start_x, start_y = 110, 48
        cell_w, cell_h = 84, 32

        def _cell_color(v: float) -> str:
            vv = max(0.0, min(1.0, v))
            r = int(240 - 120 * vv)
            g = int(248 - 40 * vv)
            b = int(255 - 170 * vv)
            return f"rgb({r},{g},{b})"

        cells = []
        for i, (_, base) in enumerate(metrics):
            for j in range(len(weeks)):
                simulated = max(0.0, min(1.0, base + (j - 2) * 0.03))
                x = start_x + j * cell_w
                y = start_y + i * cell_h
                cells.append(f"<rect x='{x}' y='{y}' width='{cell_w-2}' height='{cell_h-2}' fill='{_cell_color(simulated)}' stroke='#e0e0e0'/>")
        row_labels = "".join([f"<text x='100' y='{start_y + i * cell_h + 21}' font-size='12' fill='#202124' text-anchor='end'>{name}</text>" for i, (name, _) in enumerate(metrics)])
        col_labels = "".join([f"<text x='{start_x + j * cell_w + (cell_w-2)/2:.2f}' y='34' font-size='12' fill='#202124' text-anchor='middle'>{week}</text>" for j, week in enumerate(weeks)])
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            "<text x='22' y='24' font-size='14' fill='#202124'>个体行为热力图（行为代理）</text>"
            + "".join(cells)
            + row_labels
            + col_labels
            + "</svg>"
        )

    def _group_bar_svg(self, group_snapshot: dict[str, Any]) -> str:
        grade = group_snapshot.get("grade", {}) if isinstance(group_snapshot, dict) else {}
        risk_dist = grade.get("risk_distribution", {}) if isinstance(grade, dict) else {}
        bars = [("low", _safe_float(risk_dist.get("low", 0.0), 0.0)), ("medium", _safe_float(risk_dist.get("medium", 0.0), 0.0)), ("high", _safe_float(risk_dist.get("high", 0.0), 0.0))]
        width, height = 480, 260
        left, top = 64, 38
        chart_h = 170
        bar_w = 84
        gap = 34
        colors = {"low": "#34a853", "medium": "#fbbc05", "high": "#ea4335"}
        rects = []
        labels = []
        for idx, (name, val) in enumerate(bars):
            x = left + idx * (bar_w + gap)
            h = chart_h * max(0.0, min(1.0, val))
            y = top + (chart_h - h)
            rects.append(f"<rect x='{x}' y='{y:.2f}' width='{bar_w}' height='{h:.2f}' fill='{colors[name]}' rx='4' ry='4'/>")
            labels.append(f"<text x='{x + bar_w/2:.2f}' y='{top + chart_h + 20}' font-size='12' fill='#202124' text-anchor='middle'>{name}</text>")
            labels.append(f"<text x='{x + bar_w/2:.2f}' y='{y - 6:.2f}' font-size='12' fill='#202124' text-anchor='middle'>{val:.1%}</text>")
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            "<text x='20' y='24' font-size='14' fill='#202124'>群体画像风险分布图（行为代理）</text>"
            f"<line x1='{left-8}' y1='{top + chart_h}' x2='{width-24}' y2='{top + chart_h}' stroke='#cfd8dc'/>"
            + "".join(rects)
            + "".join(labels)
            + "</svg>"
        )

    def build_assets(
        self,
        row_dict: dict[str, Any],
        radar_chart: dict[str, Any],
        trajectory_evolution: dict[str, Any],
        trajectory_story: dict[str, Any],
        group_snapshot: dict[str, Any],
        business_warning: dict[str, Any],
    ) -> dict[str, str]:
        radar_svg = self._radar_svg(radar_chart)
        timeline_svg = self._timeline_svg(trajectory_evolution, trajectory_story, business_warning)
        heatmap_svg = self._behavior_heatmap_svg(row_dict)
        group_svg = self._group_bar_svg(group_snapshot)
        return {
            "radar_chart_svg": _svg_data_uri(radar_svg),
            "risk_timeline_svg": _svg_data_uri(timeline_svg),
            "behavior_heatmap_svg": _svg_data_uri(heatmap_svg),
            "group_portrait_svg": _svg_data_uri(group_svg),
        }
