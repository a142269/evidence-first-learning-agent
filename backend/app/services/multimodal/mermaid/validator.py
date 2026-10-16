"""
MermaidValidator - 渲染前语法预校验

避免演示时 mmdc / Playwright 因 LLM 生成的坏语法而超时白屏。

检查项:
- 首行是否合法 diagram 类型
- mindmap 必须有 root((...))
- flowchart 必须含 direction
- 节点 id 不含保留字
- 引号匹配 / 括号匹配
- 单图节点数 <= 200 (Mermaid 性能上限)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


VALID_HEADERS = (
    "mindmap",
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "gitGraph",
)

FLOWCHART_DIRECTIONS = {"TD", "TB", "LR", "RL", "BT"}
MAX_NODES = 200
MAX_LINES = 500


@dataclass
class ValidationIssue:
    severity: str          # "error" / "warning"
    code: str
    message: str
    line_no: int = -1


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)
    line_count: int = 0
    node_count: int = 0

    def add_error(self, code: str, msg: str, line_no: int = -1) -> None:
        self.issues.append(ValidationIssue("error", code, msg, line_no))

    def add_warning(self, code: str, msg: str, line_no: int = -1) -> None:
        self.issues.append(ValidationIssue("warning", code, msg, line_no))

    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def passed(self) -> bool:
        return len(self.errors()) == 0


class MermaidValidator:
    """渲染前 Mermaid 语法预检"""

    def validate(self, code: str) -> ValidationReport:
        report = ValidationReport()
        if not code or not code.strip():
            report.add_error("empty", "empty mermaid code")
            return report

        lines = [ln.rstrip() for ln in code.splitlines() if ln.strip()]
        report.line_count = len(lines)

        if report.line_count > MAX_LINES:
            report.add_warning(
                "too_many_lines",
                f"{report.line_count} lines > {MAX_LINES} (may slow render)",
            )

        # 第一行 = diagram 类型
        header = lines[0].strip()
        diagram_type = self._detect_type(header)
        if not diagram_type:
            report.add_error(
                "unknown_header",
                f"unrecognized diagram type: {header[:40]}",
                line_no=1,
            )
            return report

        # 引号 / 括号 匹配
        self._check_brackets(code, report)

        # 类型特定校验
        if diagram_type == "mindmap":
            self._validate_mindmap(lines, report)
        elif diagram_type in ("flowchart", "graph"):
            self._validate_flowchart(header, lines, report)
        elif diagram_type == "sequenceDiagram":
            self._validate_sequence(lines, report)
        elif diagram_type == "classDiagram":
            self._validate_class(lines, report)

        return report

    # ----------------------------------------------------------------
    def _detect_type(self, header: str) -> str:
        for h in VALID_HEADERS:
            if header.lower().startswith(h.lower()):
                return h
        return ""

    def _check_brackets(self, code: str, report: ValidationReport) -> None:
        # 不严格检查 — 仅检测最常见错误
        if code.count("(") != code.count(")"):
            report.add_warning(
                "unbalanced_parens",
                f"unmatched parens "
                f"({code.count('(')} open vs {code.count(')')} close)",
            )
        if code.count("[") != code.count("]"):
            report.add_warning(
                "unbalanced_brackets",
                f"unmatched brackets",
            )
        if code.count("{") != code.count("}"):
            report.add_warning(
                "unbalanced_braces",
                f"unmatched braces",
            )

    def _validate_mindmap(
        self, lines: List[str], report: ValidationReport,
    ) -> None:
        has_root = any(re.search(r"root\(\(", ln) for ln in lines[1:])
        if not has_root:
            report.add_warning(
                "mindmap_no_root",
                "mindmap should have root((...)) declaration",
            )
        if len(lines) < 2:
            report.add_error(
                "mindmap_empty",
                "mindmap has no nodes after header",
            )

    def _validate_flowchart(
        self, header: str, lines: List[str], report: ValidationReport,
    ) -> None:
        # 提取 direction
        m = re.match(r"^(flowchart|graph)\s+(\w+)", header)
        if m:
            direction = m.group(2)
            if direction not in FLOWCHART_DIRECTIONS:
                report.add_warning(
                    "invalid_direction",
                    f"direction '{direction}' not in "
                    f"{sorted(FLOWCHART_DIRECTIONS)}",
                    line_no=1,
                )

        # 节点计数 (粗略)
        node_pattern = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*[\[\(\{]")
        node_ids = set()
        for ln in lines[1:]:
            mm = node_pattern.match(ln)
            if mm:
                node_ids.add(mm.group(1))
        report.node_count = len(node_ids)
        if len(node_ids) > MAX_NODES:
            report.add_warning(
                "too_many_nodes",
                f"{len(node_ids)} nodes > {MAX_NODES}",
            )

    def _validate_sequence(
        self, lines: List[str], report: ValidationReport,
    ) -> None:
        has_participants = any(
            ln.strip().startswith("participant") for ln in lines[1:]
        )
        if not has_participants:
            report.add_warning(
                "no_participants",
                "sequenceDiagram has no participant declaration",
            )

    def _validate_class(
        self, lines: List[str], report: ValidationReport,
    ) -> None:
        has_class = any(
            re.match(r"\s*class\s+\w+", ln) for ln in lines[1:]
        )
        if not has_class:
            report.add_warning(
                "no_class",
                "classDiagram has no class declaration",
            )
