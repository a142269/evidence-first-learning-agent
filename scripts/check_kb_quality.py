"""P0-1 CI 检查脚本 — 锁住知识库一致性的最小可执行清单。

用法::

    python -m scripts.check_kb_quality            # 全量（FAIL 退出 1）
    python -m scripts.check_kb_quality --strict   # WARN 也当 FAIL

输出每行形如 ``[PASS] message`` / ``[WARN] message`` / ``[FAIL] message``。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# 可直接运行（python scripts/check_kb_quality.py）也允许
ROOT = Path(__file__).resolve().parents[1]
KB_AI = ROOT / "knowledge_base" / "artificial_intelligence"
KB_PY = ROOT / "knowledge_base" / "python_programming"
KB_MAP = ROOT / "knowledge_base" / "knowledge_map.yaml"
QC = ROOT / "knowledge_base" / "knowledge_quality_checklist.md"


def emit(level: str, msg: str, *, strict_mode: bool, error_acc: list[str], warn_acc: list[str]) -> None:
    print(f"[{level.upper():4s}] {msg}")
    if level == "fail":
        error_acc.append(msg)
    elif level == "warn":
        warn_acc.append(msg)


def check_chapter_frontmatter(strict_mode: bool, errs: list[str], warns: list[str]) -> int:
    chapters_dir = KB_AI / "chapters"
    if not chapters_dir.exists():
        emit("fail", f"目录不存在: {chapters_dir}", strict_mode=strict_mode,
             error_acc=errs, warn_acc=warns)
        return 0

    files = sorted(chapters_dir.glob("*.md"))
    if not files:
        emit("fail", f"{chapters_dir} 下无章节文件", strict_mode=strict_mode,
             error_acc=errs, warn_acc=warns)
        return 0

    expected = {f"{i:02d}" for i in range(20)}
    actual = {p.name[:2] for p in files}
    missing = expected - actual
    if missing:
        emit("warn", f"章节序号缺失 {missing}", strict_mode=strict_mode,
             error_acc=errs, warn_acc=warns)

    REQUIRED = {"chapter_id", "slug", "title", "kp_ids",
                "bloom_focus", "prerequisites", "estimated_minutes"}
    ok = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            emit("fail", f"{path.name} 缺 frontmatter", strict_mode=strict_mode,
                 error_acc=errs, warn_acc=warns)
            continue
        end = text.find("\n---\n", 4)
        if end < 0:
            emit("fail", f"{path.name} frontmatter 未闭合", strict_mode=strict_mode,
                 error_acc=errs, warn_acc=warns)
            continue
        try:
            meta = yaml.safe_load(text[4:end]) or {}
        except yaml.YAMLError as exc:
            emit("fail", f"{path.name} YAML 解析失败: {exc}", strict_mode=strict_mode,
                 error_acc=errs, warn_acc=warns)
            continue
        missing_fields = REQUIRED - set(meta.keys())
        if missing_fields:
            emit("fail", f"{path.name} 缺字段 {missing_fields}",
                 strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
            continue
        ok += 1

    if ok == len(files):
        emit("pass", f"{ok}/{len(files)} chapter frontmatter 完整", strict_mode=strict_mode,
             error_acc=errs, warn_acc=warns)
    return ok


def check_code_examples(strict_mode: bool, errs: list[str], warns: list[str]) -> int:
    import ast
    code_dir = KB_AI / "code_examples"
    if not code_dir.exists():
        emit("warn", f"{code_dir} 不存在", strict_mode=strict_mode,
             error_acc=errs, warn_acc=warns)
        return 0
    files = sorted(code_dir.glob("*.py"))
    if len(files) < 3:
        emit("warn", f"仅 {len(files)} 个 code_examples（目标 ≥ 4）",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    ok = 0
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"))
            ok += 1
        except SyntaxError as exc:
            emit("fail", f"{path.name} 语法错误: {exc}",
                 strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    emit("pass", f"{ok}/{len(files)} code_examples 语法 OK", strict_mode=strict_mode,
         error_acc=errs, warn_acc=warns)
    return ok


def check_references(strict_mode: bool, errs: list[str], warns: list[str]) -> int:
    refs_dir = KB_AI / "references"
    if not refs_dir.exists():
        emit("warn", f"{refs_dir} 不存在", strict_mode=strict_mode,
             error_acc=errs, warn_acc=warns)
        return 0
    files = sorted(refs_dir.glob("*.md"))
    REQUIRED = {"title", "kp_refs", "summary_zh"}
    ok = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            emit("fail", f"{path.name} 缺 frontmatter",
                 strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
            continue
        end = text.find("\n---\n", 4)
        if end < 0:
            emit("fail", f"{path.name} frontmatter 未闭合",
                 strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
            continue
        try:
            meta = yaml.safe_load(text[4:end]) or {}
        except yaml.YAMLError:
            emit("fail", f"{path.name} YAML 解析失败",
                 strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
            continue
        miss = REQUIRED - set(meta.keys())
        if miss:
            emit("fail", f"{path.name} 缺字段 {miss}",
                 strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
            continue
        ok += 1
    if not files:
        emit("warn", "references 目录为空",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    elif len(files) < 3:
        emit("warn", f"references={len(files)} < 3（目标 ≥ 3）",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    else:
        emit("pass", f"references OK（{len(files)} 篇）",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    return ok


def check_exercises(strict_mode: bool, errs: list[str], warns: list[str]) -> int:
    ex_dir = KB_AI / "exercises"
    if not ex_dir.exists():
        emit("warn", f"{ex_dir} 不存在", strict_mode=strict_mode,
             error_acc=errs, warn_acc=warns)
        return 0
    files = sorted(ex_dir.glob("*.md"))
    if len(files) < 1:
        emit("warn", "exercises 目录为空",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
        return 0
    REQUIRED = {"chapter_ref", "kp_refs", "bloom_focus"}
    ok = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        meta: dict = {}
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end > 0:
                try:
                    meta = yaml.safe_load(text[4:end]) or {}
                except yaml.YAMLError:
                    meta = {}
        miss = REQUIRED - set(meta.keys())
        if miss:
            emit("fail", f"{path.name} 缺字段 {miss}",
                 strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
            continue
        ok += 1
    emit("pass", f"exercises OK（{ok}/{len(files)}）",
         strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    return ok


def check_question_bank(strict_mode: bool, errs: list[str], warns: list[str]) -> int:
    """跨文件题库合并检查，至少 280 题，5 种题型。"""
    sys.path.insert(0, str(ROOT))
    try:
        from backend.app.services.question_bank import get_question_bank, reset_question_bank
        reset_question_bank()
        bank = get_question_bank()
    except Exception as exc:  # pragma: no cover
        emit("fail", f"题库加载失败: {exc}",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
        return 0

    if bank.total < 280:
        emit("fail", f"合并题数 {bank.total} < 280",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    else:
        emit("pass", f"合并题数 {bank.total} ≥ 280",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)

    types = set(bank.allowed_types())
    if {"multiple_choice", "short_answer", "open_ended",
        "fill_blank", "programming"} - types:
        emit("fail", f"题型不全: {types}",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    else:
        emit("pass", f"题型完备: {sorted(types)}",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
    return bank.total


def check_quality_checklist(strict_mode: bool, errs: list[str], warns: list[str]) -> bool:
    if not QC.exists():
        emit("fail", f"quality_checklist.md 缺失: {QC}",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
        return False
    text = QC.read_text(encoding="utf-8")
    if "## " not in text:
        emit("fail", "quality_checklist.md 缺章节",
             strict_mode=strict_mode, error_acc=errs, warn_acc=warns)
        return False
    emit("pass", "quality_checklist.md 存在", strict_mode=strict_mode,
         error_acc=errs, warn_acc=warns)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="WARN 也阻断")
    args = parser.parse_args()
    errs: list[str] = []
    warns: list[str] = []
    check_chapter_frontmatter(args.strict, errs, warns)
    check_code_examples(args.strict, errs, warns)
    check_references(args.strict, errs, warns)
    check_exercises(args.strict, errs, warns)
    check_question_bank(args.strict, errs, warns)
    check_quality_checklist(args.strict, errs, warns)
    summary = {"errors": len(errs), "warns": len(warns)}
    print(json.dumps(summary, ensure_ascii=False))
    if errs or (args.strict and warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
