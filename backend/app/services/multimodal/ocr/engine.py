"""
教材页面 OCR — 三层降级识别引擎 (Phase 3 Innovation 3)

Pipeline:
    输入: 图片 (base64 / URL / local path)
    → Preprocessor: 灰度化 + 对比度增强 + 去噪
    → OCR Engine: LLM Vision → Tesseract → Mock placeholder
    → Postprocessor: 文本结构化 + 公式 LaTeX 提取 + 图表标注
    → Output: StructuredPage

设计:
    - 讯飞图像识别优先 (符合赛题工具要求)
    - 公式专用: 图像区域 → LaTeX 转换
    - 输出带 Bloom 层级标注 (便于 KG 接入)
    - 每层独立可降级

学术依据:
    - Multi-modal Document Understanding (LayoutLMv3, Huang et al. 2022)
    - Mathematical Formula Recognition (IM2LATEX, Deng et al. 2017)
    - OCR Post-correction (Tong & Evans 1996)
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path("data/artifacts/ocr")
OCR_TIMEOUT = 30  # seconds

# ================================================================
# Bloom 动词映射 — 自动标注提取文本的认知层级
# ================================================================
BLOOM_VERB_MAP: Dict[str, str] = {
    # remember — 回忆 / 识别事实
    "定义": "remember", "列出": "remember", "描述": "remember",
    "是什么": "remember", "什么是": "remember", "回忆": "remember",
    "识别": "remember", "命名": "remember",
    # understand — 解释 / 总结
    "解释": "understand", "总结": "understand", "分类": "understand",
    "为什么": "understand", "理解": "understand", "推断": "understand",
    "归纳": "understand",
    # apply — 应用 / 实现
    "使用": "apply", "实现": "apply", "应用": "apply",
    "编写": "apply", "代码": "apply", "运用": "apply", "求解": "apply",
    # analyze — 分析 / 比较
    "分析": "analyze", "比较": "analyze", "对比": "analyze",
    "区别": "analyze", "拆解": "analyze", "辨别": "analyze",
    # evaluate — 评估 / 判断
    "评估": "evaluate", "判断": "evaluate", "优缺点": "evaluate",
    "权衡": "evaluate", "选择理由": "evaluate",
    # create — 设计 / 创新
    "设计": "create", "构建": "create", "创新": "create",
    "综合": "create", "提出": "create",
}

# LaTeX 环境关键字 — 用于识别公式区域
LATEX_ENV_PATTERNS: List[str] = [
    r'\$\$.*?\$\$', r'\$.*?\$', r'\\begin\{equation\}.*?\\end\{equation\}',
    r'\\begin\{align\}.*?\\end\{align\}', r'\\begin\{pmatrix\}.*?\\end\{pmatrix\}',
    r'\\frac\{.*?\}\{.*?\}', r'\\sum_', r'\\int_', r'\\prod_',
    r'\\alpha', r'\\beta', r'\\gamma', r'\\theta', r'\\lambda', r'\\sigma', r'\\mu',
    r'\\partial', r'\\nabla', r'\\infty', r'\\in\b', r'\\forall', r'\\exists',
]


# ================================================================
# 数据模型
# ================================================================
class ContentBlockType(str, Enum):
    TEXT = "text"
    FORMULA = "formula"
    CODE = "code"
    TABLE = "table"
    IMAGE = "image"
    DIAGRAM = "diagram"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    CAPTION = "caption"


@dataclass
class ContentBlock:
    """页面中的一个内容块"""
    block_id: int
    type: ContentBlockType
    content: str                            # 文本 / LaTeX / 代码
    raw_pixels: Optional[str] = None        # 图像块的 base64 (裁剪)
    bounding_box: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h) in pixels
    confidence: float = 0.0
    bloom_level: str = ""                   # 自动标注
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredPage:
    """识别后的结构化教材页面"""
    page_id: str
    image_source: str = ""                  # 原始图像来源
    raw_text: str = ""                      # 全量原始 OCR 文本
    blocks: List[ContentBlock] = field(default_factory=list)
    title: str = ""
    summary: str = ""
    topics: List[str] = field(default_factory=list)  # 检测到的知识点
    bloom_distribution: Dict[str, int] = field(default_factory=dict)
    formulas: List[str] = field(default_factory=list)  # 提取的 LaTeX 公式
    language: str = ""                      # "zh" / "en" / "mixed"
    ocr_method: str = ""
    elapsed_ms: float = 0.0
    error: str = ""

    def to_text(self) -> str:
        """将结构化页面还原为纯文本 (用于 RAG 索引)"""
        parts = []
        if self.title:
            parts.append(f"# {self.title}")
        for b in self.blocks:
            if b.type == ContentBlockType.HEADING:
                parts.append(f"\n## {b.content}")
            elif b.type == ContentBlockType.FORMULA:
                parts.append(f"\n$${b.content}$$")
            elif b.type == ContentBlockType.CODE:
                parts.append(f"\n```\n{b.content}\n```")
            else:
                parts.append(b.content)
        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "title": self.title,
            "summary": self.summary,
            "topics": self.topics,
            "blocks": [
                {"id": b.block_id, "type": b.type.value, "content": b.content[:200],
                 "bloom_level": b.bloom_level, "confidence": b.confidence}
                for b in self.blocks
            ],
            "bloom_distribution": self.bloom_distribution,
            "formulas": self.formulas,
            "language": self.language,
            "ocr_method": self.ocr_method,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }


# ================================================================
# Preprocessor — 图像预处理
# ================================================================
class ImagePreprocessor:
    """图像预处理: 灰度 + 对比度 + 降噪

    不引入 OpenCV (避免依赖)，用纯 Pillow + numpy。
    """

    @staticmethod
    def available() -> bool:
        try:
            from PIL import Image  # noqa: F401
            return True
        except ImportError:
            return False

    def preprocess(self, image_data: bytes) -> bytes:
        """预处理图像，返回增强后的 PNG bytes"""
        try:
            from PIL import Image, ImageEnhance, ImageFilter

            img = Image.open(io.BytesIO(image_data))
            # 转灰度
            img = img.convert("L")
            # 对比度增强 1.3x
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.3)
            # 中值滤波去噪
            img = img.filter(ImageFilter.MedianFilter(3))
            # 输出
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:
            logger.warning(f"[OCR] preprocess failed: {exc}")
            return image_data  # 原样返回


# ================================================================
# Level 1: LLM Vision OCR
# ================================================================
class LLMVisionOCR:
    """用 LLM 的视觉能力做 OCR + 结构化

    支持: GPT-4o / Gemini / 讯飞星火 Vision
    优先: 讯飞星火 (符合赛题工具要求)
    """

    SYSTEM_PROMPT = """你是一个教材页面 OCR 解析器。

分析上传的教材页面图片, 提取所有内容:

1. **标题**: 页面的主标题
2. **文本块**: 每个段落/正文块, 标注类型:
   - heading: 标题/小标题
   - text: 正文段落
   - list_item: 列表项
   - caption: 图片/表格标题
3. **公式**: 所有数学公式转为 LaTeX 格式 ($$...$$ 或 $...$)
4. **代码**: 代码块保持原样, 标注语言
5. **知识点**: 从文本中提取 3-5 个核心知识点

输出 JSON 格式:
{
  "title": "页面标题",
  "language": "zh|en|mixed",
  "blocks": [
    {"type": "text|heading|formula|code|list_item|caption", "content": "..."}
  ],
  "topics": ["知识点1", "知识点2"],
  "summary": "一句话摘要"
}

只输出 JSON，不要其他文字。"""

    def __init__(self, llm_client: Any = None):
        self._llm = llm_client

    @property
    def available(self) -> bool:
        return self._llm is not None

    def recognize(
        self, image_b64: str, timeout: int = OCR_TIMEOUT,
    ) -> Optional[Dict[str, Any]]:
        """用 LLM Vision 识别页面

        Args:
            image_b64: base64 编码的图像
            timeout: 超时秒数

        Returns:
            解析后的 JSON dict，失败返回 None
        """
        if not self._llm:
            return None

        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "请解析这个教材页面"},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{image_b64}",
                    }},
                ]},
            ]

            if hasattr(self._llm, "chat"):
                raw = self._llm.chat(messages, temperature=0.1, max_tokens=2000)
            elif hasattr(self._llm, "achat"):
                import asyncio
                raw = asyncio.run(
                    self._llm.achat(messages, temperature=0.1, max_tokens=2000)
                )
            else:
                return None

            return self._parse_llm_output(raw)
        except Exception as exc:
            logger.warning(f"[OCR] LLM Vision failed: {exc}")
            return None

    def _parse_llm_output(self, raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        raw = raw.strip()
        # 去 markdown 包裹
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if m:
            raw = m.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return None


# ================================================================
# Level 2: Tesseract OCR Fallback
# ================================================================
class TesseractOCR:
    """Tesseract 离线 OCR — 作为 LLM Vision 的降级

    优势: 零网络依赖, 部署评委环境可行
    局限: 公式识别差, 需后处理
    """

    @staticmethod
    def available() -> bool:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
            return True
        except ImportError:
            return False

    def recognize(self, image_data: bytes) -> Optional[str]:
        """Tesseract OCR"""
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(image_data))
            # 中文 + 英文
            text = pytesseract.image_to_string(
                img, lang="chi_sim+eng",
                config="--psm 6",  # Assume uniform block of text
            )
            return text.strip()
        except Exception as exc:
            logger.warning(f"[OCR] Tesseract failed: {exc}")
            return None


# ================================================================
# Postprocessor — 结构化解析
# ================================================================
class PagePostprocessor:
    """后处理: 原始文本 → StructuredPage

    规则管道 (LLM 失败时的降级):
    1. 提取标题 (首行 / 字号最大的行)
    2. 分段 (空行切分)
    3. 识别公式 ($$...$$, $...$, LaTeX 环境)
    4. 识别代码块 (```...```)
    5. 自动 Bloom 标注
    6. 知识点提取
    """

    # 标题检测模式
    HEADING_PATTERNS: List[str] = [
        r'^第[一二三四五六七八九十\d]+章', r'^第[一二三四五六七八九十\d]+节',
        r'^\d+\.\d+', r'^[一二三四五六七八九十]、',
    ]

    def process(
        self,
        raw_text: str,
        llm_parsed: Optional[Dict[str, Any]] = None,
    ) -> StructuredPage:
        """将 OCR 输出结构化为 StructuredPage

        LLM 解析可用时优先使用; 否则走规则管道。
        """
        page_id = hashlib.md5(raw_text.encode()).hexdigest()[:16]

        if llm_parsed:
            return self._from_llm(page_id, raw_text, llm_parsed)

        return self._from_rules(page_id, raw_text)

    def _from_llm(
        self, page_id: str, raw_text: str, parsed: Dict[str, Any],
    ) -> StructuredPage:
        """从 LLM 解析结果构造 StructuredPage"""
        blocks: List[ContentBlock] = []
        formulas: List[str] = []
        block_id = 0

        for item in parsed.get("blocks", []):
            block_id += 1
            btype_raw = item.get("type", "text")
            content = item.get("content", "")

            # 映射类型
            type_map = {
                "text": ContentBlockType.TEXT,
                "heading": ContentBlockType.HEADING,
                "formula": ContentBlockType.FORMULA,
                "code": ContentBlockType.CODE,
                "list_item": ContentBlockType.LIST_ITEM,
                "caption": ContentBlockType.CAPTION,
                "table": ContentBlockType.TABLE,
            }
            btype = type_map.get(btype_raw, ContentBlockType.TEXT)

            # 公式收集
            if btype == ContentBlockType.FORMULA:
                formulas.append(content)
                # 清理 LaTeX 标记
                clean = content.strip()
                if clean.startswith("$$"):
                    clean = clean[2:]
                if clean.endswith("$$"):
                    clean = clean[:-2]
                if clean.startswith("$"):
                    clean = clean[1:]
                if clean.endswith("$"):
                    clean = clean[:-1]
                if clean not in formulas:
                    formulas.append(clean)

            bloom = self._detect_bloom(content)

            blocks.append(ContentBlock(
                block_id=block_id,
                type=btype,
                content=content,
                confidence=0.85,
                bloom_level=bloom,
            ))

        # Bloom 分布
        bloom_dist: Dict[str, int] = {}
        for b in blocks:
            if b.bloom_level:
                bloom_dist[b.bloom_level] = bloom_dist.get(b.bloom_level, 0) + 1

        return StructuredPage(
            page_id=page_id,
            raw_text=raw_text,
            blocks=blocks,
            title=parsed.get("title", ""),
            summary=parsed.get("summary", ""),
            topics=list(parsed.get("topics", [])),
            bloom_distribution=bloom_dist,
            formulas=formulas,
            language=parsed.get("language", "zh"),
            ocr_method="llm_vision",
        )

    def _from_rules(self, page_id: str, raw_text: str) -> StructuredPage:
        """规则管道"""
        lines = raw_text.split("\n")
        blocks: List[ContentBlock] = []
        formulas: List[str] = []
        title = ""
        block_id = 0
        current_type = ContentBlockType.TEXT
        buffer: List[str] = []

        def flush_buffer():
            nonlocal block_id, current_type
            if buffer:
                block_id += 1
                content = " ".join(buffer).strip()
                bloom = self._detect_bloom(content)
                blocks.append(ContentBlock(
                    block_id=block_id,
                    type=current_type,
                    content=content,
                    confidence=0.5,
                    bloom_level=bloom,
                ))
                buffer.clear()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush_buffer()
                current_type = ContentBlockType.TEXT
                continue

            # 标题检测
            if not title and self._is_title(stripped):
                title = stripped
                continue

            # 公式检测
            formula = self._extract_formula(stripped)
            if formula:
                flush_buffer()
                block_id += 1
                formulas.append(formula)
                blocks.append(ContentBlock(
                    block_id=block_id,
                    type=ContentBlockType.FORMULA,
                    content=formula,
                    confidence=0.7,
                    bloom_level="",
                ))
                continue

            # 代码块
            if stripped.startswith("```"):
                flush_buffer()
                current_type = ContentBlockType.CODE
                continue

            # 标题行
            if self._is_heading_line(stripped):
                flush_buffer()
                current_type = ContentBlockType.HEADING
                buffer.append(stripped)
                flush_buffer()
                current_type = ContentBlockType.TEXT
                continue

            # 列表项
            if stripped.startswith(("- ", "• ", "* ", "· ")) or re.match(r'^\d+[\.\)] ', stripped):
                flush_buffer()
                current_type = ContentBlockType.LIST_ITEM
                buffer.append(stripped)
                flush_buffer()
                current_type = ContentBlockType.TEXT
                continue

            buffer.append(stripped)

        flush_buffer()

        # Bloom 分布
        bloom_dist: Dict[str, int] = {}
        for b in blocks:
            if b.bloom_level:
                bloom_dist[b.bloom_level] = bloom_dist.get(b.bloom_level, 0) + 1

        # 知识点提取
        topics = self._extract_topics(raw_text)

        return StructuredPage(
            page_id=page_id,
            raw_text=raw_text,
            blocks=blocks,
            title=title,
            summary=self._generate_summary(blocks, title),
            topics=topics,
            bloom_distribution=bloom_dist,
            formulas=formulas,
            language=self._detect_language(raw_text),
            ocr_method="rules",
        )

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------
    def _is_title(self, line: str) -> bool:
        """判断是否为主标题"""
        for p in self.HEADING_PATTERNS:
            if re.match(p, line):
                return True
        # 全角英数字母大写开头 + 较短
        return bool(re.match(r'^[A-Z一-鿿]+[\s\w一-鿿]*$', line)) and len(line) < 60

    def _is_heading_line(self, line: str) -> bool:
        return bool(re.match(r'^\d+\.\d+\.?\s', line)) or bool(
            re.match(r'^[\(（]?[一二三四五六七八九十\d]+[\)）]', line)
        )

    def _extract_formula(self, text: str) -> str:
        """从文本行提取 LaTeX 公式"""
        # $$...$$
        for pattern in [r'\$\$(.*?)\$\$', r'\$(.*?)\$']:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
        # 纯 LaTeX 检测
        if re.match(r'^[\\a-zA-Z\{\}\[\]\(\)\^\_\=\+\-\*\/\s\.\,\;\:\!\>\<]+$', text):
            if any(re.search(p, text) for p in [r'\\frac', r'\\sum', r'\\int', r'\\prod']):
                return text.strip()
        return ""

    @staticmethod
    def _detect_bloom(text: str) -> str:
        """基于关键词检测 Bloom 层级"""
        scores: Dict[str, int] = {}
        for keyword, level in BLOOM_VERB_MAP.items():
            if keyword in text:
                scores[level] = scores.get(level, 0) + 1
        if not scores:
            return "understand"  # default
        return max(scores, key=scores.get)

    @staticmethod
    def _extract_topics(text: str, max_topics: int = 5) -> List[str]:
        """提取知识点"""
        # 简单基于高频名词 (production 用 jieba)
        try:
            import jieba
            words = jieba.lcut(text)
            # 过滤短词 + 停用词
            stop = {"的", "是", "在", "和", "了", "有", "不", "也", "中", "等", "或", "及"}
            candidates = [w for w in words if len(w) >= 2 and w not in stop]
            counts: Dict[str, int] = {}
            for w in candidates:
                counts[w] = counts.get(w, 0) + 1
            return [w for w, _ in sorted(counts.items(), key=lambda x: -x[1])[:max_topics]]
        except ImportError:
            # 无 jieba → 用正则抽取 2-4 字中文词
            words = re.findall(r'[一-鿿]{2,4}', text)
            unique = list(dict.fromkeys(words))[:max_topics]
            return unique

    @staticmethod
    def _detect_language(text: str) -> str:
        cn = len(re.findall(r'[一-鿿]', text))
        en = len(re.findall(r'[a-zA-Z]', text))
        if cn > en * 2:
            return "zh"
        if en > cn * 2:
            return "en"
        return "mixed"

    @staticmethod
    def _generate_summary(blocks: List[ContentBlock], title: str) -> str:
        """生成简短摘要"""
        text_blocks = [b.content for b in blocks if b.type == ContentBlockType.TEXT]
        first_text = text_blocks[0] if text_blocks else title
        return first_text[:120] + ("..." if len(first_text) > 120 else "")


# ================================================================
# OCREngine — 统一三级降级入口
# ================================================================
class OCREngine:
    """教材页面 OCR 统一引擎"""

    def __init__(self, llm_client: Any = None):
        self._preprocessor = ImagePreprocessor()
        self._vision = LLMVisionOCR(llm_client) if llm_client else None
        self._postprocessor = PagePostprocessor()

    def recognize(
        self,
        image_data: bytes,
        filename: str = "",
        timeout: int = OCR_TIMEOUT,
    ) -> StructuredPage:
        """识别教材页面

        Args:
            image_data: 图片原始字节
            filename: 原始文件名
            timeout: 超时

        Returns:
            StructuredPage
        """
        start = time.perf_counter()

        # -- Level 0: 预处理 ---
        if ImagePreprocessor.available():
            image_data = self._preprocessor.preprocess(image_data)

        image_b64 = base64.b64encode(image_data).decode()

        # -- Level 1a: 讯飞星火图像理解（优先，符合赛题工具要求）---
        try:
            from backend.app.services.multimodal.ocr.xunfei_image import XunfeiImageOCR
            if XunfeiImageOCR.credentials_present():
                xf = XunfeiImageOCR.from_config()
                if xf is not None:
                    parsed = xf.recognize(image_data)
                    if parsed:
                        page = self._postprocessor.process(
                            raw_text=(parsed.get("title", "") or "")
                            + "\n"
                            + "\n".join(
                                b.get("content", "") for b in parsed.get("blocks", []) or []
                            ),
                            llm_parsed=parsed,
                        )
                        page.elapsed_ms = (time.perf_counter() - start) * 1000
                        page.ocr_method = "xunfei_image"
                        return page
        except Exception as exc:
            logger.warning(f"[OCR] xunfei image failed, fall through: {exc}")

        # -- Level 1b: 通用 LLM Vision（如 qwen-vl / gpt-4o）---
        if self._vision and self._vision.available:
            parsed = self._vision.recognize(image_b64, timeout)
            if parsed:
                page = self._postprocessor.process(
                    raw_text=parsed.get("title", "") + "\n" +
                    "\n".join(b.get("content", "") for b in parsed.get("blocks", [])),
                    llm_parsed=parsed,
                )
                page.elapsed_ms = (time.perf_counter() - start) * 1000
                page.ocr_method = "llm_vision"
                return page

        # -- Level 2: Tesseract ---
        if TesseractOCR.available():
            tesseract = TesseractOCR()
            raw = tesseract.recognize(image_data)
            if raw:
                page = self._postprocessor.process(raw_text=raw)
                page.elapsed_ms = (time.perf_counter() - start) * 1000
                page.ocr_method = "tesseract"
                return page

        # -- Level 3: 降级信息展示 (不再抛错) ---
        meta_lines, meta_topics = _describe_image_meta(image_data, filename)
        raw_text = "\n".join(meta_lines)
        page = StructuredPage(
            page_id=hashlib.md5(image_data[:100]).hexdigest()[:16],
            raw_text=raw_text,
            title=filename or "教材页面",
            summary="OCR 引擎降级：已解析图片元数据；如需识别文字，请安装 Tesseract 或配置 Vision LLM。",
            topics=meta_topics,
            blocks=[
                ContentBlock(
                    block_id=idx + 1,
                    type=ContentBlockType.TEXT,
                    content=line,
                    confidence=0.2,
                    bloom_level="",
                )
                for idx, line in enumerate(meta_lines)
            ],
            ocr_method="degraded",
            elapsed_ms=(time.perf_counter() - start) * 1000,
        )
        return page


# ================================================================
# 降级信息辅助
# ================================================================
def _describe_image_meta(image_data: bytes, filename: str) -> Tuple[List[str], List[str]]:
    """在无 OCR 引擎时，至少能给前端返回一份可读的图片元数据说明。"""
    size_kb = round(len(image_data) / 1024, 1)
    lines: List[str] = [
        f"文件名：{filename or 'upload.png'}",
        f"图片体积：{size_kb} KB",
    ]
    topics: List[str] = ["图片元数据"]
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_data))
        lines.append(f"分辨率：{img.width}×{img.height}")
        lines.append(f"色彩模式：{img.mode}")
        topics.append(f"{img.width}×{img.height}")
    except Exception:
        pass
    lines.append("提示：当前环境未启用 OCR 引擎；安装 Tesseract 或在 .env 中配置 Vision LLM 后可自动切换到真实识别。")
    return lines, topics


# ================================================================
# 全局单例
# ================================================================
_engine: Optional[OCREngine] = None


def _resolve_default_llm_for_ocr() -> Any:
    """按需构造一个 LLM 客户端注入 OCR。

    OCR 只有在使用具备视觉理解能力的模型（如 qwen-vl、gpt-4o）时才有意义。
    通过环境变量 ``OCR_VISION_ENABLED=1`` 启用，避免误把普通文本 LLM 当成视觉模型调用。
    """
    if os.getenv("OCR_VISION_ENABLED", "").strip().lower() not in {"1", "true", "yes"}:
        return None
    try:
        from backend.app.core.llm_client import LLMClient
        return LLMClient()
    except Exception as exc:
        logger.warning(f"[OCR] failed to init default LLM client: {exc}")
        return None


def get_ocr_engine(llm_client: Any = None) -> OCREngine:
    global _engine
    if _engine is None:
        _engine = OCREngine(llm_client=llm_client or _resolve_default_llm_for_ocr())
    return _engine
