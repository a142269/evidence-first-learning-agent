"""
Textbook QA Agent — 教材多模态问答智能体 (Phase 3 Innovation 3)

功能:
    1. 用户上传教材页面 → OCR 提取
    2. 提取内容自动入知识图谱 (调 B 的 KG Builder)
    3. 用户就页面提问 → RAG + LLM 回答
    4. 多模态答案: 文字 + 公式 + 代码 + 图表引用

Pipeline:
    Upload → OCR → Structure → KG Index → User Question → RAG → Answer

使用:
    agent = TextbookQAAgent(llm_client)
    # 上传
    result = await agent.upload_page(image_data, filename="ch3_cnn.png")
    # 问答
    answer = await agent.ask(page_id, "这页讲了什么？")
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.services.multimodal.ocr.engine import (
    OCREngine,
    StructuredPage,
    get_ocr_engine,
)

logger = logging.getLogger(__name__)

# ================================================================
# 全局页面缓存 (session 隔离)
# ================================================================
_page_cache: Dict[str, StructuredPage] = {}  # page_id → StructuredPage


# ================================================================
# LLM 问答提示词
# ================================================================
QA_SYSTEM_PROMPT = """你是教材助教。根据 OCR 提取的教材页面内容回答学生问题。

回答规则:
- 优先引用教材原文作为依据
- 补充性解释用 "💡" 标记
- 公式用 LaTeX $$...$$ 格式
- 代码保持原缩进
- 如果页面上有相关图表，描述图表内容
- 回答末尾列出涉及的 Bloom 层级

当前教材页面:
{page_text}"""


# ================================================================
# TextbookQAAgent
# ================================================================
class TextbookQAAgent(BaseAgent):
    """教材多模态问答智能体

    支持的操作 (通过 context.extra["operation"] 路由):
    - "upload": 上传并 OCR 教材页面
    - "ask": 就指定页面提问
    - "list": 列出已上传页面
    - "kg_push": 将指定页面推入知识图谱
    """

    prompt_version = "v1"

    def __init__(self, llm_client=None):
        super().__init__(llm_client=llm_client)
        self._ocr = get_ocr_engine(llm_client=llm_client)

    @property
    def name(self) -> str:
        return "textbook_qa"

    @property
    def description(self) -> str:
        return "教材多模态问答: OCR 提取 + 结构化存储 + RAG 问答 + KG 入图"

    @property
    def system_prompt(self) -> str:
        return (
            "你是教材助教。根据 OCR 提取的教材页面回答学生的问题。\n"
            "优先引用原文，补充性解释用 💡 标记。\n"
            "公式用 LaTeX，代码保持原样。"
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        operation = context.extra.get("operation", "ask")

        if operation == "upload":
            return await self._handle_upload(context)
        elif operation == "ask":
            return await self._handle_ask(context)
        elif operation == "list":
            return self._handle_list()
        elif operation == "kg_push":
            return await self._handle_kg_push(context)
        else:
            return self._error(f"不支持的操作: {operation}")

    # ----------------------------------------------------------------
    # Upload
    # ----------------------------------------------------------------
    async def _handle_upload(self, context: AgentContext) -> AgentResponse:
        """上传教材页面: OCR → 结构化 → 缓存"""
        image_data = context.extra.get("image_data")     # base64 string
        image_path = context.extra.get("image_path")     # local file path
        filename = context.extra.get("filename", "")

        if image_data:
            import base64
            raw = base64.b64decode(image_data)
        elif image_path:
            from pathlib import Path
            raw = Path(image_path).read_bytes()
            filename = filename or Path(image_path).name
        else:
            return self._error("缺少 image_data 或 image_path")

        start = time.perf_counter()
        page = self._ocr.recognize(raw, filename=filename)
        elapsed = (time.perf_counter() - start) * 1000

        _page_cache[page.page_id] = page

        return AgentResponse(
            agent_name=self.name,
            success=True,
            content=(
                f"## 页面识别完成\n\n"
                f"**页面 ID**: {page.page_id}\n"
                f"**标题**: {page.title or '未检测到标题'}\n"
                f"**内容块**: {len(page.blocks)} 个\n"
                f"**公式**: {len(page.formulas)} 个\n"
                f"**知识点**: {', '.join(page.topics[:5])}\n"
                f"**Bloom 分布**: {page.bloom_distribution}\n"
                f"**OCR 方式**: {page.ocr_method}\n"
                f"**耗时**: {elapsed:.0f}ms\n\n"
                f"---\n## 提取的文本\n{page.to_text()[:1000]}"
            ),
            content_type="ocr_result",
            metadata={
                "page": page.to_dict(),
                "page_id": page.page_id,
                "topics": page.topics,
                "blocks_count": len(page.blocks),
                "formulas_count": len(page.formulas),
                "ocr_method": page.ocr_method,
            },
            resources=[{
                "type": "textbook_page",
                "title": page.title or filename,
                "page_id": page.page_id,
                "topics": page.topics,
                "format": "structured_text",
            }],
        )

    # ----------------------------------------------------------------
    # Ask
    # ----------------------------------------------------------------
    async def _handle_ask(self, context: AgentContext) -> AgentResponse:
        """就教材页面提问"""
        page_id = context.extra.get("page_id", "")
        question = context.user_input

        if not question or not question.strip():
            return self._error("问题不能为空")

        page = _page_cache.get(page_id)
        if not page:
            # 尝试模糊匹配
            page = next((p for pid, p in _page_cache.items() if pid.startswith(page_id)), None)

        page_text = page.to_text() if page else "[页面未找到]"

        # 构建提示词
        prompt = (
            f"学生问题: {question}\n\n"
            f"请基于以下教材页面内容回答。如果页面没有相关信息，请诚实地说明。\n\n"
            f"{page_text[:3000]}"
        )

        result = await self._acall_llm(
            user_prompt=prompt,
            extra_system=QA_SYSTEM_PROMPT.format(page_text=page_text[:3000]),
            temperature=0.3,
        )

        # 检测答案中包含的 Bloom 层级
        bloom_hints = []
        if "定义" in result or "是什么" in result:
            bloom_hints.append("remember")
        if "因为" in result or "原因是" in result:
            bloom_hints.append("understand")
        if "例如" in result or "比如" in result:
            bloom_hints.append("apply")
        if "对比" in result or "比较" in result:
            bloom_hints.append("analyze")

        return self._success(
            content=result,
            content_type="markdown",
            metadata={
                "page_id": page_id,
                "question": question,
                "page_available": page is not None,
                "page_title": page.title if page else "",
                "bloom_hints": bloom_hints,
            },
        )

    # ----------------------------------------------------------------
    # List
    # ----------------------------------------------------------------
    def _handle_list(self) -> AgentResponse:
        """列出已上传页面"""
        pages = [
            {"page_id": pid, "title": p.title, "blocks": len(p.blocks),
             "ocrm": p.ocr_method, "topics": p.topics[:3]}
            for pid, p in _page_cache.items()
        ]
        return AgentResponse(
            agent_name=self.name,
            success=True,
            content=f"已上传 {len(pages)} 个页面:\n" +
            "\n".join(f"- {p['page_id'][:8]} | {p['title'][:40]} | {p['blocks']}块 | {p['ocrm']}" for p in pages),
            content_type="text",
            metadata={"pages": pages, "total": len(pages)},
        )

    # ----------------------------------------------------------------
    # KG Push
    # ----------------------------------------------------------------
    async def _handle_kg_push(self, context: AgentContext) -> AgentResponse:
        """将页面推入知识图谱"""
        page_id = context.extra.get("page_id", "")
        page = _page_cache.get(page_id)
        if not page:
            return self._error(f"页面 {page_id} 未找到")

        try:
            from backend.app.services.knowledge_graph.builder import build_knowledge_graph
            # 写入临时 md 文件，调 KG builder
            import tempfile
            from pathlib import Path
            with tempfile.NamedTemporaryFile(
                suffix=".md", mode="w", encoding="utf-8", delete=False,
            ) as f:
                f.write(page.to_text())
                tmp_path = f.name

            # 调 B 的 KG builder（单文件模式）
            build_knowledge_graph(Path(tmp_path).parent)
            Path(tmp_path).unlink(missing_ok=True)

            return self._success(
                content=f"已推入知识图谱: {page_id[:8]}, 涉及 {len(page.topics)} 个知识点",
                content_type="text",
                metadata={"page_id": page_id, "kg_topics": page.topics},
            )
        except Exception as exc:
            logger.exception(f"[TextbookQA] KG push failed: {exc}")
            return self._error(f"KG 推入失败: {exc}")
