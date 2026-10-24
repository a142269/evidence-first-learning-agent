"""Single source of truth for tool metadata and the runtime permission matrix.

Before this module existed, tool knowledge was spread over three places: the V1
``ToolRegistry`` (name/description/JSON-schema), the V2 broker's ``ROLE_TOOLS``
and ``SCHEMAS`` dictionaries, and the MCP adapter's own decorated functions. A
new tool therefore had to be declared in several files, and forgetting one left
an undeclared capability behind. Every callable tool is now described here once,
and access is decided by ``decide_access`` with deny-by-default semantics: a call
is allowed only if the tool is registered, the caller role is listed for it, and
that role actually holds the tool's permission key.

The baseline matrix reproduces the behaviour that the two registries had before,
so nothing is newly permitted or newly revoked; roles that need a different
grant are a product decision, not an executor decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


TOOL_VERSION_V1 = "v1-agent-1"
TOOL_VERSION_V2 = "v2-readonly-1"

# The V1 agent tools are reached only from in-process product code (the resource
# generator agent and the artifact warm-up path); there is no external caller that
# can name a role, so they are granted to this one internal role.
INTERNAL_ROLE = "system"
GRAPH_ROLES = ("planner", "tutor", "practice", "reviewer")

TimeoutClass = Literal["standard", "search"]


class ToolArgs(BaseModel):
    """Base for tool arguments: unknown keys are refused, never ignored."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchArgs(ToolArgs):
    query: str = Field(min_length=1, max_length=500)


class EmptyArgs(ToolArgs):
    pass


class PrerequisiteArgs(ToolArgs):
    knowledge_point_id: str = Field(min_length=1, max_length=128)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    source: Literal["v1", "v2"]
    description: str
    permission_key: str
    allowed_roles: frozenset[str]
    side_effect: bool
    version: str
    # ``None`` means the runtime gate does not enforce a timeout because the
    # handler owns it (the code sandbox policy); it is never a placeholder copy
    # of a number nothing reads.
    timeout_seconds: Optional[float] = None
    timeout_class: TimeoutClass = "standard"
    args_model: Optional[type[ToolArgs]] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    max_result_items: Optional[int] = None
    mcp_exposed: bool = False


def _v2(name: str, description: str, permission_key: str, roles: tuple[str, ...],
        args_model: type[ToolArgs], *, timeout_seconds: float,
        timeout_class: TimeoutClass = "standard",
        max_result_items: Optional[int] = None) -> ToolSpec:
    return ToolSpec(
        name=name, source="v2", description=description, permission_key=permission_key,
        allowed_roles=frozenset(roles), side_effect=False, version=TOOL_VERSION_V2,
        timeout_seconds=timeout_seconds, timeout_class=timeout_class,
        args_model=args_model, max_result_items=max_result_items, mcp_exposed=True,
    )


def _v1(name: str, description: str, permission_key: str, parameters: dict[str, Any],
        required: tuple[str, ...], *, side_effect: bool,
        timeout_seconds: Optional[float] = None) -> ToolSpec:
    return ToolSpec(
        name=name, source="v1", description=description, permission_key=permission_key,
        allowed_roles=frozenset({INTERNAL_ROLE}), side_effect=side_effect,
        version=TOOL_VERSION_V1, timeout_seconds=timeout_seconds,
        parameters=parameters, required=required, mcp_exposed=False,
    )


_SPECS: tuple[ToolSpec, ...] = (
    _v2("search_course_evidence", "Read cited course evidence within one course scope.",
        "course:evidence:search", ("tutor",), SearchArgs,
        timeout_seconds=30.0, timeout_class="search", max_result_items=5),
    _v2("get_learning_profile", "Read the learner's allowed preference fields and course mastery.",
        "learning:profile:read", ("planner",), EmptyArgs, timeout_seconds=10.0),
    _v2("get_recent_mistakes", "Read recent mistakes for one course.",
        "learning:mistakes:read", ("planner",), EmptyArgs, timeout_seconds=10.0),
    _v2("get_prerequisites", "Read prerequisite knowledge points of one course.",
        "learning:prerequisites:read", ("planner",), PrerequisiteArgs, timeout_seconds=10.0),
    _v1("lookup_knowledge_point",
        "查询知识库中某个知识点（按名称）相关的 RAG 文档片段。", "knowledge:lookup",
        {"kp_name": {"type": "string", "description": "知识点名称或 ID"}}, ("kp_name",),
        side_effect=False),
    _v1("query_knowledge_graph",
        "查询知识图谱中某知识点周围 N 跳子图，分别返回先修图与语义相似图。", "knowledge:graph:query",
        {"kp_name": {"type": "string", "description": "知识点名称或 ID"},
         "hop": {"type": "integer", "default": 2, "minimum": 1, "maximum": 3}},
        ("kp_name",), side_effect=False),
    _v1("execute_code",
        "在受限沙箱（AST + RestrictedPython + 子进程三级降级）中执行 Python 代码。",
        "code:sandbox:execute",
        {"language": {"type": "string", "enum": ["python"], "default": "python"},
         "code": {"type": "string", "description": "要执行的 Python 源码"},
         "timeout": {"type": "integer", "default": 5, "minimum": 1, "maximum": 30}},
        ("code",), side_effect=True),
    _v1("search_resources",
        "按关键词 + 类型检索已经生成的学习资源（pptx / mermaid / code / document / manim）。",
        "resource:search",
        {"query": {"type": "string"},
         "resource_type": {"type": "string",
                           "enum": ["pptx", "mermaid", "code", "document", "manim", "tts"]},
         "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 50}},
        ("query",), side_effect=False),
    _v1("generate_learning_materials",
        "一次性生成多模态课程资料、PPT、练习题等。当用户要求生成资源或资料时调用。",
        "material:generate",
        {"topic": {"type": "string", "description": "资料的主题"},
         "types": {"type": "array",
                   "items": {"type": "string",
                             "enum": ["pptx", "mermaid", "code", "document", "manim", "tts", "quiz"]},
                   "description": "要生成的资源类型列表"},
         "description": {"type": "string", "description": "补充描述（选填）"},
         "pptx_template": {"type": "string",
                           "description": "可选 PPT 模板名（data/pptx_templates 下的文件名）"}},
        ("topic", "types"), side_effect=True),
)

TOOL_CATALOG: dict[str, ToolSpec] = {spec.name: spec for spec in _SPECS}
assert len(TOOL_CATALOG) == len(_SPECS), "duplicate tool name in the catalog"

# Which permission keys each role holds. Practice and Reviewer deliberately hold
# nothing: they only consume what the plan already retrieved.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "planner": frozenset({"learning:profile:read", "learning:mistakes:read",
                          "learning:prerequisites:read"}),
    "tutor": frozenset({"course:evidence:search"}),
    "practice": frozenset(),
    "reviewer": frozenset(),
    INTERNAL_ROLE: frozenset({spec.permission_key for spec in _SPECS if spec.source == "v1"}),
}

Refusal = Literal["unknown_role", "unknown_tool", "role_not_allowed", "permission_not_granted"]


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str
    spec: Optional[ToolSpec] = None


def source_specs(source: str) -> tuple[ToolSpec, ...]:
    """The registered tools of one surface, in catalog order."""
    return tuple(spec for spec in _SPECS if spec.source == source)


def tools_for_role(role: str) -> frozenset[str]:
    granted = ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(spec.name for spec in _SPECS if spec.permission_key in granted)


def decide_access(role: str, name: str) -> AccessDecision:
    """Deny-by-default: anything not positively granted by the matrix is refused."""
    spec = TOOL_CATALOG.get(name)
    if spec is None:
        return AccessDecision(False, "unknown_tool")
    if role not in ROLE_PERMISSIONS:
        return AccessDecision(False, "unknown_role", spec)
    if role not in spec.allowed_roles:
        return AccessDecision(False, "role_not_allowed", spec)
    if spec.permission_key not in ROLE_PERMISSIONS[role]:
        return AccessDecision(False, "permission_not_granted", spec)
    return AccessDecision(True, "granted", spec)


def matrix_violations() -> list[str]:
    """Roles listed on a spec that do not hold its permission key, or the reverse."""
    problems: list[str] = []
    for spec in _SPECS:
        for role in sorted(spec.allowed_roles):
            if spec.permission_key not in ROLE_PERMISSIONS.get(role, frozenset()):
                problems.append(f"{spec.name}: role {role} is listed but lacks {spec.permission_key}")
    for role, granted in ROLE_PERMISSIONS.items():
        for key in sorted(granted):
            if not any(spec.permission_key == key and role in spec.allowed_roles for spec in _SPECS):
                problems.append(f"{role}: holds {key} but no allowing tool is registered")
    return problems


def v2_timeouts() -> tuple[float, float]:
    """(standard, search) defaults read from the specs, never from a literal here."""
    standards = [spec.timeout_seconds for spec in _SPECS
                 if spec.source == "v2" and spec.timeout_class == "standard"]
    searches = [spec.timeout_seconds for spec in _SPECS
                if spec.source == "v2" and spec.timeout_class == "search"]
    assert standards and searches and len(set(standards)) == 1 and len(searches) == 1
    return float(standards[0]), float(searches[0])
