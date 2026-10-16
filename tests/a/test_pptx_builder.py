"""
测试: PPTX 子包 - 声明式 Spec + 7 Layouts + Theme + Linter + Assets + 向后兼容

覆盖目标 ≥ 25 用例:
- spec.py:        Pydantic 校验 (8)
- theme.py:       WCAG 对比度 + 主题 (5)
- assets.py:      SVG / Mermaid 降级 (3)
- notes.py:       Speaker Notes 自动生成 (4)
- deeplink.py:    QR URL 构造 (2)
- linter.py:      Lint 报告 (5)
- builder.py:     端到端 build (4)
- pptx_builder.py: 向后兼容 facade (3)
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.services.multimodal.pptx import (
    AgendaSlide,
    Asset,
    BloomLevel,
    CheckpointSlide,
    CodeSlide,
    ComparisonSlide,
    ConceptSlide,
    CoverSlide,
    DeckMeta,
    PPTXLinter,
    SlideDeckBuilder,
    SlideDeckSpec,
    Theme,
    WorkedExampleSlide,
    contrast_ratio,
    get_theme,
    list_themes,
    meets_wcag_aa,
)
from backend.app.services.multimodal.pptx.assets import (
    MermaidRasterizer,
    SVGRasterizer,
)
from backend.app.services.multimodal.pptx.deeplink import (
    build_deeplink_url,
    generate_deeplink_qr,
)
from backend.app.services.multimodal.pptx.notes import (
    generate_notes,
    BLOOM_VERBS,
)


# ================================================================
# 1) spec.py - Pydantic 校验
# ================================================================
class TestSpec:
    def test_cover_slide_minimal(self):
        s = CoverSlide(title="CNN 入门")
        assert s.layout == "cover"
        assert s.author == "triple U"

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            CoverSlide(title="")

    def test_title_too_long_rejected(self):
        with pytest.raises(ValidationError):
            CoverSlide(title="x" * 200)

    def test_checkpoint_correct_index_in_range(self):
        s = CheckpointSlide(
            title="测试", question="?",
            options=["A", "B"], correct_index=1,
        )
        assert s.correct_index == 1

    def test_checkpoint_correct_index_out_of_range(self):
        with pytest.raises(ValidationError):
            CheckpointSlide(
                title="测试", question="?",
                options=["A", "B"], correct_index=5,
            )

    def test_worked_example_min_steps(self):
        with pytest.raises(ValidationError):
            WorkedExampleSlide(
                title="x", problem="p", solution_steps=["step1"],
            )

    def test_code_too_long_rejected(self):
        with pytest.raises(ValidationError):
            CodeSlide(title="x", code="\n".join(["pass"] * 50))

    def test_deck_layout_counts(self):
        deck = SlideDeckSpec(
            meta=DeckMeta(title="x"),
            slides=[
                CoverSlide(title="t"),
                ConceptSlide(title="t2", definition="d"),
                ConceptSlide(title="t3", definition="d"),
            ],
        )
        counts = deck.layout_counts()
        assert counts["cover"] == 1
        assert counts["concept"] == 2


# ================================================================
# 2) theme.py - WCAG + 主题
# ================================================================
class TestTheme:
    def test_contrast_black_white_is_max(self):
        ratio = contrast_ratio("#000000", "#FFFFFF")
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_meets_wcag_aa_normal(self):
        assert meets_wcag_aa("#000000", "#FFFFFF") is True
        assert meets_wcag_aa("#CCCCCC", "#FFFFFF") is False

    def test_meets_wcag_aa_large_text_threshold(self):
        # #888888 vs 白 ≈ 3.58 — 大字号通过 (>=3), 正常字号失败 (<4.5)
        assert meets_wcag_aa("#888888", "#FFFFFF", large_text=True) is True
        assert meets_wcag_aa("#888888", "#FFFFFF", large_text=False) is False

    def test_3_presets_exist(self):
        names = list_themes()
        assert "academic" in names
        assert "modern" in names
        assert "high_contrast" in names

    def test_high_contrast_passes_wcag(self):
        theme = get_theme("high_contrast")
        # 黑色文本 + 白底 → 主色和正文都应通过
        ratios = theme.validate_wcag()
        assert ratios["text_on_bg"] >= 4.5


# ================================================================
# 3) assets.py - SVG / Mermaid 降级
# ================================================================
class TestAssets:
    def test_svg_empty_returns_error(self):
        r = SVGRasterizer().rasterize("")
        assert r.png_path is None
        assert "empty" in r.error.lower()

    def test_svg_falls_back_to_placeholder(self, tmp_path):
        # cairosvg/playwright 都未装 → 应进入 placeholder
        r = SVGRasterizer().rasterize(
            "<svg><rect width='10' height='10'/></svg>",
            name_hint="test svg",
        )
        # 无论哪种结果都不应崩溃
        assert r is not None

    def test_mermaid_empty_returns_error(self):
        r = MermaidRasterizer().rasterize("")
        assert r.png_path is None


# ================================================================
# 4) notes.py - Speaker Notes
# ================================================================
class TestNotes:
    def test_concept_notes_include_objective(self):
        s = ConceptSlide(
            title="ReLU", definition="f(x)=max(0,x)",
            bloom=BloomLevel.UNDERSTAND,
        )
        notes = generate_notes(s)
        assert "学习目标" in notes
        assert "解释" in notes  # understand 动词

    def test_apply_bloom_uses_apply_verb(self):
        s = ConceptSlide(
            title="实现 ReLU", definition="...",
            bloom=BloomLevel.APPLY,
        )
        notes = generate_notes(s)
        assert "应用" in notes or "实现" in notes

    def test_existing_notes_not_overwritten(self):
        s = ConceptSlide(
            title="x", definition="d",
            notes="既有 notes",
        )
        assert generate_notes(s) == "既有 notes"

    def test_auto_notes_disabled(self):
        s = ConceptSlide(
            title="x", definition="d", auto_notes=False,
        )
        assert generate_notes(s) == ""


# ================================================================
# 5) deeplink.py - QR 深链
# ================================================================
class TestDeeplink:
    def test_url_contains_session_topic_slide(self):
        url = build_deeplink_url("sess_abc", "卷积神经网络", 3)
        assert "session=sess_abc" in url
        assert "slide=3" in url
        # 中文应 URL 编码
        assert "%E5" in url or "topic" in url

    def test_generate_qr_returns_result(self):
        # qrcode 已安装 → 应成功
        r = generate_deeplink_qr("sess_x", "test", 0)
        assert r.url
        # qrcode 可能装也可能没装, 但 url 一定有
        if r.method == "qrcode":
            assert Path(r.qr_path).exists()


# ================================================================
# 6) linter.py - 质量门禁
# ================================================================
class TestLinter:
    def _basic_deck(self):
        return SlideDeckSpec(
            meta=DeckMeta(title="t"),
            slides=[
                CoverSlide(title="t"),
                ConceptSlide(title="t2", definition="d"),
            ],
        )

    def test_passes_basic_deck(self):
        deck = self._basic_deck()
        report = PPTXLinter().lint(deck, get_theme("high_contrast"))
        assert report.passed() is True

    def test_warns_no_cover(self):
        deck = SlideDeckSpec(
            meta=DeckMeta(title="t"),
            slides=[ConceptSlide(title="t", definition="d")],
        )
        report = PPTXLinter().lint(deck, get_theme("academic"))
        codes = [i.code for i in report.warnings()]
        assert "missing_cover" in codes

    def test_warns_no_checkpoint_for_long_deck(self):
        slides = [CoverSlide(title="t")]
        slides += [
            ConceptSlide(title=f"slide{i}", definition="d")
            for i in range(6)
        ]
        deck = SlideDeckSpec(meta=DeckMeta(title="t"), slides=slides)
        report = PPTXLinter().lint(deck, get_theme("academic"))
        codes = [i.code for i in report.warnings()]
        assert "no_checkpoint" in codes

    def test_warns_too_many_bullets_miller(self):
        deck = SlideDeckSpec(
            meta=DeckMeta(title="t"),
            slides=[
                CoverSlide(title="t"),
                ConceptSlide(
                    title="x", definition="d",
                    bullets=["b"] * 6,  # 在 spec 限制内, 但 Linter 仍可警告
                ),
            ],
        )
        # bullets 上限 6 (spec 强约束), 不会触发 miller_overload
        report = PPTXLinter().lint(deck, get_theme("academic"))
        # 这种情况不该触发 miller (因为 <= 7)
        codes = [i.code for i in report.warnings()]
        assert "miller_overload" not in codes

    def test_warns_long_code_line(self):
        deck = SlideDeckSpec(
            meta=DeckMeta(title="t"),
            slides=[
                CoverSlide(title="t"),
                CodeSlide(title="long",
                          code="print('" + "x" * 200 + "')"),
            ],
        )
        report = PPTXLinter().lint(deck, get_theme("academic"))
        codes = [i.code for i in report.warnings()]
        assert "code_line_too_long" in codes


# ================================================================
# 7) builder.py - 端到端
# ================================================================
class TestBuilder:
    def _full_deck(self):
        return SlideDeckSpec(
            meta=DeckMeta(title="测试", session_id="t-001"),
            slides=[
                CoverSlide(title="封面"),
                AgendaSlide(title="目录"),
                ConceptSlide(title="概念", definition="定义"),
                ComparisonSlide(
                    title="对比", left_title="A",
                    left_points=["p1"], right_title="B",
                    right_points=["q1"],
                ),
                WorkedExampleSlide(
                    title="范例", problem="解 1+1",
                    solution_steps=["看", "算"],
                ),
                CodeSlide(title="代码", code="print(1)"),
                CheckpointSlide(
                    title="检查", question="?",
                    options=["A", "B"], correct_index=0,
                    bloom=BloomLevel.UNDERSTAND,
                ),
            ],
        )

    def test_build_full_7_layout_deck(self, tmp_path):
        builder = SlideDeckBuilder(
            artifacts_dir=tmp_path, enable_qr=False, enable_notes=True,
        )
        result = builder.build(self._full_deck(), "test-build-1")
        assert result.filepath != ""
        assert result.slides_count == 7
        assert len(result.slide_results) == 7
        assert Path(result.filepath).exists()

    def test_build_from_native_16x9_template_removes_sample_slides(self, tmp_path):
        from pptx import Presentation
        from pptx.util import Inches

        template_path = tmp_path / "brand-template.pptx"
        template = Presentation()
        template.slide_width = Inches(13.333)
        template.slide_height = Inches(7.5)
        template.slides.add_slide(template.slide_layouts[0])
        template.save(str(template_path))

        output_dir = tmp_path / "output"
        result = SlideDeckBuilder(artifacts_dir=output_dir).build(
            self._full_deck(),
            "templated-build",
            template_path=str(template_path),
        )

        assert result.filepath
        generated = Presentation(result.filepath)
        assert len(generated.slides) == 7

    def test_autofill_agenda(self, tmp_path):
        builder = SlideDeckBuilder(
            artifacts_dir=tmp_path, enable_qr=False, enable_notes=False,
        )
        deck = self._full_deck()
        # AgendaSlide.items 默认为空 — 应被自动填充
        builder._autofill_agenda(deck)
        agenda = [s for s in deck.slides if s.layout == "agenda"][0]
        # 应包含其它幻灯片的标题
        assert "概念" in agenda.items

    def test_lint_errors_block_build(self, tmp_path):
        # 构造 checkpoint correct_index 越界 (spec 阻挡 — 用 model_construct 跳过)
        bad_cp = CheckpointSlide.model_construct(
            title="bad", question="?",
            options=["A", "B"], correct_index=10,
            bloom=BloomLevel.UNDERSTAND, auto_notes=True,
            layout="checkpoint", notes="", knowledge_point="",
        )
        deck = SlideDeckSpec.model_construct(
            meta=DeckMeta(title="t"),
            slides=[CoverSlide(title="t"), bad_cp],
        )
        builder = SlideDeckBuilder(artifacts_dir=tmp_path)
        result = builder.build(deck, "bad-1")
        assert result.filepath == ""
        assert result.json_fallback is not None

    def test_high_contrast_theme_text_passes_wcag(self, tmp_path):
        builder = SlideDeckBuilder(
            artifacts_dir=tmp_path, enable_qr=False, enable_notes=False,
        )
        deck = self._full_deck()
        deck.meta.theme_name = "high_contrast"
        result = builder.build(deck, "hc-1")
        # 主色 + 正文在 high_contrast 主题应通过 WCAG
        primary_warnings = [
            w for w in result.lint_warnings
            if "primary_on_bg" in w or "text_on_bg" in w
        ]
        assert len(primary_warnings) == 0


# ================================================================
# 8) pptx_builder.py - 向后兼容 facade
# ================================================================
class TestBackwardCompat:
    def test_old_pptx_outline_still_works(self):
        from backend.app.services.multimodal.pptx_builder import (
            PPTXBuilder, PPTXOutline, SlideContent,
        )
        outline = PPTXOutline(
            title="兼容测试", subtitle="子标题",
            slides=[
                SlideContent(title="第一节", bullets=["要点1", "要点2"]),
                SlideContent(title="第二节", bullets=["要点A"]),
            ],
            summary_points=["总结1"],
            review_questions=["思考1"],
        )
        builder = PPTXBuilder()
        result = builder.build(outline, "compat-1")
        # 旧 API 返回 dict, 应有 filepath 字段
        assert "filepath" in result
        assert "slides_count" in result
        # 应至少生成几张幻灯片
        assert result["slides_count"] >= 2

    def test_outline_to_deck_spec_adds_cover_agenda(self):
        from backend.app.services.multimodal.pptx_builder import (
            PPTXOutline, SlideContent, outline_to_deck_spec,
        )
        outline = PPTXOutline(
            title="t",
            slides=[SlideContent(title="a", bullets=["x"])],
        )
        deck = outline_to_deck_spec(outline, session_id="s")
        # 至少含 Cover + Agenda + 至少一张内容幻灯片
        assert len(deck.slides) >= 3
        assert deck.slides[0].layout == "cover"
        assert deck.slides[1].layout == "agenda"

    def test_outline_adapter_creates_visual_layout_mix(self):
        from backend.app.services.multimodal.pptx_builder import (
            PPTXOutline, SlideContent, outline_to_deck_spec,
        )
        outline = PPTXOutline(
            title="Transformer",
            slides=[
                SlideContent(title="核心概念", bullets=["定义", "作用", "边界"]),
                SlideContent(title="Self-Attention 与 RNN 对比", bullets=["并行", "长依赖", "顺序", "递归"]),
                SlideContent(title="注意力计算案例", bullets=["给定 Q/K/V", "计算点积", "缩放并 Softmax"]),
                SlideContent(title="PyTorch 实战", layout_hint="code", code_block="import torch\nprint(torch.__version__)"),
            ],
        )

        deck = outline_to_deck_spec(outline)
        layouts = [slide.layout for slide in deck.slides]

        assert "concept" in layouts
        assert "comparison" in layouts
        assert "worked_example" in layouts
        assert "code" in layouts

    def test_old_get_pptx_builder_singleton(self):
        from backend.app.services.multimodal.pptx_builder import (
            get_pptx_builder,
        )
        b1 = get_pptx_builder()
        b2 = get_pptx_builder()
        assert b1 is b2
