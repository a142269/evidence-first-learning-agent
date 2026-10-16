#!/usr/bin/env python3
"""
Database restore script — replaces current database with a verified backup.

Usage:
    python scripts/restore_database.py data/backups/a3_backup_20260618.db
    python scripts/restore_database.py --check data/backups/a3_backup_20260618.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "a3_learning.db"
DB_PATH = Path(os.getenv("DATABASE_URL", "").replace("sqlite:///", "") or DEFAULT_DB)


def restore_database(backup_path: Path, target_path: Path) -> dict:
    """Restore target from backup. Target is completely replaced."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    # Verify backup first — NEVER restore from a corrupt file
    backup_conn = sqlite3.connect(str(backup_path))
    try:
        try:
            integrity = backup_conn.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            return {"error": f"Backup is not a valid SQLite database: {exc}", "restored": False}
        if integrity != "ok":
            return {"error": f"Backup integrity check failed: {integrity}", "restored": False}
    finally:
        backup_conn.close()

    # If target exists, create a safety copy before overwriting
    if target_path.exists():
        safety_path = target_path.with_suffix(".db.pre_restore")
        import shutil
        shutil.copy2(target_path, safety_path)

    # Remove existing target
    if target_path.exists():
        target_path.unlink()

    # Restore
    source = sqlite3.connect(str(backup_path))
    target = sqlite3.connect(str(target_path))

    try:
        source.backup(target)
        target_integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        target_count = target.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

        return {
            "restored": True,
            "target_path": str(target_path),
            "integrity": target_integrity,
            "profiles_rows": target_count,
        }
    finally:
        source.close()
        target.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A3 database restore")
    parser.add_argument("backup", help="Path to the backup file to restore from")
    parser.add_argument("--target", "-t", default=str(DB_PATH), help="Target database path")
    parser.add_argument("--check", action="store_true", help="Verify backup without restoring")
    parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    backup_path = Path(args.backup)

    if args.check:
        conn = sqlite3.connect(str(backup_path))
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            print(f"[restore] backup integrity: {integrity}")
            print(f"[restore] tables ({len(tables)}): {[t[0] for t in tables]}")
        finally:
            conn.close()
        return

    target = Path(args.target)

    if not args.force:
        print(f"⚠️  This will REPLACE {target} with {backup_path}")
        print(f"   A safety copy will be saved as {target.with_suffix('.db.pre_restore')}")
        confirm = input("   Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("[restore] cancelled")
            return

    result = restore_database(backup_path, target)

    if result.get("restored"):
        print(f"[restore] ✅ 恢复成功: {target}")
        print(f"  integrity: {result['integrity']}")
        print(f"  profiles rows: {result['profiles_rows']}")
    else:
        print(f"[restore] ❌ 恢复失败: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
