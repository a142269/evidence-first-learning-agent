"""
讲解类幻灯片 layouts: Concept / Comparison / WorkedExample

教学心理学:
- Concept:       Mayer Contiguity Principle (文字与配图相邻)
- Comparison:    Mayer Multimedia Principle (同步对比促差异辨识)
- WorkedExample: Sweller Worked Example Effect (1988)
"""
from __future__ import annotations

from backend.app.services.multimodal.pptx.layouts._helpers import (
    LayoutRenderer,
    RenderContext,
    add_connector,
    add_oval,
    add_panel,
    add_textbox,
    blend_hex,
    draw_asset,
)
from backend.app.services.multimodal.pptx.spec import (
    ComparisonSlide,
    ConceptSlide,
    SlideRenderResult,
    WorkedExampleSlide,
)


class ConceptLayout(LayoutRenderer):
    """3. 概念定义 (Mayer Contiguity)"""
    name = "concept"

    def render(
        self, idx: int, slide_spec: ConceptSlide, ctx: RenderContext,
    ) -> SlideRenderResult:
        s = self.new_slide(ctx)
        add_textbox(
            s, 0.8, 0.4, 11.5, 0.8, slide_spec.title,
            color=ctx.theme.primary, size_pt=ctx.theme.title_size_pt,
            bold=True, font=ctx.theme.font_title,
        )
        definition_fill = blend_hex(ctx.theme.primary, ctx.theme.bg, 0.08)
        add_panel(
            s, 0.8, 1.28, 11.5, 0.92,
            fill=definition_fill,
            line=blend_hex(ctx.theme.primary, ctx.theme.bg, 0.2),
        )
        add_textbox(
            s, 1.05, 1.42, 11.0, 0.58, slide_spec.definition,
            color=ctx.theme.text, size_pt=19, bold=True,
            font=ctx.theme.font_body,
        )

        has_asset = bool(slide_spec.asset)
        if has_asset:
            y = 2.5
            for i, b in enumerate(slide_spec.bullets[:6], 1):
                add_textbox(
                    s, 0.8, y, 5.95, 0.68, f"{i:02d}  {b}",
                    color=ctx.theme.text, size_pt=16,
                    font=ctx.theme.font_body,
                )
                y += 0.72
        else:
            # 旧版把长要点塞进 0.5 英寸文本框，再用四个椭圆截断中文，
            # 最终会出现“多 / 元 / 函”这类不可读的伪导图。改成可读的
            # “关键关系”面板：保留顺序和重点，但不制造没有语义的节点图。
            for i, b in enumerate(slide_spec.bullets[:5], 1):
                y = 2.5 + (i - 1) * 0.72
                add_textbox(
                    s, 0.88, y, 6.05, 0.64, f"{i:02d}  {b}",
                    color=ctx.theme.text, size_pt=16,
                    font=ctx.theme.font_body,
                )
            add_panel(
                s, 7.2, 2.48, 5.1, 3.95,
                fill=blend_hex(ctx.theme.secondary, ctx.theme.bg, 0.07),
                line=blend_hex(ctx.theme.secondary, ctx.theme.bg, 0.2),
            )
            add_textbox(
                s, 7.5, 2.72, 4.45, 0.45,
                "关键关系",
                color=ctx.theme.primary, size_pt=22, bold=True,
                font=ctx.theme.font_title,
            )
            for i, b in enumerate(slide_spec.bullets[:4], 1):
                add_textbox(
                    s, 7.5, 3.25 + (i - 1) * 0.72, 4.4, 0.64,
                    f"{i}. {b}",
                    color=ctx.theme.text, size_pt=15,
                    font=ctx.theme.font_body,
                )

        method = ""
        if has_asset and slide_spec.asset:
            method = draw_asset(
                ctx, s, slide_spec.asset,
                left=7.2, top=2.5, width=5.3, height=4.0,
            )
            if slide_spec.asset.caption:
                add_textbox(
                    s, 7.2, 6.5, 5.3, 0.4,
                    slide_spec.asset.caption,
                    color=ctx.theme.subtle, size_pt=12,
                    font=ctx.theme.font_body, align="center",
                )
        return self.finalize(idx, slide_spec, ctx, s, asset_method=method)


class ComparisonLayout(LayoutRenderer):
    """4. 左右对比 (Mayer Multimedia)"""
    name = "comparison"

    def render(
        self, idx: int, slide_spec: ComparisonSlide, ctx: RenderContext,
    ) -> SlideRenderResult:
        s = self.new_slide(ctx)
        add_textbox(
            s, 0.8, 0.4, 11.5, 0.8, slide_spec.title,
            color=ctx.theme.primary, size_pt=ctx.theme.title_size_pt,
            bold=True, font=ctx.theme.font_title,
        )
        add_panel(
            s, 0.75, 1.35, 5.82, 4.75,
            fill=blend_hex(ctx.theme.secondary, ctx.theme.bg, 0.07),
            line=blend_hex(ctx.theme.secondary, ctx.theme.bg, 0.2),
        )
        add_panel(
            s, 6.75, 1.35, 5.82, 4.75,
            fill=blend_hex(ctx.theme.accent, ctx.theme.bg, 0.06),
            line=blend_hex(ctx.theme.accent, ctx.theme.bg, 0.18),
        )
        self._draw_column(
            s, ctx, x=0.8, title=slide_spec.left_title,
            color=ctx.theme.secondary, points=slide_spec.left_points,
        )
        self._draw_column(
            s, ctx, x=6.8, title=slide_spec.right_title,
            color=ctx.theme.accent, points=slide_spec.right_points,
        )
        if slide_spec.verdict:
            add_textbox(
                s, 0.8, 6.4, 11.5, 0.5,
                f"结论: {slide_spec.verdict}",
                color=ctx.theme.primary, size_pt=16, bold=True,
                font=ctx.theme.font_body, align="center",
            )
        return self.finalize(idx, slide_spec, ctx, s)

    def _draw_column(
        self, s, ctx: RenderContext, x: float, title: str,
        color: str, points: list,
    ) -> None:
        add_textbox(
            s, x + 0.2, 1.55, 5.35, 0.6, title,
            color=color, size_pt=ctx.theme.h2_size_pt,
            bold=True, font=ctx.theme.font_title,
        )
        y = 2.35
        for i, p in enumerate(points[:4], 1):
            add_textbox(
                s, x + 0.2, y, 5.25, 0.72, f"{i:02d}  {p}",
                color=ctx.theme.text, size_pt=15,
                font=ctx.theme.font_body,
            )
            y += 0.86


class WorkedExampleLayout(LayoutRenderer):
    """5. 范例 (Sweller Worked Example Effect)"""
    name = "worked_example"

    def render(
        self, idx: int, slide_spec: WorkedExampleSlide, ctx: RenderContext,
    ) -> SlideRenderResult:
        s = self.new_slide(ctx)
        add_textbox(
            s, 0.8, 0.4, 11.5, 0.8, slide_spec.title,
            color=ctx.theme.primary, size_pt=ctx.theme.title_size_pt,
            bold=True, font=ctx.theme.font_title,
        )
        add_panel(
            s, 0.8, 1.27, 11.5, 0.72,
            fill=blend_hex(ctx.theme.accent, ctx.theme.bg, 0.08),
            line=blend_hex(ctx.theme.accent, ctx.theme.bg, 0.2),
        )
        add_textbox(
            s, 1.05, 1.38, 11.0, 0.45,
            f"问题: {slide_spec.problem}",
            color=ctx.theme.accent, size_pt=18, bold=True,
            font=ctx.theme.font_body,
        )
        y = 2.25
        steps = list(slide_spec.solution_steps[:5])
        for i, step in enumerate(steps, 1):
            if i < len(steps):
                add_connector(
                    s, 1.24, y + 0.48, 1.24, y + 0.98,
                    color=blend_hex(ctx.theme.primary, ctx.theme.bg, 0.5),
                    width_pt=2.0,
                )
            add_oval(
                s, 0.98, y, 0.52, 0.52,
                fill=ctx.theme.primary if i % 2 else ctx.theme.secondary,
                line=ctx.theme.primary if i % 2 else ctx.theme.secondary,
            )
            add_textbox(
                s, 0.98, y + 0.09, 0.52, 0.32, f"{i:02d}",
                color=ctx.theme.bg, size_pt=11, bold=True,
                font=ctx.theme.font_title, align="center",
            )
            add_textbox(
                s, 1.78, y - 0.01, 10.4, 0.7, step,
                color=ctx.theme.text, size_pt=15,
                font=ctx.theme.font_body,
            )
            y += 0.78
        if slide_spec.reflection:
            add_textbox(
                s, 0.8, 6.3, 11.5, 0.6,
                f"反思: {slide_spec.reflection}",
                color=ctx.theme.secondary, size_pt=14,
                font=ctx.theme.font_body,
            )
        return self.finalize(idx, slide_spec, ctx, s)
