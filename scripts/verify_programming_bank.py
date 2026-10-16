"""
verify_programming_bank.py — D2 编程题 code_sandbox 验收 (Plan D Round 4 C 主线)

目的
----
对 data/question_bank_programming_extra_0704.json 里 8 道编程题
逐题跑三层验证, 验收"题库 harness 字符串可执行" — 不写参考实现,
只确认每道题的 test_harness 能被沙箱接收并给出执行结果。

三层验证
--------
1. 语法层:  test_harness 字符串能用 compile() 解析为合法 Python
2. import 层: harness 中的 import 语句能在沙箱里跑通 (无 NameError 之前的)
3. 执行层:  沙箱实际执行 harness, 收集失败原因分类
            - NameError (实现缺失)  → 预期行为, 题库无 starter
            - AssertionError        → 沙箱挂上参考实现才能测, 本脚本不覆盖
            - ImportError           → 沙箱策略问题, 需要排查
            - SecurityViolation     → 沙箱拦截, OK
            - Other                 → 需要关注

用法
----
    python -m scripts.verify_programming_bank           # 跑 8 道题
    python -m scripts.verify_programming_bank --json    # 输出 JSON 报告
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
D2_PATH = WORKSPACE / "data" / "question_bank_programming_extra_0704.json"
REPORT_PATH = WORKSPACE / "data" / "programming_bank_verify_report.json"


# ============================================================
# 1. 题目 schema 校验
# ============================================================
def validate_schema(q: dict[str, Any]) -> list[str]:
    """返回 schema 缺字段清单 (空 = 完整)"""
    required = ["id", "kp_id", "kp_name", "bloom", "type", "stem", "test_harness", "language"]
    return [k for k in required if not q.get(k)]


# ============================================================
# 2. 语法层
# ============================================================
def check_syntax(harness: str) -> tuple[bool, str]:
    try:
        compile(harness, "<harness>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} at line {e.lineno}"


# ============================================================
# 3. 执行层 (sandbox)
# ============================================================
def check_execution(harness: str) -> dict[str, Any]:
    """用 code_sandbox.execute 跑 harness, 分类失败原因"""
    from backend.app.services.multimodal.code_sandbox import get_code_sandbox

    sandbox = get_code_sandbox()
    result = sandbox.execute(harness, language="python", timeout=8)

    out: dict[str, Any] = {
        "passed": result.passed,
        "execution_level": result.execution_level,
        "exit_code": result.exit_code,
        "stdout_chars": len(result.stdout or ""),
        "stderr": (result.stderr or "")[:200],
        "error": (result.error or "")[:200],
        "security_warnings": result.security_warnings or [],
    }

    # 分类失败原因
    err = (result.error or "") + (result.stderr or "")
    if result.passed:
        out["category"] = "PASS"
    elif "NameError" in err or "is not defined" in err:
        out["category"] = "NEEDS_STARTER"
    elif "AssertionError" in err or "assert" in err.lower():
        out["category"] = "ASSERTION_FAIL"
    elif "ImportError" in err or "ModuleNotFoundError" in err:
        out["category"] = "IMPORT_BLOCKED"
    elif "SecurityError" in err or "SecurityWarning" in err or result.security_warnings:
        out["category"] = "SECURITY_BLOCKED"
    elif "SyntaxError" in err:
        out["category"] = "SYNTAX_FAIL"
    elif "timeout" in err.lower() or "TimeoutExpired" in err:
        out["category"] = "TIMEOUT"
    elif "BannedModule" in err or "blocked" in err.lower():
        out["category"] = "POLICY_BLOCKED"
    else:
        out["category"] = "OTHER"

    return out


# ============================================================
# 4. 主体
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="D2 编程题 code_sandbox 验收")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args()

    print("=" * 72)
    print("A3 Round 4 C 主线 — D2 编程题 code_sandbox 验收")
    print("=" * 72)

    # 1) 加载题库
    if not D2_PATH.exists():
        print(f"[FAIL] 题库不存在: {D2_PATH}")
        return 1
    bank = json.loads(D2_PATH.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])
    print(f"[1] 加载题库: {len(questions)} 道编程题")
    print(f"    来源: {D2_PATH.relative_to(WORKSPACE)}")
    print(f"    元信息: {bank.get('_meta', {}).get('description', '?')}")
    print()

    # 2) schema 校验
    print(f"[2] schema 校验")
    schema_ok = 0
    schema_bad: list[tuple[str, list[str]]] = []
    for q in questions:
        missing = validate_schema(q)
        if missing:
            schema_bad.append((q.get("id", "?"), missing))
        else:
            schema_ok += 1
    print(f"    通过 {schema_ok}/{len(questions)}")
    for qid, missing in schema_bad:
        print(f"    [FAIL] {qid}  缺字段: {missing}")
    print()

    # 3) 三层验证
    print(f"[3] 三层验证 (语法 / 沙箱执行 / 失败分类)")
    print("    " + "-" * 68)
    rows: list[dict[str, Any]] = []
    cat_count: dict[str, int] = {}
    for i, q in enumerate(questions, 1):
        qid = q["id"]
        harness = q.get("test_harness", "")
        if not harness.strip():
            print(f"    {i:>2}. {qid:<40}  [SKIP] harness 为空")
            continue

        # 语法层
        syntax_ok, syntax_err = check_syntax(harness)

        # 执行层
        try:
            exec_info = check_execution(harness)
        except Exception as e:
            exec_info = {
                "passed": False,
                "execution_level": 0,
                "category": "SANDBOX_ERROR",
                "error": f"{type(e).__name__}: {e}"[:200],
                "stderr": "",
                "security_warnings": [],
            }

        cat = exec_info["category"]
        cat_count[cat] = cat_count.get(cat, 0) + 1

        # 打印一行
        syntax_mark = "OK " if syntax_ok else "ERR"
        exec_mark = "OK " if exec_info["passed"] else "ERR"
        print(
            f"    {i:>2}. {qid:<40}  "
            f"syn={syntax_mark}  exec={exec_mark}  cat={cat:<18}  "
            f"level={exec_info['execution_level']}  "
            f"err={exec_info['error'][:60]}"
        )

        rows.append({
            "id": qid,
            "kp_id": q.get("kp_id"),
            "bloom": q.get("bloom"),
            "difficulty": q.get("difficulty"),
            "syntax_ok": syntax_ok,
            "syntax_err": syntax_err,
            "exec_category": cat,
            "execution_level": exec_info["execution_level"],
            "exec_passed": exec_info["passed"],
            "exec_error": exec_info["error"],
            "exec_stderr": exec_info["stderr"],
            "security_warnings": exec_info["security_warnings"],
        })
    print("    " + "-" * 68)
    print()

    # 4) 分类汇总
    print(f"[4] 失败原因分类汇总")
    for cat, n in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f"    {cat:<18}  {n}")
    print()

    # 5) 总结
    n_total = len(rows)
    n_syntax_ok = sum(1 for r in rows if r["syntax_ok"])
    n_sandbox_run = sum(1 for r in rows if r["exec_category"] not in {"SANDBOX_ERROR"})
    n_implementable = sum(
        1 for r in rows
        if r["exec_category"] in {"PASS", "NEEDS_STARTER", "ASSERTION_FAIL"}
    )
    n_security_safe = sum(1 for r in rows if not r["security_warnings"])

    print("=" * 72)
    print(f"[SUMMARY]")
    print(f"  题数           {n_total}")
    print(f"  语法解析通过   {n_syntax_ok} / {n_total}")
    print(f"  沙箱可执行     {n_sandbox_run} / {n_total}  (含 NEEDS_STARTER/ASSERTION_FAIL 等预期失败)")
    print(f"  可挂参考实现   {n_implementable} / {n_total}  (含 PASS/NEEDS_STARTER/ASSERTION_FAIL)")
    print(f"  无安全警告     {n_security_safe} / {n_total}")
    print("=" * 72)

    # 6) 写报告
    report = {
        "version": "round4-0705",
        "bank_path": str(D2_PATH.relative_to(WORKSPACE)),
        "total": n_total,
        "syntax_passed": n_syntax_ok,
        "sandbox_runnable": n_sandbox_run,
        "implementable": n_implementable,
        "security_clean": n_security_safe,
        "category_distribution": cat_count,
        "questions": rows,
    }
    if args.json:
        print()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        print(f"\n报告已写: {REPORT_PATH.relative_to(WORKSPACE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
