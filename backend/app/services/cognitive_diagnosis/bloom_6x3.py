"""Bloom 6×3 子层级详细配置（Anderson & Krathwohl 2001 完整版）

每个认知过程维度 × 知识维度 的交叉点定义了学习目标。
本文件为 YAML 配置，供 bloom_taxonomy.py 动态加载。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent / "bloom_6x3_config.yaml"


def _default_config() -> dict[str, Any]:
    """内置默认配置，无需外部 YAML 也能运行。"""
    return {
        "cognitive_dimensions": {
            "remember": {
                "label": "记忆",
                "sub_levels": {
                    "recognizing": {
                        "label": "识别",
                        "definition": "从长时记忆中识别相关知识",
                        "keywords": ["识别", "匹配", "选择", "辨认", "identify", "recognize"],
                        "examples": ["识别下列代码中的语法错误", "匹配术语与定义"],
                        "anti_examples": ["解释为什么该语法错误会发生"],  # 这是 understand
                    },
                    "recalling": {
                        "label": "回忆",
                        "definition": "从长时记忆中提取相关知识",
                        "keywords": ["回忆", "列举", "描述", "复述", "recall", "list"],
                        "examples": ["回忆卷积核的定义", "列举 5 种优化算法"],
                        "anti_examples": ["比较梯度下降与牛顿法"],  # 这是 analyze
                    },
                },
            },
            "understand": {
                "label": "理解",
                "sub_levels": {
                    "interpreting": {
                        "label": "解释",
                        "definition": "将信息从一种形式转换为另一种形式",
                        "keywords": ["解释", "转换", "改写", "paraphrase", "interpret"],
                        "examples": ["用自己的话解释反向传播", "将伪代码转为流程图"],
                        "anti_examples": ["设计一个更高效的反向传播变体"],  # create
                    },
                    "exemplifying": {
                        "label": "举例",
                        "definition": "找到具体例子说明概念",
                        "keywords": ["举例", "实例", "示范", "example", "illustrate"],
                        "examples": ["给出一个过拟合的实例", "示范 dropout 的使用场景"],
                        "anti_examples": ["评估 dropout 的效果"],  # evaluate
                    },
                    "classifying": {
                        "label": "分类",
                        "definition": "将某事物归入某一类别",
                        "keywords": ["分类", "归类", "区分", "classify", "categorize"],
                        "examples": ["将以下算法归类为监督/无监督", "区分 CNN 与 RNN 的适用场景"],
                        "anti_examples": ["分析分类错误的根因"],  # analyze
                    },
                    "summarizing": {
                        "label": "概括",
                        "definition": "提炼主要思想或观点",
                        "keywords": ["概括", "总结", "归纳", "summarize", "abstract"],
                        "examples": ["概括 Transformer 的核心思想", "总结论文的主要贡献"],
                        "anti_examples": ["评价论文贡献的原创性"],  # evaluate
                    },
                    "inferring": {
                        "label": "推断",
                        "definition": "从已知信息中推导结论",
                        "keywords": ["推断", "推导", "预测", "infer", "extrapolate"],
                        "examples": ["根据训练曲线推断学习率是否合适", "预测增加层数的影响"],
                        "anti_examples": ["设计实验验证该推断"],  # create
                    },
                    "comparing": {
                        "label": "比较",
                        "definition": "发现两个事物之间的相似与差异",
                        "keywords": ["比较", "对比", "区分", "compare", "contrast"],
                        "examples": ["比较 Adam 与 SGD 的收敛特性", "对比 L1 与 L2 正则化"],
                        "anti_examples": ["评估哪种优化器更适合当前任务"],  # evaluate
                    },
                    "explaining": {
                        "label": "说明",
                        "definition": "构建并运用因果模型",
                        "keywords": ["说明", "解释", "为何", "explain", "why"],
                        "examples": ["说明 batch normalization 为何加速训练", "解释梯度消失的原因"],
                        "anti_examples": ["实现 batch normalization 的前向传播"],  # apply
                    },
                },
            },
            "apply": {
                "label": "应用",
                "sub_levels": {
                    "executing": {
                        "label": "执行",
                        "definition": "面对熟悉任务时执行程序",
                        "keywords": ["执行", "计算", "应用", "execute", "carry out"],
                        "examples": ["执行一次前向传播计算", "应用给定的公式计算损失"],
                        "anti_examples": ["优化公式以提升计算效率"],  # create
                    },
                    "implementing": {
                        "label": "实施",
                        "definition": "面对不熟悉任务时实施程序",
                        "keywords": ["实现", "实施", "编码", "implement", "code"],
                        "examples": ["实现注意力机制", "用 PyTorch 编码一个残差块"],
                        "anti_examples": ["分析残差连接为何有效"],  # analyze
                    },
                },
            },
            "analyze": {
                "label": "分析",
                "sub_levels": {
                    "differentiating": {
                        "label": "区分",
                        "definition": "区分相关与不相关的部分",
                        "keywords": ["区分", "筛选", "鉴别", "differentiate", "discriminate"],
                        "examples": ["区分相关特征与噪声", "鉴别过拟合与欠拟合信号"],
                        "anti_examples": ["设计去噪方案"],  # create
                    },
                    "organizing": {
                        "label": "组织",
                        "definition": "识别并整合各要素之间的结构",
                        "keywords": ["组织", "结构", "整合", "organize", "structure"],
                        "examples": ["组织模型各层的依赖关系", "整合多源数据为统一表示"],
                        "anti_examples": ["评估该表示的质量"],  # evaluate
                    },
                    "attributing": {
                        "label": "归因",
                        "definition": "确定现象背后的潜在原因或意图",
                        "keywords": ["归因", "归因于", "attribute", "ascribe"],
                        "examples": ["将性能下降归因于数据分布偏移", "分析错误归因于梯度爆炸"],
                        "anti_examples": ["提出解决梯度爆炸的方案"],  # create
                    },
                },
            },
            "evaluate": {
                "label": "评价",
                "sub_levels": {
                    "checking": {
                        "label": "检验",
                        "definition": "检测内部矛盾或谬误",
                        "keywords": ["检验", "检查", "验证", "check", "verify"],
                        "examples": ["检验模型输出的逻辑一致性", "检查超参数设置是否合理"],
                        "anti_examples": ["修正不一致的输出"],  # create
                    },
                    "critiquing": {
                        "label": "评判",
                        "definition": "基于标准做出判断",
                        "keywords": ["评判", "评价", "判断", "critique", "judge"],
                        "examples": ["评判该论文方法的创新性", "评价模型在实际场景中的可用性"],
                        "anti_examples": ["提出改进该方法的方案"],  # create
                    },
                },
            },
            "create": {
                "label": "创造",
                "sub_levels": {
                    "generating": {
                        "label": "生成",
                        "definition": "从现有要素中提出新假设或观点",
                        "keywords": ["生成", "提出", "假设", "generate", "hypothesize"],
                        "examples": ["生成一个改进注意力机制的新假设", "提出一种新的数据增强策略"],
                        "anti_examples": ["验证该假设是否成立"],  # evaluate
                    },
                    "planning": {
                        "label": "计划",
                        "definition": "设计达成目标的步骤",
                        "keywords": ["计划", "设计", "规划", "plan", "design"],
                        "examples": ["设计一个完整的实验方案", "规划模型架构搜索的策略"],
                        "anti_examples": ["执行该实验方案"],  # apply
                    },
                    "producing": {
                        "label": "建构",
                        "definition": "创造新产品或观点",
                        "keywords": ["建构", "开发", "创建", "produce", "construct"],
                        "examples": ["开发一个新颖的模型架构", "构建一个端到端的学习系统"],
                        "anti_examples": ["评估该系统的性能"],  # evaluate
                    },
                },
            },
        },
        "knowledge_dimensions": {
            "factual": {"label": "事实性", "description": "术语、细节、要素"},
            "conceptual": {"label": "概念性", "description": "分类、原理、理论、模型"},
            "procedural": {"label": "程序性", "description": "技能、算法、方法、准则"},
            "metacognitive": {"label": "元认知", "description": "策略、自我认知、情境知识"},
        },
    }


class Bloom6x3Config:
    """Anderson & Krathwohl 2001 完整版 6×3/6×4 配置管理器。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _CONFIG_PATH
        self._data: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        if self._data is not None:
            return self._data
        if self.path.exists():
            try:
                text = self.path.read_text(encoding="utf-8")
                self._data = yaml.safe_load(text)
            except Exception:
                self._data = _default_config()
        else:
            self._data = _default_config()
        return self._data

    def get_sub_level(self, level: str, sub: str) -> dict[str, Any]:
        data = self.load()
        return data.get("cognitive_dimensions", {}).get(level, {}).get("sub_levels", {}).get(sub, {})

    def get_knowledge_dim(self, kd: str) -> dict[str, Any]:
        data = self.load()
        return data.get("knowledge_dimensions", {}).get(kd, {})

    def all_cognitive_levels(self) -> list[str]:
        data = self.load()
        return list(data.get("cognitive_dimensions", {}).keys())

    def sub_levels_for(self, level: str) -> list[str]:
        data = self.load()
        return list(data.get("cognitive_dimensions", {}).get(level, {}).get("sub_levels", {}).keys())

    # 高层认知（create/evaluate/analyze）应压过低层——即使命中次数相同，
    # 也倾向于把带有 “设计/构建/评价/分析” 的题目归为更高层。
    _LEVEL_WEIGHT: dict[str, float] = {
        "remember": 1.0,
        "understand": 1.05,
        "apply": 1.15,
        "analyze": 1.25,
        "evaluate": 1.35,
        "create": 1.5,
    }

    def classify_text(self, text: str) -> dict[str, Any]:
        """基于关键词匹配，返回最匹配的 (level, sub_level, knowledge_dim)。

        计分：命中次数 × 层级权重（高阶认知加成），避免 “设计…对比…”
        这类既有 create 又有 understand 关键词的题目错分为“比较”。
        """
        data = self.load()
        text_lower = text.lower()
        best_weighted = 0.0
        best_hits = 0
        best = {"level": "understand", "sub_level": "interpreting", "knowledge_dim": "conceptual"}

        for level, level_info in data.get("cognitive_dimensions", {}).items():
            weight = self._LEVEL_WEIGHT.get(level, 1.0)
            for sub, sub_info in level_info.get("sub_levels", {}).items():
                kws = sub_info.get("keywords", [])
                hits = sum(1 for kw in kws if kw and kw in text_lower)
                if hits == 0:
                    continue
                weighted = hits * weight
                if weighted > best_weighted:
                    best_weighted = weighted
                    best_hits = hits
                    best = {"level": level, "sub_level": sub, "knowledge_dim": "conceptual"}

        # 知识维度判断（词库扩充：程序性 & 概念性 覆盖数据结构 / 算法 / 模型 / 方法）
        proc_kws = [
            "代码", "code", "实现", "算法", "程序", "步骤", "流程", "过程",
            "python", "pytorch", "tensorflow", "java", "c++", "sql",
            "遍历", "递归", "查找", "排序",
        ]
        concept_kws = [
            "原理", "概念", "理论", "分类", "模型", "定义",
            "范式", "假设", "定理", "公式",
            "k-means", "dbscan", "聚类", "回归", "分类器",
        ]
        meta_kws = [
            "策略", "反思", "监控", "元认知", "方法论",
        ]
        code_indicators = sum(1 for t in proc_kws if t in text_lower)
        concept_indicators = sum(1 for t in concept_kws if t in text_lower)
        meta_indicators = sum(1 for t in meta_kws if t in text_lower)
        if meta_indicators > code_indicators and meta_indicators > concept_indicators:
            best["knowledge_dim"] = "metacognitive"
        # 程序性动词命中且不弱于概念性 → 程序性（"实现" 应优先于 "机制/模型"）
        elif code_indicators > 0 and code_indicators >= concept_indicators:
            best["knowledge_dim"] = "procedural"
        elif concept_indicators > 0:
            best["knowledge_dim"] = "conceptual"
        else:
            best["knowledge_dim"] = "factual"

        return {**best, "score": best_hits, "method": "keyword"}


_bloom6x3: Bloom6x3Config | None = None


def get_bloom6x3_config() -> Bloom6x3Config:
    global _bloom6x3
    if _bloom6x3 is None:
        _bloom6x3 = Bloom6x3Config()
    return _bloom6x3
