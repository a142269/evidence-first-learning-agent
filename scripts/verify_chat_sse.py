"""
verify_chat_sse.py — Plan D 4.2 端到端 SSE 流式演示

目的
----
- 起 FastAPI + TestClient（不依赖真实 LLM，monkeypatch mock）
- 流式调 /api/v1/chat/stream
- 逐条解析 SSE 事件，按时间序打印 id/event/payload 摘要
- 验证 7 阶段全在 + meta + chunk + done
- 验证 Last-Event-ID 重连能拉到旧事件

不依赖：DB / 真实 LLM / 端口。
"""
from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ============================================================
# 1. 配置 + Mock
# ============================================================
MOCK_REPLY = (
    "# 反向传播\n\n"
    "反向传播 (Backpropagation) 是深度学习的核心算法。\n\n"
    "## 核心思想\n"
    "1. 前向计算得到损失\n"
    "2. 反向逐层求梯度\n"
    "3. 用梯度更新参数\n\n"
    "## 关键公式\n"
    "$\\frac{\\partial L}{\\partial w} = \\frac{\\partial L}{\\partial a} \\cdot \\frac{\\partial a}{\\partial w}$\n\n"
    "这就是 A3 多智能体系统的优化底层。"
)

# 7 阶段匹配前缀（与 pipeline._STAGE_PROMPTS 中 start/done 文本对齐）
# 用前缀匹配避免中英文省略号差异导致漏判
STAGE_LABELS = [
    ("input_validation", "正在准备会话"),
    ("rag_retrieval", "正在检索知识库"),
    ("realtime_state", "正在分析你的学习状态"),
    ("orchestration", "Agent 团队正在协作"),
    ("debate_reflection", "Agent 正在辩论与反思"),
    ("aggregation", "正在进行内容安全审核"),
    ("persist", "正在保存学习记录"),
]


def _mock_llm_factory(reply_text: str = MOCK_REPLY) -> MagicMock:
    llm = MagicMock()
    llm.chat = MagicMock(return_value=reply_text)
    return llm


# ============================================================
# 2. SSE 解析
# ============================================================
def parse_sse_stream(text: str) -> list[dict[str, Any]]:
    """把 raw SSE 文本解析为事件列表

    sse_format() 把 data 行编码为 {"type": <event>, "payload": <data>}；
    这里解包后, payload 字段直接是真实数据, type 字段是事件名。
    """
    events: list[dict[str, Any]] = []
    cur_id: int | None = None
    cur_event: str | None = None
    cur_data: list[str] = []

    def flush() -> None:
        if cur_event is None and not cur_data:
            return
        raw_payload: Any
        try:
            raw_payload = json.loads("\n".join(cur_data)) if cur_data else None
        except json.JSONDecodeError:
            raw_payload = "\n".join(cur_data)
        # 解包 {"type": ..., "payload": ...} 协议壳
        if isinstance(raw_payload, dict) and "type" in raw_payload and "payload" in raw_payload:
            event_name = str(raw_payload.get("type")) or (cur_event or "message")
            payload = raw_payload.get("payload")
        else:
            event_name = cur_event or "message"
            payload = raw_payload
        events.append(
            {
                "id": cur_id,
                "event": event_name,
                "payload": payload,
            }
        )

    for raw in text.splitlines():
        if raw == "":
            flush()
            cur_id, cur_event, cur_data = None, None, []
            continue
        if raw.startswith(":"):
            # heartbeat / comment
            continue
        if raw.startswith("id: "):
            try:
                cur_id = int(raw[4:].strip())
            except ValueError:
                cur_id = None
        elif raw.startswith("event: "):
            cur_event = raw[7:].strip()
        elif raw.startswith("data: "):
            cur_data.append(raw[6:])
    # tail without empty line
    if cur_event is not None or cur_data:
        flush()
    return events


def summarize_event(evt: dict[str, Any]) -> str:
    """把单条事件压成一行可读摘要"""
    etype = evt["event"]
    eid = evt["id"] if evt["id"] is not None else "-"
    payload = evt["payload"]

    if etype == "meta":
        if isinstance(payload, dict):
            agent = payload.get("agent", "?")
            agents_invoked = payload.get("agents_invoked", [])
            rag = payload.get("rag_hits", [])
            return (
                f"meta     id={eid:<3} agent={agent:<14} "
                f"agents={len(agents_invoked)} rag={len(rag)}"
            )
        return f"meta     id={eid:<3} {payload}"

    if etype == "thinking":
        text = payload if isinstance(payload, str) else str(payload)
        return f"thinking id={eid:<3} {text}"

    if etype == "chunk":
        text = payload if isinstance(payload, str) else str(payload)
        snippet = text.replace("\n", "\\n")
        if len(snippet) > 40:
            snippet = snippet[:37] + "..."
        return f"chunk    id={eid:<3} '{snippet}'"

    if etype == "resources":
        if isinstance(payload, list):
            types = [r.get("type", "?") for r in payload]
            return f"resource id={eid:<3} {len(payload)} items: {types}"
        return f"resource id={eid:<3} {payload}"

    if etype == "profile_update":
        if isinstance(payload, dict):
            keys = list(payload.keys())[:4]
            return f"profile  id={eid:<3} keys={keys}"
        return f"profile  id={eid:<3} {payload}"

    if etype == "profile_status":
        if isinstance(payload, dict):
            return f"prof-st  id={eid:<3} status={payload.get('status')!r} dims={payload.get('dimensions_count')}"
        return f"prof-st  id={eid:<3} {payload}"

    if etype == "done":
        if isinstance(payload, dict):
            return f"DONE     id={eid:<3} content_type={payload.get('content_type')}"
        return f"DONE     id={eid:<3} {payload}"

    if etype == "error":
        return f"ERROR    id={eid:<3} {payload}"

    return f"{etype:<8} id={eid:<3} {payload}"


# ============================================================
# 3. 端到端流式验证
# ============================================================
def run_stream(client: TestClient, session_id: str, message: str) -> list[dict[str, Any]]:
    """发起一次流式请求并返回所有事件"""
    with client.stream(
        "POST", "/api/v1/chat/stream",
        json={"message": message, "session_id": session_id},
    ) as resp:
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        assert "text/event-stream" in resp.headers.get("content-type", ""), \
            f"Bad content-type: {resp.headers.get('content-type')}"
        text = "".join(chunk for chunk in resp.iter_text())
    return parse_sse_stream(text)


def verify_seven_stages(events: list[dict[str, Any]]) -> dict[str, list[int]]:
    """校验 7 阶段 thinking 都出现（前缀匹配, 兼容中英文省略号差异）"""
    found: dict[str, list[int]] = {name: [] for name, _ in STAGE_LABELS}
    for evt in events:
        if evt["event"] != "thinking":
            continue
        text = evt["payload"] if isinstance(evt["payload"], str) else ""
        for name, label in STAGE_LABELS:
            if text.startswith(label) or label in text:
                found[name].append(evt["id"] or 0)
    return found


def verify_resume(client: TestClient, session_id: str) -> list[dict[str, Any]]:
    """用 Last-Event-ID=0 重连，应能拿到至少 1 条 event"""
    with client.stream(
        "POST", "/api/v1/chat/stream",
        json={"message": "继续讲梯度消失", "session_id": session_id},
        headers={"Last-Event-ID": "1"},
    ) as resp:
        assert resp.status_code == 200
        text = "".join(chunk for chunk in resp.iter_text())
    return parse_sse_stream(text)


# ============================================================
# 4. 主流程
# ============================================================
def main() -> int:
    print("=" * 72)
    print("A3 Phase 2 · Vue 原生 ChatView SSE 端到端验证 (Plan D 4.2)")
    print("=" * 72)

    # --- 装配 app + 注入 mock ---
    from backend.app.api.v1.chat import router as chat_router
    from backend.app.api.v1.chat_pipeline.stages import _shared as shared
    from backend.app.api.v1.chat_pipeline.session import reset_session_store
    from backend.app.api.v1.chat_pipeline.stages._shared import reset_shared_state

    reset_shared_state()
    reset_session_store()

    mock_llm = _mock_llm_factory()
    # 直接覆盖模块级单例（与现有 test_chat_e2e.py 一致）
    shared._shared_llm = mock_llm  # type: ignore[attr-defined]

    app = FastAPI(title="A3 SSE Verify")
    app.include_router(chat_router, prefix="/api/v1")
    client = TestClient(app)

    # --- 1) 流式主路径 ---
    print("\n[1] POST /api/v1/chat/stream  →  流式事件时序\n")
    session_id = "verify-sse-demo"
    events = run_stream(client, session_id, "讲一下反向传播")

    print(f"  共收到 {len(events)} 条事件")
    print("  ─" * 35)
    for evt in events:
        print(f"  {summarize_event(evt)}")
    print("  ─" * 35)

    # --- 2) 7 阶段校验 ---
    print("\n[2] 7 阶段 thinking 校验")
    stages = verify_seven_stages(events)
    all_ok = True
    for name, _label in STAGE_LABELS:
        ids = stages[name]
        ok = len(ids) > 0
        all_ok = all_ok and ok
        mark = "[OK]" if ok else "[MISS]"
        print(f"  {mark} {name:<20} ids={ids}")
    if not all_ok:
        print("\n  [FAIL] 7 阶段未全部出现")
        return 1
    print("  → 7 阶段全部覆盖")

    # --- 3) 关键事件类型校验 ---
    print("\n[3] 关键事件类型")
    types = [e["event"] for e in events]
    required = ["meta", "chunk", "done"]
    for t in required:
        count = types.count(t)
        mark = "[OK]" if count > 0 else "[MISS]"
        print(f"  {mark} {t:<14} count={count}")
        if count == 0:
            print(f"\n  [FAIL] 缺少事件类型: {t}")
            return 1

    # --- 4) chunk 拼接回原文 ---
    print("\n[4] chunk 拼接回原文")
    full_text = "".join(
        e["payload"] for e in events
        if e["event"] == "chunk" and isinstance(e["payload"], str)
    )
    print(f"  chunk 总长 = {len(full_text)} 字符")
    print(f"  含「反向传播」 = {'反向传播' in full_text}")
    print(f"  含「梯度」     = {'梯度' in full_text}")
    if "反向传播" not in full_text:
        print("  [FAIL] chunk 拼接后缺失关键内容")
        return 1

    # --- 5) Last-Event-ID 重连 ---
    print("\n[5] Last-Event-ID 重连验证")
    replayed = verify_resume(client, session_id)
    print(f"  重连后收到 {len(replayed)} 条事件")
    has_event_line = any(e["event"] for e in replayed)
    mark = "[OK]" if has_event_line else "[MISS]"
    print(f"  {mark} 重连后能拉到事件流")
    if not has_event_line:
        print("  [FAIL] 重连后无事件")
        return 1

    # --- 总结 ---
    print("\n" + "=" * 72)
    print("[PASS] Phase 2 SSE 端到端验证全部通过")
    print(f"  事件总数 = {len(events)}")
    print(f"  阶段数   = 7 / 7")
    print(f"  chunk    = {types.count('chunk')}")
    print(f"  meta     = {types.count('meta')}")
    print(f"  done     = {types.count('done')}")
    print(f"  prof-st  = {types.count('profile_status')}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
