"""
ArtifactRegistry - 资源元数据登记中心

设计:
- 单一权威源, 所有 generate 端点都通过 register() 写入
- JSON 持久化，服务重启后仍可恢复资源预览
- 内置过期清理（默认 365 天）
- 支持按 type / session_id 过滤查询
- 线程安全 (用 threading.RLock)

替代原 artifacts.py 中的模块级 `_artifact_registry: dict`。
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_TTL_SECONDS = 365 * 86400


@dataclass
class ArtifactRecord:
    """单条资源记录"""
    id: str
    type: str              # pptx / mp3 / mermaid_png / code_result / manim_video / ...
    filepath: str
    exists: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        exists = False
        size_bytes = 0
        if self.filepath:
            try:
                path = Path(self.filepath)
                exists = path.is_file()
                size_bytes = path.stat().st_size if exists else 0
            except OSError:
                # 一条损坏或暂时不可访问的记录不能让整个资源列表 500。
                exists = False
                size_bytes = 0
        d["exists"] = exists
        d["size_bytes"] = size_bytes
        d["download_ready"] = exists and size_bytes > 0
        return d


class ArtifactRegistry:
    """资源元数据登记中心。

    ``storage_path`` 为空时保持纯内存模式，便于单元测试；生产单例会把
    元数据写到 ``data/artifacts/registry.json``，避免后端重启后资源失联。
    """

    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        storage_path: Optional[Path] = None,
    ):
        self._records: Dict[str, ArtifactRecord] = {}
        self._path_index: Dict[str, str] = {}
        self._ttl = ttl_seconds
        self._storage_path = Path(storage_path) if storage_path else None
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
            rows = payload.get("records", []) if isinstance(payload, dict) else payload
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                record = ArtifactRecord(
                    id=str(row["id"]),
                    type=str(row.get("type") or "file"),
                    filepath=str(row.get("filepath") or ""),
                    exists=bool(row.get("exists")),
                    metadata=dict(row.get("metadata") or {}),
                    created_at=float(row.get("created_at") or time.time()),
                    session_id=str(row.get("session_id") or ""),
                )
                self._records[record.id] = record
                if record.filepath:
                    self._path_index[self._path_key(record.filepath)] = record.id
            if self._evict_expired():
                self._persist()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # 损坏的索引不应阻断服务启动；startup scanner 会重新登记现有文件。
            self._records = {}

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": time.time(),
            "records": [asdict(record) for record in self._records.values()],
        }
        tmp = self._storage_path.with_suffix(self._storage_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._storage_path)

    def register(
        self,
        resource_id: str,
        artifact_type: str,
        filepath: str,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: str = "",
        persist: bool = True,
    ) -> ArtifactRecord:
        """注册一条 artifact"""
        with self._lock:
            self._evict_expired()
            previous = self._records.get(resource_id)
            if previous and previous.filepath:
                self._path_index.pop(self._path_key(previous.filepath), None)
            rec = ArtifactRecord(
                id=resource_id,
                type=artifact_type,
                filepath=filepath,
                exists=bool(filepath) and Path(filepath).exists(),
                metadata=dict(metadata or {}),
                session_id=session_id,
            )
            self._records[resource_id] = rec
            if filepath:
                self._path_index[self._path_key(filepath)] = resource_id
            if persist:
                self._persist()
            return rec

    def flush(self) -> None:
        """批量恢复登记完成后一次性落盘，避免启动扫描重复写大 JSON。"""
        with self._lock:
            self._persist()

    def prune_missing(self) -> int:
        """清理由磁盘删除的持久化资源；仅在启动恢复完成后显式调用。"""
        with self._lock:
            removed = self._prune_missing()
            if removed:
                self._persist()
            return removed

    def get(self, resource_id: str) -> Optional[ArtifactRecord]:
        with self._lock:
            if self._evict_expired():
                self._persist()
            return self._records.get(resource_id)

    def find_by_filepath(self, filepath: str) -> Optional[ArtifactRecord]:
        """按规范化绝对路径查找，供启动扫描去重。"""
        with self._lock:
            resource_id = self._path_index.get(self._path_key(filepath))
            return self._records.get(resource_id) if resource_id else None

    def list(
        self,
        artifact_type: str = "",
        session_id: str = "",
        limit: int = 100,
    ) -> List[ArtifactRecord]:
        """按 type / session_id 过滤查询"""
        with self._lock:
            if self._evict_expired():
                self._persist()
            items = list(self._records.values())
            if artifact_type:
                items = [a for a in items if a.type == artifact_type]
            if session_id:
                items = [a for a in items if a.session_id == session_id]
            items.sort(key=lambda r: r.created_at, reverse=True)
            return items[:limit]

    def clear(self) -> int:
        """清空所有记录 (测试用)"""
        with self._lock:
            n = len(self._records)
            self._records.clear()
            self._path_index.clear()
            self._persist()
            return n

    def remove(self, resource_id: str) -> bool:
        with self._lock:
            record = self._records.pop(resource_id, None)
            removed = record is not None
            if record and record.filepath:
                self._path_index.pop(self._path_key(record.filepath), None)
            if removed:
                self._persist()
            return removed

    def size(self) -> int:
        with self._lock:
            return len(self._records)

    def _evict_expired(self) -> int:
        now = time.time()
        expired = [
            rid for rid, r in self._records.items()
            if now - r.created_at > self._ttl
        ]
        for rid in expired:
            record = self._records.pop(rid, None)
            if record and record.filepath:
                self._path_index.pop(self._path_key(record.filepath), None)
        return len(expired)

    def _prune_missing(self) -> int:
        missing = [
            rid for rid, record in self._records.items()
            if record.filepath and not Path(record.filepath).exists()
        ]
        for rid in missing:
            record = self._records.pop(rid, None)
            if record and record.filepath:
                self._path_index.pop(self._path_key(record.filepath), None)
        return len(missing)

    @staticmethod
    def _path_key(filepath: str) -> str:
        return str(Path(filepath).resolve()).casefold()


# ================================================================
# 单例
# ================================================================
_registry: Optional[ArtifactRegistry] = None


def get_artifact_registry() -> ArtifactRegistry:
    global _registry
    if _registry is None:
        # pytest 用纯内存注册表，避免测试清理动作改写真实资源索引。
        storage_path = None
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            storage_path = Path(__file__).resolve().parents[5] / "data" / "artifacts" / "registry.json"
        _registry = ArtifactRegistry(storage_path=storage_path)
    return _registry


def reset_artifact_registry() -> None:
    global _registry
    _registry = None
