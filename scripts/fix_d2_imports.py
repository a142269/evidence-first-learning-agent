"""
fix_d2_imports.py — 修 D2 题库 3 道题的 test_harness (Round 5.1)

Round 4 C 主线验收发现 3 道题 harness 用 import math/numpy,
但 sandbox RestrictedPython 拦了所有 __import__。本脚本按题库改写策略 A
(题库改写, 沙箱策略不动) 改写 harness, 验收目标:

- 3 道题从 IMPORT_BLOCKED 变成 NEEDS_STARTER (用户实现缺失的预期失败)
- 不引入新的语法/逻辑错误
- 不破坏其他 5 道题

改写原则 (基于 probe_final.py 探查):
  - 沙箱拦: import / 下标 obj[i] / 解包 a,b=x / all/any / isinstance(x, dict)
  - 沙箱放: for x in list 迭代 / list.append / dict.values/get / range/len/abs
  - 关键技术: list.pop(0) 绕开下标访问

改写后保留的语义:
  - 题 4: shape (2,3)+(1,3)+(3,1)+(1,1) = 13 个有限数
  - 题 6: dW 是 finite float
  - 题 8: rbf_kernel 算 RBF (用户用 .pop(0) 或别的方式)

用法:
    python -m scripts.fix_d2_imports --dry    # 预览 diff
    python -m scripts.fix_d2_imports --apply  # 实际写盘
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
D2_PATH = WORKSPACE / "data" / "question_bank_programming_extra_0704.json"


# ============================================================
# 3 道题改写后的 harness
# ============================================================
HARNESS_Q4 = '''# 用 mulberry32 LCG 生成 [0, 1) → [-1, 1) 均匀伪随机数
# 替代 np.random.seed(0) + np.random.randn (sandbox 不支持 import / 下标)
def lcgstate(s):
    return (s * 1664525 + 1013904223) & 0xFFFFFFFF

def lcgvalue(s):
    return s / 0xFFFFFFFF * 2 - 1

def rgen(rows, cols, s):
    out = []
    for i in range(rows):
        row = []
        for j in range(cols):
            v = lcgvalue(s)
            s = lcgstate(s)
            row.append(v)
        out.append(row)
    return out

def zmat(rows, cols):
    out = []
    for i in range(rows):
        row = []
        for j in range(cols):
            row.append(0.0)
        out.append(row)
    return out

state = 0
state = lcgstate(state)
X = rgen(4, 2, state)
y = [[1], [0], [1], [0]]
W1 = rgen(2, 3, state)
b1 = zmat(1, 3)
W2 = rgen(3, 1, state)
b2 = zmat(1, 1)

grads = mlp_forward_backward(X, y, W1, b1, W2, b2)

# 校验: dict 4 项 + 总元素数 (2*3 + 1*3 + 3*1 + 1*1 = 13) + 全部有限
assert len(grads) == 4
total = 0
ok = True
for v in grads.values():
    for row in v:
        for x in row:
            total = total + 1
            if not (-1e308 < x < 1e308):
                ok = False
assert ok
assert total == 13
'''

HARNESS_Q6 = '''dW = bptt_dw([1.0, 2.0, 3.0], 0.5, 1.0)
assert isinstance(dW, float)
assert -1e308 < dW < 1e308
'''

HARNESS_Q8 = '''assert abs(rbf_kernel([1,2], [1,2]) - 1.0) < 1e-6
assert abs(rbf_kernel([0,0], [10,10], gamma=0.5)) < 1e-3
'''


# ============================================================
# 主体
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="修 D2 题库 3 道题 harness")
    parser.add_argument("--dry", action="store_true", help="只预览, 不写盘")
    parser.add_argument("--apply", action="store_true", help="实际写盘")
    args = parser.parse_args()

    if not args.dry and not args.apply:
        args.dry = True  # 默认 dry

    print("=" * 72)
    print("A3 Round 5.1 — D2 题库 3 道题 test_harness 改写 (策略 A: 题库改写)")
    print("=" * 72)
    print(f"模式: {'[APPLY 写盘]' if args.apply else '[DRY-RUN 预览]'}\n")

    if not D2_PATH.exists():
        print(f"[FAIL] 题库不存在: {D2_PATH}")
        return 1

    bank = json.loads(D2_PATH.read_text(encoding="utf-8"))
    questions = bank.get("questions", [])

    targets = {
        "prog-mlp-gradient-0704": ("harness", HARNESS_Q4),
        "prog-rnn-bptt-0704": ("harness", HARNESS_Q6),
        "prog-svm-kernel-0704": ("harness", HARNESS_Q8),
    }

    print(f"[1] 题库共 {len(questions)} 道, 目标改写 {len(targets)} 道")
    print()

    print(f"[2] 改写前 vs 改写后 harness 长度")
    print("    " + "-" * 65)
    changes: list[dict] = []
    for q in questions:
        if q["id"] not in targets:
            continue
        old_harness = q.get("test_harness", "")
        _, new_harness = targets[q["id"]]
        diff_len = len(new_harness) - len(old_harness)
        sign = "+" if diff_len >= 0 else ""
        print(f"    {q['id']:<35}  {len(old_harness):>4} → {len(new_harness):<4}  ({sign}{diff_len})")
        changes.append({
            "id": q["id"],
            "old_len": len(old_harness),
            "new_len": len(new_harness),
            "old": old_harness,
            "new": new_harness,
        })
    print()

    print(f"[3] 改写内容预览 (新 harness):")
    print("    " + "-" * 65)
    for c in changes:
        print(f"\n--- {c['id']} ---")
        for line in c["new"].splitlines()[:8]:
            print(f"    {line}")
        if len(c["new"].splitlines()) > 8:
            print(f"    ... (共 {len(c['new'].splitlines())} 行)")
    print()

    if args.dry:
        print("[DRY] 预览结束, 用 --apply 实际写盘")
        return 0

    # 实际写盘
    print(f"[4] 实际写盘")
    applied = 0
    for q in questions:
        if q["id"] not in targets:
            continue
        _, new_harness = targets[q["id"]]
        q["test_harness"] = new_harness
        # 同时加一个字段说明改写历史 (方便 review)
        q["harness_rewrite"] = {
            "round": "5.1",
            "reason": "原 harness 用 import math/numpy, sandbox 拦 __import__",
            "strategy": "策略 A - 题库改写, 沙箱策略不动",
        }
        applied += 1
        print(f"    [APPLY] {q['id']}")

    # 更新 _meta 加改写说明
    if "_meta" in bank:
        bank["_meta"]["harness_rewrite_round51"] = "prog-mlp-gradient, prog-rnn-bptt, prog-svm-kernel"
        bank["_meta"]["harness_rewrite_note"] = "Round 5.1 把 3 道 harness 改成 sandbox 友好 (无 import, 纯算术+迭代)"

    D2_PATH.write_text(
        json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"\n[APPLY DONE] {applied} 道题 harness 改写, 题库 {D2_PATH.relative_to(WORKSPACE)} 已更新")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
