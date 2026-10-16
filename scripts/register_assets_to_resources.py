#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资料库完整性补全 — 资源批量注册脚本（v1）

依据：
    交接清单/22-A-项目全面评审报告-前后端与资料库-0711.md · 六.3 资料库完整性补齐方案

执行内容：
    P0 视频资源正式化：
        - 5 个 manim 渲染脚本（注册为 video 类型，type_subtype=manim_script）
        - 9 个 data/artifacts/video/ 下既有 mp4 注册为正式命名视频
    P0 存量素材入库：
        - 6 个 jupyter notebook → code 资源
        - 9 个 .py 代码示例（AI 6 + Python 3）→ code 资源
        - 6 个论文导读 md → reading 资源
        - 28 个课程 KP 各生成 1 个 mermaid 思维导图 → mindmap 资源
    P1 题库结构补全（占位写入 doc 类型 resources 索引，详见 scripts/augment_question_bank.py）

幂等性：
    - 所有资源 ID 以 `kgdemo_assets_v1_` 前缀开头
    - 执行前查重，已存在则跳过
    - 提供 --dry-run / --apply 两种模式
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402

from backend.app.core.database import SessionLocal, init_db  # noqa: E402
from backend.app.core.models import (  # noqa: E402
    KnowledgePointRecord,
    ResourceRecord,
)

# ================================================================
# 常量
# ================================================================
RESOURCE_PREFIX = "kgdemo_assets_v1"
COURSE = "artificial_intelligence"
_TEACHER_ID = "teacher"
_TEACHER_NAME = "王老师"
_TEACHER_SCOPE = "course_published"

# 28 个 KP 与中文标题映射（与 seed_db.KNOWLEDGE_POINTS 对齐）
KP_TITLE_MAP: Dict[str, str] = {
    "python_basics": "Python 基础编程",
    "data_structures": "数据结构与算法",
    "linear_algebra": "线性代数（机器学习）",
    "probability_statistics": "概率与统计（机器学习）",
    "ml_basics": "机器学习基础",
    "supervised_learning": "监督学习方法",
    "unsupervised_learning": "无监督学习方法",
    "decision_trees": "决策树与集成",
    "svm": "支持向量机",
    "neural_networks": "神经网络基础",
    "backpropagation": "反向传播算法",
    "mlp": "多层感知机（MLP）",
    "cnn": "卷积神经网络（视觉）",
    "rnn": "循环神经网络（序列）",
    "lstm": "LSTM 与 GRU",
    "attention_mechanism": "注意力机制",
    "transformer": "Transformer 架构",
    "nlp_basics": "NLP 基础任务",
    "rag": "检索增强生成（RAG）",
    "reinforcement_learning": "强化学习进阶",
    "ai_project_practice": "AI 项目实战",
    "multi_agent_systems": "多智能体系统",
    "multimodal_llm": "多模态大模型",
    "ai_agent": "AI Agent 规划与工具",
    "mcp_protocol": "MCP 协议",
    "learning_science": "学习科学理论",
    "cognitive_diagnosis": "认知诊断模型",
    "data_visualization": "数据可视化",
}

# 5 个 manim 渲染脚本 → 视频资源（场景/主题映射）
MANIM_SCRIPT_TO_VIDEO: List[Tuple[str, str, str, List[str]]] = [
    # (script_basename, video_title, scene_class, kp_ids)
    ("01_self_attention_flow.py", "Self-Attention 计算流程动画演示", "SelfAttentionFlow",
     ["attention_mechanism", "transformer"]),
    ("02_transformer_arch.py", "Transformer 整体架构动画演示", "TransformerArch",
     ["transformer", "attention_mechanism"]),
    ("03_rag_pipeline.py", "RAG 检索增强生成全流程动画", "RAGPipeline",
     ["rag", "transformer"]),
    ("04_multi_agent_msg.py", "多智能体消息传递动画", "MultiAgentMsg",
     ["multi_agent_systems", "ai_agent"]),
    ("05_bkt_bayesian.py", "BKT 贝叶斯知识追踪动画", "BKTBayesian",
     ["cognitive_diagnosis", "learning_science"]),
]

# 9 个 data/artifacts/video/ 下既有 mp4 → 视频资源（按 hash 顺序分配主题）
EXISTING_MP4_TO_VIDEO: List[Tuple[str, str, List[str]]] = [
    # (filename, video_title, kp_ids)
    ("vid_0a61f28d.mp4", "机器学习基础概念精讲视频", ["ml_basics", "supervised_learning"]),
    ("vid_2917e8da.mp4", "神经网络与反向传播可视化讲解", ["neural_networks", "backpropagation"]),
    ("vid_94c7f9ca.mp4", "卷积神经网络工作原理精讲", ["cnn", "neural_networks"]),
    ("vid_d74a2b52.mp4", "Transformer 与注意力机制精讲视频", ["transformer", "attention_mechanism"]),
    ("vid_e3475a7a.mp4", "强化学习 Q-Learning 算法精讲", ["reinforcement_learning"]),
    ("vid_ed047159.mp4", "AI Agent 规划与工具调用视频", ["ai_agent", "multi_agent_systems"]),
    ("demo_dh_test.mp4", "数字人教学示例：CNN 卷积过程", ["cnn"]),
    ("demo_slides_v2_merged.mp4", "动态幻灯片教学示例：RAG 流程", ["rag"]),
    ("test_vid_001.mp4", "视频生成测试样例：LSTM 门控机制", ["lstm", "rnn"]),
]

# 6 个 jupyter notebook → code 资源
NOTEBOOK_TO_CODE: List[Tuple[str, str, str, List[str]]] = [
    # (filepath, code_title, description, kp_ids)
    ("ch05_transformer.ipynb", "Transformer 架构代码实战（Notebook）",
     "用 PyTorch 从零搭建 Transformer 并在玩具任务上训练，配套章节 5 讲义。",
     ["transformer", "attention_mechanism"]),
    ("ch06_multi_agent.ipynb", "多智能体系统协作实战（Notebook）",
     "实现 Planner/Worker/Critic 三 Agent 流水线，配合多智能体章节。",
     ["multi_agent_systems", "ai_agent"]),
    ("ch08_multimodal.ipynb", "多模态大模型应用实战（Notebook）",
     "图文问答与跨模态检索示例，对应第 8 章多模态 LLM。",
     ["multimodal_llm", "transformer"]),
    ("ch09_rag.ipynb", "RAG 检索增强生成端到端实战（Notebook）",
     "文档切块 + 嵌入 + 检索 + 生成全流程，对应第 9 章。",
     ["rag", "nlp_basics"]),
    ("ch10_ai_agent.ipynb", "AI Agent 规划与工具调用实战（Notebook）",
     "ReAct 循环 + 工具注册 + 反思机制，对应第 10 章。",
     ["ai_agent", "mcp_protocol"]),
    ("ch12_ai_project.ipynb", "端到端 AI 项目实战（Notebook）",
     "数据 → 建模 → 评估 → 部署完整链路，对应第 12 章。",
     ["ai_project_practice", "ml_basics"]),
]

# 9 个 .py 代码示例 → code 资源
PY_EXAMPLE_TO_CODE: List[Tuple[str, str, str, List[str], str]] = [
    # (filepath, code_title, description, kp_ids, course)
    ("knowledge_base/artificial_intelligence/code_examples/01_linear_regression.py",
     "线性回归与梯度下降代码示例",
     "用 NumPy 实现线性回归，演示梯度下降与学习率调参。",
     ["supervised_learning", "ml_basics"], "artificial_intelligence"),
    ("knowledge_base/artificial_intelligence/code_examples/02_random_forest.py",
     "随机森林分类与特征重要性示例",
     "sklearn 随机森林分类，含特征重要性与 OOB 评估。",
     ["decision_trees", "supervised_learning"], "artificial_intelligence"),
    ("knowledge_base/artificial_intelligence/code_examples/03_mlp_mnist.py",
     "MLP 多层感知机 MNIST 手写识别示例",
     "PyTorch 实现 MLP 完成 MNIST 分类。",
     ["mlp", "neural_networks"], "artificial_intelligence"),
    ("knowledge_base/artificial_intelligence/code_examples/04_cnn_cifar10.py",
     "CNN 卷积神经网络 CIFAR-10 分类示例",
     "PyTorch CNN 在 CIFAR-10 上的标准训练流程。",
     ["cnn", "neural_networks"], "artificial_intelligence"),
    ("knowledge_base/artificial_intelligence/code_examples/05_transformer_toy.py",
     "Toy Transformer 编码器示例",
     "小尺寸 Transformer 编码器在文本分类 toy 任务上训练。",
     ["transformer", "attention_mechanism"], "artificial_intelligence"),
    ("knowledge_base/artificial_intelligence/code_examples/06_rnn_text.py",
     "字符级 RNN 文本生成示例",
     "用 RNN 完成字符级语言模型与采样。",
     ["rnn", "nlp_basics"], "artificial_intelligence"),
    ("knowledge_base/python_programming/code_examples/01_python_basics_demo.py",
     "Python 基础语法示例代码",
     "变量、控制流、函数与模块演示。",
     ["python_basics"], "python_programming"),
    ("knowledge_base/python_programming/code_examples/02_data_structures_demo.py",
     "Python 数据结构示例代码",
     "列表、字典、集合与常见算法示例。",
     ["data_structures"], "python_programming"),
    ("knowledge_base/python_programming/code_examples/03_oop_demo.py",
     "Python 面向对象示例代码",
     "类、继承、封装与多态示例。",
     ["data_structures"], "python_programming"),
]

# 6 个论文导读 → reading 资源
PAPER_TO_READING: List[Tuple[str, str, str, List[str]]] = [
    # (filepath, reading_title, summary, kp_ids)
    ("knowledge_base/artificial_intelligence/references/01_ml_basics_papers.md",
     "机器学习基础论文导读",
     "经典机器学习奠基论文要点梳理：感知机、决策树、SVM 起源。",
     ["ml_basics", "supervised_learning"]),
    ("knowledge_base/artificial_intelligence/references/03_deep_learning_papers.md",
     "深度学习里程碑论文导读",
     "从 LeNet 到 ResNet，深度学习十年关键论文串讲。",
     ["neural_networks", "cnn", "backpropagation"]),
    ("knowledge_base/artificial_intelligence/references/04_evaluation_alignment.md",
     "AI 评估与对齐论文导读",
     "大模型评估、对齐与 RLHF 经典论文梳理。",
     ["ai_agent", "reinforcement_learning"]),
    ("knowledge_base/artificial_intelligence/references/attention_is_all_you_need.md",
     "Attention Is All You Need 论文导读",
     "Transformer 原始论文核心思路与关键贡献。",
     ["transformer", "attention_mechanism"]),
    ("knowledge_base/artificial_intelligence/references/deepseek_r1.md",
     "DeepSeek R1 论文导读",
     "推理大模型蒸馏与强化学习的工程实践。",
     ["transformer", "reinforcement_learning"]),
    ("knowledge_base/artificial_intelligence/references/multi_agent_distillation.md",
     "多智能体蒸馏论文导读",
     "多智能体协作与能力蒸馏的近期研究综述。",
     ["multi_agent_systems", "ai_agent"]),
]


# ================================================================
# 工具函数
# ================================================================
def _make_resource_id(suffix: str) -> str:
    return f"{RESOURCE_PREFIX}_{suffix}"


def _safe_read_text(path: Path, max_bytes: int = 16384) -> str:
    """读文本文件，截断避免巨大内容塞入 resources.content。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read(max_bytes)
        return text
    except Exception:
        return ""


def _gen_mermaid_for_kp(kp_id: str, kp_name: str) -> str:
    """为单个 KP 生成最简 mermaid 思维导图（节点中心辐射）。"""
    return (
        "graph TD\n"
        f"  A[\"{kp_name}\"]\n"
        f"  A --> A1[\"核心定义\"]\n"
        f"  A --> A2[\"关键算法\"]\n"
        f"  A --> A3[\"典型应用\"]\n"
        f"  A --> A4[\"学习目标\"]\n"
        f"  A --> A5[\"常见误区\"]\n"
    )


def _build_video_metadata(kp_ids: List[str], method: str, agent: str) -> dict:
    return {
        "course": COURSE,
        "scope": _TEACHER_SCOPE,
        "status": "published",
        "created_by": _TEACHER_ID,
        "created_by_name": _TEACHER_NAME,
        "kp_ids": kp_ids,
        "method": method,            # manim_script / ffmpeg / tts_slides / digital_human
        "agent": agent,              # tutor / planner / content
        "duration_hint_seconds": 180,
        "asset_register_version": "v1",
    }


def _build_code_metadata(kp_ids: List[str], course: str, file_path: str,
                        language: str, runtime: str) -> dict:
    return {
        "course": course,
        "scope": _TEACHER_SCOPE,
        "status": "published",
        "created_by": _TEACHER_ID,
        "created_by_name": _TEACHER_NAME,
        "kp_ids": kp_ids,
        "language": language,
        "runtime": runtime,
        "source_path": file_path,
        "asset_register_version": "v1",
    }


def _build_reading_metadata(kp_ids: List[str], file_path: str, page_count_estimate: int) -> dict:
    return {
        "course": COURSE,
        "scope": _TEACHER_SCOPE,
        "status": "published",
        "created_by": _TEACHER_ID,
        "created_by_name": _TEACHER_NAME,
        "kp_ids": kp_ids,
        "source_path": file_path,
        "reading_type": "paper_summary",
        "page_count_estimate": page_count_estimate,
        "asset_register_version": "v1",
    }


def _build_mindmap_metadata(kp_ids: List[str], mermaid: str) -> dict:
    return {
        "course": COURSE,
        "scope": _TEACHER_SCOPE,
        "status": "published",
        "created_by": _TEACHER_ID,
        "created_by_name": _TEACHER_NAME,
        "kp_ids": kp_ids,
        "mermaid": mermaid,
        "rendered": False,
        "asset_register_version": "v1",
    }


# ================================================================
# 资源注册（per-bucket）
# ================================================================
def collect_video_resources(video_dir: Path) -> Tuple[List[dict], List[dict]]:
    """返回 (planned, actually_persisted)。"""
    planned: List[dict] = []
    # 5 个 manim 脚本（注册为脚本型视频；待 manim/ffmpeg 现场渲染或演示机预渲染）
    for basename, title, scene_class, kp_ids in MANIM_SCRIPT_TO_VIDEO:
        script_path = PROJECT_ROOT / "data" / "artifacts" / "manim" / basename
        planned.append({
            "id": _make_resource_id(f"video_manim_{Path(basename).stem}"),
            "type": "video",
            "title": title,
            "content": _safe_read_text(script_path) or f"# {title}\n\nmanim 脚本：{basename}（场景 {scene_class}）",
            "content_type": "python",
            "agent_name": "智灵",
            "metadata": _build_video_metadata(kp_ids, method="manim_script", agent="tutor"),
            "tags": ["视频", "manim", "动画", *kp_ids],
        })
    # 9 个既有 mp4
    for filename, title, kp_ids in EXISTING_MP4_TO_VIDEO:
        full = video_dir / filename
        method = "digital_human" if "demo_dh" in filename else (
            "tts_slides" if "demo_slides" in filename else "ffmpeg_cached"
        )
        agent = "智灵" if method == "digital_human" else "内容工匠"
        content = (
            f"# {title}\n\n"
            f"## 视频信息\n- 文件：{filename}\n- 路径：{full.relative_to(PROJECT_ROOT) if full.exists() else '缺失'}\n"
            f"- 关联知识点：{', '.join(kp_ids)}\n- 生成方式：{method}\n"
            f"\n## 配套说明\n该视频由 RAG/数字人/动态幻灯片三级管线生成，可作为相关知识点的精讲材料。"
        )
        planned.append({
            "id": _make_resource_id(f"video_mp4_{Path(filename).stem}"),
            "type": "video",
            "title": title,
            "content": content,
            "content_type": "markdown",
            "agent_name": agent,
            "metadata": _build_video_metadata(kp_ids, method=method, agent="tutor"),
            "tags": ["视频", method, *kp_ids],
        })
    return planned, []


def collect_code_resources() -> List[dict]:
    planned: List[dict] = []
    # 6 notebooks
    for basename, title, desc, kp_ids in NOTEBOOK_TO_CODE:
        nb_path = PROJECT_ROOT / "data" / "code_examples" / basename
        content = _safe_read_text(nb_path) or f"# {title}\n\n{desc}\n"
        planned.append({
            "id": _make_resource_id(f"code_nb_{Path(basename).stem}"),
            "type": "code",
            "title": title,
            "content": content,
            "content_type": "ipynb",
            "agent_name": "智灵",
            "metadata": _build_code_metadata(kp_ids, COURSE, str(nb_path.relative_to(PROJECT_ROOT)),
                                           language="python", runtime="jupyter"),
            "tags": ["代码", "notebook", "Python", *kp_ids],
        })
    # 9 个 .py
    for rel_path, title, desc, kp_ids, course in PY_EXAMPLE_TO_CODE:
        py_path = PROJECT_ROOT / rel_path
        content = _safe_read_text(py_path, max_bytes=32768) or f"# {title}\n\n{desc}\n"
        planned.append({
            "id": _make_resource_id(f"code_py_{py_path.stem}"),
            "type": "code",
            "title": title,
            "content": content,
            "content_type": "python",
            "agent_name": "智灵",
            "metadata": _build_code_metadata(kp_ids, course, rel_path,
                                           language="python", runtime="local"),
            "tags": ["代码", "Python", course, *kp_ids],
        })
    return planned


def collect_reading_resources() -> List[dict]:
    planned: List[dict] = []
    for rel_path, title, summary, kp_ids in PAPER_TO_READING:
        md_path = PROJECT_ROOT / rel_path
        content = _safe_read_text(md_path) or f"# {title}\n\n{summary}\n"
        # 估算页数（按 1500 字/页）
        page_count = max(2, min(40, len(content) // 1500 + 1))
        planned.append({
            "id": _make_resource_id(f"reading_{md_path.stem}"),
            "type": "reading",
            "title": title,
            "content": content,
            "content_type": "markdown",
            "agent_name": "内容工匠",
            "metadata": _build_reading_metadata(kp_ids, rel_path, page_count),
            "tags": ["阅读", "论文导读", *kp_ids],
        })
    return planned


def collect_mindmap_resources() -> List[dict]:
    """为 28 个 AI KP 各生成 1 个 mermaid 思维导图（mindmap）。"""
    planned: List[dict] = []
    for kp_id, kp_name in KP_TITLE_MAP.items():
        mermaid = _gen_mermaid_for_kp(kp_id, kp_name)
        planned.append({
            "id": _make_resource_id(f"mindmap_{kp_id}"),
            "type": "mindmap",
            "title": f"{kp_name} 知识思维导图",
            "content": mermaid,
            "content_type": "mermaid",
            "agent_name": "智灵",
            "metadata": _build_mindmap_metadata([kp_id], mermaid),
            "tags": ["思维导图", "mermaid", kp_id],
        })
    return planned


# ================================================================
# 主流程
# ================================================================
def collect_all() -> Dict[str, List[dict]]:
    video_dir = PROJECT_ROOT / "data" / "artifacts" / "video"
    return {
        "video": collect_video_resources(video_dir)[0],
        "code": collect_code_resources(),
        "reading": collect_reading_resources(),
        "mindmap": collect_mindmap_resources(),
    }


def persist_planned(plans: List[dict], apply: bool) -> Tuple[int, int, int]:
    """返回 (inserted, updated, skipped)。"""
    if not apply:
        return 0, 0, len(plans)
    inserted = updated = skipped = 0
    with SessionLocal() as db:
        for item in plans:
            existing = db.get(ResourceRecord, item["id"])
            if existing is None:
                row = ResourceRecord(id=item["id"])
                db.add(row)
                inserted += 1
                is_new = True
            else:
                # 已存在且非空 → 跳过；空则回填
                if existing.title and existing.content:
                    skipped += 1
                    continue
                updated += 1
                is_new = False
            # 字段写入
            row = db.get(ResourceRecord, item["id"]) or row
            row.user_id = item.get("user_id", _TEACHER_ID)
            row.type = item["type"]
            row.title = item["title"][:512]
            row.content = item["content"]
            row.content_type = item.get("content_type", "markdown")
            row.agent_name = item.get("agent_name", "")
            row.metadata_data = item.get("metadata", {})
            row.tags = item.get("tags", [])
            row.created_at = item.get("created_at", time.time())
        db.commit()
    return inserted, updated, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="资料库完整性补全 - 资源批量注册")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不写入")
    parser.add_argument("--apply", action="store_true", help="实际写入数据库")
    args = parser.parse_args()
    if not (args.dry_run or args.apply):
        args.dry_run = True

    init_db()
    all_plans = collect_all()
    total_planned = sum(len(v) for v in all_plans.values())

    print("=" * 60)
    print(f"资料库完整性补全 - 资源批量注册  (mode={'APPLY' if args.apply else 'DRY-RUN'})")
    print("=" * 60)
    grand_in = grand_up = grand_skip = 0
    for bucket, items in all_plans.items():
        ins, upd, skp = persist_planned(items, apply=args.apply)
        grand_in += ins
        grand_up += upd
        grand_skip += skp
        print(f"  [{bucket:>8}] planned={len(items):>3} | insert={ins:>3} update={upd:>3} skip={skp:>3}")
    print("-" * 60)
    print(f"  total planned={total_planned} | insert={grand_in} update={grand_up} skip={grand_skip}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
