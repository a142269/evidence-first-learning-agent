"""
知识图谱构建器 —— 从 Markdown 知识库提取知识点实体和关系

双通道策略：
  1) 正则通道（确定性、毫秒级）：从 ##/### 标题、加粗术语、代码块标签提取实体，
     从"前提""前置""依赖"等关键词推断 prerequisite 关系
  2) LLM 通道（可选增强）：抽取正则漏掉的隐含实体和 analogous 关系

实体落入 knowledge_points 表，关系落入 kp_relations 表。
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.services.knowledge_graph.store import KnowledgeGraphStore

logger = logging.getLogger(__name__)

# ── 正则规则 ────────────────────────────────────────────
_HEADING_PATTERN = re.compile(r"^#{2,4}\s+(.+)$", re.MULTILINE)
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_CODE_TAG = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]{2,40})`")
# 中文术语（书名号、引号中的概念）
_CN_TERM = re.compile(r"[《「『]([^》」』]{2,30})[》」』]")

# 前置/依赖关键词 → prerequisite
_PREREQ_TRIGGERS = [
    "前提", "前置", "需要先", "依赖", "基于", "建立在.*基础",
    "prerequisite", "require", "depends on", "before learning",
    "先修", "预备知识", "入门.*之后", "在学.*之前",
]
_PREREQ_RE = re.compile("|".join(_PREREQ_TRIGGERS), re.IGNORECASE)

# 包含关系关键词 → part_of
_PARTOF_TRIGGERS = [
    "包括", "包含", "分为", "由.*组成", "涵盖",
    "consists of", "includes", "comprises",
]
_PARTOF_RE = re.compile("|".join(_PARTOF_TRIGGERS), re.IGNORECASE)


def _slug(name: str) -> str:
    """稳定的知识点 ID（拼音无关，只用 hash）"""
    return "kp_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:12]


def _extract_entities_regex(md_text: str, course: str) -> Dict[str, dict]:
    """正则通道：从 Markdown 文本抽取实体候选。

    返回 {kp_id: {name, description, bloom_level, course}}
    """
    entities: Dict[str, dict] = {}

    # 1) 标题实体（## / ### 行）
    for match in _HEADING_PATTERN.finditer(md_text):
        name = match.group(1).strip()
        if len(name) < 2 or len(name) > 80:
            continue
        # 过滤纯数字/符号标题
        if re.match(r"^[\d\.\s\-]+$", name):
            continue
        kp_id = _slug(name)
        if kp_id not in entities:
            entities[kp_id] = {
                "name": name,
                "description": name,
                "bloom_level": "",
                "course": course,
            }

    # 2) 加粗术语
    for match in _BOLD_PATTERN.finditer(md_text):
        name = match.group(1).strip()
        if 2 <= len(name) <= 60:
            kp_id = _slug(name)
            if kp_id not in entities:
                entities[kp_id] = {
                    "name": name,
                    "description": name,
                    "bloom_level": "",
                    "course": course,
                }

    # 3) 代码标签（如 `torch.nn.Module`）
    for match in _CODE_TAG.finditer(md_text):
        name = match.group(1).strip()
        if 3 <= len(name) <= 50:
            kp_id = _slug(name)
            if kp_id not in entities:
                entities[kp_id] = {
                    "name": name,
                    "description": f"技术概念：{name}",
                    "bloom_level": "",
                    "course": course,
                }

    # 4) 中文书名号/引号术语
    for match in _CN_TERM.finditer(md_text):
        name = match.group(1).strip()
        if 2 <= len(name) <= 30:
            kp_id = _slug(name)
            if kp_id not in entities:
                entities[kp_id] = {
                    "name": name,
                    "description": name,
                    "bloom_level": "",
                    "course": course,
                }

    return entities


def _extract_relations_regex(md_text: str, entities: Dict[str, dict]) -> List[dict]:
    """正则通道：从文本推断关系。

    返回 [{"source_id", "target_id", "relation_type", "weight"}, ...]
    """
    relations: List[dict] = []
    entity_list = list(entities.values())

    # 策略 A：段落内 co-occurrence → part_of 候选
    paragraphs = md_text.split("\n\n")
    for para in paragraphs:
        present = []
        for ent in entity_list:
            if ent["name"] in para:
                present.append(ent)
        # 如果段落内有标题实体 + 其他实体，推断 part_of
        headings = [e for e in present if e["name"] in [
            e2["name"] for e2 in entity_list
            if re.match(r"^#{2,4}\s+" + re.escape(e["name"]), md_text, re.MULTILINE)
        ]]
        for h in headings:
            for other in present:
                if other["name"] != h["name"]:
                    relations.append({
                        "source_id": _slug(other["name"]),
                        "target_id": _slug(h["name"]),
                        "relation_type": "part_of",
                        "weight": 0.7,
                    })

    # 策略 B：前置关键词检测 → prerequisite
    for ent_a in entity_list:
        for ent_b in entity_list:
            if ent_a["name"] == ent_b["name"]:
                continue
            # 找同时出现两个实体的段落
            for para in paragraphs:
                if ent_a["name"] in para and ent_b["name"] in para:
                    if _PREREQ_RE.search(para):
                        # ent_a 是 ent_b 的前置
                        relations.append({
                            "source_id": _slug(ent_a["name"]),
                            "target_id": _slug(ent_b["name"]),
                            "relation_type": "prerequisite",
                            "weight": 0.8,
                        })

    # 去重
    seen = set()
    deduped = []
    for rel in relations:
        key = (rel["source_id"], rel["target_id"], rel["relation_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(rel)
    return deduped


def build_knowledge_graph(
    knowledge_root: Path,
    course: str = "",
    use_llm: bool = False,
    llm_client=None,
) -> Dict[str, int]:
    """从 knowledge_root/**/*.md 构建知识图谱。

    Args:
        knowledge_root: 知识库根目录
        course: 限定课程名（空 = 全部）
        use_llm: 是否启动 LLM 增强（可选）
        llm_client: LLM 客户端实例

    Returns:
        {"nodes": int, "edges": int}
    """
    store = KnowledgeGraphStore()
    all_entities: Dict[str, dict] = {}
    all_relations: List[dict] = []

    md_files = sorted(knowledge_root.glob("**/*.md"))
    if course:
        md_files = [f for f in md_files if course in str(f)]

    for md_path in md_files:
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning(f"[KG] 无法读取 {md_path}: {exc}")
            continue

        rel = md_path.relative_to(knowledge_root)
        file_course = rel.parts[0] if len(rel.parts) > 1 else "general"

        # 正则通道
        entities = _extract_entities_regex(text, file_course)
        relations = _extract_relations_regex(text, entities)

        all_entities.update(entities)
        all_relations.extend(relations)

        logger.debug(f"[KG] {rel}: +{len(entities)} entities, +{len(relations)} relations")

    # LLM 增强（可选）
    if use_llm and llm_client:
        logger.info("[KG] LLM 增强暂未实现，仅使用正则通道")

    # 写入数据库
    for kp_id, data in all_entities.items():
        store.upsert_kp(
            kp_id=kp_id,
            name=data["name"],
            course=data["course"],
            description=data.get("description", ""),
            bloom_level=data.get("bloom_level", ""),
            metadata=data,
        )

    for rel_data in all_relations:
        store.add_relation(
            source_id=rel_data["source_id"],
            target_id=rel_data["target_id"],
            relation_type=rel_data["relation_type"],
            weight=rel_data.get("weight", 1.0),
        )

    stats = {"nodes": len(all_entities), "edges": len(all_relations)}
    logger.info(f"[KG] 构建完成: {stats['nodes']} 节点, {stats['edges']} 边")
    return stats
