"""Agent 工具注册表 — Plan P1-1 闭环版

四个核心工具（lookup_knowledge_point / query_knowledge_graph /
execute_code / search_resources），全部接真实服务层：

  - lookup_knowledge_point / query_knowledge_graph → services/rag_service + knowledge_graph
  - execute_code → services/multimodal/code_sandbox (真实 AST+RestrictedPython)
  - search_resources → api/v1/artifacts/registry 的 artifact registry

新增：
  - ToolCallTrace：thread-safe 环形缓冲，前端 Workflow/Cockpit 拉取最近 N 条
  - traced_call()：所有内部 handler 入口都过一遍，自动记录 tool_name / args /
    result / latency / success。Service 异常会被吞掉转成 error 字段，保证 trace
    永远能返回。

设计参考：Plan P1-1 / AgentTutor 论文 (arxiv 2601.04219) "教学反思 + 工具调用"
"""
from __future__ import annotations

import hashlib
import logging
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

from backend.app.services.tool_audit import record_tool_event
from backend.app.services.tool_catalog import (
    INTERNAL_ROLE, TOOL_CATALOG, decide_access, source_specs,
)

logger = logging.getLogger(__name__)


# ============================================================
# Schema / 注册
# ============================================================
@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict
    required: List[str] = field(default_factory=list)

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


@dataclass
class ToolRegistration:
    schema: ToolSchema
    handler: Callable
    owner: str = "A"


# ============================================================
# Tool Call Trace — 环形缓冲 (thread-safe)
# ============================================================
@dataclass
class ToolCallRecord:
    tool: str
    args: Dict[str, Any]
    success: bool
    latency_ms: float
    timestamp: float = field(default_factory=time.time)
    result_preview: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "args": dict(self.args or {}),
            "success": bool(self.success),
            "latency_ms": round(float(self.latency_ms), 2),
            "timestamp": self.timestamp,
            "result_preview": self.result_preview,
            "error": self.error,
        }


class ToolCallTrace:
    """最近的 N 条 tool call，供前端 SSE / CockpitView 拉取。"""

    def __init__(self, max_size: int = 200, session_filter: bool = True):
        self._max = int(max_size)
        self._lock = threading.RLock()
        # 若启用 session_filter，按 session_id 分组；否则全局共享
        self._by_session: Dict[str, Deque[ToolCallRecord]] = {}
        self._global: Deque[ToolCallRecord] = deque(maxlen=self._max)
        self._session_filter = bool(session_filter)

    def record(self, record: ToolCallRecord, session_id: str = "") -> None:
        if not self._session_filter or not session_id:
            with self._lock:
                self._global.append(record)
            return
        with self._lock:
            buf = self._by_session.setdefault(session_id, deque(maxlen=self._max))
            buf.append(record)

    def recent(self, session_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            if self._session_filter and session_id:
                buf = self._by_session.get(session_id) or deque()
                items = list(buf)
            else:
                items = list(self._global)
        items.reverse()  # 最新在前
        return [r.to_dict() for r in items[:limit]]

    def stats(self, session_id: str = "") -> Dict[str, Any]:
        with self._lock:
            buf = (
                self._by_session.get(session_id, deque())
                if self._session_filter and session_id
                else self._global
            )
            items = list(buf)
        total = len(items)
        success = sum(1 for r in items if r.success)
        by_tool: Dict[str, int] = {}
        for r in items:
            by_tool[r.tool] = by_tool.get(r.tool, 0) + 1
        return {
            "total": total,
            "success": success,
            "failed": total - success,
            "success_rate": round(success / max(1, total), 3),
            "by_tool": by_tool,
        }

    def clear(self, session_id: str = "") -> None:
        with self._lock:
            if self._session_filter and session_id:
                self._by_session.pop(session_id, None)
            else:
                self._global.clear()


_trace: Optional[ToolCallTrace] = None


def get_tool_trace() -> ToolCallTrace:
    global _trace
    if _trace is None:
        _trace = ToolCallTrace()
    return _trace


def reset_tool_trace() -> None:
    global _trace
    _trace = None


# ============================================================
# 内部：traced_call 包装器
# ================================================================
def _request_hash(tool: str, kwargs: Dict[str, Any]) -> str:
    """Digest only — the unified audit never keeps an argument value."""
    payload = f"v1:{tool}:{sorted((str(k), repr(v)) for k, v in kwargs.items())}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _traced_call(tool: str, fn: Callable[..., Any], **kwargs: Any) -> Any:
    """统一记录 tool 调用耗时与成败。Service 异常吞掉并转成 dict。

    单一目录的 deny-by-default：未在 ``tool_catalog`` 登记的工具名不再执行 handler，
    返回结构化失败并写审计事件，所以"绕过注册表自己拼一个工具名"不会落到执行面。

    设计：fn 都是 closure 已经从外层捕获入参，所以这里**不**把 kwargs 透传给
    fn（否则 closure 函数会因为收到未声明的 kwarg 抛 TypeError）。kwargs 仅
    用于：(a) 抽取 __session_id__ 走 trace 的 session 过滤，(b) 写进 trace 的
    args 字段供前端展示。
    """
    session_id = str(kwargs.pop("__session_id__", "") or "")
    access = decide_access(INTERNAL_ROLE, tool)
    if not access.allowed:
        get_tool_trace().record(
            ToolCallRecord(tool=tool, args={}, success=False, latency_ms=0.0,
                           error=f"tool_access_denied: {access.reason}"),
            session_id=session_id)
        record_tool_event(tool=tool, spec=None, role=INTERNAL_ROLE, status="denied",
                          decision=access.reason, latency_ms=0,
                          request_hash=_request_hash(tool, kwargs), session_id=session_id)
        return {"success": False, "error": f"tool_access_denied: {access.reason}", "tool": tool}
    started = time.perf_counter()
    success = True
    error = ""
    error_class = ""
    result: Any = None
    try:
        # 修复：fn 是 closure，已经捕获入参；kwargs 仅用于 trace 记录，不再回传
        result = fn()
    except Exception as exc:  # noqa: BLE001
        success = False
        error = f"{type(exc).__name__}: {exc}"
        error_class = type(exc).__name__
        logger.warning("[tool:%s] failed: %s", tool, error)
        result = {"success": False, "error": error, "tool": tool}
    latency_ms = (time.perf_counter() - started) * 1000
    preview = ""
    try:
        if isinstance(result, dict):
            preview = str({k: v for k, v in result.items() if k != "kp"})[:200]
        else:
            preview = str(result)[:200]
    except Exception:  # noqa: BLE001
        preview = ""
    get_tool_trace().record(
        ToolCallRecord(
            tool=tool,
            args={k: v for k, v in kwargs.items() if k != "__session_id__"},
            success=success,
            latency_ms=latency_ms,
            result_preview=preview,
            error=error,
        ),
        session_id=session_id,
    )
    record_tool_event(tool=tool, spec=TOOL_CATALOG[tool], role=INTERNAL_ROLE,
                      status="success" if success else "failed", decision="granted",
                      reason=error_class, latency_ms=int(latency_ms),
                      request_hash=_request_hash(tool, kwargs), session_id=session_id)
    return result


# ============================================================
# 工具实现：全部接真实服务层
# ============================================================
async def _lookup_kp(kp_name: str, **kw: Any) -> Dict[str, Any]:
    """单点 RAG 检索：知识点 → top-K 文档片段。"""
    session_id = str(kw.pop("__session_id__", "") or "")

    def _do() -> Dict[str, Any]:
        try:
            from backend.app.services.rag_service import get_rag_service
            hits = get_rag_service().retrieve(kp_name, top_k=3)
            if not hits:
                return {"found": False, "kp": {"name": kp_name}, "source": "rag"}
            return {
                "found": True,
                "kp": {
                    "name": kp_name,
                    "chunks": [str(h.get("content", ""))[:500] for h in hits],
                    "sources": [h.get("source", "") for h in hits],
                },
                "source": "rag",
            }
        except Exception as exc:  # noqa: BLE001
            return {"found": False, "reason": f"RAG unavailable: {exc}", "kp": {"name": kp_name}}

    return _traced_call(
        "lookup_knowledge_point", _do,
        kp_name=kp_name,
        __session_id__=session_id,
    )


async def _query_kg(kp_name: str, hop: int = 2, **kw: Any) -> Dict[str, Any]:
    """2-hop 知识图谱子图：用于展示先修关系 / 语义相似图。"""
    session_id = str(kw.pop("__session_id__", "") or "")

    def _do() -> Dict[str, Any]:
        from backend.app.services.knowledge_graph.store import get_kg_store

        store = get_kg_store()
        # kp_name 既支持 id 也支持按 name 解析
        resolved = store.get_kp(kp_name)
        if resolved is None:
            candidates = store.find_by_name(kp_name)
            if not candidates:
                return {"found": False, "reason": "kp_not_found", "kp": kp_name}
            resolved = candidates[0]
        seed_id = resolved.id

        # 先修图（prerequisite 类型）
        prereq_relations = store.list_relations(kp_id=seed_id, relation_type="prerequisite")
        prereq_ids = sorted({r.source_id for r in prereq_relations} | {r.target_id for r in prereq_relations if r.target_id == seed_id})
        subgraph = store.get_subgraph([seed_id], hops=max(1, min(int(hop), 3)))

        # 语义相似：1-hop 内除 prerequisite 外的关系（related/extends/specialization/foundation）
        SIM_TYPES = {"related", "extends", "specialization", "foundation", "similar"}
        similar_neighbors = []
        for nb in store.get_neighbors(seed_id, direction="both"):
            if nb["relation_type"] in SIM_TYPES:
                similar_neighbors.append({
                    "kp_id": nb["kp_id"],
                    "relation_type": nb["relation_type"],
                    "weight": nb["weight"],
                })

        nodes = []
        for nid, row in subgraph.get("nodes", {}).items():
            nodes.append({
                "id": nid,
                "name": row.name,
                "course": row.course,
                "bloom": (row.metadata_data or {}).get("bloom", "Understand"),
            })

        return {
            "found": True,
            "center_kp": seed_id,
            "center_name": resolved.name,
            "depth": int(hop),
            "prereq_graph": {
                "nodes": nodes,
                "edges": [
                    {"source": s, "target": t, "type": rt, "weight": w}
                    for s, t, rt, w in subgraph.get("edges", [])
                ],
            },
            "similar_graph": {
                "neighbors": similar_neighbors,
                "note": "related/extends/specialization/foundation/similar 类型边",
            },
        }

    return _traced_call(
        "query_knowledge_graph", _do,
        kp_name=kp_name, hop=hop,
        __session_id__=session_id,
    )


async def _exec_code(language: str = "python", code: str = "", **kw: Any) -> Dict[str, Any]:
    """沙箱执行 Python 代码 — 真实接入 multimodal/code_sandbox。"""
    session_id = str(kw.pop("__session_id__", "") or "")
    timeout = kw.get("timeout", 5)

    def _do() -> Dict[str, Any]:
        if language and language != "python":
            return {"success": False, "passed": False, "error": f"language {language} not supported"}
        try:
            from backend.app.services.multimodal.code_sandbox import get_code_sandbox
            sandbox = get_code_sandbox()
            # 走默认策略；超时由沙箱 policy 控制，这里 timeout 仅做 hint
            result = sandbox.execute(code, level="auto")
            payload = result.to_dict()
            payload["tool"] = "execute_code"
            return payload
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
                "stdout": "",
                "stderr": "",
                "tool": "execute_code",
                "execution_level": 0,
            }

    return _traced_call("execute_code", _do, language=language, code=code, timeout=timeout, __session_id__=session_id)


async def _search_res(query: str, resource_type: str = "", **kw: Any) -> Dict[str, Any]:
    """搜索已生成的学习资源 — 真实接入 artifacts/registry。"""
    session_id = str(kw.pop("__session_id__", "") or "")
    limit = int(kw.get("limit", 5))

    def _do() -> Dict[str, Any]:
        try:
            # 优先用 artifacts/registry（单例，含文件存在性）
            from backend.app.api.v1.artifacts.registry import get_artifact_registry
            items = [
                rec.to_dict() for rec in get_artifact_registry().list(
                    artifact_type=resource_type, limit=200,
                )
            ]
            # 若 registry 空，再回退到 resources API 内存缓存（含 DB 写入的双写结果）
            if not items:
                try:
                    from backend.app.api.v1 import resources as r
                    items = list(r._resources.values())
                except Exception:  # noqa: BLE001
                    items = []
            q = (query or "").lower()
            matched = []
            for item in items:
                title = str(item.get("title") or item.get("metadata", {}).get("title", ""))
                content = str(item.get("content") or item.get("filepath") or "")
                if q and q not in (title + " " + content).lower():
                    continue
                matched.append({
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "title": title[:120],
                    "preview": content[:200],
                    "metadata": dict(item.get("metadata") or {}),
                    "exists": bool(item.get("exists")),
                    "created_at": item.get("created_at"),
                })
                if len(matched) >= limit:
                    break
            return {"found": len(matched), "results": matched, "total_pool": len(items)}
        except Exception as exc:  # noqa: BLE001
            return {"found": 0, "results": [], "error": f"{type(exc).__name__}: {exc}"}

    return _traced_call(
        "search_resources", _do,
        query=query, resource_type=resource_type, limit=limit,
        __session_id__=session_id,
    )


async def _generate_learning_materials(topic: str, types: List[str], **kw: Any) -> Dict[str, Any]:
    """统一生成学习资料（API 调用入口）。"""
    session_id = str(kw.pop("__session_id__", "") or "")
    user_id = str(kw.pop("user_id", "") or "")
    pptx_template = str(kw.get("pptx_template", "") or "").strip()[:80]
    # Tool 入口也做一次防御性压缩。这样即使未来请求模型调整，Agent 工具也不会
    # 因整段群聊协作提示过长而把 Pydantic ValidationError 暴露给学生。
    description = " ".join(str(kw.get("description", "")).split())
    if len(description) > 400:
        description = f"{description[:300].rstrip()} … {description[-96:].lstrip()}"[:400]
    
    def _do() -> Dict[str, Any]:
        import asyncio
        from backend.app.api.v1.artifacts.multi_with_fallback import generate_multi_with_fallback
        from backend.app.api.v1.artifacts.multi import MultiResourceRequest
        req = MultiResourceRequest(
            topic=topic,
            description=description,
            types=types,
            session_id=session_id,
            user_id=user_id,
            pptx_template=pptx_template or None,
            include_manim="manim" in types,
        )
        try:
            def run_in_new_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(generate_multi_with_fallback(req))
                finally:
                    loop.close()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                resp = pool.submit(run_in_new_loop).result()
            return resp.model_dump()
        except Exception as exc:
            return {"success": False, "error": str(exc), "tool": "generate_learning_materials"}

    return _traced_call(
        "generate_learning_materials", _do,
        topic=topic, types=types, __session_id__=session_id
    )


# ============================================================
# Registry
# ============================================================
class ToolRegistry:
    """The V1 agent tools. Their metadata lives in ``tool_catalog``, not here."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolRegistration] = {}
        handlers = {
            "lookup_knowledge_point": _lookup_kp,
            "query_knowledge_graph": _query_kg,
            "execute_code": _exec_code,
            "search_resources": _search_res,
            "generate_learning_materials": _generate_learning_materials,
        }
        for spec in source_specs("v1"):
            # Registering a new tool means adding one catalog entry plus its handler.
            self.register(
                ToolSchema(name=spec.name, description=spec.description,
                           parameters=spec.parameters, required=list(spec.required)),
                handlers[spec.name],
            )

    def register(self, schema: ToolSchema, handler: Callable) -> None:
        self._tools[schema.name] = ToolRegistration(schema=schema, handler=handler)

    def list_a_tools(self) -> List[ToolRegistration]:
        return list(self._tools.values())

    def to_openai_tools(self) -> List[dict]:
        return [t.schema.to_openai_format() for t in self._tools.values()]


_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
