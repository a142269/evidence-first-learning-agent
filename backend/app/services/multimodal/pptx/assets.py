"""
Asset Embed Pipeline - SVG / Mermaid → PNG 3 级降级

降级链:
- SVG:     cairosvg → Playwright (headless) → PIL 占位
- Mermaid: mmdc CLI → Playwright + mermaid.js → 文本占位

设计:
- 每级都返回标准 EmbedResult, 包含 method 字段
- 失败不抛, 退到占位图 (避免演示时 PPTX 整页空白)
- 缓存: 同 source hash 不重复渲染
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


# ================================================================
# 缓存目录
# ================================================================
CACHE_DIR = Path("data/artifacts/asset_cache")
PNG_DIR = Path("data/artifacts/png")


def _ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)


def _hash(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


# ================================================================
# 结果模型
# ================================================================
@dataclass
class EmbedResult:
    """SVG / Mermaid 嵌入结果"""
    png_path: Optional[str] = None
    method: str = "placeholder"
    width_px: int = 0
    height_px: int = 0
    error: str = ""


# ================================================================
# SVG → PNG
# ================================================================
class SVGRasterizer:
    """3 级降级 SVG 光栅化器

    Level 1: cairosvg (推荐)
    Level 2: Playwright (headless Chromium 截图)
    Level 3: PIL 占位图
    """

    def __init__(
        self,
        default_width: int = 800,
        default_height: int = 600,
    ):
        _ensure_dirs()
        self.default_width = default_width
        self.default_height = default_height

    def rasterize(self, svg_text: str, name_hint: str = "") -> EmbedResult:
        if not svg_text or not svg_text.strip():
            return EmbedResult(error="empty svg")

        cache_key = _hash(svg_text)
        out_path = PNG_DIR / f"svg_{cache_key}.png"
        if out_path.exists():
            return EmbedResult(
                png_path=str(out_path), method="cache",
                width_px=self.default_width, height_px=self.default_height,
            )

        for level in (self._try_cairosvg, self._try_playwright):
            try:
                result = level(svg_text, out_path)
                if result.png_path:
                    return result
            except Exception as exc:
                logger.warning(
                    f"[SVGRasterizer] {level.__name__} failed: {exc}"
                )

        return self._placeholder(out_path, hint=name_hint or "SVG")

    def _try_cairosvg(
        self, svg_text: str, out_path: Path,
    ) -> EmbedResult:
        try:
            import cairosvg
        except ImportError:
            return EmbedResult(error="cairosvg not installed")
        cairosvg.svg2png(
            bytestring=svg_text.encode("utf-8"),
            write_to=str(out_path),
            output_width=self.default_width,
            output_height=self.default_height,
        )
        return EmbedResult(
            png_path=str(out_path), method="cairosvg",
            width_px=self.default_width, height_px=self.default_height,
        )

    def _try_playwright(
        self, svg_text: str, out_path: Path,
    ) -> EmbedResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return EmbedResult(error="playwright not installed")
        html = (
            f"<html><body style='margin:0'>"
            f"<div style='width:{self.default_width}px;"
            f"height:{self.default_height}px;'>{svg_text}</div>"
            f"</body></html>"
        )
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={
                    "width": self.default_width,
                    "height": self.default_height,
                }
            )
            page.set_content(html)
            page.screenshot(path=str(out_path), full_page=False)
            browser.close()
        return EmbedResult(
            png_path=str(out_path), method="playwright",
            width_px=self.default_width, height_px=self.default_height,
        )

    def _placeholder(self, out_path: Path, hint: str) -> EmbedResult:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return EmbedResult(error="PIL not installed")
        img = Image.new(
            "RGB", (self.default_width, self.default_height),
            color=(248, 250, 252),
        )
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except OSError:
            font = ImageFont.load_default()
        text = f"[SVG 占位]\n{hint[:40]}"
        draw.text(
            (40, self.default_height // 2 - 30), text,
            fill=(100, 116, 139), font=font,
        )
        img.save(str(out_path))
        return EmbedResult(
            png_path=str(out_path), method="placeholder",
            width_px=self.default_width, height_px=self.default_height,
        )


# ================================================================
# Mermaid → PNG
# ================================================================
class MermaidRasterizer:
    """3 级降级 Mermaid 光栅化器"""

    def __init__(
        self,
        default_width: int = 800,
        default_height: int = 600,
        timeout: int = 60,
    ):
        _ensure_dirs()
        self.default_width = default_width
        self.default_height = default_height
        self.timeout = timeout

    def rasterize(self, code: str, name_hint: str = "") -> EmbedResult:
        if not code or not code.strip():
            return EmbedResult(error="empty mermaid code")

        cache_key = _hash(code)
        out_path = PNG_DIR / f"mmd_{cache_key}.png"
        if out_path.exists():
            return EmbedResult(
                png_path=str(out_path), method="cache",
                width_px=self.default_width, height_px=self.default_height,
            )

        for level in (self._try_mmdc, self._try_playwright):
            try:
                result = level(code, out_path)
                if result.png_path:
                    return result
            except Exception as exc:
                logger.warning(
                    f"[MermaidRasterizer] {level.__name__} failed: {exc}"
                )

        return self._placeholder(out_path, hint=name_hint or "Mermaid")

    def _try_mmdc(self, code: str, out_path: Path) -> EmbedResult:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".mmd", mode="w", encoding="utf-8", delete=False,
        )
        try:
            tmp.write(code)
            tmp.close()
            args = [
                "npx", "-y", "@mermaid-js/mermaid-cli",
                "mmdc", "-i", tmp.name, "-o", str(out_path), "-s", "2",
            ]
            r = subprocess.run(
                args, capture_output=True, timeout=self.timeout, shell=True,
            )
            if r.returncode == 0 and out_path.exists():
                return EmbedResult(
                    png_path=str(out_path), method="mmdc",
                    width_px=self.default_width,
                    height_px=self.default_height,
                )
            return EmbedResult(error=f"mmdc rc={r.returncode}")
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def _try_playwright(self, code: str, out_path: Path) -> EmbedResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return EmbedResult(error="playwright not installed")
        # 用 mermaid.js CDN 在 headless chromium 中渲染
        html = (
            "<!DOCTYPE html><html><head>"
            "<script src='https://cdn.jsdelivr.net/npm/mermaid/dist/"
            "mermaid.min.js'></script></head>"
            "<body style='margin:0;background:#fff'>"
            f"<div class='mermaid'>{code}</div>"
            "<script>mermaid.initialize({startOnLoad:true});</script>"
            "</body></html>"
        )
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={
                "width": self.default_width,
                "height": self.default_height,
            })
            page.set_content(html)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(out_path), full_page=True)
            browser.close()
        return EmbedResult(
            png_path=str(out_path), method="playwright",
            width_px=self.default_width, height_px=self.default_height,
        )

    def _placeholder(self, out_path: Path, hint: str) -> EmbedResult:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return EmbedResult(error="PIL not installed")
        img = Image.new(
            "RGB", (self.default_width, self.default_height),
            color=(240, 249, 255),
        )
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except OSError:
            font = ImageFont.load_default()
        text = f"[Mermaid 占位]\n{hint[:60]}"
        draw.text(
            (40, self.default_height // 2 - 20), text,
            fill=(30, 64, 175), font=font,
        )
        img.save(str(out_path))
        return EmbedResult(
            png_path=str(out_path), method="placeholder",
            width_px=self.default_width, height_px=self.default_height,
        )
