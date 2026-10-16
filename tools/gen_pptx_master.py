"""生成 16:9 PPT 母版：学术蓝灰 (campus-indigo)。

设计：浅色背景 (#FCFDFF) + 顶部品牌色条 (#1E40AF) + 底部细线页脚 +
右下角双层圆角标识 + 右上角出血圆。所有可见形状 shadow.inherit = False；
页面中部完全留空；装饰总视觉占比 < 5%。

用法：
    pip install python-pptx
    python gen_pptx_master.py                       # 默认输出 campus-indigo.pptx
    python gen_pptx_master.py --out default.pptx    # 自定义输出
"""
import argparse
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# --- 16:9 标准尺寸 (必须显式设置，否则 python-pptx 默认 4:3) ---
PAGE_W = Inches(13.333)
PAGE_H = Inches(7.5)

# --- 配色：学术蓝灰 ---
BG_COLOR     = RGBColor(0xFC, 0xFD, 0xFF)   # 背景：极浅冷白
BRAND_COLOR  = RGBColor(0x1E, 0x40, 0xAF)   # 主品牌色：深蓝
FOOTER_COLOR = RGBColor(0x94, 0xA3, 0xB8)   # 页脚字 / 细线：浅灰
DECO_COLOR   = RGBColor(0xDB, 0xEA, 0xFE)   # 装饰色：极浅蓝
DECO_COLOR_2 = RGBColor(0xEE, 0xF2, 0xFF)   # 装饰色 2：更浅的蓝
FOOTER_TEXT  = "AI 学习伙伴 · 智能教学系统"


def set_fill_alpha(shape, alpha_pct: int) -> None:
    """设置形状填充透明度 (0=不透明, 100=完全透明)。OOXML alpha val: 0-100000。"""
    sppr = shape._element.spPr
    solidFill = sppr.find(qn("a:solidFill"))
    if solidFill is None:
        return
    srgbClr = solidFill.find(qn("a:srgbClr"))
    if srgbClr is None:
        return
    for a in srgbClr.findall(qn("a:alpha")):
        srgbClr.remove(a)
    alpha_el = srgbClr.makeelement(
        qn("a:alpha"), {"val": str(int(alpha_pct * 1000))}
    )
    srgbClr.append(alpha_el)


def kill_shadow(shape) -> None:
    """关闭 PowerPoint 默认阴影。"""
    try:
        shape.shadow.inherit = False
    except Exception:
        pass


def build(path: str = "campus-indigo.pptx") -> str:
    prs = Presentation()
    prs.slide_width, prs.slide_height = PAGE_W, PAGE_H
    master = prs.slide_masters[0]

    # 1) 背景：纯色 (浅色，亮度 L ≈ 99%)
    master.background.fill.solid()
    master.background.fill.fore_color.rgb = BG_COLOR

    # 临时页：先在普通页上建好形状，再 lxml append 到 master.shapes._spTree
    temp = prs.slides.add_slide(prs.slide_layouts[6])  # 6 = blank layout

    def move_to_master(shape) -> None:
        master.shapes._spTree.append(shape._element)

    # ============ 2) 顶部品牌色条 ============
    bar = temp.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, PAGE_W, Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BRAND_COLOR
    bar.line.fill.background()
    kill_shadow(bar)
    move_to_master(bar)

    # ============ 3a) 底部页脚细线 ============
    line_y = PAGE_H - Inches(0.45)
    line = temp.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.6), line_y,
        PAGE_W - Inches(1.2), Emu(12700),  # 12700 EMU ≈ 1pt ≈ 0.014 in
    )
    line.fill.solid()
    line.fill.fore_color.rgb = FOOTER_COLOR
    line.line.fill.background()
    kill_shadow(line)
    move_to_master(line)

    # ============ 3b) 页脚文字 (10pt 浅灰) ============
    footer = temp.shapes.add_textbox(
        Inches(0.6), PAGE_H - Inches(0.35), Inches(8), Inches(0.3)
    )
    tf = footer.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = False
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = FOOTER_TEXT
    run.font.size = Pt(10)
    run.font.color.rgb = FOOTER_COLOR
    run.font.name = "Microsoft YaHei"
    kill_shadow(footer)
    move_to_master(footer)

    # ============ 4) 右下角标识：双层圆角矩形 ============
    mark_size = Inches(0.32)
    mark_x = PAGE_W - mark_size - Inches(0.25)
    mark_y = PAGE_H - mark_size - Inches(0.25)

    outer = temp.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, mark_x, mark_y, mark_size, mark_size
    )
    outer.fill.solid()
    outer.fill.fore_color.rgb = BRAND_COLOR
    outer.line.fill.background()
    outer.adjustments[0] = 0.25
    kill_shadow(outer)
    move_to_master(outer)

    inner_size = Inches(0.18)
    inner = temp.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        mark_x - Inches(0.08), mark_y - Inches(0.08),
        inner_size, inner_size,
    )
    inner.fill.solid()
    inner.fill.fore_color.rgb = DECO_COLOR
    inner.line.fill.background()
    inner.adjustments[0] = 0.3
    kill_shadow(inner)
    move_to_master(inner)

    # ============ 5) 右上角出血圆 (大半径 + 负坐标 + 高透明度) ============
    big = temp.shapes.add_shape(
        MSO_SHAPE.OVAL,
        PAGE_W - Inches(2.2), -Inches(1.6),  # 负 y 让圆一半以上溢出版心
        Inches(3.6), Inches(3.6),
    )
    big.fill.solid()
    big.fill.fore_color.rgb = DECO_COLOR
    big.line.fill.background()
    kill_shadow(big)
    move_to_master(big)
    set_fill_alpha(big, 95)  # 几乎不可见 (5% 不透明)

    small = temp.shapes.add_shape(
        MSO_SHAPE.OVAL,
        PAGE_W - Inches(1.0), -Inches(0.6),
        Inches(2.0), Inches(2.0),
    )
    small.fill.solid()
    small.fill.fore_color.rgb = DECO_COLOR_2
    small.line.fill.background()
    kill_shadow(small)
    move_to_master(small)
    set_fill_alpha(small, 95)

    # ============ 6) 删掉临时页：母版文件不应包含任何普通页 ============
    slide_ids = prs.slides._sldIdLst
    for sid in list(slide_ids):
        prs.part.drop_rel(sid.rId)
        slide_ids.remove(sid)

    prs.save(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 16:9 PPT 母版")
    parser.add_argument("--out", default="campus-indigo.pptx",
                        help="输出文件名 (默认: campus-indigo.pptx)")
    args = parser.parse_args()
    out = build(args.out)
    print("saved:", out)
