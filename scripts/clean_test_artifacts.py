#!/usr/bin/env python
"""Remove stale pytest temp dirs and SQLite journals **without** the recycle bin.

Every full-suite run creates a ``--basetemp`` tree full of tiny SQLite files and
``.db-journal`` leftovers.  Deleting such trees through Explorer sends every
entry to the Windows Recycle Bin; on a project this size that can accumulate
into hundreds of thousands of entries and make the bin almost impossible to
empty.  This helper deletes directly with ``shutil.rmtree`` / ``os.unlink`` so
nothing is staged for recycle.

Only paths *under the repository's* ``output/`` are considered:

* directories named ``base*``, ``basetemp*`` or ``pytest-*`` (pytest basetemps)
* files ending in ``.db-journal`` (SQLite rollback journals)

It never deletes evaluation results, reports, databases, models or source.
Dry-run is the default; pass ``--apply`` to actually remove.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
BASETEMP_PREFIXES = ("base", "basetemp", "pytest-")
JOURNAL_SUFFIX = ".db-journal"


def _safe_path(path: Path) -> bool:
    """True only for a non-symlink path strictly inside ``output/``."""
    try:
        resolved = path.resolve()
        output = OUTPUT.resolve()
    except OSError:
        return False
    if path.is_symlink() or resolved == output:
        return False
    return output in resolved.parents


def iter_targets() -> tuple[list[Path], list[Path]]:
    """Return (stale basetemp dirs, stray SQLite journals) under output/."""
    dirs: list[Path] = []
    journals: list[Path] = []
    if not OUTPUT.is_dir():
        return dirs, journals
    for dirpath, dirnames, filenames in os.walk(OUTPUT, topdown=True, followlinks=False):
        parent = Path(dirpath)
        for name in list(dirnames):
            candidate = parent / name
            if not name.startswith(BASETEMP_PREFIXES) or not _safe_path(candidate):
                continue
            # Do not descend into a tree that is about to be deleted.
            dirnames.remove(name)
            dirs.append(candidate)
        for name in filenames:
            if name.endswith(JOURNAL_SUFFIX):
                candidate = parent / name
                if _safe_path(candidate):
                    journals.append(candidate)
    return dirs, journals


def _tree_size(path: Path) -> int:
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(path, followlinks=False):
            for name in filenames:
                try:
                    total += (Path(dirpath) / name).stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete stale pytest basetemps and SQLite journals directly "
                    "(never via the Recycle Bin). Dry-run by default.")
    parser.add_argument("--apply", action="store_true",
                        help="actually delete the listed paths (default: dry-run)")
    args = parser.parse_args(argv)

    dirs, journals = iter_targets()
    dir_bytes = sum(_tree_size(path) for path in dirs)
    journal_bytes = sum(path.stat().st_size for path in journals if path.exists())

    print(f"[clean-test-artifacts] root={ROOT}")
    print(f"[clean-test-artifacts] stale basetemp dirs: {len(dirs)} "
          f"({_human_bytes(dir_bytes)})")
    print(f"[clean-test-artifacts] SQLite journals:     {len(journals)} "
          f"({_human_bytes(journal_bytes)})")
    for path in (dirs + journals)[:20]:
        print(f"  - {path.relative_to(ROOT)}")
    if len(dirs) + len(journals) > 20:
        print(f"  ... and {len(dirs) + len(journals) - 20} more")

    if not args.apply:
        print("[clean-test-artifacts] dry-run: pass --apply to delete directly")
        return 0

    failures = 0
    for path in dirs:
        if not _safe_path(path):
            failures += 1
            continue
        try:
            shutil.rmtree(path)
        except OSError as exc:
            failures += 1
            print(f"[clean-test-artifacts] FAILED dir {path}: {exc}", file=sys.stderr)
    for path in journals:
        if not _safe_path(path):
            failures += 1
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError as exc:
            failures += 1
            print(f"[clean-test-artifacts] FAILED file {path}: {exc}", file=sys.stderr)

    print(f"[clean-test-artifacts] deleted {len(dirs)} dirs + {len(journals)} journals "
          f"directly; failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
