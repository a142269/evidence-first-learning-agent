"""
知识库管理 API

管理课程知识库的索引、状态查询、重建
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body

from backend.app.knowledge.course_loader import CourseKnowledgeLoader

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


@router.get("/status")
def get_knowledge_status() -> dict[str, Any]:
    """获取知识库状态"""
    kb_path = _project_root() / "knowledge_base"
    courses = []
    if kb_path.is_dir():
        courses = [d.name for d in kb_path.iterdir() if d.is_dir()]

    return {
        "status": "ready" if courses else "empty",
        "knowledge_base_path": str(kb_path),
        "courses": courses,
        "total_courses": len(courses),
    }


@router.post("/index/{course_name}")
def index_course(course_name: str) -> dict[str, Any]:
    """索引一门课程"""
    kb_path = _project_root() / "knowledge_base"
    loader = CourseKnowledgeLoader(kb_path)

    try:
        chunks = loader.load_course(course_name)
        return {
            "status": "indexed",
            "course": course_name,
            "total_chunks": len(chunks),
            "sample_chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "type": c.chunk_type,
                    "difficulty": c.difficulty,
                    "knowledge_points": c.knowledge_points,
                    "preview": c.content[:200],
                }
                for c in chunks[:5]
            ],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/courses")
def list_courses() -> dict[str, Any]:
    """列出可用课程（含 course.yaml 清单的显示名/简介；仅已发布课程）。

    2026-07-16 平台化改造：课程元数据由 knowledge_base/<slug>/course.yaml
    提供，前端不再维护写死的 slug→中文名映射表。
    """
    from backend.app.services.course_registry import get_course_registry

    courses = [
        {
            "id": course["id"],
            "name": course["id"],  # 兼容旧前端字段
            "display_name": course["display_name"],
            "description": course["description"],
            "file_count": course["file_count"],
            "md_count": course["md_count"],
            "has_knowledge_map": course["has_knowledge_map"],
        }
        for course in get_course_registry().list_courses(include_draft=False)
    ]
    return {"courses": courses}
