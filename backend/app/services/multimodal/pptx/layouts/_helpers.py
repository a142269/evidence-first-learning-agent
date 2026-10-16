"""
Layout 共享: RenderContext + textbox 辅助 + Asset 嵌入 + QR + Notes 绑定
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from backend.app.services.multimodal.pptx.assets import (
    EmbedResult,
    MermaidRasterizer,
    SVGRasterizer,
)
from backend.app.services.multimodal.pptx.deeplink import generate_deeplink_qr
from backend.app.services.multimodal.pptx.notes import generate_notes
from backend.app.services.multimodal.pptx.spec import (
    Asset,
    DeckMeta,
    SlideRenderResult,
    SlideSpec,
)
from backend.app.services.multimodal.pptx.theme import Theme, hex_to_rgb


logger = logging.getLogger(__name__)


# python-pptx 延迟导入
try:
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
    _PPTX_AVAILABLE = True
except ImportError:
    _PPTX_AVAILABLE = False


# ================================================================
# 渲染上下文
# ================================================================
@dataclass
class RenderContext:
    """渲染时共享对象"""
    prs: Any
    theme: Theme
    deck_meta: DeckMeta
    svg_rast: SVGRasterizer
    mmd_rast: MermaidRasterizer
    base_url: str = "https://f3.edu.local/chat"
    enable_qr: bool = False
    enable_notes: bool = True
    template_mode: bool = False


# ================================================================
# 颜色 + 文本框
# ================================================================
def _color(hex_str: str):
    r, g, b = hex_to_rgb(hex_str)
    return RGBColor(r, g, b)


def add_textbox(
    slide, left: float, top: float, width: float, height: float,
    text: str, *, color: str, size_pt: int,
    bold: bool = False, font: str = "Microsoft YaHei",
    align: str = "left",
):
    tx = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height),
    )
    tf = tx.text_frame
    tf.word_wrap = True
    # 文字内容来自模型，长度不可完全预知。让 PowerPoint 在保留文本框
    # 边界的前提下自动缩小字号，避免长标题/要点互相覆盖或溢出。
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.margin_left = Inches(0.06)
    tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.03)
    tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = text
    if align == "center":
        p.alignment = PP_ALIGN.CENTER
    elif align == "right":
        p.alignment = PP_ALIGN.RIGHT
    for run in p.runs:
        run.font.size = Pt(size_pt)
        run.font.bold = bold
        run.font.color.rgb = _color(color)
        run.font.name = font
    return tx


def blend_hex(foreground: str, background: str, weight: float = 0.12) -> str:
    """把前景色以 weight 混入背景色，生成稳定的浅色面板。"""
    fr, fg, fb = hex_to_rgb(foreground)
    br, bg, bb = hex_to_rgb(background)
    w = max(0.0, min(1.0, weight))
    return "#{:02X}{:02X}{:02X}".format(
        round(fr * w + br * (1 - w)),
        round(fg * w + bg * (1 - w)),
        round(fb * w + bb * (1 - w)),
    )


def add_panel(
    slide, left: float, top: float, width: float, height: float,
    *, fill: str, line: str | None = None, rounded: bool = True,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        shape_type, Inches(left), Inches(top), Inches(width), Inches(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _color(fill)
    shape.line.color.rgb = _color(line or fill)
    shape.line.width = Pt(0.8)
    return shape


def add_oval(
    slide, left: float, top: float, width: float, height: float,
    *, fill: str, line: str | None = None,
):
    """Add a diagram node; kept separate from card panels for shape-native layouts."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Inches(left), Inches(top), Inches(width), Inches(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _color(fill)
    shape.line.color.rgb = _color(line or fill)
    shape.line.width = Pt(1.1)
    return shape


def add_connector(
    slide, x1: float, y1: float, x2: float, y2: float,
    *, color: str, width_pt: float = 1.5,
):
    """Draw a connector behind nodes so concept maps read as diagrams, not card grids."""
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1), Inches(y1), Inches(x2), Inches(y2),
    )
    connector.line.color.rgb = _color(color)
    connector.line.width = Pt(width_pt)
    return connector


def add_rule(
    slide, left: float, top: float, width: float,
    *, color: str, height: float = 0.04,
):
    return add_panel(
        slide, left, top, width, height,
        fill=color, line=color, rounded=False,
    )


def set_solid_bg(slide, hex_str: str) -> None:
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _color(hex_str)


def attach_notes(slide, notes_text: str) -> None:
    if not notes_text:
        return
    try:
        slide.notes_slide.notes_text_frame.text = notes_text
    except Exception:
        pass


def draw_qr(ctx: RenderContext, slide, title: str, idx: int) -> None:
    if not ctx.enable_qr:
        return
    try:
        result = generate_deeplink_qr(
            session_id=ctx.deck_meta.session_id,
            title=title, slide_index=idx,
            base_url=ctx.base_url,
        )
        if result.qr_path:
            slide.shapes.add_picture(
                result.qr_path,
                Inches(12.4), Inches(6.6), Inches(0.7), Inches(0.7),
            )
    except Exception as exc:
        logger.warning(f"[QR] embed skip: {exc}")


def draw_asset(
    ctx: RenderContext, slide, asset: Asset,
    left: float, top: float, width: float, height: float,
) -> str:
    method = "skipped"
    if asset.kind == "svg":
        r: EmbedResult = ctx.svg_rast.rasterize(
            asset.source, name_hint=asset.alt_text,
        )
        method = r.method
        if r.png_path:
            slide.shapes.add_picture(
                r.png_path, Inches(left), Inches(top),
                Inches(width), Inches(height),
            )
    elif asset.kind == "mermaid":
        r = ctx.mmd_rast.rasterize(
            asset.source, name_hint=asset.alt_text,
        )
        method = r.method
        if r.png_path:
            slide.shapes.add_picture(
                r.png_path, Inches(left), Inches(top),
                Inches(width), Inches(height),
            )
    elif asset.kind == "image":
        try:
            slide.shapes.add_picture(
                asset.source, Inches(left), Inches(top),
                Inches(width), Inches(height),
            )
            method = "image"
        except Exception as exc:
            logger.warning(f"[image] add failed: {exc}")
    return method


# ================================================================
# LayoutRenderer 抽象
# ================================================================
class LayoutRenderer(ABC):
    name: str = "layout"

    @abstractmethod
    def render(
        self, idx: int, slide_spec: SlideSpec, ctx: RenderContext,
    ) -> SlideRenderResult:
        ...

    def new_slide(self, ctx: RenderContext):
        layouts = list(ctx.prs.slide_layouts)
        blank_layout = next(
            (
                layout for layout in layouts
                if str(getattr(layout, "name", "")).strip().lower() in {"blank", "空白"}
            ),
            layouts[-1],
        )
        slide = ctx.prs.slides.add_slide(blank_layout)
        # 原生模板模式保留母版背景与品牌装饰；无模板时使用内置主题底色。
        if not ctx.template_mode:
            set_solid_bg(slide, ctx.theme.bg)
        return slide

    def finalize(
        self, idx: int, slide_spec: SlideSpec, ctx: RenderContext,
        s, asset_method: str = "",
    ) -> SlideRenderResult:
        if ctx.enable_notes:
            attach_notes(s, generate_notes(slide_spec))
        draw_qr(ctx, s, slide_spec.title, idx)
        add_rule(s, 0.8, 7.12, 11.5, color=blend_hex(ctx.theme.primary, ctx.theme.bg, 0.18), height=0.02)
        add_textbox(
            s, 12.25, 7.0, 0.45, 0.25, f"{idx + 1:02d}",
            color=ctx.theme.subtle, size_pt=9, font=ctx.theme.font_body,
            align="right",
        )
        return SlideRenderResult(
            slide_index=idx, layout=self.name,
            title=slide_spec.title, rendered=True,
            asset_method=asset_method,
        )
