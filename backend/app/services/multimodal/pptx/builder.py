"""
SlideDeckBuilder - 主入口

设计:
- 接收 SlideDeckSpec → 经 Linter → 调 LayoutRenderer → 输出 .pptx
- 各 Stage 独立, 失败不阻塞 (单张幻灯片渲染失败仅记录 warning)

向后兼容:
- pptx_builder.py 中保留 PPTXBuilder facade, 让旧调用方继续工作
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from backend.app.services.multimodal.pptx.assets import (
    MermaidRasterizer,
    SVGRasterizer,
)
from backend.app.services.multimodal.pptx.layouts import (
    LAYOUT_REGISTRY,
    RenderContext,
    get_layout,
)
from backend.app.services.multimodal.pptx.linter import PPTXLinter
from backend.app.services.multimodal.pptx.spec import (
    AgendaSlide,
    DeckBuildResult,
    SlideDeckSpec,
)
from backend.app.services.multimodal.pptx.theme import Theme, get_theme


logger = logging.getLogger(__name__)


# python-pptx 延迟导入
_PPTX_AVAILABLE = False
try:
    from pptx import Presentation
    from pptx.util import Inches
    _PPTX_AVAILABLE = True
except ImportError:
    pass


ARTIFACTS_DIR = Path("data/artifacts/pptx")


def _sanitize_filename(title: str) -> str:
    """将标题转为安全的文件名，保留中英文和数字。"""
    # 去掉 Windows/Linux 非法文件名字符
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
    # 去掉首尾空白和点
    safe = safe.strip(". ")
    # 限制长度（中文字符占 3 字节，保守限制 60 字符）
    if len(safe) > 60:
        safe = safe[:60]
    # 如果为空，用默认名
    return safe or "未命名课件"


def _clear_template_slides(prs) -> None:
    """移除模板中的示例页，同时保留母版、主题、字体和版式。"""
    slide_ids = prs.slides._sldIdLst  # python-pptx 尚未提供公开删除 API
    for slide_id in list(slide_ids):
        rel_id = slide_id.rId
        prs.part.drop_rel(rel_id)
        slide_ids.remove(slide_id)


# ================================================================
# 主 Builder
# ================================================================
class SlideDeckBuilder:
    """声明式幻灯片构建器

    流程:
    1. lint deck spec
    2. autofill: 若 AgendaSlide.items 为空 → 用其它幻灯片 title 填充
    3. setup theme + 资源 rasterizer
    4. 遍历 slides 调 layout renderer
    5. 保存 .pptx
    """

    def __init__(
        self,
        artifacts_dir: Path = ARTIFACTS_DIR,
        enable_qr: bool = False,
        enable_notes: bool = True,
        base_url: str = "https://f3.edu.local/chat",
    ):
        self.artifacts_dir = artifacts_dir
        self.enable_qr = enable_qr
        self.enable_notes = enable_notes
        self.base_url = base_url
        self.linter = PPTXLinter()

    def build(
        self,
        deck: SlideDeckSpec,
        resource_id: str,
        theme: Optional[Theme] = None,
        template_path: Optional[str] = None,
    ) -> DeckBuildResult:
        """构建一份完整 PPTX"""
        start = time.perf_counter()
        theme_obj = theme or get_theme(deck.meta.theme_name)

        result = DeckBuildResult(
            theme_name=theme_obj.name,
        )

        # ---- 1. Lint ----
        report = self.linter.lint(deck, theme_obj)
        for issue in report.errors():
            result.lint_errors.append(
                f"[{issue.code}@slide{issue.slide_index}] {issue.message}"
            )
        for issue in report.warnings():
            result.lint_warnings.append(
                f"[{issue.code}@slide{issue.slide_index}] {issue.message}"
            )
        if report.errors():
            result.json_fallback = json.dumps({
                "title": deck.meta.title,
                "errors": result.lint_errors,
            })
            return result

        # ---- 2. python-pptx 不可用 → JSON fallback ----
        if not _PPTX_AVAILABLE:
            result.slides_count = len(deck.slides)
            result.json_fallback = json.dumps({
                "title": deck.meta.title,
                "slides": [
                    {"title": s.title, "layout": s.layout}
                    for s in deck.slides
                ],
            })
            return result

        # ---- 3. autofill Agenda ----
        self._autofill_agenda(deck)

        # ---- 4. 准备 Presentation + RenderContext ----
        try:
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            # 使用标题作为文件名，而非 resource_id 哈希
            safe_title = _sanitize_filename(deck.meta.title)
            filepath = self.artifacts_dir / f"{safe_title}.pptx"
            # 若同名文件已存在，追加序号避免覆盖
            counter = 1
            while filepath.exists():
                filepath = self.artifacts_dir / f"{safe_title}_{counter}.pptx"
                counter += 1

            template_mode = False
            if template_path and Path(template_path).is_file():
                prs = Presentation(str(template_path))
                ratio = float(prs.slide_width) / max(float(prs.slide_height), 1.0)
                if abs(ratio - (16 / 9)) > 0.08:
                    result.lint_warnings.append(
                        "[template_ratio] 模板不是 16:9，已回退到内置版式"
                    )
                    prs = Presentation()
                else:
                    _clear_template_slides(prs)
                    template_mode = True
            else:
                prs = Presentation()
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)

            ctx = RenderContext(
                prs=prs,
                theme=theme_obj,
                deck_meta=deck.meta,
                svg_rast=SVGRasterizer(),
                mmd_rast=MermaidRasterizer(),
                base_url=self.base_url,
                enable_qr=self.enable_qr,
                enable_notes=self.enable_notes,
                template_mode=template_mode,
            )

            for i, slide_spec in enumerate(deck.slides):
                try:
                    layout = get_layout(slide_spec.layout)
                    sr = layout.render(i, slide_spec, ctx)
                    result.slide_results.append(sr)
                except Exception as exc:
                    logger.exception(
                        f"[Builder] slide {i} ({slide_spec.layout}) failed"
                    )
                    result.lint_warnings.append(
                        f"[render_fail@slide{i}] {exc}"
                    )

            prs.save(str(filepath))
            result.filepath = str(filepath)
            result.slides_count = len(result.slide_results)
        except Exception as exc:
            logger.exception("[Builder] save failed")
            result.json_fallback = str(exc)

        result.duration_ms = (time.perf_counter() - start) * 1000
        return result

    @staticmethod
    def _autofill_agenda(deck: SlideDeckSpec) -> None:
        """若 AgendaSlide.items 为空, 用其它幻灯片 title 填充"""
        non_agenda_titles = [
            s.title for s in deck.slides
            if s.layout not in {"agenda", "cover"}
        ]
        for s in deck.slides:
            if isinstance(s, AgendaSlide) and not s.items:
                s.items = list(non_agenda_titles)


# ================================================================
# 单例
# ================================================================
_builder: Optional[SlideDeckBuilder] = None


def get_slide_deck_builder() -> SlideDeckBuilder:
    global _builder
    if _builder is None:
        _builder = SlideDeckBuilder()
    return _builder


def reset_builder() -> None:
    global _builder
    _builder = None
