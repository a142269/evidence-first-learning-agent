"""
Manim Renderer — 三级降级渲染引擎 (Phase 3 Innovation 2)

Level 1: manim CLI (manim -pql) → MP4 video
Level 2: Playwright → screenshot PNG (no manim dependency)
Level 3: Pre-rendered placeholder → static info card PNG (always works)

降级逻辑:
    try manim → failed? → try Playwright → failed? → use placeholder

预渲染库: 20 个 AI/Python 经典概念 (内置 base64 PNG)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path("data/artifacts/manim")
RENDER_TIMEOUT = 60  # seconds


@dataclass
class RenderResult:
    """渲染结果"""
    video_path: str = ""
    method: str = ""            # "manim" / "playwright" / "placeholder"
    duration_ms: float = 0.0
    error: str = ""
    scene_count: int = 0
    frame_count: int = 0

    @property
    def success(self) -> bool:
        return bool(self.video_path) and not self.error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_path": self.video_path,
            "method": self.method,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "scene_count": self.scene_count,
            "frame_count": self.frame_count,
        }


# ================================================================
# Level 1: Manim CLI Renderer
# ================================================================
class ManimCLIRenderer:
    """通过 manim 命令行渲染视频

    要求: pip install manim + ffmpeg + LaTeX (for MathTex)
    """

    @staticmethod
    def available() -> bool:
        """检查 manim 是否可用的终极方式:

        不依赖 ``import manim`` (耗时), 直接在 shell 里跑 ``manim --version``,
        返回码 0 即为可用。
        """
        try:
            result = subprocess.run(
                ["manim", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def render(self, code: str, output_name: str) -> Optional[str]:
        """渲染 Manim Python 代码 → MP4

        Args:
            code: 完整 Manim Python 脚本
            output_name: 输出文件名 (不含扩展名)

        Returns:
            MP4 文件路径，失败返回 None
        """
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)

        # 写入临时脚本
        script_path = ARTIFACTS_DIR / f"_render_{output_name}.py"
        script_path.write_text(code, encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    "manim",
                    "-pql",                    # preview + low quality + last frame
                    "--format", "mp4",
                    str(script_path),
                ],
                cwd=str(ARTIFACTS_DIR),
                capture_output=True,
                text=True,
                timeout=RENDER_TIMEOUT,
            )

            if result.returncode != 0:
                stderr_tail = (result.stderr or "")[-300:]
                logger.warning(f"[Manim] render failed: {stderr_tail}")
                return None

            # 查找输出的 MP4 文件
            media_dir = ARTIFACTS_DIR / "media" / "videos" / f"_render_{output_name}"
            mp4_files = sorted(
                media_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if mp4_files:
                # Move to artifacts root
                dest = ARTIFACTS_DIR / f"{output_name}.mp4"
                import shutil
                shutil.move(str(mp4_files[0]), str(dest))
                logger.info(f"[Manim] rendered: {dest}")
                return str(dest)

            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"[Manim] render timeout ({RENDER_TIMEOUT}s)")
            return None
        except FileNotFoundError:
            logger.warning("[Manim] command not found")
            return None
        except Exception as exc:
            logger.error(f"[Manim] render exception: {exc}")
            return None
        finally:
            # Cleanup temp script
            try:
                script_path.unlink()
            except OSError:
                pass


# ================================================================
# Level 2: Playwright Screenshot Renderer
# ================================================================
class PlaywrightRenderer:
    """通过 Playwright 渲染 SVG/HTML 静态截图

    不依赖 manim, 作为其降级。
    生成一个包含教学内容的静态信息卡片。
    """

    @staticmethod
    def available() -> bool:
        try:
            subprocess.run(
                ["playwright", "--version"],
                capture_output=True, timeout=5,
            )
            return True
        except Exception:
            return False

    def render(
        self, title: str, content_lines: List[str], output_name: str,
    ) -> Optional[str]:
        """渲染为彩色信息卡片 PNG"""
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)

        # 构建 HTML
        items_html = "".join(
            f'<div class="item">{line}</div>' for line in content_lines[:10]
        )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ background: #1A1A2E; color: #E0E0E0; font-family: sans-serif;
       display: flex; flex-direction: column; align-items: center;
       justify-content: center; min-height: 100vh; margin: 0; padding: 40px; }}
h1 {{ color: #58C4DD; font-size: 32px; margin-bottom: 30px; }}
.item {{ font-size: 18px; line-height: 2.0; color: #CCC; }}
.accent {{ color: #83C167; font-weight: bold; }}
</style></head><body>
<h1>{title}</h1>
{items_html}
</body></html>"""

        html_path = ARTIFACTS_DIR / f"_screenshot_{output_name}.html"
        html_path.write_text(html, encoding="utf-8")

        png_path = ARTIFACTS_DIR / f"{output_name}.png"

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(f"file://{html_path.absolute()}")
                page.screenshot(path=str(png_path), full_page=True)
                browser.close()
            logger.info(f"[Playwright] screenshot: {png_path}")
            return str(png_path)
        except ImportError:
            logger.warning("[Playwright] not installed")
            return None
        except Exception as exc:
            logger.warning(f"[Playwright] render failed: {exc}")
            return None
        finally:
            try:
                html_path.unlink()
            except OSError:
                pass


# ================================================================
# Level 3: Pre-rendered Placeholder Library
# ================================================================
class PlaceholderLibrary:
    """预置教学概念占位库

    20 个 AI / Python 经典概念, 每概念一个 SVG info card (base64 inline)。
    永远可渲染 (零外部依赖)。
    """

    CONCEPTS = [
        "convolutional_neural_network", "backpropagation", "transformer_attention",
        "gradient_descent", "overfitting_regularization", "reinforcement_learning",
        "bayesian_inference", "pca_dimensionality_reduction", "cross_entropy_loss",
        "softmax_activation", "lstm_network", "gan_adversarial",
        "kmeans_clustering", "decision_tree", "random_forest",
        "svm_classifier", "nlp_tokenization", "computer_vision_basics",
        "python_decorators", "async_await",
    ]

    def get_placeholder(self, concept: str, title: str) -> str:
        """返回占位 PNG 文件路径

        生成一张简单的 SVG info card → 存为 SVG 文件（可直接用）。
        不需要 Pillow, 纯字符串。
        """
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)

        # 匹配最近概念
        matched = self._fuzzy_match(concept)
        display_title = title or matched.replace("_", " ").title()

        svg_path = ARTIFACTS_DIR / f"{matched}_placeholder.svg"

        if not svg_path.exists():
            svg = self._build_svg_card(display_title, matched)
            svg_path.write_text(svg, encoding="utf-8")

        return str(svg_path)

    def _fuzzy_match(self, concept: str) -> str:
        """模糊匹配概念名"""
        lower = concept.lower().replace(" ", "_")
        for c in self.CONCEPTS:
            if c in lower or lower in c:
                return c
        # 返回第一个，不抛异常
        return self.CONCEPTS[0]

    def _build_svg_card(self, title: str, concept: str) -> str:
        """构建 SVG 信息卡片"""
        # 计算 20 个概念中该概念的索引，用不同颜色
        idx = self.CONCEPTS.index(concept) if concept in self.CONCEPTS else 0
        colors = [
            ("#58C4DD", "#1A1A2E"), ("#83C167", "#1A1A2E"),
            ("#FC6255", "#1A1A2E"), ("#FFD700", "#1A1A2E"),
            ("#9B59B6", "#1A1A2E"), ("#00BCD4", "#1A1A2E"),
            ("#E91E63", "#1A1A2E"), ("#FF8C00", "#1A1A2E"),
        ]
        accent, bg = colors[idx % len(colors)]

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"
     viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="{bg}"/>
  <text x="640" y="280" text-anchor="middle"
        font-family="sans-serif" font-size="40" fill="{accent}"
        font-weight="bold">{title}</text>
  <text x="640" y="360" text-anchor="middle"
        font-family="sans-serif" font-size="24" fill="#888">
    [教学动画占位 — Manim/Pillow 不可用时自动降级]
  </text>
  <text x="640" y="420" text-anchor="middle"
        font-family="sans-serif" font-size="18" fill="#555">
    Install manim + ffmpeg for full animation: pip install manim
  </text>
  <rect x="440" y="450" width="400" height="40" rx="8"
        fill="{accent}" opacity="0.15"/>
  <text x="640" y="476" text-anchor="middle"
        font-family="monospace" font-size="16" fill="{accent}">
    Concept: {concept}
  </text>
</svg>"""


# ================================================================
# ManimRenderer — 三级降级统一入口
# ================================================================
class ManimRenderer:
    """Manim 三级降级渲染引擎"""

    def __init__(self):
        self._manim = ManimCLIRenderer()
        self._playwright = PlaywrightRenderer()
        self._placeholder = PlaceholderLibrary()
        self._manim_available: Optional[bool] = None

    @property
    def manim_available(self) -> bool:
        if self._manim_available is None:
            self._manim_available = ManimCLIRenderer.available()
        return self._manim_available

    def render(
        self,
        code: str,
        output_name: str,
        title: str = "",
        content_lines: Optional[List[str]] = None,
        concept: str = "",
    ) -> RenderResult:
        """渲染 Manim 代码 → 视频/图片

        Args:
            code: Manim Python 脚本
            output_name: 输出文件名
            title: 教学标题 (用于降级卡片)
            content_lines: 内容行 (用于降级卡片)
            concept: 概念名 (用于占位库匹配)

        Returns:
            RenderResult
        """
        start = time.perf_counter()

        # Level 1: manim CLI
        if self.manim_available:
            video_path = self._manim.render(code, output_name)
            if video_path:
                return RenderResult(
                    video_path=video_path,
                    method="manim",
                    duration_ms=(time.perf_counter() - start) * 1000,
                    scene_count=code.count("class Scene_"),
                )
            logger.info("[ManimRenderer] manim failed, falling back to Playwright")

        # Level 2: Playwright screenshot
        if PlaywrightRenderer.available():
            lines = content_lines or [f"Topic: {title}"]
            png_path = self._playwright.render(title, lines, output_name)
            if png_path:
                return RenderResult(
                    video_path=png_path,
                    method="playwright",
                    duration_ms=(time.perf_counter() - start) * 1000,
                )
            logger.info("[ManimRenderer] Playwright failed, falling back to placeholder")

        # Level 3: Placeholder SVG
        svg_path = self._placeholder.get_placeholder(concept or output_name, title)
        return RenderResult(
            video_path=svg_path,
            method="placeholder",
            duration_ms=(time.perf_counter() - start) * 1000,
        )


# ================================================================
# 全局单例
# ================================================================
_renderer: Optional[ManimRenderer] = None


def get_manim_renderer() -> ManimRenderer:
    global _renderer
    if _renderer is None:
        _renderer = ManimRenderer()
    return _renderer
