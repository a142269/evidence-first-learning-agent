"""Aggregate recorded model usage from evaluation artifacts; never calls an API.

Read-only over existing evaluation ``runs.jsonl`` records. The accounting rules
are not reimplemented here: every record is projected through the product's own
``backend.app.services.run_usage.summarize_run_usage`` and grouped with
``aggregate_run_usage``, which totals only over runs that carry a real
measurement and counts the rest. Nothing applies a tariff and this module imports
no ``os``, so it cannot read the environment or a ``.env`` file: a record whose
cost was never priced stays ``unknown`` and is never rendered as 0.

Output is redacted: model names, artifact paths, counts and the recorded numbers
only. Dataset/evidence digests are deliberately not reproduced.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.services.run_usage import (  # noqa: E402
    aggregate_run_usage,
    summarize_run_usage,
)

UNLABELED = "未标注"
NOT_PRICED = "金额未记录 (无 estimated 记录)"
BUDGET_FIELDS = ("actual_input_tokens", "actual_output_tokens", "input_chars",
                 "output_token_limit")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _exact(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def _cell(value) -> str:
    return "未记录" if value is None else _exact(value)


class _RecordRow:
    """Adapts one ``runs.jsonl`` record to what ``summarize_run_usage`` reads.

    Only ``metadata_data`` carries data; the remaining attributes exist so the
    product projection runs unchanged over offline artifacts instead of DB rows.
    """

    workflow_type = None
    status = None
    created_at = None
    duration_ms = None
    tool_calls = None

    def __init__(self, run_id: str, record: dict) -> None:
        self.id = run_id
        self.metadata_data = {"result": record.get("result")}


def _load(path: Path):
    records, bad = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
        else:
            bad += 1
    return records, bad


class Bucket:
    """One aggregation group; absent values are counted, never zero-filled."""

    def __init__(self) -> None:
        self.summaries: list[dict] = []
        self.rows: list[tuple[dict, float | None, float | None]] = []
        self.calls: list[float] = []
        self.chars: list[float] = []
        self.latency: list[float] = []
        self.records = 0
        self.models: Counter[str] = Counter()
        self.completed: Counter[str] = Counter()
        self.errors = 0
        self.top_cost_cny = 0
        self.field_missing: Counter[str] = Counter()
        self.projection_dropped: Counter[str] = Counter()

    def add(self, run_id: str, record: dict) -> None:
        result = _mapping(record.get("result"))
        budget = _mapping(result.get("budget"))
        summary = summarize_run_usage(_RecordRow(run_id, record))
        self.summaries.append(summary)
        self.records += 1
        model = _mapping(record.get("config")).get("model")
        self.models[model if isinstance(model, str) and model else UNLABELED] += 1
        completed = record.get("completed", result.get("completed"))
        self.completed[UNLABELED if completed is None else str(completed)] += 1
        if result.get("error") is not None:
            self.errors += 1
        if _number(record.get("cost_cny")) is not None:
            self.top_cost_cny += 1
        # run_usage._count 只接受整数, 而 latency_ms 是小数, 产品投影会把它判成"未记录";
        # 这一项按原始值读, 并在报告里单列披露偏差条数。
        latency = _number(result.get("latency_ms"))
        if latency is None:
            latency = _number(record.get("latency_ms"))
        if latency is not None and summary["reported_latency_ms"] is None:
            self.projection_dropped["latency_ms"] += 1
        if summary["model_calls"] is None and _number(budget.get("model_calls")) is not None:
            self.projection_dropped["model_calls"] += 1
        chars = _number(budget.get("input_chars"))
        for value, target in ((summary["model_calls"], self.calls),
                              (latency, self.latency),
                              (chars, self.chars)):
            if value is not None:
                target.append(value)
        self.rows.append((summary, latency, chars))
        for name in BUDGET_FIELDS:
            if _number(budget.get(name)) is None:
                self.field_missing[name] += 1

    def aggregate(self) -> dict:
        return aggregate_run_usage(self.summaries)


def _total(values: list[float], records: int) -> str:
    if not values:
        return f"未记录 (0/{records} 条有值)"
    return f"{_exact(sum(values))} ({len(values)}/{records} 条有值)"


def _measured_total(group: dict, key: str) -> str:
    present = group["runs"] - group["runs_without_token_data"]
    return f"{group[key]} ({present}/{group['runs']} 条有值)"


def _latency(values: list[float], records: int) -> str:
    if not values:
        return f"未记录 (0/{records} 条有值)"
    return (f"{_exact(statistics.median(values))} "
            f"[{_exact(min(values))}~{_exact(max(values))}] ({len(values)}/{records})")


def _counter(counter: Counter[str]) -> str:
    return ", ".join(f"{k}x{v}" for k, v in sorted(counter.items())) or "-"


def _statuses(counts: dict[str, int]) -> str:
    return ", ".join(f"{k}x{v}" for k, v in sorted(counts.items()) if v) or "-"


def _cost_cell(group: dict) -> str:
    """Render cost so an unpriced run can never be read as 0 元."""
    estimated = group["cost_status"].get("estimated", 0)
    amount = (f"estimated 金额合计 {_exact(group['cost_cny_estimated_sum'])} "
              f"({estimated}/{group['runs']} 条)") if estimated else NOT_PRICED
    return (f"cost_status: {_statuses(group['cost_status'])}; {amount}; "
            f"无 estimated 成本 {group['runs_without_estimated_cost']} 条")


def _missing_cell(bucket: Bucket) -> str:
    parts = [f"{name} 缺 {count}" for name, count in sorted(bucket.field_missing.items())]
    for name, values in (("model_calls", bucket.calls), ("input_chars", bucket.chars),
                         ("latency_ms", bucket.latency)):
        absent = bucket.records - len(values)
        if absent:
            parts.append(f"{name} 缺 {absent}")
    return ", ".join(parts) or "无"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    return lines + ["| " + " | ".join(row) + " |" for row in rows]


def discover(scan_root: Path):
    """Split every ``*.jsonl`` holding ``result.budget`` into eval vs fixture.

    A path is a pytest fixture when one of its components starts with ``test_``,
    which is how ``--basetemp`` directories name their per-test subdirectories.
    """
    included, excluded = [], []
    for path in sorted(scan_root.rglob("*.jsonl")):
        try:
            records, _ = _load(path)
        except OSError:
            continue
        if not any(isinstance(_mapping(r.get("result")).get("budget"), dict) for r in records):
            continue
        if any(part.startswith("test_") for part in path.parts):
            excluded.append((path, len(records)))
        else:
            included.append((path, len(records)))
    return included, excluded


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_sources(raw: list[str], parser: argparse.ArgumentParser) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for item in raw:
        label, sep, value = item.partition("=")
        if not sep or not label.strip() or not value.strip():
            parser.error("--source must be LABEL=PATH")
        path = Path(value.strip())
        if not path.is_file():
            parser.error(f"--source path does not exist: {value.strip()}")
        sources[label.strip()] = path
    return sources


def _copies(record: dict, key: str) -> list[float]:
    """Every recorded copy of one metric, used to audit cross-field agreement."""
    result = _mapping(record.get("result"))
    budget = _mapping(result.get("budget"))
    found = [_number(container.get(key)) for container in (result, record, budget)]
    return [value for value in found if value is not None]


def _command(args: argparse.Namespace) -> str:
    parts = ["python scripts/report_eval_cost.py"]
    parts += ([f"--source {item}" for item in args.source] if args.source
              else [f"--scan-root {_rel(args.scan_root)}"])
    return " ".join([*parts, f"--out {_rel(args.out)}"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", default=[], metavar="LABEL=PATH",
                        help="evaluation artifact to aggregate; repeatable. When omitted the "
                             "scan root is used and pytest fixtures are excluded automatically.")
    parser.add_argument("--scan-root", type=Path, default=ROOT / "output",
                        help="root scanned for the exclusion census")
    parser.add_argument("--out", type=Path, required=True,
                        help="redacted markdown report; must be a new file under output/")
    args = parser.parse_args()

    if not args.out.resolve().is_relative_to((ROOT / "output").resolve()):
        parser.error("report must be written under the ignored output/ directory")
    if args.out.exists():
        parser.error(f"report path already exists, pick a new name: {_rel(args.out)}")

    found, excluded = discover(args.scan_root)
    selected = list(parse_sources(args.source, parser).items()) or [
        (_rel(path).removesuffix(".jsonl").removeprefix("output/"), path) for path, _ in found]

    total = Bucket()
    per_source: dict[str, Bucket] = {}
    per_arm: dict[tuple[str, str], Bucket] = {}
    per_case: dict[tuple[str, str, str], Bucket] = {}
    disagreements = Counter()
    bad_lines = 0
    for label, path in selected:
        rows, bad = _load(path)
        bad_lines += bad
        per_source[label] = Bucket()
        for index, record in enumerate(rows, start=1):
            for key in ("model_calls", "latency_ms"):
                if len(set(_copies(record, key))) > 1:
                    disagreements[key] += 1
            arm = record.get("arm")
            arm = arm if isinstance(arm, str) and arm else UNLABELED
            case = record.get("case_id")
            case = case if isinstance(case, str) and case else UNLABELED
            run_id = f"{label}#{index}"
            for bucket in (total, per_source[label],
                           per_arm.setdefault((label, arm), Bucket()),
                           per_case.setdefault((label, arm, case), Bucket())):
                bucket.add(run_id, record)

    agg = total.aggregate()
    reasons = Counter(_mapping(item["cost"]).get("reason", "-") for item in total.summaries)
    lines: list[str] = [
        "# 评测调用量/Token/延迟/成本 只读汇总 (QWEN-109)", "",
        "- 生成脚本: `scripts/report_eval_cost.py` (只读, 不 import os, 不读取 .env)",
        f"- 命令: `{_command(args)}`",
        "- 证据等级: offline (对本机已有评测产物的只读再汇总, 无模型调用)",
        "- 记账口径: 直接调用产品代码 `backend/app/services/run_usage.py` 的 "
        "`summarize_run_usage` + `aggregate_run_usage`, 脚本不自己另写一套成本/用量判定",
        "- 成本口径: 逐条照抄记录里的 `result.budget.cost`; 不套用任何单价, `unknown` 原样输出, "
        "绝不写成 0; 无 estimated 记录时金额一律显示为未记录",
        "- 字段来源: `model_calls`/token/cost/usage_status 全部走产品投影; `latency_ms` 是唯一"
        "例外, 按原始 `result.latency_ms` 读 (原因见下一行与第 2 节); `input_chars` 取 budget",
        f"- 与产品投影的偏差: latency_ms 有 {total.projection_dropped['latency_ms']} 条被投影判为"
        f"未记录, model_calls 有 {total.projection_dropped['model_calls']} 条",
        f"- 跨副本一致性: model_calls 不一致 {disagreements['model_calls']} 条, "
        f"latency_ms 不一致 {disagreements['latency_ms']} 条 "
        "(record / result / budget 三处副本互相校验)",
        f"- 记录总数 {total.records} 条, 来源 {len(selected)} 个, 无法解析的行 {bad_lines} 行",
        "",
    ]

    lines += ["## 1. 数据来源与样本量", "",
              "只统计真实评测产物; pytest 的 basetemp 夹具按路径组件 `test_*` 识别并整份排除。",
              ""]
    lines += _table(["来源标签", "路径", "记录数", "臂", "模型", "completed"],
                    [[label, f"`{_rel(path)}`", str(per_source[label].records),
                      _counter(Counter({arm: bucket.records for (src, arm), bucket
                                        in per_arm.items() if src == label})),
                      _counter(per_source[label].models),
                      _counter(per_source[label].completed)]
                     for label, path in selected])
    groups: Counter[str] = Counter()
    for path, count in excluded:
        try:
            key = path.resolve().relative_to(args.scan_root.resolve()).parts[0]
        except (ValueError, IndexError):
            key = _rel(path).split("/")[0]
        groups[key + "/..."] += count
    lines += ["",
              f"- 扫描根 `{_rel(args.scan_root)}` 下含 `result.budget` 的 `.jsonl` 共 "
              f"{len(found) + len(excluded)} 份",
              f"- 计入 {len(found)} 份 / {sum(n for _, n in found)} 条记录 "
              f"(本次汇总选用 {len(selected)} 份 / {total.records} 条)",
              f"- 排除 pytest 夹具 {len(excluded)} 份 / {sum(n for _, n in excluded)} 条记录",
              "",
              f"被排除的夹具按 `{_rel(args.scan_root)}` 下第一层目录归并, 数字为记录数:", ""]
    lines += _table(["目录", "被排除记录数"], [[k, str(v)] for k, v in sorted(groups.items())])

    lines += ["", "## 2. 未知项与缺失样本 (单列计数, 不补 0)", ""]
    lines += _table(["项", "计数", "说明"], [
        ["budget 有记录", f"{agg['budget_recorded_runs']}/{agg['runs']}",
         "run_usage 的 budget_recorded"],
        ["cost_status=unknown", str(agg["cost_status"].get("unknown", 0)),
         "运行时未配置 `V2_LLM_*_CNY_PER_MILLION` 单价 (usage_meter.py:29-37)"],
        ["cost_status=estimated", str(agg["cost_status"].get("estimated", 0)),
         "有单价时的估算成本"],
        ["cost.reason=cost_not_recorded", str(reasons["cost_not_recorded"]),
         "记录里根本没有 cost 对象"],
        ["cost.reason=no_cost_amount_recorded", str(reasons["no_cost_amount_recorded"]),
         "有 cost 对象但没有金额"],
        ["cost.reason=cost_status_invalid", str(reasons["cost_status_invalid"]),
         "status 不在产品允许集 (estimated/unknown)"],
        ["无 estimated 成本的记录", str(agg["runs_without_estimated_cost"]),
         "成本维度只能报 unknown"],
        ["estimated 金额合计", _exact(agg["cost_cny_estimated_sum"])
         if agg["cost_status"].get("estimated") else NOT_PRICED,
         "不套用单价, 无估算即不显示金额"],
        ["顶层 cost_cny 有值", str(total.top_cost_cny), "收集器写入的顶层成本字段"],
        ["无 token 数据的记录", str(agg["runs_without_token_data"]),
         "两侧 token 都无值, 不参与 token 求和"],
        ["usage_status=measured", str(agg["usage_status"].get("measured", 0)),
         "两侧 token 都有值"],
        ["usage_status=partial", str(agg["usage_status"].get("partial", 0)),
         "有 usage_unknown_calls"],
        ["usage_status=unknown", str(agg["usage_status"].get("unknown", 0)),
         "两侧 token 都无值"],
        ["usage_unknown_calls 合计", str(agg["usage_unknown_calls"]),
         "provider 没回 usage 的调用数"],
        ["actual_input_tokens 缺失", str(total.field_missing["actual_input_tokens"]),
         "输入 token 无值"],
        ["actual_output_tokens 缺失", str(total.field_missing["actual_output_tokens"]),
         "输出 token 无值"],
        ["model_calls 缺失", str(total.records - len(total.calls)), "调用数无值"],
        ["latency_ms 缺失", str(total.records - len(total.latency)), "延迟无值"],
        ["latency_ms 被产品投影判为未记录", str(total.projection_dropped["latency_ms"]),
         "已由 QWEN-104b/104c 修复: `run_usage.py` 的 `_number` 现接受非负 int/float 并要求 "
         "math.isfinite, 复跑本计数 127 -> 0; 本报告仍按原始值读, 本行由产品投影实时算出"],
        ["model_calls 被产品投影判为未记录", str(total.projection_dropped["model_calls"]),
         "同一规则; 实测 0 条, 说明调用数都记成了整数"],
        ["arm 未标注", str(sum(bucket.records for (_label, arm), bucket in per_arm.items()
                               if arm == UNLABELED)), "重跑/复测产物没有写臂标签"],
        ["config.model 未标注", str(total.models[UNLABELED]), "重跑/复测产物没有写模型名"],
        ["completed 未标注", str(total.completed[UNLABELED]),
         "record.completed 与 result.completed 都缺失"],
        ["result.error 有值", str(total.errors), "运行本身失败的记录, token 可能不完整"],
    ])
    lines += ["",
              "- `unknown` 的含义是**未记录**, 不是 0 元; 本报告不套用任何单价, 也不给折算金额。",
              f"- 产品聚合器自带的口径说明: {agg['note']}",
              ""]

    lines += ["## 3. 每臂汇总", ""]
    lines += _table(["来源", "臂", "样本", "completed", "调用数合计", "输入 token 合计",
                     "输出 token 合计", "input_chars 合计", "latency_ms 中位数 [min~max]",
                     "成本", "usage 状态", "无 token 数据", "缺失"],
                    [[label, arm, str(bucket.records), _counter(bucket.completed),
                      _total(bucket.calls, bucket.records),
                      _measured_total(group, "input_tokens"),
                      _measured_total(group, "output_tokens"),
                      _total(bucket.chars, bucket.records),
                      _latency(bucket.latency, bucket.records), _cost_cell(group),
                      _statuses(group["usage_status"]), str(group["runs_without_token_data"]),
                      _missing_cell(bucket)]
                     for (label, arm), bucket in sorted(per_arm.items())
                     for group in (bucket.aggregate(),)])
    lines += [""]

    lines += ["## 4. 每题明细", "",
              "单条记录直接取产品投影结果; `未记录` 表示原始记录里没有该字段, 不是 0。", ""]
    lines += _table(["来源", "臂", "题号", "调用数", "输入 token", "输出 token", "input_chars",
                     "latency_ms", "cost_status", "usage_status"],
                    [[label, arm, case, _cell(item["model_calls"]), _cell(item["input_tokens"]),
                      _cell(item["output_tokens"]), _cell(chars), _cell(latency),
                      item["cost_status"], item["usage_status"]]
                     for (label, arm, case), bucket in sorted(per_case.items())
                     for item, latency, chars in bucket.rows])
    lines += [""]

    lines += ["## 5. 跨来源合计与口径警告", ""]
    lines += _table(["维度", "值"], [
        ["记录总数", str(agg["runs"])],
        ["调用数合计", _total(total.calls, total.records)],
        ["输入 token 合计", _measured_total(agg, "input_tokens")],
        ["输出 token 合计", _measured_total(agg, "output_tokens")],
        ["input_chars 合计", _total(total.chars, total.records)],
        ["latency_ms 中位数 [min~max]", _latency(total.latency, total.records)],
        ["成本", _cost_cell(agg)],
        ["usage 状态", _statuses(agg["usage_status"])],
        ["无 token 数据", str(agg["runs_without_token_data"])],
        ["缺失", _missing_cell(total)],
    ])
    seen: dict[str, set[str]] = {}
    for label, _arm, case in per_case:
        seen.setdefault(case, set()).add(label)
    shared = sorted(case for case, labels in seen.items() if len(labels) > 1)
    lines += ["",
              f"- 合计是**记录求和**, 不是去重题数: 有 {len(shared)} 个题号出现在多个来源 "
              f"(例如 {', '.join(shared[:4])}), 同一题在不同轮次被重复计入。",
              "- 各来源的 `dataset_sha256` 并不相同 (重跑/复测产物甚至没有写该字段), 因此跨来源"
              "合计只能当作调用量上界, 不能当作一次评测的结果。",
              "- 数据集/证据摘要存在于原始记录中, 本报告按脱敏要求不复现其取值。",
              ""]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")
    print(f"[report-eval-cost] sources={len(selected)} records={total.records} "
          f"arms={len(per_arm)} cases={len(per_case)} "
          f"cost_status={_statuses(agg['cost_status'])} "
          f"runs_without_token_data={agg['runs_without_token_data']} "
          f"excluded_fixtures={len(excluded)} -> {_rel(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
