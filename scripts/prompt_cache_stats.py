"""PromptCache 命中率统计 CLI

用法:
    python -m scripts.prompt_cache_stats
    python -m scripts.prompt_cache_stats --json
    python -m scripts.prompt_cache_stats --clear   # 清空缓存（危险）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from backend.app.services.prompt_cache import DEFAULT_DB_PATH, PromptCache


def _humanize_seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    if s < 3600:
        return f"{s / 60:.1f}m"
    if s < 86400:
        return f"{s / 3600:.1f}h"
    return f"{s / 86400:.1f}d"


def run(db_path: Path, clear: bool, as_json: bool) -> int:
    if clear:
        cache = PromptCache(db_path=db_path)
        removed = cache.clear()
        cache.close()
        if as_json:
            print(json.dumps({"cleared": removed}))
        else:
            print(f"[clear] removed {removed} entries from {db_path}")
        return 0

    if not Path(db_path).exists() and str(db_path) != ":memory:":
        if as_json:
            print(json.dumps({"error": "db_not_found", "db_path": str(db_path)}))
        else:
            print(f"[warn] db not found: {db_path}")
            print("[hint] Cache is empty (DB file will be created on first set())")
        return 1

    cache = PromptCache(db_path=db_path)
    stats = cache.stats()
    cache.close()

    payload: Dict[str, Any] = {
        "db_path": str(db_path),
        "total_entries": stats.total_entries,
        "total_hits": stats.total_hits,
        "hit_rate": round(stats.hit_rate, 4),
        "oldest_entry_age": _humanize_seconds(stats.oldest_entry_age_s),
        "newest_entry_age": _humanize_seconds(stats.newest_entry_age_s),
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 60)
    print(" PromptCache Stats")
    print("=" * 60)
    print(f"  DB             : {db_path}")
    print(f"  Total entries  : {stats.total_entries}")
    print(f"  Total hits     : {stats.total_hits}")
    print(f"  Hit rate       : {stats.hit_rate * 100:.1f}%  "
          f"(calls = {stats.total_entries + stats.total_hits})")
    print(f"  Oldest entry   : {_humanize_seconds(stats.oldest_entry_age_s)} ago")
    print(f"  Newest entry   : {_humanize_seconds(stats.newest_entry_age_s)} ago")
    print("=" * 60)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="PromptCache 命中率统计")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite DB path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument(
        "--clear", action="store_true", help="清空缓存 (危险，不可恢复)"
    )
    args = parser.parse_args()
    sys.exit(run(args.db, clear=args.clear, as_json=args.json))


if __name__ == "__main__":
    main()
