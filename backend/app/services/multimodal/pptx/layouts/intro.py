"""
开场幻灯片 layouts: Cover + Agenda

教学心理学:
- Cover: Vygotsky ZPD 营造学习动机
- Agenda: Ausubel Advance Organizer - 在学习前提供框架
"""
from __future__ import annotations

from backend.app.services.multimodal.pptx.layouts._helpers import (
    LayoutRenderer,
    RenderContext,
    add_panel,
    add_rule,
    add_textbox,
    attach_notes,
    blend_hex,
    set_solid_bg,
)
from backend.app.services.multimodal.pptx.notes import generate_notes
from backend.app.services.multimodal.pptx.spec import (
    AgendaSlide,
    CoverSlide,
    SlideRenderResult,
)


class CoverLayout(LayoutRenderer):
    """1. 封面 - 课程开篇 + 讲者信息"""
    name = "cover"

    def render(
        self, idx: int, slide_spec: CoverSlide, ctx: RenderContext,
    ) -> SlideRenderResult:
        s = self.new_slide(ctx)
        soft = blend_hex(ctx.theme.primary, ctx.theme.bg, 0.08)
        set_solid_bg(s, soft)
        add_panel(
            s, 0.03, 0.03, 8.52, 7.42,
            fill=ctx.theme.primary, line=ctx.theme.primary, rounded=False,
        )
        add_rule(s, 0.95, 1.25, 0.9, color=ctx.theme.secondary, height=0.08)

        add_textbox(
            s, 0.95, 1.55, 6.75, 1.8, slide_spec.title,
            color=ctx.theme.bg, size_pt=50, bold=True,
            font=ctx.theme.font_title,
        )
        if slide_spec.subtitle:
            add_textbox(
                s, 0.95, 3.55, 6.65, 0.95, slide_spec.subtitle,
                color=ctx.theme.bg, size_pt=24,
                font=ctx.theme.font_body,
            )
        meta_text = f"{slide_spec.chapter}  ·  {slide_spec.author}".strip(" ·")
        add_textbox(
            s, 0.95, 6.55, 6.7, 0.4, meta_text,
            color=blend_hex(ctx.theme.bg, ctx.theme.primary, 0.78), size_pt=13,
            font=ctx.theme.font_body,
        )

        for i, (label, detail) in enumerate([
            ("01", "建立框架"),
            ("02", "推演原理"),
            ("03", "迁移实战"),
        ]):
            y = 1.35 + i * 1.55
            add_panel(
                s, 9.05, y, 3.65, 1.15,
                fill=ctx.theme.bg,
                line=blend_hex(ctx.theme.primary, ctx.theme.bg, 0.18),
            )
            add_textbox(
                s, 9.3, y + 0.18, 0.65, 0.65, label,
                color=ctx.theme.secondary, size_pt=20, bold=True,
                font=ctx.theme.font_title,
            )
            add_textbox(
                s, 10.05, y + 0.2, 2.3, 0.6, detail,
                color=ctx.theme.text, size_pt=17, bold=True,
                font=ctx.theme.font_body,
            )

        if ctx.enable_notes:
            attach_notes(s, generate_notes(slide_spec))
        # Cover 不带 QR (保持封面简洁)
        return SlideRenderResult(
            slide_index=idx, layout=self.name,
            title=slide_spec.title, rendered=True,
        )


class AgendaLayout(LayoutRenderer):
    """2. 目录 - 提供学习路径预告"""
    name = "agenda"

    MAX_ITEMS = 12

    def render(
        self, idx: int, slide_spec: AgendaSlide, ctx: RenderContext,
    ) -> SlideRenderResult:
        s = self.new_slide(ctx)
        add_textbox(
            s, 1.0, 0.6, 11.3, 0.8, slide_spec.title or "目录",
            color=ctx.theme.primary, size_pt=ctx.theme.title_size_pt,
            bold=True, font=ctx.theme.font_title,
        )
        soft = blend_hex(ctx.theme.primary, ctx.theme.bg, 0.08)
        for i, item in enumerate(slide_spec.items[:self.MAX_ITEMS], 1):
            col = (i - 1) % 2
            row = (i - 1) // 2
            x = 0.9 + col * 6.05
            y = 1.65 + row * 0.88
            add_panel(
                s, x, y, 5.55, 0.68,
                fill=soft, line=blend_hex(ctx.theme.primary, ctx.theme.bg, 0.16),
            )
            add_textbox(
                s, x + 0.2, y + 0.06, 0.55, 0.5, f"{i:02d}",
                color=ctx.theme.secondary, size_pt=15, bold=True,
                font=ctx.theme.font_title,
            )
            add_textbox(
                s, x + 0.85, y + 0.06, 4.4, 0.5, item,
                color=ctx.theme.text, size_pt=16, bold=True,
                font=ctx.theme.font_body,
            )
        return self.finalize(idx, slide_spec, ctx, s)
