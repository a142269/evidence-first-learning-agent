from backend.app.api.v1.insights import (
    _build_multimodal_mistake_repair_stages,
    _scope_nodes_to_course,
)


def test_path_generation_scopes_the_shared_map_to_artificial_intelligence() -> None:
    nodes = {"AI_015": {"name": "多模态大模型"}, "PY_001": {"name": "Python 语言概述"}}

    scoped = _scope_nodes_to_course(nodes, "artificial_intelligence")

    assert list(scoped) == ["AI_015"]


def test_path_generation_scopes_the_shared_map_to_python() -> None:
    nodes = {"AI_015": {"name": "多模态大模型"}, "PY_001": {"name": "Python 语言概述"}}

    scoped = _scope_nodes_to_course(nodes, "python_programming")

    assert list(scoped) == ["PY_001"]


def test_multimodal_mistake_replan_keeps_a_visible_five_stage_repair_loop() -> None:
    nodes = {
        "AI_015": {"name": "多模态大模型"},
        "AI_008": {"name": "计算机视觉(CV)"},
    }

    stages = _build_multimodal_mistake_repair_stages(
        nodes,
        ["模型为实验楼图片生成了图书馆说明，应如何处理？"],
    )

    assert [stage["title"] for stage in stages] == [
        "错因定位与图文回放",
        "视觉编码与图文对齐补强",
        "跨模态检索与证据推理",
        "可信评测与一致性校验",
        "变式闯关与综合迁移",
    ]
    assert stages[0]["kp_ids"] == ["AI_015"]
    assert stages[-1]["kp_ids"] == ["AI_008"]
    assert all(stage["repair_mode"] == "mistake_repair" for stage in stages)
