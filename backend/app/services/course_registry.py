"""课程注册表 —— "课程即数据"的核心服务。

设计目标（docs/08-知识库平台化改造方案.md）：
* 新增一门课程 = knowledge_base/<slug>/ 目录 + course.yaml 清单，零代码变更
* 显示名/简介/状态等元数据由 course.yaml 提供，前端不再维护写死的映射表
* 知识图谱按课程拆分：优先读 knowledge_base/<slug>/knowledge_map.yaml，
  兼容读取旧的全局 knowledge_base/knowledge_map.yaml（AI/PY 存量节点）
* 只依赖 stdlib + PyYAML，进程内带 TTL 缓存，写操作后主动失效

目录约定：
    knowledge_base/
    ├── <slug>/
    │   ├── course.yaml          # 课程清单（本服务读写）
    │   ├── chapters/*.md        # 章节（可选）
    │   ├── uploads/*.md         # 教师上传经流水线转换后的正文（RAG 自动扫描）
    │   ├── uploads/_raw/*       # 上传原件（非 .md，不入索引）
    │   └── knowledge_map.yaml   # 课程级知识点图谱（可选）
    └── knowledge_map.yaml       # 旧全局图谱（存量 AI_*/PY_*/MATH_*/CODE_* 节点）
"""
from __future__ import annotations

import logging
import re
import shutil
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_KB_ROOT = _PROJECT_ROOT / "knowledge_base"

_MANIFEST_NAME = "course.yaml"
_COURSE_MAP_NAME = "knowledge_map.yaml"

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

# 存量课程的显示名兜底（迁移期：老目录还没有 course.yaml 时也能给出中文名）
_LEGACY_DISPLAY_NAMES = {
    "artificial_intelligence": "人工智能导论",
    "python_programming": "Python 程序设计",
}

# 旧全局图谱中各命名空间归属的课程（迁移期兼容）
_LEGACY_NODE_COURSE_PREFIXES = {
    "PY_": "python_programming",
    "AI_": "artificial_intelligence",
    "MATH_": "artificial_intelligence",
    "CODE_": "artificial_intelligence",
}

_CACHE_TTL_SECONDS = 30.0


class CourseRegistryError(RuntimeError):
    """课程创建/更新入参非法或磁盘操作失败。"""


def kb_root() -> Path:
    return _KB_ROOT


def validate_slug(slug: str) -> str:
    slug = str(slug or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise CourseRegistryError(
            "课程标识需为 2-64 位小写字母/数字/下划线，且以字母开头"
        )
    return slug


def _default_display_name(slug: str) -> str:
    return _LEGACY_DISPLAY_NAMES.get(slug) or slug.replace("_", " ").title()


class CourseRegistry:
    """knowledge_base 目录 + course.yaml 的读写门面。"""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else _KB_ROOT
        self._lock = Lock()
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_at = 0.0

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------
    def list_courses(self, include_draft: bool = True) -> List[Dict[str, Any]]:
        """所有课程清单（含统计）。include_draft=False 时仅返回已发布课程。"""
        now = time.time()
        with self._lock:
            if self._cache is not None and now - self._cache_at < _CACHE_TTL_SECONDS:
                courses = list(self._cache)
            else:
                courses = self._scan()
                self._cache = courses
                self._cache_at = now
        if include_draft:
            return [dict(c) for c in courses]
        return [dict(c) for c in courses if c.get("status") == "published"]

    def get_course(self, slug: str) -> Optional[Dict[str, Any]]:
        slug = str(slug or "").strip().lower()
        for course in self.list_courses():
            if course["id"] == slug:
                return course
        return None

    def _scan(self) -> List[Dict[str, Any]]:
        courses: List[Dict[str, Any]] = []
        if not self.root.is_dir():
            return courses
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir() or entry.name.startswith((".", "_")):
                continue
            courses.append(self._describe(entry))
        return courses

    def _describe(self, course_dir: Path) -> Dict[str, Any]:
        slug = course_dir.name
        manifest = self._read_manifest(course_dir)
        md_count = len(list(course_dir.glob("**/*.md")))
        file_count = sum(1 for p in course_dir.glob("**/*") if p.is_file())
        has_chapters = (course_dir / "chapters").is_dir()
        has_map = (course_dir / _COURSE_MAP_NAME).is_file() or self._legacy_map_covers(slug)
        return {
            "id": slug,
            "name": slug,  # 兼容旧前端（HomeView 曾读 item.name）
            "display_name": str(manifest.get("display_name") or _default_display_name(slug)),
            "description": str(manifest.get("description") or ""),
            "status": str(manifest.get("status") or "published"),
            "owner": str(manifest.get("owner") or ""),
            "created_at": manifest.get("created_at") or "",
            "updated_at": manifest.get("updated_at") or "",
            "builtin": bool(manifest.get("builtin", slug in _LEGACY_DISPLAY_NAMES)),
            "md_count": md_count,
            "file_count": file_count,
            "has_chapters": has_chapters,
            "has_knowledge_map": has_map,
            "path": str(course_dir),
        }

    def _read_manifest(self, course_dir: Path) -> Dict[str, Any]:
        manifest_path = course_dir / _MANIFEST_NAME
        if not manifest_path.is_file():
            return {}
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        except yaml.YAMLError as exc:
            logger.warning("[course-registry] %s 解析失败: %s", manifest_path, exc)
            return {}

    def _legacy_map_covers(self, slug: str) -> bool:
        """旧全局图谱是否覆盖该课程（存量 AI/PY）。"""
        return slug in set(_LEGACY_NODE_COURSE_PREFIXES.values()) and (
            self.root / _COURSE_MAP_NAME
        ).is_file()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    def create_course(
        self,
        slug: str,
        display_name: str,
        description: str = "",
        owner: str = "",
        status: str = "published",
    ) -> Dict[str, Any]:
        slug = validate_slug(slug)
        display_name = str(display_name or "").strip() or _default_display_name(slug)
        course_dir = self.root / slug
        if course_dir.exists():
            raise CourseRegistryError(f"课程已存在: {slug}")

        (course_dir / "chapters").mkdir(parents=True)
        (course_dir / "uploads" / "_raw").mkdir(parents=True)
        self._write_manifest(
            course_dir,
            {
                "display_name": display_name,
                "description": str(description or "").strip(),
                "status": status if status in {"draft", "published"} else "published",
                "owner": str(owner or ""),
                "builtin": False,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            },
        )
        self.invalidate()
        logger.info("[course-registry] 新建课程 %s (%s)", slug, display_name)
        return self.get_course(slug) or {}

    def update_course(self, slug: str, **fields: Any) -> Dict[str, Any]:
        slug = str(slug or "").strip().lower()
        course_dir = self.root / slug
        if not course_dir.is_dir():
            raise CourseRegistryError(f"课程不存在: {slug}")

        manifest = self._read_manifest(course_dir)
        allowed = {"display_name", "description", "status", "owner"}
        changed = False
        for key, value in fields.items():
            if key not in allowed or value is None:
                continue
            value = str(value).strip()
            if key == "status" and value not in {"draft", "published", "archived"}:
                raise CourseRegistryError("status 仅支持 draft / published / archived")
            if key == "display_name" and not value:
                continue
            manifest[key] = value
            changed = True
        if changed:
            manifest.setdefault("created_at", _now_iso())
            manifest["updated_at"] = _now_iso()
            manifest.setdefault("builtin", slug in _LEGACY_DISPLAY_NAMES)
            self._write_manifest(course_dir, manifest)
            self.invalidate()
        return self.get_course(slug) or {}

    def archive_course(self, slug: str) -> Dict[str, Any]:
        """归档自建课程：停止在学生端课程清单中展示，但完整保留可恢复的数据。"""
        course = self.get_course(slug)
        if course is None:
            raise CourseRegistryError(f"课程不存在: {slug}")
        if course.get("builtin"):
            raise CourseRegistryError("内置课程受保护，不能归档")
        return self.update_course(str(course["id"]), status="archived")

    def restore_course(self, slug: str) -> Dict[str, Any]:
        """恢复归档课程为已发布状态，重新出现在全端课程选择器中。"""
        course = self.get_course(slug)
        if course is None:
            raise CourseRegistryError(f"课程不存在: {slug}")
        if course.get("builtin"):
            raise CourseRegistryError("内置课程无需恢复")
        return self.update_course(str(course["id"]), status="published")

    def delete_course(self, slug: str) -> Dict[str, Any]:
        """永久移除已归档的自建课程目录。调用方负责先清理数据库索引。"""
        course = self.get_course(slug)
        if course is None:
            raise CourseRegistryError(f"课程不存在: {slug}")
        if course.get("builtin"):
            raise CourseRegistryError("内置课程受保护，不能永久删除")
        if course.get("status") != "archived":
            raise CourseRegistryError("请先归档课程，再执行永久删除")

        course_dir = self.root / str(course["id"])
        if not course_dir.is_dir():
            raise CourseRegistryError(f"课程目录不存在: {slug}")
        try:
            shutil.rmtree(course_dir)
        except OSError as exc:
            raise CourseRegistryError(f"课程目录删除失败: {exc}") from exc
        self.invalidate()
        return course

    def _write_manifest(self, course_dir: Path, manifest: Dict[str, Any]) -> None:
        payload = yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False)
        (course_dir / _MANIFEST_NAME).write_text(payload, encoding="utf-8")

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_at = 0.0

    # ------------------------------------------------------------------
    # 知识点图谱（课程级优先，全局兼容）
    # ------------------------------------------------------------------
    def load_map_nodes(self, course: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """返回 {kp_id: meta}，meta 额外带 course 字段。

        * course=None：聚合全部（全局旧文件 + 各课程文件），课程文件优先覆盖同名节点
        * course=slug：优先课程级文件；没有则从全局文件按命名空间前缀筛选
        """
        if course:
            course = str(course).strip().lower()
            per_course = self._load_map_file(self.root / course / _COURSE_MAP_NAME, course)
            if per_course:
                return per_course
            return {
                kp_id: meta
                for kp_id, meta in self._load_legacy_map().items()
                if meta.get("course") == course
            }

        merged = dict(self._load_legacy_map())
        for entry in sorted(self.root.iterdir()) if self.root.is_dir() else []:
            if not entry.is_dir() or entry.name.startswith((".", "_")):
                continue
            merged.update(self._load_map_file(entry / _COURSE_MAP_NAME, entry.name))
        return merged

    def _load_map_file(self, path: Path, course: str) -> Dict[str, Dict[str, Any]]:
        if not path.is_file():
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.warning("[course-registry] %s 解析失败: %s", path, exc)
            return {}
        nodes = payload.get("nodes") or {}
        if not isinstance(nodes, dict):
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        for kp_id, meta in nodes.items():
            if isinstance(meta, dict):
                enriched = dict(meta)
                enriched["course"] = course
                result[str(kp_id)] = enriched
        return result

    def _load_legacy_map(self) -> Dict[str, Dict[str, Any]]:
        nodes = self._load_map_file(self.root / _COURSE_MAP_NAME, "")
        for kp_id, meta in nodes.items():
            meta["course"] = _legacy_node_course(kp_id)
        return nodes

    def write_course_map(self, course: str, nodes: Dict[str, Dict[str, Any]]) -> Path:
        """把自动生成/人工整理的节点写入课程级图谱文件。"""
        course = str(course or "").strip().lower()
        course_dir = self.root / course
        if not course_dir.is_dir():
            raise CourseRegistryError(f"课程不存在: {course}")
        cleaned = {
            str(kp_id): {k: v for k, v in dict(meta).items() if k != "course"}
            for kp_id, meta in nodes.items()
            if isinstance(meta, dict)
        }
        path = course_dir / _COURSE_MAP_NAME
        payload = {
            "course": {"slug": course, "updated_at": _now_iso()},
            "nodes": cleaned,
        }
        path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path


def _legacy_node_course(kp_id: str) -> str:
    for prefix, course in _LEGACY_NODE_COURSE_PREFIXES.items():
        if str(kp_id).startswith(prefix):
            return course
    return "artificial_intelligence"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


_registry: Optional[CourseRegistry] = None


def get_course_registry() -> CourseRegistry:
    global _registry
    if _registry is None:
        _registry = CourseRegistry()
    return _registry


def reset_course_registry() -> None:
    """测试钩子。"""
    global _registry
    _registry = None
