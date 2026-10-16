"""
PPTXLinter - 渲染前质量门禁

检查项:
- 标题缺失 / 标题过长 (> 80 字符)
- 单行文本可能溢出 (> 120 字符)
- 必填字段为空
- WCAG AA 对比度不达标
- 单张幻灯片要点数过多 (> 7, Miller 1956 7±2)
- Bloom 层级与 layout 类型矛盾 (e.g. checkpoint 应至少 apply 级)

输出 LintReport:
- errors:   阻塞渲染
- warnings: 不阻塞但应改进

学术依据:
- Miller (1956) "The Magical Number Seven Plus or Minus Two"
- WCAG 2.1 AA Contrast
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from backend.app.services.multimodal.pptx.spec import (
    BloomLevel,
    CheckpointSlide,
    CodeSlide,
    ComparisonSlide,
    ConceptSlide,
    CoverSlide,
    SlideDeckSpec,
    SlideSpec,
    WorkedExampleSlide,
)
from backend.app.services.multimodal.pptx.theme import Theme, contrast_ratio


# ================================================================
# Lint 报告
# ================================================================
@dataclass
class LintIssue:
    severity: str           # "error" / "warning"
    code: str               # 错误码
    message: str
    slide_index: int = -1   # -1 = deck 级


@dataclass
class LintReport:
    issues: List[LintIssue] = field(default_factory=list)

    def add(self, issue: LintIssue) -> None:
        self.issues.append(issue)

    def add_error(self, code: str, message: str, slide_index: int = -1) -> None:
        self.issues.append(LintIssue("error", code, message, slide_index))

    def add_warning(
        self, code: str, message: str, slide_index: int = -1,
    ) -> None:
        self.issues.append(LintIssue("warning", code, message, slide_index))

    def errors(self) -> List[LintIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> List[LintIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def passed(self) -> bool:
        return len(self.errors()) == 0


# ================================================================
# Linter
# ================================================================
class PPTXLinter:
    """渲染前质量校验

    用法:
        linter = PPTXLinter()
        report = linter.lint(deck_spec, theme)
        if not report.passed(): raise ValueError(report.errors())
    """

    MAX_TITLE_LEN = 80
    MAX_LINE_LEN = 120
    MAX_BULLETS = 7

    def lint(self, deck: SlideDeckSpec, theme: Theme) -> LintReport:
        report = LintReport()
        self._lint_theme(theme, report)
        self._lint_deck_structure(deck, report)
        for i, slide in enumerate(deck.slides):
            self._lint_slide(i, slide, report)
        return report

    # ------------------------------------------------------------
    # Theme 级
    # ------------------------------------------------------------
    def _lint_theme(self, theme: Theme, report: LintReport) -> None:
        failures = theme.wcag_failures()
        for pair, ratio in failures.items():
            report.add_warning(
                "wcag_aa_contrast",
                f"theme={theme.name} {pair} contrast={ratio:.2f} < 4.5",
            )

    # ------------------------------------------------------------
    # Deck 级
    # ------------------------------------------------------------
    def _lint_deck_structure(
        self, deck: SlideDeckSpec, report: LintReport,
    ) -> None:
        counts = deck.layout_counts()
        if counts.get("cover", 0) == 0:
            report.add_warning(
                "missing_cover",
                "deck has no cover slide, suggest adding CoverSlide first",
            )
        if counts.get("checkpoint", 0) == 0 and len(deck.slides) >= 5:
            report.add_warning(
                "no_checkpoint",
                "deck >= 5 slides but no CheckpointSlide "
                "(retrieval practice missing)",
            )
        if len(deck.slides) > 30:
            report.add_warning(
                "deck_too_long",
                f"deck has {len(deck.slides)} slides, "
                "consider splitting into multiple decks",
            )

    # ------------------------------------------------------------
    # Slide 级
    # ------------------------------------------------------------
    def _lint_slide(
        self, idx: int, slide: SlideSpec, report: LintReport,
    ) -> None:
        title = slide.title or ""
        if not title.strip():
            report.add_error("empty_title", "title is empty", idx)
        elif len(title) > self.MAX_TITLE_LEN:
            report.add_warning(
                "title_too_long",
                f"title={len(title)} chars > {self.MAX_TITLE_LEN}",
                idx,
            )

        if isinstance(slide, ConceptSlide):
            self._lint_concept(idx, slide, report)
        elif isinstance(slide, ComparisonSlide):
            self._lint_comparison(idx, slide, report)
        elif isinstance(slide, WorkedExampleSlide):
            self._lint_worked(idx, slide, report)
        elif isinstance(slide, CodeSlide):
            self._lint_code(idx, slide, report)
        elif isinstance(slide, CheckpointSlide):
            self._lint_checkpoint(idx, slide, report)

    def _lint_concept(
        self, idx: int, s: ConceptSlide, report: LintReport,
    ) -> None:
        if len(s.bullets) > self.MAX_BULLETS:
            report.add_warning(
                "miller_overload",
                f"{len(s.bullets)} bullets > {self.MAX_BULLETS} "
                "(Miller 7±2)", idx,
            )
        for b in s.bullets:
            if len(b) > self.MAX_LINE_LEN:
                report.add_warning(
                    "bullet_too_long",
                    f"bullet '{b[:30]}...' = {len(b)} chars", idx,
                )

    def _lint_comparison(
        self, idx: int, s: ComparisonSlide, report: LintReport,
    ) -> None:
        if abs(len(s.left_points) - len(s.right_points)) > 2:
            report.add_warning(
                "comparison_imbalanced",
                f"left={len(s.left_points)} vs right={len(s.right_points)} "
                "(prefer balanced)", idx,
            )

    def _lint_worked(
        self, idx: int, s: WorkedExampleSlide, report: LintReport,
    ) -> None:
        if len(s.solution_steps) < 2:
            report.add_error(
                "worked_too_short",
                f"worked example needs >= 2 steps, got "
                f"{len(s.solution_steps)}", idx,
            )

    def _lint_code(
        self, idx: int, s: CodeSlide, report: LintReport,
    ) -> None:
        lines = s.code.splitlines()
        for ln in lines:
            if len(ln) > self.MAX_LINE_LEN:
                report.add_warning(
                    "code_line_too_long",
                    f"code line {len(ln)} chars (will overflow)", idx,
                )
                break

    def _lint_checkpoint(
        self, idx: int, s: CheckpointSlide, report: LintReport,
    ) -> None:
        if s.bloom == BloomLevel.REMEMBER:
            report.add_warning(
                "checkpoint_bloom_low",
                "checkpoint at REMEMBER level - prefer >= UNDERSTAND",
                idx,
            )
        if s.correct_index >= len(s.options):
            report.add_error(
                "checkpoint_index_oor",
                f"correct_index={s.correct_index} but only "
                f"{len(s.options)} options",
                idx,
            )
