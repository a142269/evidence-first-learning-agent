"""
知识库索引脚本

用法:
  python -m scripts.index_knowledge        # 全量重建
  python -m scripts.index_knowledge --stats  # 仅查看统计

目的：
1. 把 knowledge_base 下所有课程 .md 加载到 RAGService
2. 输出统计信息便于答辩演示和调试
3. 保留接口，未来可平滑替换为 ChromaDB 持久化
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 兼容直接运行
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="A3 RAG 知识库索引脚本")
    parser.add_argument("--stats", action="store_true", help="只查看统计，不强制重新加载")
    parser.add_argument("--query", type=str, default="", help="可选：跑一次检索 demo")
    args = parser.parse_args()

    from backend.app.services.rag_service import get_rag_service

    t0 = time.time()
    rag = get_rag_service()
    rag.load()
    print(json.dumps({"status": "indexed", "elapsed_s": round(time.time() - t0, 3), **rag.stats()},
                     ensure_ascii=False, indent=2))

    if args.query:
        hits = rag.retrieve(args.query, top_k=5)
        print("\n[检索演示]", args.query)
        for h in hits:
            print(f"  · score={h['score']:.3f}  source={h['source']}  course={h['course']}")
            print(f"    {h['content'][:120].strip()}...\n")


if __name__ == "__main__":
    main()
