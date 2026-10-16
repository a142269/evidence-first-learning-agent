"""
课程知识库加载器
迁移自: 旧项目数据治理的 ETL 经验
- data_pipeline/etl_core.py 的数据清洗管道设计
- configs/data/source_tables.yaml 的数据源配置模式
- configs/data/quality_rules.yaml 的质量规则体系
- configs/data/field_mapping.yaml 的字段映射标准化思路
"""
import os
import json
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class KnowledgeChunk:
    """知识块 —— 借鉴旧项目的数据标准化模型"""
    chunk_id: str
    content: str
    source_file: str
    knowledge_points: List[str]  # 关联的知识点
    difficulty: str              # easy / medium / hard
    chunk_type: str              # definition / example / exercise / reference
    embedding: Optional[List[float]] = None
    metadata: dict = field(default_factory=dict)


class CourseKnowledgeLoader:
    """
    课程知识库加载器

    完全迁移旧项目 ETL 管道的设计思想:
    ┌──────────────────────────────────────────────────────┐
    │ 旧项目: 数据源 → 清洗(clean_rules) → 标准化(mapping) → 特征 │
    │ 新项目: 课程文档 → 预处理(quality_rules) → 知识点标准化 → 分块+嵌入 │
    └──────────────────────────────────────────────────────┘
    """

    # ---- 知识点标准化映射表 ----
    # 借鉴旧项目 field_mapping.yaml 的设计：多个来源 → 统一命名
    KNOWLEDGE_POINT_ALIASES = {
        "机器学习": ["machine learning", "ML", "统计学习"],
        "深度学习": ["deep learning", "DL", "深度神经网络"],
        "监督学习": ["supervised learning", "有监督学习"],
        "卷积神经网络": ["CNN", "convolutional neural network", "卷积网络"],
        "循环神经网络": ["RNN", "recurrent neural network", "递归神经网络"],
        "Transformer": ["transformer", "注意力机制", "attention mechanism"],
        "梯度下降": ["gradient descent", "SGD", "随机梯度下降"],
        "过拟合": ["overfitting", "over-fitting", "过配"],
        "正则化": ["regularization", "L1", "L2", "dropout"],
    }

    # ---- 内容质量规则 ----
    # 借鉴旧项目 configs/data/quality_rules.yaml
    QUALITY_RULES = {
        "min_content_length": 50,       # 最少50字符
        "max_content_length": 8000,     # 最多8000字符（一个chunk）
        "required_elements": [           # 必须包含的元素之一
            "定义", "概念", "原理", "公式", "代码", "示例"
        ],
        "noise_patterns": [             # 噪音模式
            r"^[\(\（].*[\)\）]$",       # 纯括号内容
            r"^第\d+页$",               # 页码
            r"^\d+/\d+$",               # 页码格式
        ]
    }

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.chunks: List[KnowledgeChunk] = []
        self.knowledge_graph: Dict[str, List[str]] = {}  # 知识点 → 前置知识点

    # ================================================================
    # 加载流程 —— 对应旧项目 ETL pipeline
    # ================================================================
    def load_course(self, course_name: str) -> List[KnowledgeChunk]:
        """加载一门课程的所有材料"""
        course_path = self.base_path / course_name

        # Step 1: 解析文档 —— 对应旧项目 define_source_schema
        documents = self._parse_documents(course_path)

        # Step 2: 清洗 —— 对应旧项目 clean_rules()
        cleaned = self._apply_clean_rules(documents)

        # Step 3: 标准化知识点 —— 对应旧项目 standardization()
        standardized = self._standardize_knowledge_points(cleaned)

        # Step 4: 分块 —— 对应旧项目 feature engineering 的窗口切分
        chunks = self._chunk_documents(standardized)

        self.chunks = chunks
        return chunks

    def _parse_documents(self, course_path: Path) -> List[dict]:
        """解析课程目录下的所有文档"""
        documents = []
        for ext in ["*.md", "*.txt", "*.json"]:
            for file_path in course_path.glob(f"**/{ext}"):
                with open(file_path, "r", encoding="utf-8") as f:
                    documents.append({
                        "source": str(file_path.relative_to(course_path)),
                        "content": f.read(),
                        "type": file_path.suffix,
                    })
        return documents

    def _apply_clean_rules(self, documents: List[dict]) -> List[dict]:
        """数据清洗 —— 直接复用旧项目的规则引擎设计模式"""
        cleaned = []
        for doc in documents:
            content = doc["content"]

            # 规则1: 长度检查
            if len(content) < self.QUALITY_RULES["min_content_length"]:
                continue
            if len(content) > self.QUALITY_RULES["max_content_length"]:
                # 过长文档将在 _chunk_documents 中处理
                pass

            # 规则2: 噪音过滤
            is_noise = False
            for pattern in self.QUALITY_RULES["noise_patterns"]:
                if re.match(pattern, content.strip()):
                    is_noise = True
                    break
            if is_noise:
                continue

            cleaned.append(doc)
        return cleaned

    def _standardize_knowledge_points(self, documents: List[dict]) -> List[dict]:
        """
        知识点标准化 —— 借鉴旧项目字段映射的设计

        旧项目: card_no → student_id, trans_time → event_time
        新项目: "ML" → "机器学习", "CNN" → "卷积神经网络"
        """
        for doc in documents:
            content = doc["content"]
            # 反向构建别名映射
            alias_to_standard = {}
            for standard, aliases in self.KNOWLEDGE_POINT_ALIASES.items():
                for alias in aliases:
                    alias_to_standard[alias.lower()] = standard

            # 识别并替换
            doc["knowledge_points"] = []
            for alias, standard in alias_to_standard.items():
                if alias in content.lower():
                    doc["knowledge_points"].append(standard)

            # 去重
            doc["knowledge_points"] = list(set(doc["knowledge_points"]))

        return documents

    def _chunk_documents(self, documents: List[dict]) -> List[KnowledgeChunk]:
        """文档分块 —— 借鉴旧项目时间窗口特征切分的思路"""
        chunks = []
        for doc in documents:
            content = doc["content"]
            source = doc["source"]

            # 按段落分块（自然语言文档）
            paragraphs = content.split("\n\n")

            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) < 2000:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk.strip():
                        chunk = self._create_chunk(
                            current_chunk, source, doc.get("knowledge_points", [])
                        )
                        chunks.append(chunk)
                    current_chunk = para + "\n\n"

            # 最后一个chunk
            if current_chunk.strip():
                chunk = self._create_chunk(
                    current_chunk, source, doc.get("knowledge_points", [])
                )
                chunks.append(chunk)

        return chunks

    def _create_chunk(
        self, content: str, source: str, knowledge_points: List[str]
    ) -> KnowledgeChunk:
        """创建知识块"""
        chunk_id = hashlib.md5(
            f"{source}:{content[:100]}".encode()
        ).hexdigest()[:12]

        # 判断难度（简单规则，实际可用LLM判断）
        difficulty = "medium"
        if any(kw in content for kw in ["基础", "入门", "简介", "概述"]):
            difficulty = "easy"
        if any(kw in content for kw in ["高级", "进阶", "推导", "证明"]):
            difficulty = "hard"

        # 判断类型
        chunk_type = "definition"
        if "示例" in content or "example" in content.lower() or "```" in content:
            chunk_type = "example"
        if "习题" in content or "练习" in content:
            chunk_type = "exercise"
        if "参考" in content or "引用" in content:
            chunk_type = "reference"

        return KnowledgeChunk(
            chunk_id=chunk_id,
            content=content.strip(),
            source_file=source,
            knowledge_points=knowledge_points,
            difficulty=difficulty,
            chunk_type=chunk_type,
        )
