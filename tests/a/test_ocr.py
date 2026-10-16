"""
测试: Textbook OCR + 多模态问答 (Phase 3 Innovation 3)

覆盖目标 ≥ 20 用例:
- ContentBlock / StructuredPage 数据模型
- ImagePreprocessor available / preprocess
- PagePostprocessor: LLM parsed / rules / formula extraction / Bloom detection / topics
- OCREngine: mock fallback always works
- TextbookQAAgent: upload with mock / ask / list / kg_push error
"""
from __future__ import annotations

import base64
import io
import re
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from backend.app.services.multimodal.ocr.engine import (
    BLOOM_VERB_MAP,
    ContentBlock,
    ContentBlockType,
    ImagePreprocessor,
    LLMVisionOCR,
    OCREngine,
    PagePostprocessor,
    StructuredPage,
    TesseractOCR,
    get_ocr_engine,
)
from backend.app.agents.textbook_qa_agent import TextbookQAAgent, _page_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    _page_cache.clear()


# ================================================================
# 1) 数据模型
# ================================================================
class TestContentBlock:
    def test_text_block(self):
        b = ContentBlock(block_id=1, type=ContentBlockType.TEXT, content="Hello")
        assert b.type == ContentBlockType.TEXT
        assert b.bloom_level == ""

    def test_formula_block(self):
        b = ContentBlock(block_id=2, type=ContentBlockType.FORMULA,
                         content=r"E=mc^2", confidence=0.9)
        assert b.type == ContentBlockType.FORMULA
        assert b.confidence == 0.9

    def test_code_block(self):
        b = ContentBlock(block_id=3, type=ContentBlockType.CODE,
                         content="print('hello')",
                         bounding_box=(100, 200, 400, 300))
        assert b.bounding_box == (100, 200, 400, 300)


class TestStructuredPage:
    def test_empty_page(self):
        p = StructuredPage(page_id="test", ocr_method="mock")
        assert p.title == ""
        assert len(p.blocks) == 0

    def test_to_text(self):
        p = StructuredPage(
            page_id="p1", title="CNN 入门",
            blocks=[
                ContentBlock(1, ContentBlockType.HEADING, "卷积层"),
                ContentBlock(2, ContentBlockType.TEXT, "卷积层是CNN的核心组件"),
                ContentBlock(3, ContentBlockType.FORMULA, r"(f*g)(t)=\int f(\tau)g(t-\tau)d\tau"),
                ContentBlock(4, ContentBlockType.CODE, "import torch\nnn.Conv2d(3,64,3)"),
            ],
            formulas=[r"(f*g)(t)=\int f(\tau)g(t-\tau)d\tau"],
            language="zh",
        )
        text = p.to_text()
        assert "# CNN 入门" in text
        assert "## 卷积层" in text
        assert "$$" in text
        assert "```" in text

    def test_to_dict(self):
        p = StructuredPage(
            page_id="p1", title="Test",
            blocks=[ContentBlock(1, ContentBlockType.TEXT, "hello")],
            bloom_distribution={"understand": 1},
            formulas=["x=y"],
        )
        d = p.to_dict()
        assert d["page_id"] == "p1"
        assert len(d["blocks"]) == 1
        assert "x=y" in d["formulas"]


# ================================================================
# 2) ImagePreprocessor
# ================================================================
class TestImagePreprocessor:
    def test_available(self):
        assert isinstance(ImagePreprocessor.available(), bool)

    def test_preprocess_passthrough(self):
        """preprocess 不崩溃 + 返回非空"""
        # 生成最小 1x1 PNG
        try:
            from PIL import Image
            buf = io.BytesIO()
            Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, "PNG")
            raw = buf.getvalue()
            pp = ImagePreprocessor()
            result = pp.preprocess(raw)
            assert len(result) > 0
        except ImportError:
            pytest.skip("Pillow not installed")


# ================================================================
# 3) PagePostprocessor
# ================================================================
class TestPagePostprocessor:
    @pytest.fixture
    def pp(self):
        return PagePostprocessor()

    def test_from_rules_basic(self, pp):
        text = "卷积神经网络\n\nCNN 是一种深度学习架构。\n\n公式: $$y=f(x)$$\n\n- 卷积层\n- 池化层"
        page = pp.process(text)
        assert len(page.blocks) >= 2
        assert "CNN" in page.raw_text

    def test_from_llm_parsed(self, pp):
        parsed = {
            "title": "CNN 入门",
            "blocks": [
                {"type": "heading", "content": "1.1 卷积层"},
                {"type": "text", "content": "卷积层提取局部特征。"},
                {"type": "formula", "content": r"$$y = W * x + b$$"},
                {"type": "code", "content": "nn.Conv2d(3, 64, 3)"},
            ],
            "topics": ["CNN", "卷积", "特征提取"],
            "summary": "CNN 基础概念",
            "language": "zh",
        }
        page = pp.process("raw", llm_parsed=parsed)
        assert page.title == "CNN 入门"
        assert len(page.blocks) == 4
        assert page.topics == ["CNN", "卷积", "特征提取"]
        assert len(page.formulas) >= 1
        assert page.language == "zh"

    def test_formula_extraction(self, pp):
        text = "能量公式: $$E=mc^2$$ 是爱因斯坦提出的。"
        formula = pp._extract_formula(text)
        assert "E=mc^2" in formula

    def test_bloom_detection(self, pp):
        assert pp._detect_bloom("请实现一个CNN") == "apply"
        assert pp._detect_bloom("什么是卷积神经网络") == "remember"
        assert pp._detect_bloom("请解释为什么使用ReLU") == "understand"

    def test_topics_extraction(self, pp):
        topics = pp._extract_topics("卷积神经网络用于图像识别，卷积核提取特征。")
        assert len(topics) >= 1

    def test_language_detection(self):
        assert PagePostprocessor._detect_language("CNN is a neural network") == "en"
        assert PagePostprocessor._detect_language("卷积神经网络是一种") == "zh"

    def test_bloom_distribution_in_output(self, pp):
        parsed = {
            "title": "T",
            "blocks": [
                {"type": "text", "content": "定义: CNN"},
                {"type": "text", "content": "请实现这个函数"},
            ],
            "topics": [], "summary": "", "language": "zh",
        }
        page = pp.process("raw", llm_parsed=parsed)
        assert "remember" in page.bloom_distribution or "apply" in page.bloom_distribution


# ================================================================
# 4) OCREngine
# ================================================================
class TestOCREngine:
    def test_mock_fallback_always_works(self):
        engine = OCREngine(llm_client=None)
        img = b"fake_image_data_" * 20
        page = engine.recognize(img, filename="test.png")
        # 兼容旧命名 "mock" 与新的降级命名 "degraded"
        assert page.ocr_method in {"mock", "degraded"}
        assert page.page_id
        assert page.elapsed_ms >= 0

    def test_singleton(self):
        e1 = get_ocr_engine()
        e2 = get_ocr_engine()
        assert e1 is e2


# ================================================================
# 5) TextbookQAAgent
# ================================================================
class TestTextbookQAAgent:
    @pytest.fixture
    def agent(self, mock_llm_client):
        mock_llm_client.chat.return_value = "Mock answer: CNN is a neural network."
        return TextbookQAAgent(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_upload_with_base64(self, agent):
        from backend.app.agents.base import AgentContext
        import base64
        ctx = AgentContext(
            user_input="upload",
            extra={"operation": "upload", "image_data": base64.b64encode(b"fake_image").decode()},
        )
        resp = await agent.execute(ctx)
        assert resp.success is True
        page_id = resp.metadata.get("page_id", "")
        assert page_id
        assert resp.metadata["ocr_method"] in {"mock", "degraded"}

    @pytest.mark.asyncio
    async def test_upload_no_data(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="upload", extra={"operation": "upload"})
        resp = await agent.execute(ctx)
        assert resp.success is False

    @pytest.mark.asyncio
    async def test_ask_page_not_found(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(
            user_input="这页讲了什么？",
            extra={"operation": "ask", "page_id": "nonexistent"},
        )
        resp = await agent.execute(ctx)
        assert resp.success is True  # ask 不 fail, 只是告知没找到

    @pytest.mark.asyncio
    async def test_list(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="list", extra={"operation": "list"})
        resp = await agent.execute(ctx)
        assert resp.success is True
        assert "total" in resp.metadata

    @pytest.mark.asyncio
    async def test_unknown_operation(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="x", extra={"operation": "invalid"})
        resp = await agent.execute(ctx)
        assert resp.success is False
        assert "不支持" in resp.error

    @pytest.mark.asyncio
    async def test_agent_in_registry(self):
        from backend.app.agents import AGENT_REGISTRY
        assert "textbook_qa" in AGENT_REGISTRY
