"""
零依赖 SVG 可视化服务

**移植自老项目** `student-behavior-analysis/backend/app/services/reports/report_visualization_service.py`

价值：
- 纯 Python 拼字符串生成 SVG，**不依赖 matplotlib / pillow / ECharts**
- 输出可直接嵌入 Markdown / PPT / PDF / 前端 img(src=data:image/svg+xml;base64,...)
- 评估页和报告导出共用同一份 SVG，保证视觉一致
- 演示视频里图表渲染永不出锅（不存在 npm 包丢失风险）

A3 适配后提供 4 种核心图：
1. 8 维画像雷达图（含学生 vs 班级均值对比）
2. 学习掌握度趋势图（线 / 柱可切换）
3. 知识点掌握度热力图（按学习周）
4. Bloom 6 层级分布柱状图

使用：
  from backend.app.services.svg_visualization import SVGVisualizer

  viz = SVGVisualizer()
  svg = viz.profile_radar({
      "student_score": {"knowledge_base": 0.7, ...},
      "peer_avg_score": {"knowledge_base": 0.55, ...},
  })
  data_uri = SVGVisualizer.to_data_uri(svg)   # 直接给前端 img src
"""
from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, dict):
            value = value.get("score", default)
        return float(value)
    except Exception:
        return default


def _norm_100(value: Any) -> float:
    num = _safe_float(value, 0.0)
    if num <= 1.0:
        num *= 100.0
    return max(0.0, min(100.0, num))


def _compact_label(value: Any, max_len: int = 12) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return text if len(text) <= max_len else f"{text[:max_len - 2]}..."


# ---------------------------------------------------------------------------
# 主服务
# ---------------------------------------------------------------------------
@dataclass
class SVGVisualizer:
    """零依赖 SVG 图表生成器"""

    # ------------------------------------------------------------------
    # 1. 8 维画像雷达图
    # ------------------------------------------------------------------
    def profile_radar(self, radar_data: Dict[str, Any]) -> str:
        """
        8 维画像雷达图（A3 适配）

        Args:
            radar_data: {
                "student_score": {dim_name: 0-1, ...},
                "peer_avg_score": {dim_name: 0-1, ...},   # 可选
                "title": "..."                            # 可选
            }
        """
        dims = ["知识基础", "学习偏好", "薄弱识别", "时间管理",
                "自我效能", "认知风格", "学习目标", "交互模式"]
        dim_keys = ["knowledge_base", "learning_preference", "weak_points", "time_management",
                    "self_efficacy", "cognitive_style", "learning_goal", "interaction_pattern"]

        student_score = radar_data.get("student_score", {}) or {}
        peer_score = radar_data.get("peer_avg_score", {}) or {}
        title = str(radar_data.get("title", "学习者画像雷达图"))

        values_student = [_norm_100(student_score.get(k, 0.0)) for k in dim_keys]
        values_peer = [_norm_100(peer_score.get(k, 0.0)) for k in dim_keys] if peer_score else []

        width, height = 560, 480
        cx, cy = 260, 240
        radius = 155
        rings = 5
        n = len(dims)

        # 主轴
        points_axis: List[Tuple[float, float]] = []
        for i in range(n):
            angle = -math.pi / 2 + 2 * math.pi * i / n
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points_axis.append((x, y))

        # 同心多边形
        grid_polys = []
        for r in range(1, rings + 1):
            rr = radius * r / rings
            pts = []
            for i in range(n):
                angle = -math.pi / 2 + 2 * math.pi * i / n
                pts.append(f"{cx + rr * math.cos(angle):.2f},{cy + rr * math.sin(angle):.2f}")
            grid_polys.append(f"<polygon points='{' '.join(pts)}' fill='none' stroke='#e5e7eb' stroke-width='1'/>")

        # 径向轴
        axis_lines = [
            f"<line x1='{cx}' y1='{cy}' x2='{x:.2f}' y2='{y:.2f}' stroke='#e5e7eb' stroke-width='1'/>"
            for x, y in points_axis
        ]

        # 标签
        labels = []
        for idx, (x, y) in enumerate(points_axis):
            lx = cx + (radius + 26) * math.cos(-math.pi / 2 + 2 * math.pi * idx / n)
            ly = cy + (radius + 26) * math.sin(-math.pi / 2 + 2 * math.pi * idx / n)
            labels.append(f"<text x='{lx:.2f}' y='{ly:.2f}' font-size='13' fill='#1f2937' "
                         f"text-anchor='middle' dominant-baseline='central'>{dims[idx]}</text>")

        def _poly(vals: List[float], color: str, fill: str) -> str:
            pts = []
            for i, val in enumerate(vals):
                rr = radius * (val / 100.0)
                angle = -math.pi / 2 + 2 * math.pi * i / n
                pts.append(f"{cx + rr * math.cos(angle):.2f},{cy + rr * math.sin(angle):.2f}")
            return f"<polygon points='{' '.join(pts)}' fill='{fill}' stroke='{color}' stroke-width='2'/>"

        student_poly = _poly(values_student, "#3b82f6", "rgba(59,130,246,0.30)")
        peer_poly = _poly(values_peer, "#10b981", "rgba(16,185,129,0.20)") if values_peer else ""

        # 图例
        legend_items = [
            "<rect x='420' y='52' width='14' height='14' fill='rgba(59,130,246,0.30)' stroke='#3b82f6'/>",
            "<text x='442' y='64' font-size='12' fill='#1f2937'>学习者画像</text>",
        ]
        if values_peer:
            legend_items.extend([
                "<rect x='420' y='78' width='14' height='14' fill='rgba(16,185,129,0.20)' stroke='#10b981'/>",
                "<text x='442' y='90' font-size='12' fill='#1f2937'>班级均值</text>",
            ])
        legend = "".join(legend_items)

        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            f"<text x='20' y='28' font-size='15' font-weight='600' fill='#111827'>{title}</text>"
            + "".join(grid_polys)
            + "".join(axis_lines)
            + (peer_poly if peer_poly else "")
            + student_poly
            + "".join(labels)
            + legend
            + "</svg>"
        )

    # ------------------------------------------------------------------
    # 2. 学习掌握度趋势图（线 / 柱）
    # ------------------------------------------------------------------
    def mastery_trend(
        self,
        timeline_scores: Dict[str, float],
        chart_type: str = "line",
        title: str = "学习掌握度演化趋势",
        warning_level: Optional[str] = None,
    ) -> str:
        """
        Args:
            timeline_scores: {时间标签: 0-1 掌握度}
            chart_type: line / bar
            warning_level: low / medium / high（右上角徽章）
        """
        ordered = sorted(timeline_scores.items(), key=lambda x: str(x[0]))
        width, height = 680, 340
        left, right, top, bottom = 60, 28, 30, 80
        chart_w = width - left - right
        chart_h = height - top - bottom

        if not ordered:
            return (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
                "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
                f"<text x='20' y='28' font-size='15' font-weight='600' fill='#111827'>{title}</text>"
                "<text x='20' y='80' font-size='13' fill='#6b7280'>当前样本缺少连续时序数据</text>"
                "</svg>"
            )

        vals = [_safe_float(v, 0.0) for _, v in ordered]
        v_min, v_max = min(vals), max(vals)
        if abs(v_max - v_min) < 1e-6:
            v_max = v_min + 1.0

        points: List[Tuple[float, float]] = []
        labels = []
        label_step = max(1, math.ceil(len(ordered) / 6)) if len(ordered) > 8 else 1

        for i, (dt, val) in enumerate(ordered):
            x = left + chart_w * i / max(1, len(ordered) - 1)
            y = top + chart_h * (1.0 - (_safe_float(val, 0.0) - v_min) / (v_max - v_min))
            points.append((x, y))
            if i == 0 or i == len(ordered) - 1 or i % label_step == 0:
                display = _compact_label(dt)
                labels.append(
                    f"<text x='{x:.2f}' y='{height - 32}' font-size='11' fill='#6b7280' "
                    f"text-anchor='end' transform='rotate(-30 {x:.2f} {height - 32})'>{display}</text>"
                )

        grid = "".join([
            f"<line x1='{left}' y1='{top + chart_h * i / 4:.2f}' x2='{left + chart_w}' y2='{top + chart_h * i / 4:.2f}' "
            f"stroke='#f3f4f6' stroke-width='1'/>"
            for i in range(5)
        ])

        if chart_type == "bar":
            bars = []
            for idx, (_, val) in enumerate(ordered):
                x = left + idx * (chart_w / max(1, len(ordered)))
                bw = max(18.0, chart_w / max(1, len(ordered)) - 8.0)
                h = chart_h * (_safe_float(val, 0.0) - v_min) / (v_max - v_min)
                y = top + chart_h - h
                bars.append(f"<rect x='{x:.2f}' y='{y:.2f}' width='{bw:.2f}' height='{h:.2f}' "
                           f"fill='#3b82f6' opacity='0.85' rx='3'/>")
            plot_part = "".join(bars)
        else:
            polyline = (
                "<polyline fill='none' stroke='#3b82f6' stroke-width='2.5' points='"
                + " ".join(f"{x:.2f},{y:.2f}" for x, y in points) + "'/>"
            )
            circles = "".join([f"<circle cx='{x:.2f}' cy='{y:.2f}' r='3.6' fill='#3b82f6'/>" for x, y in points])
            plot_part = polyline + circles

        badge = ""
        if warning_level:
            color = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}.get(warning_level, "#10b981")
            badge = (
                f"<rect x='{width - 184}' y='20' width='160' height='28' rx='6' ry='6' fill='{color}'/>"
                f"<text x='{width - 104}' y='39' font-size='12' fill='#ffffff' text-anchor='middle'>"
                f"学情预警等级：{warning_level}</text>"
            )

        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            f"<text x='20' y='28' font-size='15' font-weight='600' fill='#111827'>{title}</text>"
            f"<line x1='{left}' y1='{top + chart_h}' x2='{left + chart_w}' y2='{top + chart_h}' stroke='#d1d5db'/>"
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + chart_h}' stroke='#d1d5db'/>"
            + grid
            + plot_part
            + "".join(labels)
            + badge
            + "</svg>"
        )

    # ------------------------------------------------------------------
    # 3. 知识点掌握度热力图（按学习周）
    # ------------------------------------------------------------------
    def mastery_heatmap(
        self,
        kp_scores: Dict[str, List[float]],
        title: str = "知识点掌握度热力图",
        week_labels: Optional[List[str]] = None,
    ) -> str:
        """
        Args:
            kp_scores: {知识点名: [W-5, W-4, W-3, W-2, W-1, W0] 掌握度（0-1）}
            week_labels: 自定义周列名
        """
        if not kp_scores:
            kp_scores = {
                "知识点 A": [0.3, 0.4, 0.5, 0.55, 0.6, 0.65],
                "知识点 B": [0.5, 0.6, 0.65, 0.7, 0.75, 0.8],
            }
        weeks = week_labels or ["W-5", "W-4", "W-3", "W-2", "W-1", "W0"]

        kps = list(kp_scores.keys())[:8]
        width = 760
        cell_w, cell_h = 90, 36
        start_x, start_y = 130, 56
        height = start_y + len(kps) * cell_h + 36

        def _cell_color(v: float) -> str:
            vv = max(0.0, min(1.0, v))
            # 浅蓝→深蓝渐变（掌握度越高色越深）
            r = int(241 - 121 * vv)
            g = int(245 - 100 * vv)
            b = int(255 - 60 * vv)
            return f"rgb({r},{g},{b})"

        cells = []
        for i, kp in enumerate(kps):
            scores = (kp_scores[kp] + [0.0] * len(weeks))[:len(weeks)]
            for j, score in enumerate(scores):
                x = start_x + j * cell_w
                y = start_y + i * cell_h
                cells.append(
                    f"<rect x='{x}' y='{y}' width='{cell_w - 2}' height='{cell_h - 2}' "
                    f"fill='{_cell_color(score)}' stroke='#e5e7eb'/>"
                )
                # 数值标注（仅显示边界值）
                if j == 0 or j == len(weeks) - 1:
                    cells.append(
                        f"<text x='{x + (cell_w - 2) / 2:.2f}' y='{y + cell_h / 2 + 4:.2f}' "
                        f"font-size='11' fill='#1f2937' text-anchor='middle'>{score:.2f}</text>"
                    )

        row_labels = "".join([
            f"<text x='120' y='{start_y + i * cell_h + 22}' font-size='12' fill='#1f2937' text-anchor='end'>"
            f"{_compact_label(name, 16)}</text>"
            for i, name in enumerate(kps)
        ])
        col_labels = "".join([
            f"<text x='{start_x + j * cell_w + (cell_w - 2) / 2:.2f}' y='44' "
            f"font-size='12' fill='#1f2937' text-anchor='middle'>{w}</text>"
            for j, w in enumerate(weeks)
        ])

        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            f"<text x='20' y='28' font-size='15' font-weight='600' fill='#111827'>{title}</text>"
            + "".join(cells)
            + row_labels
            + col_labels
            + "</svg>"
        )

    # ------------------------------------------------------------------
    # 4. Bloom 6 层级分布柱状图
    # ------------------------------------------------------------------
    def bloom_distribution(
        self,
        bloom_counts: Dict[str, int],
        title: str = "认知层级分布（Bloom 分类法）",
    ) -> str:
        """
        Args:
            bloom_counts: {"remember": 5, "understand": 8, ...}（资源 / 题目数）
        """
        order = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
        label_cn = {
            "remember": "记忆",
            "understand": "理解",
            "apply": "应用",
            "analyze": "分析",
            "evaluate": "评价",
            "create": "创造",
        }
        colors = {
            "remember": "#94a3b8",
            "understand": "#60a5fa",
            "apply": "#34d399",
            "analyze": "#fbbf24",
            "evaluate": "#fb923c",
            "create": "#f87171",
        }

        vals = [(k, int(bloom_counts.get(k, 0))) for k in order]
        v_max = max([v for _, v in vals] + [1])

        width, height = 540, 300
        left, top = 64, 44
        chart_h = 190
        bar_w = 56
        gap = 18

        rects = []
        labels = []
        for idx, (key, val) in enumerate(vals):
            x = left + idx * (bar_w + gap)
            h = chart_h * (val / v_max) if v_max else 0
            y = top + (chart_h - h)
            rects.append(
                f"<rect x='{x}' y='{y:.2f}' width='{bar_w}' height='{h:.2f}' "
                f"fill='{colors[key]}' rx='4' ry='4'/>"
            )
            labels.append(
                f"<text x='{x + bar_w / 2:.2f}' y='{top + chart_h + 22}' font-size='12' "
                f"fill='#1f2937' text-anchor='middle'>{label_cn[key]}</text>"
            )
            labels.append(
                f"<text x='{x + bar_w / 2:.2f}' y='{y - 6:.2f}' font-size='12' "
                f"fill='#1f2937' text-anchor='middle'>{val}</text>"
            )

        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect x='0' y='0' width='100%' height='100%' fill='#ffffff'/>"
            f"<text x='20' y='28' font-size='15' font-weight='600' fill='#111827'>{title}</text>"
            f"<line x1='{left - 8}' y1='{top + chart_h}' x2='{width - 24}' y2='{top + chart_h}' stroke='#d1d5db'/>"
            + "".join(rects)
            + "".join(labels)
            + "</svg>"
        )

    # ------------------------------------------------------------------
    # 5. BKT 学习时光机预测图（Day 9 新增）
    # ------------------------------------------------------------------
    def mastery_forecast_svg(
        self,
        forecast: list[dict],
        milestones: list[dict] | None = None,
        history: list[dict] | None = None,
        title: str = "学习时光机 · 30 天掌握度预测",
    ) -> str:
        """实线=历史，虚线=预测，阴影=90% CI，里程碑标注"""
        width, height = 800, 380
        left, right, top, bottom = 60, 30, 40, 70
        chart_w = width - left - right
        chart_h = height - top - bottom

        all_points = (history or []) + forecast
        if not all_points:
            return self._empty_svg(width, height, title)

        days = [p["day"] for p in all_points]
        ps = [p.get("p_learned", p.get("mastery", 0.5)) for p in all_points]
        day_min, day_max = min(days), max(days)
        if day_min == day_max:
            day_max += 1

        def _x(d):
            return left + chart_w * (d - day_min) / max(1, day_max - day_min)
        def _y(p_val):
            return top + chart_h * (1 - p_val)

        # Grid
        lines = []
        for v in [0.2, 0.4, 0.6, 0.8, 1.0]:
            y = _y(v)
            lines.append(
                f"<line x1='{left}' y1='{y:.1f}' x2='{left + chart_w}' y2='{y:.1f}' "
                f"stroke='#f1f5f9' stroke-width='1'/>"
            )
            lines.append(
                f"<text x='{left - 6}' y='{y + 4:.1f}' font-size='11' fill='#94a3b8' "
                f"text-anchor='end'>{int(v * 100)}%</text>"
            )

        # History polyline (solid blue)
        history_poly = ""
        if history and len(history) >= 2:
            pts = " ".join(
                f"{_x(p['day']):.1f},{_y(p.get('p_learned', p.get('mastery', 0.5))):.1f}"
                for p in history
            )
            history_poly = (
                f"<polyline fill='none' stroke='#3b82f6' stroke-width='2.5' points='{pts}'/>"
            )

        # Forecast polyline (dashed purple)
        forecast_pts = " ".join(
            f"{_x(p['day']):.1f},{_y(p.get('p_learned', 0.5)):.1f}"
            for p in forecast
        )
        forecast_poly = (
            f"<polyline fill='none' stroke='#8b5cf6' stroke-width='2.5' "
            f"stroke-dasharray='6,4' points='{forecast_pts}'/>"
        )

        # CI polygon (purple translucent)
        ci_parts = []
        for p in forecast:
            if "ci_low" in p and "ci_high" in p:
                x = _x(p["day"])
                ci_parts.append((x, _y(p["ci_high"]), _y(p["ci_low"])))
        ci_polygon = ""
        if ci_parts:
            upper = " ".join(f"{x:.1f},{yh:.1f}" for x, yh, _ in ci_parts)
            lower = " ".join(f"{x:.1f},{yl:.1f}" for x, _, yl in reversed(ci_parts))
            ci_polygon = (
                f"<polygon points='{upper} {lower}' fill='#8b5cf6' fill-opacity='0.15'/>"
            )

        # Milestones
        m_marks = []
        for m in (milestones or []):
            x = _x(m["day"])
            y = _y(m["p_at_day"])
            m_marks.extend([
                f"<line x1='{x:.1f}' y1='{y:.1f}' x2='{x:.1f}' y2='{top + chart_h}' "
                f"stroke='#f59e0b' stroke-dasharray='3,3'/>",
                f"<circle cx='{x:.1f}' cy='{y:.1f}' r='6' fill='#f59e0b'/>",
                f"<text x='{x:.1f}' y='{y - 12:.1f}' font-size='12' fill='#f59e0b' "
                f"text-anchor='middle' font-weight='bold'>{m['label']}</text>",
                f"<text x='{x:.1f}' y='{top + chart_h + 18:.1f}' font-size='11' "
                f"fill='#92400e' text-anchor='middle'>第 {m['day']} 天</text>",
            ])

        # Current marker
        current = ""
        if history:
            last_h = history[-1]
            cx = _x(last_h["day"])
            cy = _y(last_h.get("p_learned", last_h.get("mastery", 0.5)))
            current = (
                f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='8' fill='#3b82f6' "
                f"stroke='white' stroke-width='3'/>"
                f"<text x='{cx + 14:.1f}' y='{cy + 4:.1f}' font-size='12' "
                f"fill='#1e293b' font-weight='bold'>当前</text>"
            )

        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
            f"viewBox='0 0 {width} {height}'>"
            "<rect width='100%' height='100%' fill='#ffffff'/>"
            f"<text x='20' y='28' font-size='15' font-weight='600' fill='#111827'>{title}</text>"
            + "".join(lines)
            + ci_polygon
            + history_poly
            + forecast_poly
            + "".join(m_marks)
            + current
            + f"<line x1='{left}' y1='{top + chart_h}' x2='{left + chart_w}' "
            f"y2='{top + chart_h}' stroke='#cbd5e1'/>"
            + f"<text x='{width // 2}' y='{height - 8}' font-size='11' fill='#64748b' "
            f"text-anchor='middle'>实线=历史观测 · 虚线=BKT 预测 · 阴影=90% 置信区间</text>"
            "</svg>"
        )

    @staticmethod
    def _empty_svg(w: int, h: int, title: str = "") -> str:
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
            f"viewBox='0 0 {w} {h}'>"
            "<rect width='100%' height='100%' fill='#ffffff'/>"
            f"<text x='20' y='28' font-size='15' font-weight='600' fill='#111827'>{title}</text>"
            f"<text x='{w // 2}' y='{h // 2}' font-size='14' fill='#94a3b8' "
            f"text-anchor='middle'>暂无数据</text></svg>"
        )

    # ------------------------------------------------------------------
    # 工具：SVG → data URI（前端 img src 直接用）
    # ------------------------------------------------------------------
    @staticmethod
    def to_data_uri(svg_text: str) -> str:
        raw = svg_text.encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    # ------------------------------------------------------------------
    # 批量产出（评估页 / 报告导出共用）
    # ------------------------------------------------------------------
    def build_assessment_assets(
        self,
        profile_radar_data: Dict[str, Any],
        mastery_timeline: Dict[str, float],
        kp_heatmap: Dict[str, List[float]],
        bloom_counts: Dict[str, int],
        warning_level: Optional[str] = None,
    ) -> Dict[str, str]:
        """一次性产出 4 张图，返回 data:image/svg+xml;base64,... URI 串"""
        radar_svg = self.profile_radar(profile_radar_data)
        trend_svg = self.mastery_trend(mastery_timeline, warning_level=warning_level)
        heatmap_svg = self.mastery_heatmap(kp_heatmap)
        bloom_svg = self.bloom_distribution(bloom_counts)
        return {
            "profile_radar_svg": self.to_data_uri(radar_svg),
            "mastery_trend_svg": self.to_data_uri(trend_svg),
            "mastery_heatmap_svg": self.to_data_uri(heatmap_svg),
            "bloom_distribution_svg": self.to_data_uri(bloom_svg),
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------
_visualizer: Optional[SVGVisualizer] = None


def get_svg_visualizer() -> SVGVisualizer:
    global _visualizer
    if _visualizer is None:
        _visualizer = SVGVisualizer()
    return _visualizer
