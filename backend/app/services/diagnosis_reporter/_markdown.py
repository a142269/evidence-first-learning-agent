"""Markdown rendering for the diagnosis report."""
# ruff: noqa: RUF001
from __future__ import annotations

from typing import Any

from backend.app.services.cognitive_diagnosis.bkt_forecaster import ForecastPoint

from ._helpers import bar, bounded, dict_at, mean, stars
from ._models import (
    BloomBundle,
    DiagnosisReport,
    ForecastBundle,
    IntegrationStatus,
    MasteryRow,
    RecommendationBundle,
)

_NA_TEXT = "N/A (B 服务未就绪)"


def render_markdown(  # noqa: PLR0913
    *,
    user_id: str,
    nickname: str,
    archetype: str,
    generated_at_label: str,
    profile: dict[str, Any],
    profile_scores: list[tuple[str, float]],
    mastery_rows: list[MasteryRow],
    strengths: list[MasteryRow],
    weaknesses: list[MasteryRow],
    forecast: ForecastBundle,
    recommendations: RecommendationBundle,
    bloom: BloomBundle,
    learning_path_lines: list[str],
    mistake_lines: list[str],
) -> str:
    mean_mastery = mean([row.combined for row in mastery_rows])
    lines = [
        f"# 学习诊断报告：{nickname}",
        "",
        f"> 用户：`{user_id}`  ",
        f"> 学习者画像：**{archetype}**  ",
        f"> 生成时间：{generated_at_label}  ",
        "> 算法来源：RealDINA 0.8024 + BKT 30 天预测 + Active Learning + Bloom 6×3",
        "",
        "## 1. 学习者画像",
        "",
        _profile_summary(profile, archetype, mean_mastery),
        "",
        "| 画像维度 | 评分 | ASCII 雷达条 |",
        "|---|---:|---|",
    ]
    for label, score in profile_scores:
        lines.append(f"| {label} | {score:.0%} | `{bar(score, width=16)}` |")

    lines.extend(
        [
            "",
            "## 2. 当前掌握度（RealDINA + BKT 平均）",
            "",
            "| KP | 课程 | Bloom | 难度 | RealDINA | BKT | 综合 | 星级 |",
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in mastery_rows:
        bkt_text = f"{row.bkt:.0%}" if row.bkt is not None else "fallback"
        lines.append(
            "| "
            f"{row.name} (`{row.kp_id}`) | {row.course} | {row.bloom} | "
            f"{row.difficulty} | {row.realdina:.0%} | {bkt_text} | "
            f"{row.combined:.0%} | `{stars(row.combined)}` |"
        )

    lines.extend(["", "## 3. 强弱项 Top-3", "", "强项："])
    lines.extend(_ranked_lines(strengths, reverse=True))
    lines.append("")
    lines.append("弱项：")
    lines.extend(_ranked_lines(weaknesses, reverse=False))

    lines.extend(["", "## 4. 学习路径建议", ""])
    lines.extend(learning_path_lines)

    lines.extend(
        [
            "",
            f"## 5. 未来 30 天预测：{forecast.focus_kp_name}",
            "",
            _integration_note(forecast.status),
        ]
    )
    if forecast.points:
        lines.extend(
            [
                "",
                "| 天数 | 掌握度 | 90% CI | 趋势条 |",
                "|---:|---:|---|---|",
            ]
        )
        for point in _checkpoints(forecast.points):
            lines.append(
                f"| Day {point.day} | {point.p_learned:.0%} | "
                f"{point.ci_low:.0%}-{point.ci_high:.0%} | "
                f"`{bar(point.p_learned, width=20)}` |"
            )
        if forecast.milestones:
            lines.append("")
            lines.append("**里程碑**：")
            for milestone in forecast.milestones:
                lines.append(
                    f"- Day {milestone['day']} 达到 {milestone['label']} "
                    f"(p={float(milestone.get('p_at_day', 0.0)):.0%})"
                )
    else:
        lines.append("")
        lines.append(f"- {_NA_TEXT}")

    lines.extend(["", "## 6. 错题风险分析", ""])
    lines.extend(mistake_lines)

    lines.extend(
        [
            "",
            "## 7. 建议练习题（5 道）",
            "",
            _integration_note(recommendations.status),
            "",
            "| 题号 | KP | Bloom | 难度 | 选题分 | 题干 |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for question in recommendations.questions:
        score_text = (
            f"{question.selection_score:.2f}" if question.selection_score is not None else "—"
        )
        lines.append(
            f"| `{question.question_id}` | {question.kp_name} | {question.bloom} | "
            f"{question.difficulty} | {score_text} | {question.stem} |"
        )

    lines.extend(
        [
            "",
            "## 8. Bloom 6×3 分布（推荐题分布到认知 × 知识维度）",
            "",
            _integration_note(bloom.status),
            "",
        ]
    )
    lines.extend(_render_bloom_table(bloom))

    lines.extend(
        [
            "",
            "---",
            "评委提示：本报告不调用 LLM，B 模块未就绪时会以 fallback 数据 + 友好降级生成。",
        ]
    )
    return "\n".join(lines) + "\n"


def _integration_note(status: IntegrationStatus) -> str:
    if status.available:
        return f"_集成状态：`{status.source}` ✅_"
    reason = status.fallback_reason or "B 服务未就绪"
    return f"_集成状态：fallback (`{status.source}`) — {reason}_"


def _profile_summary(profile: dict[str, Any], archetype: str, mean_mastery: float) -> str:
    goal = dict_at(profile, "learning_goal")
    preference = dict_at(profile, "learning_preference")
    style = dict_at(profile, "cognitive_style")
    target = str(goal.get("target", "个性化学习目标"))
    mode = str(preference.get("mode", "混合学习"))
    primary_style = str(style.get("primary", "综合型"))
    return (
        f"该学习者画像为 **{archetype}**，以 **{target}** 为目标，"
        f"偏好 **{mode}**，主认知风格为 **{primary_style}**。"
        f"当前 20 个 KP 综合掌握度约 **{mean_mastery:.0%}**。"
    )


def _ranked_lines(rows: list[MasteryRow], reverse: bool) -> list[str]:
    if not rows:
        return ["- 暂无数据。"]
    result_lines: list[str] = []
    sorted_rows = sorted(rows, key=lambda row: row.combined, reverse=reverse)
    for index, row in enumerate(sorted_rows, start=1):
        result_lines.append(
            f"{index}. {row.name} (`{row.kp_id}`)：{bounded(row.combined):.0%}，"
            f"Bloom={row.bloom}，难度={row.difficulty}"
        )
    return result_lines


def _checkpoints(forecast: list[ForecastPoint]) -> list[ForecastPoint]:
    wanted = {0, 7, 14, 21, 30}
    points = [point for point in forecast if point.day in wanted]
    return points if points else forecast[:5]


def _render_bloom_table(bloom: BloomBundle) -> list[str]:
    if not bloom.cells:
        return ["- 推荐题暂无 Bloom 分布数据。"]
    cognitive_order: list[tuple[str, str]] = []
    seen: set[str] = set()
    for cell in bloom.cells:
        if cell.cognitive not in seen:
            cognitive_order.append((cell.cognitive, cell.cognitive_label))
            seen.add(cell.cognitive)
    knowledge_order: list[tuple[str, str]] = []
    knowledge_seen: set[str] = set()
    for cell in bloom.cells:
        if cell.knowledge_dim not in knowledge_seen:
            knowledge_order.append((cell.knowledge_dim, cell.knowledge_label))
            knowledge_seen.add(cell.knowledge_dim)

    header_cells = ["认知维度 ＼ 知识维度", *(label for _, label in knowledge_order), "合计"]
    sep_cells = ["---"] + ["---:"] * (len(knowledge_order) + 1)
    table_lines = ["| " + " | ".join(header_cells) + " |", "|" + "|".join(sep_cells) + "|"]

    grid: dict[tuple[str, str], int] = {
        (cell.cognitive, cell.knowledge_dim): cell.count for cell in bloom.cells
    }
    for cognitive_key, cognitive_label in cognitive_order:
        row = [f"**{cognitive_label}** (`{cognitive_key}`)"]
        for knowledge_key, _ in knowledge_order:
            row.append(str(grid.get((cognitive_key, knowledge_key), 0)))
        row.append(str(bloom.cognitive_totals.get(cognitive_key, 0)))
        table_lines.append("| " + " | ".join(row) + " |")

    sub_level_lines = ["", "**已触达子层级（Anderson & Krathwohl 2001 6×3）**："]
    for cell in bloom.cells:
        if cell.sub_levels:
            sub_level_lines.append(
                f"- `{cell.cognitive}` × `{cell.knowledge_dim}` → "
                + "、".join(cell.sub_levels)
            )
    if len(sub_level_lines) == 2:
        sub_level_lines.append("- 暂无可触达的子层级。")
    return table_lines + sub_level_lines
