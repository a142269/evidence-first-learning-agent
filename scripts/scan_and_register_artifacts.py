#!/usr/bin/env python3
"""
扫描并注册现有资源文件到 ArtifactRegistry
运行: python scripts/scan_and_register_artifacts.py
"""
import os
import sys
import json
from pathlib import Path

# 添加 backend 到路径
backend_path = str(Path(__file__).parent.parent)
sys.path.insert(0, backend_path)

# 直接复制 registry 代码避免导入问题
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_TTL_SECONDS = 86400  # 24h

@dataclass
class ArtifactRecord:
    id: str
    type: str
    filepath: str
    exists: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["exists"] = Path(self.filepath).exists() if self.filepath else False
        return d

class ArtifactRegistry:
    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS):
        self._records: Dict[str, ArtifactRecord] = {}
        self._ttl = ttl_seconds
        self._lock = threading.RLock()

    def register(self, resource_id: str, artifact_type: str, filepath: str,
                 metadata: Optional[Dict[str, Any]] = None, session_id: str = "") -> ArtifactRecord:
        with self._lock:
            rec = ArtifactRecord(
                id=resource_id, type=artifact_type, filepath=filepath,
                exists=bool(filepath) and Path(filepath).exists(),
                metadata=dict(metadata or {}), session_id=session_id,
            )
            self._records[resource_id] = rec
            return rec

    def list(self, artifact_type: str = "", session_id: str = "", limit: int = 100) -> List[ArtifactRecord]:
        with self._lock:
            items = list(self._records.values())
            if artifact_type:
                items = [a for a in items if a.type == artifact_type]
            if session_id:
                items = [a for a in items if a.session_id == session_id]
            items.sort(key=lambda r: r.created_at, reverse=True)
            return items[:limit]

    def size(self) -> int:
        with self._lock:
            return len(self._records)

# 单例
_registry = None

def get_artifact_registry() -> ArtifactRegistry:
    global _registry
    if _registry is None:
        _registry = ArtifactRegistry()
    return _registry

def scan_directory(base_dir: str, artifact_type: str, ext: str, metadata_fn=None):
    """扫描目录下的文件并注册"""
    registry = get_artifact_registry()
    registered = 0

    base_path = Path(base_dir)
    if not base_path.exists():
        print(f"[SKIP] 目录不存在: {base_dir}")
        return 0

    for file_path in base_path.rglob(f"*{ext}"):
        if file_path.name.startswith('_') or file_path.name.startswith('.'):
            continue

        # 生成资源ID
        try:
            rel_path = file_path.relative_to(Path(__file__).parent.parent)
        except ValueError:
            rel_path = file_path.name
        resource_id = f"{artifact_type}_{file_path.stem}_{hash(str(file_path)) % 10000:04d}"

        # 构建元数据
        metadata = {
            "title": file_path.stem.replace('_', ' ').replace('-', ' '),
            "filename": file_path.name,
            "relative_path": str(rel_path).replace('\\', '/'),
        }

        if metadata_fn:
            metadata.update(metadata_fn(file_path))

        # 注册
        registry.register(
            resource_id=resource_id,
            artifact_type=artifact_type,
            filepath=str(file_path.absolute()),
            metadata=metadata,
            session_id="system_scan"
        )
        registered += 1

    return registered


def main():
    print("=" * 60)
    print("扫描并注册现有资源文件")
    print("=" * 60)

    total = 0

    # 1. 扫描 MP3 文件
    count = scan_directory(
        "data/artifacts/mp3",
        "mp3",
        ".mp3",
        lambda p: {"title": f"语音导学: {p.stem}", "duration": "5-8分钟"}
    )
    print(f"[MP3] 注册 {count} 个语音文件")
    total += count

    # 2. 扫描 PPT 文件
    count = scan_directory(
        "data/artifacts/pptx",
        "pptx",
        ".pptx",
        lambda p: {"title": f"课件: {p.stem}", "slides": "10-20页"}
    )
    print(f"[PPT] 注册 {count} 个课件文件")
    total += count

    # 3. 扫描 Mermaid 图片
    count = scan_directory(
        "data/artifacts/mermaid_png",
        "mermaid_png",
        ".png",
        lambda p: {"title": f"知识图谱: {p.stem}", "type": "思维导图"}
    )
    print(f"[Mermaid] 注册 {count} 个思维导图")
    total += count

    # 4. 扫描 Manim 动画脚本
    count = scan_directory(
        "data/artifacts/manim",
        "manim",
        ".py",
        lambda p: {"title": f"动画演示: {p.stem}", "type": "数学动画"}
    )
    print(f"[Manim] 注册 {count} 个动画脚本")
    total += count

    # 5. 扫描代码示例
    count = scan_directory(
        "data/code_examples",
        "code",
        ".ipynb",
        lambda p: {"title": f"代码示例: {p.stem}", "type": "Jupyter Notebook"}
    )
    print(f"[Code] 注册 {count} 个代码示例")
    total += count

    # 6. 扫描题库 (作为特殊资源)
    quiz_files = [
        ("data/question_bank.json", "question_bank", "主题库"),
        ("data/quiz_bank.json", "quiz_bank", "测验题库"),
        ("data/question_bank_analytics_0708.json", "analytics_quiz", "分析题库"),
    ]

    registry = get_artifact_registry()
    for filepath, qtype, desc in quiz_files:
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    qcount = len(data) if isinstance(data, list) else len(data.get('questions', []))

                resource_id = f"quiz_{qtype}_{hash(filepath) % 10000:04d}"
                registry.register(
                    resource_id=resource_id,
                    artifact_type="quiz_bank",
                    filepath=os.path.abspath(filepath),
                    metadata={
                        "title": f"{desc} ({qcount}题)",
                        "question_count": qcount,
                        "type": "题库资源"
                    },
                    session_id="system_scan"
                )
                print(f"[Quiz] 注册 {desc}: {qcount} 题")
                total += 1
            except Exception as e:
                print(f"[ERR] 注册题库失败 {filepath}: {e}")

    print("\n" + "=" * 60)
    print(f"总计注册: {total} 个资源")
    print(f"Registry 当前大小: {registry.size()}")
    print("=" * 60)

    # 列出所有注册的资源
    print("\n已注册资源列表:")
    for item in registry.list(limit=100):
        print(f"  - [{item.type}] {item.metadata.get('title', item.id)}")


if __name__ == "__main__":
    main()
