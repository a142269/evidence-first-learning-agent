#!/usr/bin/env python3
"""
Database backup script — sqlite3 online backup with integrity verification.

Usage:
    python scripts/backup_database.py                          # default backup path
    python scripts/backup_database.py --output data/backups/a3_backup_20260618.db
    python scripts/backup_database.py --verify                 # verify existing backup
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "a3_learning.db"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "backups"

# Also try env override
DB_PATH = Path(os.getenv("DATABASE_URL", "").replace("sqlite:///", "") or DEFAULT_DB)


def backup_database(source_path: Path, target_path: Path) -> dict:
    """Backup using sqlite3.Connection.backup with progress."""
    if not source_path.exists():
        raise FileNotFoundError(f"Source database not found: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()

    source = sqlite3.connect(str(source_path))
    target = sqlite3.connect(str(target_path))

    try:
        source.backup(target)
        # Verify both
        source_integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        target_integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        source_count = source.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        target_count = target.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

        return {
            "source_path": str(source_path),
            "target_path": str(target_path),
            "source_integrity": source_integrity,
            "target_integrity": target_integrity,
            "source_profiles": source_count,
            "target_profiles": target_count,
            "verified": source_integrity == "ok" and target_integrity == "ok" and source_count == target_count,
        }
    finally:
        source.close()
        target.close()


def verify_backup(backup_path: Path) -> dict:
    """Verify a backup file with PRAGMA integrity_check."""
    if not backup_path.exists():
        return {"error": f"Backup file not found: {backup_path}"}

    conn = sqlite3.connect(str(backup_path))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        return {
            "path": str(backup_path),
            "integrity": integrity,
            "table_count": len(tables),
            "tables": tables,
            "size_bytes": backup_path.stat().st_size,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A3 database backup")
    parser.add_argument("--output", "-o", default="", help="Target backup file path")
    parser.add_argument("--verify", "-v", default="", help="Verify an existing backup file")
    parser.add_argument("--source", "-s", default=str(DB_PATH), help="Source database path")
    args = parser.parse_args()

    if args.verify:
        result = verify_backup(Path(args.verify))
        for k, v in result.items():
            print(f"  {k}: {v}")
        return

    source = Path(args.source)
    if args.output:
        target = Path(args.output)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        target = DEFAULT_BACKUP_DIR / f"a3_backup_{ts}.db"

    print(f"[backup] source: {source}")
    print(f"[backup] target: {target}")

    result = backup_database(source, target)

    if result["verified"]:
        print(f"[backup] OK backup created: {target}")
        print(f"  profiles: {result['source_profiles']} rows -> {result['target_profiles']} rows")
    else:
        print(f"[backup] ⚠️  完整性检查失败!")
        print(f"  source integrity: {result['source_integrity']}")
        print(f"  target integrity: {result['target_integrity']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
