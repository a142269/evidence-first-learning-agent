#!/usr/bin/env python3
"""Day 5 - 给 knowledge_base/artificial_intelligence/chapters/*.md 加 YAML frontmatter。

幂等：再次运行会用 CHAPTER_META 字典覆写已存在的 frontmatter。

用法:
    python -m scripts.build_chapter_frontmatter            # 写入所有章节
    python -m scripts.build_chapter_frontmatter --check    # 仅打印 diff
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHAPTERS_DIR = PROJECT_ROOT / "knowledge_base" / "artificial_intelligence" / "chapters"

# ============================================================
# 元数据：与 data/seed_extended.json 的 20 KP + 题库 Bloom 等级对齐
# ============================================================
# 字段：
#   chapter_id     与文件名前缀一致（2 位数字字符串）
#   slug           文件名去掉数字前缀的核心标识
#   title          章节标题，与正文 H1 一致
#   kp_ids         覆盖的 KP（来自 seed_extended.json）；空列表表示该章节为应用 / 进阶
#                  补充（如 Multi-Agent / MCP / AI Agent），不直接对应任何单一 KP
#   bloom_focus    主要训练的 Bloom 等级，1-3 个
#   prerequisites  推荐先修章节 ID 列表
#   estimated_minutes  自学预计耗时
# ============================================================
CHAPTER_META: dict[str, dict] = {
    "00": {
        "chapter_id": "00",
        "slug": "ai_overview",
        "title": "人工智能导论",
        "kp_ids": ["ml_basics"],
        "bloom_focus": ["Remember", "Understand"],
        "prerequisites": [],
        "estimated_minutes": 40,
    },
    "01": {
        "chapter_id": "01",
        "slug": "ml_fundamentals",
        "title": "机器学习基础",
        "kp_ids": ["ml_basics"],
        "bloom_focus": ["Understand", "Apply"],
        "prerequisites": ["00"],
        "estimated_minutes": 60,
    },
    "02": {
        "chapter_id": "02",
        "slug": "math_foundations",
        "title": "数学基础",
        "kp_ids": ["linear_algebra", "probability_statistics"],
        "bloom_focus": ["Understand"],
        "prerequisites": [],
        "estimated_minutes": 60,
    },
    "03": {
        "chapter_id": "03",
        "slug": "neural_network_basics",
        "title": "神经网络基础",
        "kp_ids": ["neural_networks"],
        "bloom_focus": ["Understand", "Apply"],
        "prerequisites": ["01", "02"],
        "estimated_minutes": 50,
    },
    "04": {
        "chapter_id": "04",
        "slug": "cnn_and_vision",
        "title": "卷积神经网络与视觉",
        "kp_ids": ["cnn"],
        "bloom_focus": ["Apply", "Analyze"],
        "prerequisites": ["03"],
        "estimated_minutes": 50,
    },
    "05": {
        "chapter_id": "05",
        "slug": "transformer_and_llm",
        "title": "Transformer 与大语言模型",
        "kp_ids": ["transformer", "attention_mechanism"],
        "bloom_focus": ["Analyze", "Evaluate"],
        "prerequisites": ["03", "18"],
        "estimated_minutes": 70,
    },
    "06": {
        "chapter_id": "06",
        "slug": "multi_agent_systems",
        "title": "多智能体系统",
        "kp_ids": [],
        "bloom_focus": ["Analyze", "Create"],
        "prerequisites": ["10"],
        "estimated_minutes": 45,
    },
    "07": {
        "chapter_id": "07",
        "slug": "reinforcement_learning",
        "title": "强化学习",
        "kp_ids": ["reinforcement_learning"],
        "bloom_focus": ["Understand", "Apply", "Analyze"],
        "prerequisites": ["01", "02"],
        "estimated_minutes": 60,
    },
    "08": {
        "chapter_id": "08",
        "slug": "multimodal_llm",
        "title": "多模态大模型",
        "kp_ids": [],
        "bloom_focus": ["Apply", "Analyze"],
        "prerequisites": ["04", "05"],
        "estimated_minutes": 50,
    },
    "09": {
        "chapter_id": "09",
        "slug": "rag",
        "title": "检索增强生成 (RAG)",
        "kp_ids": ["rag"],
        "bloom_focus": ["Apply", "Evaluate"],
        "prerequisites": ["05", "19"],
        "estimated_minutes": 55,
    },
    "10": {
        "chapter_id": "10",
        "slug": "ai_agent",
        "title": "AI Agent 智能体",
        "kp_ids": [],
        "bloom_focus": ["Apply", "Analyze"],
        "prerequisites": ["05"],
        "estimated_minutes": 50,
    },
    "11": {
        "chapter_id": "11",
        "slug": "mcp_protocol",
        "title": "MCP 模型上下文协议",
        "kp_ids": [],
        "bloom_focus": ["Understand", "Apply"],
        "prerequisites": ["10"],
        "estimated_minutes": 40,
    },
    "12": {
        "chapter_id": "12",
        "slug": "ai_project_practice",
        "title": "AI 项目实战",
        "kp_ids": ["ai_project_practice"],
        "bloom_focus": ["Apply", "Create"],
        "prerequisites": ["01", "04", "05", "09"],
        "estimated_minutes": 75,
    },
    "13": {
        "chapter_id": "13",
        "slug": "supervised_learning",
        "title": "监督学习",
        "kp_ids": ["supervised_learning", "ml_basics"],
        "bloom_focus": ["Understand", "Apply"],
        "prerequisites": ["01", "02"],
        "estimated_minutes": 55,
    },
    "14": {
        "chapter_id": "14",
        "slug": "unsupervised_learning",
        "title": "无监督学习",
        "kp_ids": ["unsupervised_learning"],
        "bloom_focus": ["Understand", "Apply"],
        "prerequisites": ["01"],
        "estimated_minutes": 50,
    },
    "15": {
        "chapter_id": "15",
        "slug": "decision_trees_ensemble",
        "title": "决策树与集成学习",
        "kp_ids": ["decision_trees", "supervised_learning"],
        "bloom_focus": ["Apply", "Analyze"],
        "prerequisites": ["13"],
        "estimated_minutes": 55,
    },
    "16": {
        "chapter_id": "16",
        "slug": "svm",
        "title": "支持向量机",
        "kp_ids": ["svm", "supervised_learning"],
        "bloom_focus": ["Analyze", "Evaluate"],
        "prerequisites": ["02", "13"],
        "estimated_minutes": 55,
    },
    "17": {
        "chapter_id": "17",
        "slug": "backpropagation",
        "title": "反向传播与优化器",
        "kp_ids": ["backpropagation", "neural_networks"],
        "bloom_focus": ["Analyze", "Apply"],
        "prerequisites": ["02", "03"],
        "estimated_minutes": 60,
    },
    "18": {
        "chapter_id": "18",
        "slug": "rnn_and_lstm",
        "title": "循环神经网络与 LSTM",
        "kp_ids": ["rnn", "lstm"],
        "bloom_focus": ["Apply", "Analyze"],
        "prerequisites": ["03", "17"],
        "estimated_minutes": 55,
    },
    "19": {
        "chapter_id": "19",
        "slug": "nlp_basics",
        "title": "NLP 基础",
        "kp_ids": ["nlp_basics"],
        "bloom_focus": ["Understand", "Apply"],
        "prerequisites": ["18"],
        "estimated_minutes": 50,
    },
}

assert len(CHAPTER_META) == 20, "CHAPTER_META must have exactly 20 entries"


FRONTMATTER_DELIM = "---"


def parse_existing_frontmatter(text: str) -> tuple[dict | None, str]:
    """如果文件已带 frontmatter，返回 (meta_dict, body_after)；否则 (None, original_text)。"""
    if not text.startswith(FRONTMATTER_DELIM + "\n"):
        return None, text
    end = text.find("\n" + FRONTMATTER_DELIM + "\n", len(FRONTMATTER_DELIM) + 1)
    if end == -1:
        return None, text
    yaml_block = text[len(FRONTMATTER_DELIM) + 1 : end]
    body = text[end + len("\n" + FRONTMATTER_DELIM + "\n") :]
    try:
        meta = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return None, text
    return meta, body


def build_frontmatter(meta: dict) -> str:
    dump = yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    return f"{FRONTMATTER_DELIM}\n{dump}{FRONTMATTER_DELIM}\n"


def find_chapter_files() -> list[Path]:
    paths: list[Path] = []
    for cid in sorted(CHAPTER_META.keys()):
        slug = CHAPTER_META[cid]["slug"]
        match = CHAPTERS_DIR / f"{cid}_{slug}.md"
        if not match.exists():
            print(f"[chapter-meta] WARN missing file: {match}", file=sys.stderr)
            continue
        paths.append(match)
    return paths


def apply_frontmatter(path: Path, meta: dict, dry_run: bool = False) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    _, body = parse_existing_frontmatter(text)
    body = body.lstrip("\n")
    new_text = build_frontmatter(meta) + body
    if new_text == text:
        return False, "unchanged"
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True, "rewrote"


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 5 chapter frontmatter writer")
    parser.add_argument("--check", action="store_true", help="dry-run, do not write")
    args = parser.parse_args()

    changed = 0
    for path in find_chapter_files():
        cid = path.name[:2]
        meta = CHAPTER_META[cid]
        wrote, note = apply_frontmatter(path, meta, dry_run=args.check)
        marker = "*" if wrote else " "
        print(f"  {marker} {path.name:50s} {note}")
        if wrote:
            changed += 1
    verb = "would update" if args.check else "updated"
    print(f"[chapter-meta] {verb} {changed} / {len(CHAPTER_META)} files")


if __name__ == "__main__":
    main()
