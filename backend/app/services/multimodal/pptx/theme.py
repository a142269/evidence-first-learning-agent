"""
Theme 系统 + 3 预设主题 + WCAG AA 对比度验证

设计目标:
- 颜色 / 字号 / 间距 全部可配置
- 默认 3 预设:
  - academic    锐利学术 (蓝白)
  - modern      柔和现代 (紫粉)
  - high_contrast 高对比色盲安全 (黑黄)
- 对比度按 WCAG 2.1 AA 计算 (≥ 4.5 for body, ≥ 3 for large)

参考:
- WCAG 2.1 SC 1.4.3 Contrast (Minimum)
- 色盲友好调色板: Wong Nature Methods 2011
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, Tuple


# ================================================================
# 颜色工具
# ================================================================
def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """#RRGGBB -> (r, g, b)"""
    s = hex_str.lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", s):
        msg = f"invalid hex color: {hex_str}"
        raise ValueError(msg)
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """WCAG 2.1 相对亮度"""
    def chan(c: int) -> float:
        c_s = c / 255.0
        return c_s / 12.92 if c_s <= 0.03928 else math.pow(
            (c_s + 0.055) / 1.055, 2.4,
        )
    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """WCAG 2.1 对比度比 (1:1 - 21:1)"""
    l1 = _relative_luminance(hex_to_rgb(fg_hex))
    l2 = _relative_luminance(hex_to_rgb(bg_hex))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def meets_wcag_aa(
    fg_hex: str, bg_hex: str, large_text: bool = False,
) -> bool:
    """WCAG AA: ≥ 4.5 (normal) / ≥ 3 (large)"""
    threshold = 3.0 if large_text else 4.5
    return contrast_ratio(fg_hex, bg_hex) >= threshold


# ================================================================
# Theme dataclass
# ================================================================
@dataclass(frozen=True)
class Theme:
    """主题配置 - 颜色 + 字体 + 间距

    属性命名:
    - primary    主色 (标题/重点)
    - secondary  辅色 (次级标题/链接)
    - accent     强调色 (引导问题/注解)
    - bg         背景色
    - text       正文色
    - subtle     淡色 (辅助文本/分割线)
    """
    name: str
    primary: str
    secondary: str
    accent: str
    bg: str
    text: str
    subtle: str

    font_title: str = "Microsoft YaHei"
    font_body: str = "Microsoft YaHei"
    font_code: str = "Consolas"

    title_size_pt: int = 35
    h2_size_pt: int = 24
    body_size_pt: int = 18
    note_size_pt: int = 12
    code_size_pt: int = 14

    margin_left_inch: float = 0.8
    margin_top_inch: float = 0.4
    line_spacing: float = 1.2

    def validate_wcag(self) -> Dict[str, float]:
        """检查 WCAG AA 对比度

        返回:
            {"title_on_bg": 12.3, "body_on_bg": 8.1, "accent_on_bg": 5.0}
        """
        return {
            "primary_on_bg": contrast_ratio(self.primary, self.bg),
            "text_on_bg": contrast_ratio(self.text, self.bg),
            "accent_on_bg": contrast_ratio(self.accent, self.bg),
            "secondary_on_bg": contrast_ratio(self.secondary, self.bg),
        }

    def wcag_failures(self) -> Dict[str, float]:
        """返回未达 WCAG AA 的对比对 (ratio < 4.5)"""
        return {k: v for k, v in self.validate_wcag().items() if v < 4.5}


# ================================================================
# 3 预设主题
# ================================================================
THEMES: Dict[str, Theme] = {
    # 锐利学术 (深蓝 + 浅白)
    "academic": Theme(
        name="academic",
        primary="#1E40AF",       # 深蓝
        secondary="#0369A1",     # 深青蓝（白底满足 WCAG AA）
        accent="#DC2626",        # 强调红
        bg="#FFFFFF",
        text="#0F172A",          # 接近黑
        subtle="#64748B",        # 中性灰
    ),
    # 柔和现代 (紫粉)
    "modern": Theme(
        name="modern",
        primary="#7C3AED",       # 紫色
        secondary="#EC4899",     # 粉色
        accent="#F59E0B",        # 琥珀
        bg="#FAFAFA",
        text="#1F2937",
        subtle="#6B7280",
    ),
    # 高对比 (色盲安全 - Wong 2011 调色板的高对比版)
    "high_contrast": Theme(
        name="high_contrast",
        primary="#000000",       # 纯黑
        secondary="#0072B2",     # Wong 蓝
        accent="#D55E00",        # Wong 橙
        bg="#FFFFFF",
        text="#000000",
        subtle="#56494E",        # 暖灰
    ),
}


def get_theme(name: str = "academic") -> Theme:
    """获取预设主题, 未知名退化到 academic"""
    return THEMES.get(name) or THEMES["academic"]


def list_themes() -> list:
    return list(THEMES.keys())
