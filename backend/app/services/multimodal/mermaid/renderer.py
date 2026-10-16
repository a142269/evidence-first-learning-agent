"""
MermaidRenderer - 3 级降级渲染

降级链 (复用 pptx/assets.py 的 MermaidRasterizer 设计):
    Level 1: npx mmdc CLI       (推荐, 生产质量)
    Level 2: Playwright + mermaid.js (无 npm 时)
    Level 3: PIL 占位图         (最坏情况)

缓存:
- 按 hash(code) 缓存 PNG, 同代码不重复渲染
- TTL 24h (data/artifacts/png 目录)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

PNG_DIR = Path("data/artifacts/mermaid_png")


def _ensure_dirs() -> None:
    PNG_DIR.mkdir(parents=True, exist_ok=True)


def _hash(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


@dataclass
class RenderResult:
    png_path: Optional[str] = None
    data_uri: Optional[str] = None
    method: str = "placeholder"
    width_px: int = 0
    height_px: int = 0
    error: str = ""
    duration_ms: float = 0.0


class MermaidRenderer:
    """3 级降级 Mermaid 渲染器

    Args:
        default_width / default_height: 默认尺寸
        timeout:    单次渲染超时
        scale:      mmdc 输出 PNG 缩放因子 (清晰度 vs 体积)
    """

    def __init__(
        self,
        default_width: int = 1000,
        default_height: int = 700,
        timeout: int = 60,
        scale: int = 2,
    ):
        _ensure_dirs()
        self.default_width = default_width
        self.default_height = default_height
        self.timeout = timeout
        self.scale = scale

    # ----------------------------------------------------------------
    def render(self, code: str, name_hint: str = "") -> RenderResult:
        """主入口"""
        start = time.perf_counter()
        result = self._render_inner(code, name_hint)
        result.duration_ms = (time.perf_counter() - start) * 1000
        return result

    def _render_inner(self, code: str, name_hint: str) -> RenderResult:
        if not code or not code.strip():
            return RenderResult(error="empty mermaid code")

        cache_key = _hash(code)
        out_path = PNG_DIR / f"{cache_key}.png"
        verified_path = PNG_DIR / f"{cache_key}.verified"
        # 旧版本会把 Mermaid 的错误页（例如 ``No diagram type detected``）
        # 截图并缓存成 PNG。没有成功标记的历史图片一律不再复用，避免修正
        # 源码后页面仍长期展示旧错误图。
        if out_path.exists() and verified_path.exists():
            return self._with_data_uri(RenderResult(
                png_path=str(out_path), method="cache",
                width_px=self.default_width, height_px=self.default_height,
            ))
        self._safe_unlink(out_path)
        self._safe_unlink(verified_path)

        for level in (self._try_mmdc, self._try_playwright):
            try:
                result = level(code, out_path)
                if result.png_path:
                    verified_path.write_text(result.method, encoding="utf-8")
                    return self._with_data_uri(result)
            except Exception as exc:
                logger.warning(
                    f"[MermaidRenderer] {level.__name__} failed: {exc}"
                )
            # 部分渲染器失败时仍可能留下错误页或不完整 PNG，下一层降级前
            # 必须清理，防止其被误判为有效输出。
            self._safe_unlink(out_path)
        return self._with_data_uri(
            self._placeholder(out_path, name_hint or "Mermaid")
        )

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.debug("[MermaidRenderer] unable to remove stale file: %s", path)

    def _with_data_uri(self, result: RenderResult) -> RenderResult:
        if result.png_path and Path(result.png_path).exists():
            try:
                with open(result.png_path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("ascii")
                result.data_uri = f"data:image/png;base64,{data}"
            except OSError:
                pass
        return result

    # ----------------------------------------------------------------
    # Level 1: mmdc CLI
    # ----------------------------------------------------------------
    def _try_mmdc(
        self, code: str, out_path: Path,
    ) -> RenderResult:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".mmd", mode="w", encoding="utf-8", delete=False,
        )
        try:
            tmp.write(code)
            tmp.close()
            args = [
                "npx", "-y", "@mermaid-js/mermaid-cli", "mmdc",
                "-i", tmp.name, "-o", str(out_path),
                "-s", str(self.scale),
                "-b", "transparent",
            ]
            r = subprocess.run(
                args, capture_output=True,
                timeout=self.timeout, shell=True,
            )
            if r.returncode == 0 and out_path.exists():
                return RenderResult(
                    png_path=str(out_path), method="mmdc",
                    width_px=self.default_width * self.scale,
                    height_px=self.default_height * self.scale,
                )
            return RenderResult(error=f"mmdc rc={r.returncode}")
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # ----------------------------------------------------------------
    # Level 2: Playwright + mermaid.js
    # ----------------------------------------------------------------
    def _try_playwright(
        self, code: str, out_path: Path,
    ) -> RenderResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return RenderResult(error="playwright not installed")

        html = (
            "<!DOCTYPE html><html><head>"
            "<script src='https://cdn.jsdelivr.net/npm/mermaid/dist/"
            "mermaid.min.js'></script></head>"
            "<body style='margin:0;background:transparent'>"
            f"<div class='mermaid'>{code}</div>"
            "<script>mermaid.initialize("
            "{startOnLoad:true,theme:'default',securityLevel:'loose'}"
            ");</script>"
            "</body></html>"
        )
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(
                    viewport={
                        "width": self.default_width,
                        "height": self.default_height,
                    }
                )
                page.set_content(html)
                page.wait_for_timeout(2000)
                body_text = page.locator("body").inner_text().lower()
                # Mermaid 会把解析错误渲染成带炸弹图标的 SVG。过去这里直接
                # 截全页，导致“Syntax error in text”被当作成功思维导图返回。
                error_markers = (
                    "syntax error",
                    "mermaid version",
                    "no diagram type detected",
                    "parse error",
                    "error in text",
                    "expecting '",
                )
                if any(marker in body_text for marker in error_markers):
                    return RenderResult(error="mermaid syntax error")
                if page.locator(".error-icon, .error-text").count() > 0:
                    return RenderResult(error="mermaid rendered an error diagram")
                diagram = page.locator(".mermaid svg")
                if diagram.count() < 1:
                    return RenderResult(error="mermaid produced no diagram svg")
                diagram.first.screenshot(path=str(out_path))
            finally:
                browser.close()
        if out_path.exists():
            return RenderResult(
                png_path=str(out_path), method="playwright",
                width_px=self.default_width,
                height_px=self.default_height,
            )
        return RenderResult(error="playwright produced no file")

    # ----------------------------------------------------------------
    # Level 3: PIL Placeholder
    # ----------------------------------------------------------------
    def _placeholder(
        self, out_path: Path, hint: str,
    ) -> RenderResult:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return RenderResult(error="PIL not installed")

        img = Image.new(
            "RGB", (self.default_width, self.default_height),
            color=(248, 250, 252),
        )
        draw = ImageDraw.Draw(img)
        # 渐变边框
        for i, c in enumerate([(30, 64, 175), (14, 165, 233)]):
            draw.rectangle(
                [i, i, self.default_width - i - 1, self.default_height - i - 1],
                outline=c, width=2,
            )
        try:
            font = ImageFont.truetype("arial.ttf", 28)
            small = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            font = ImageFont.load_default()
            small = font
        title = "[Mermaid 占位图]"
        draw.text((40, 40), title, fill=(30, 64, 175), font=font)
        draw.text(
            (40, 90), f"主题: {hint[:50]}",
            fill=(15, 23, 42), font=small,
        )
        draw.text(
            (40, self.default_height - 60),
            "Tip: 安装 @mermaid-js/mermaid-cli 或 playwright 以获得真实渲染",
            fill=(100, 116, 139), font=small,
        )
        img.save(str(out_path))
        return RenderResult(
            png_path=str(out_path), method="placeholder",
            width_px=self.default_width, height_px=self.default_height,
        )
