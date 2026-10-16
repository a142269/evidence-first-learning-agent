"""
练习类幻灯片 layouts: Code / Checkpoint

教学心理学:
- Code:       Chi et al. (1989) Self-Explanation Effect (注解促进自解释)
- Checkpoint: Roediger & Karpicke (2006) Testing Effect (主动检索)
"""
from __future__ import annotations

from backend.app.services.multimodal.pptx.layouts._helpers import (
    LayoutRenderer,
    RenderContext,
    add_panel,
    add_textbox,
    blend_hex,
)
from backend.app.services.multimodal.pptx.spec import (
    CheckpointSlide,
    CodeSlide,
    SlideRenderResult,
)


class CodeLayout(LayoutRenderer):
    """6. 代码 (Chi Self-Explanation)"""
    name = "code"

    MAX_LINES = 18

    def render(
        self, idx: int, slide_spec: CodeSlide, ctx: RenderContext,
    ) -> SlideRenderResult:
        s = self.new_slide(ctx)
        add_textbox(
            s, 0.8, 0.4, 11.5, 0.8,
            f"{slide_spec.title}  [{slide_spec.language}]",
            color=ctx.theme.primary, size_pt=ctx.theme.title_size_pt,
            bold=True, font=ctx.theme.font_title,
        )
        # 代码块 (等宽字体 + 行号)
        lines = slide_spec.code.splitlines()[:self.MAX_LINES]
        add_panel(
            s, 0.75, 1.28, 11.85, 5.55,
            fill="#0F172A", line="#1E293B",
        )
        for i, color in enumerate(("#EF4444", "#F59E0B", "#22C55E")):
            add_panel(
                s, 1.02 + i * 0.25, 1.5, 0.12, 0.12,
                fill=color, line=color,
            )
        y = 1.82
        code_bottom = 6.18 if slide_spec.annotations else 6.55
        line_height = min(0.32, max(0.23, (code_bottom - y) / max(1, len(lines))))
        for i, line in enumerate(lines, 1):
            text = f"{i:>2}  {line}"
            add_textbox(
                s, 1.02, y, 11.15, line_height, text,
                color="#E2E8F0", size_pt=ctx.theme.code_size_pt,
                font=ctx.theme.font_code,
            )
            y += line_height
        if slide_spec.annotations:
            text = "  ·  ".join(slide_spec.annotations[:3])
            add_textbox(
                s, 1.02, 6.35, 11.1, 0.3, text,
                color="#94A3B8", size_pt=11,
                font=ctx.theme.font_body,
            )
        return self.finalize(idx, slide_spec, ctx, s)


class CheckpointLayout(LayoutRenderer):
    """7. 理解检查 (Roediger Testing Effect)"""
    name = "checkpoint"

    LABELS = ["A", "B", "C", "D", "E"]

    def render(
        self, idx: int, slide_spec: CheckpointSlide, ctx: RenderContext,
    ) -> SlideRenderResult:
        s = self.new_slide(ctx)
        heading = (
            slide_spec.title
            if any(token in slide_spec.title for token in ("检查", "自检", "测验"))
            else f"理解检查: {slide_spec.title}"
        )
        add_textbox(
            s, 0.8, 0.4, 11.5, 0.8,
            heading,
            color=ctx.theme.primary, size_pt=ctx.theme.title_size_pt,
            bold=True, font=ctx.theme.font_title,
        )
        add_panel(
            s, 0.8, 1.38, 11.5, 1.05,
            fill=blend_hex(ctx.theme.primary, ctx.theme.bg, 0.07),
            line=blend_hex(ctx.theme.primary, ctx.theme.bg, 0.2),
        )
        add_textbox(
            s, 1.05, 1.52, 11.0, 0.72,
            slide_spec.question,
            color=ctx.theme.text, size_pt=20,
            font=ctx.theme.font_body,
        )
        y = 3.0
        for i, opt in enumerate(slide_spec.options[:5]):
            add_panel(
                s, 1.15, y, 10.55, 0.52,
                fill=blend_hex(ctx.theme.secondary, ctx.theme.bg, 0.055),
                line=blend_hex(ctx.theme.secondary, ctx.theme.bg, 0.15),
            )
            add_textbox(
                s, 1.4, y + 0.02, 10.0, 0.42,
                f"{self.LABELS[i]}. {opt}",
                color=ctx.theme.text, size_pt=ctx.theme.body_size_pt,
                font=ctx.theme.font_body,
            )
            y += 0.6
        if slide_spec.hint:
            add_textbox(
                s, 0.8, 6.5, 11.5, 0.4,
                f"提示: {slide_spec.hint}",
                color=ctx.theme.subtle, size_pt=12,
                font=ctx.theme.font_body,
            )
        return self.finalize(idx, slide_spec, ctx, s)
