#!/usr/bin/env python3
"""
一键构建知识图谱

用法:
    python scripts/build_kg.py                        # 默认全部课程
    python scripts/build_kg.py --course python_programming
    python scripts/build_kg.py --stats               # 仅查看统计
    python scripts/build_kg.py --rebuild             # 清空重来
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import init_db
from backend.app.services.knowledge_graph.builder import build_knowledge_graph
from backend.app.services.knowledge_graph.store import get_kg_store


def main() -> None:
    parser = argparse.ArgumentParser(description="构建知识图谱")
    parser.add_argument("--course", default="", help="限定课程（空=全部）")
    parser.add_argument("--stats", action="store_true", help="仅查看统计")
    parser.add_argument("--rebuild", action="store_true", help="清空已有数据重建")
    args = parser.parse_args()

    init_db()
    store = get_kg_store()

    if args.stats:
        print(f"知识点: {store.kp_count()}")
        print(f"关系:   {store.relation_count()}")
        for kp in store.list_kps()[:5]:
            print(f"  - {kp.name} [{kp.course}]")
        return

    if args.rebuild:
        # 简单清空：删除全部 KP 和关系（通过 store 的 session 删）
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord, KnowledgeRelationRecord
        with SessionLocal() as db:
            db.query(KnowledgeRelationRecord).delete()
            db.query(KnowledgePointRecord).delete()
            db.commit()
        print("[build_kg] 已清空已有数据")

    kb_path = PROJECT_ROOT / "knowledge_base"
    if not kb_path.is_dir():
        print(f"[build_kg] 知识库路径不存在: {kb_path}")
        sys.exit(1)

    stats = build_knowledge_graph(kb_path, course=args.course)
    print(f"[build_kg] 完成: {stats['nodes']} 节点, {stats['edges']} 边")


if __name__ == "__main__":
    main()
