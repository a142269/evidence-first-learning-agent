"""
Mermaid Renderer - 向后兼容 Facade (P1-4 重构版)

旧 32 行 spaghetti 一行式代码已替换为 backend/app/services/multimodal/mermaid/ 包。
本文件保留旧 API 名 (`MermaidRenderer`, `get_mermaid_renderer`) 作为兼容层,
内部转发到新的 MermaidStudio。

新代码请直接使用:
    from backend.app.services.multimodal.mermaid import (
        MermaidStudio, MindmapSpec, FlowchartSpec, ...,
        get_mermaid_studio, detect_intent,
    )
"""
from __future__ import annotations

import base64
import re
from typing import Any, Dict, List, Optional

from backend.app.services.multimodal.mermaid import (
    MermaidStudio,
    get_mermaid_studio,
)


# ================================================================
# 旧 API: MermaidRenderer
# ================================================================
class MermaidRenderer:
    """旧 32 行 MermaidRenderer 兼容 facade

    内部转发到 MermaidStudio.render_code()。返回旧字典结构。
    """

    def __init__(self) -> None:
        self._studio: MermaidStudio = get_mermaid_studio()

    def render(self, code: str, rid: str = "") -> Dict[str, Any]:
        """旧签名: 返回 {png_path, data_uri, mermaid_text, method}"""
        result = self._studio.render_code(code, name_hint=rid)
        return {
            "png_path": result.png_path,
            "data_uri": result.data_uri,
            "mermaid_text": code,
            "method": result.method,
        }

    @staticmethod
    def extract_blocks(text: str) -> List[str]:
        """旧静态方法 — 从 Markdown 提取所有 ```mermaid 代码块"""
        return re.findall(
            r"```mermaid\s*\n(.*?)\n```", text, re.DOTALL,
        )


# ================================================================
# 单例兼容
# ================================================================
_renderer: Optional[MermaidRenderer] = None


def get_mermaid_renderer() -> MermaidRenderer:
    global _renderer
    if _renderer is None:
        _renderer = MermaidRenderer()
    return _renderer
