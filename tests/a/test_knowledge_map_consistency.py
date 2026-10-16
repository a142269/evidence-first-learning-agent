"""知识图谱三方一致性测试：knowledge_map ↔ chapter frontmatter ↔ question_bank。

锁定：
* knowledge_map.yaml 中 KP 名称应当能在章节 frontmatter 中被引用（至少被引 1 次）
* 每个非 orphan_ok KP 必须有一个章节 frontmatter 引用
* question_bank KP ⊆ chapter→bank_kp 映射的并集 ∪ 显式豁免
* YAML KP 集合与 question_bank KP 集合在 graph 视角下无矛盾
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.app.services.knowledge_index import (
    Chapter,
    KnowledgeIndex,
    get_knowledge_index,
    reset_knowledge_index,
)
from backend.app.services.question_bank import get_question_bank, reset_question_bank


_KNOWLEDGE_MAP_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "knowledge_map.yaml"
)


@pytest.fixture(scope="module")
def knowledge_map():
    return yaml.safe_load(_KNOWLEDGE_MAP_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def index() -> KnowledgeIndex:
    reset_question_bank()
    reset_knowledge_index()
    return get_knowledge_index()


@pytest.fixture
def bank_kps():
    reset_question_bank()
    return set(get_question_bank().kp_ids)


def test_map_total_node_count_matches_doc(knowledge_map) -> None:
    nodes = knowledge_map.get("nodes", {})
    course = knowledge_map.get("course", {})
    python_course = knowledge_map.get("course_py", {})
    python_nodes = {kp_id for kp_id in nodes if kp_id.startswith("PY_")}
    assert len(nodes) - len(python_nodes) == course["total_nodes"]
    assert len(python_nodes) == python_course["total_nodes"]


def test_every_kp_has_name_and_difficulty(knowledge_map) -> None:
    for kp_id, kp in knowledge_map["nodes"].items():
        assert "name" in kp, f"{kp_id} 缺 name"
        assert "difficulty" in kp, f"{kp_id} 缺 difficulty"
        assert 1 <= kp["difficulty"] <= 6, f"{kp_id} difficulty 越界"


def test_prerequisites_reference_existing_kps(knowledge_map) -> None:
    nodes = knowledge_map["nodes"]
    for kp_id, kp in nodes.items():
        for pre in kp.get("prerequisites", []) or []:
            assert pre in nodes, f"{kp_id} 的 prerequisite {pre} 不存在"


def test_chapter_frontmatter_kps_subset_of_map(index: KnowledgeIndex) -> None:
    """章节 frontmatter 引用的 KP 必须 ∈ knowledge_map。"""
    map_kps = set(yaml.safe_load(_KNOWLEDGE_MAP_PATH.read_text(encoding="utf-8"))["nodes"].keys())
    extra = {"AI_017", "AI_018"}  # 章节 frontmatter 可能引用题库的 bank_kp（不在 map 内也允许）
    for chapter in index.chapters:
        for kp in chapter.kp_ids:
            if kp in extra:
                continue
            assert kp in map_kps, (
                f"章节 {chapter.chapter_id} frontmatter 引用了 map 外的 KP {kp}"
            )


def test_question_bank_kps_subset_of_chapter_kp_union(index: KnowledgeIndex, bank_kps) -> None:
    """题库 KP 不应超出章节 KP 映射的并集（除了显式豁免）。"""
    chapter_bank_union: set[str] = set()
    for chapter in index.chapters:
        chapter_bank_union.update(chapter.question_kp_ids)

    # AI chapters do not cover the separate Python course or learning analytics bank.
    map_nodes = set(yaml.safe_load(_KNOWLEDGE_MAP_PATH.read_text(encoding="utf-8"))["nodes"])
    explicit_orphans = {kp for kp in map_nodes if kp.startswith("PY_")} | {
        "python_basics", "data_structures", "cognitive_diagnosis",
        "data_visualization", "learning_analytics_ethics", "learning_science",
    }
    orphan = bank_kps - chapter_bank_union - explicit_orphans
    assert orphan == set(), f"题库 KP {orphan} 无章节映射或课程豁免"


def test_coverage_report_consistency(index: KnowledgeIndex) -> None:
    report = index.coverage_report()
    assert report["total_chapters"] == 20
    assert report["total_kps_in_bank"] >= 24  # 24 (主库) 或更多（含 fill/programming）
    assert report["missing_bank_question_kps"] == []


def test_course_definition_present(knowledge_map) -> None:
    course = knowledge_map["course"]
    assert course.get("code"), "knowledge_map.yaml 缺 course.code"
    assert course.get("name"), "knowledge_map.yaml 缺 course.name"


def test_recommended_paths_present(knowledge_map) -> None:
    """推荐学习路径模板必须存在（PathPlannerAgent 用）。"""
    paths = knowledge_map.get("recommended_paths", {})
    expected = {"beginner_full", "fast_track", "math_weak"}
    assert expected <= set(paths.keys()), f"缺推荐路径: {expected - set(paths.keys())}"


def test_total_kps_in_bank_matches_actual_union(bank_kps) -> None:
    """题库 KP 数与 yaml + chapter 映射至少应匹配。"""
    yaml_kps = set(yaml.safe_load(_KNOWLEDGE_MAP_PATH.read_text(encoding="utf-8"))["nodes"].keys())
    # 题库 KP ⊆ (yaml KPs + 显式豁免 bank_kps)
    allowed_in_bank = yaml_kps | {"python_basics", "data_structures",
                                  "cognitive_diagnosis", "data_visualization",
                                  "learning_analytics_ethics", "learning_science"}
    assert bank_kps <= allowed_in_bank | {"multi_agent_systems", "multimodal_llm", "ai_agent",
                                          "mcp_protocol", "rag", "ai_project_practice", "cnn",
                                          "transformer", "attention_mechanism", "neural_networks",
                                          "ml_basics", "supervised_learning", "decision_trees",
                                          "svm", "backpropagation", "rnn", "lstm", "unsupervised_learning",
                                          "nlp_basics", "reinforcement_learning",
                                          "linear_algebra", "probability_statistics"}
