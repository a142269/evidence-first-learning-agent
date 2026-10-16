"""
SSE Events 协议 + 断线重连 (Last-Event-ID)

设计:
- 每个 SSE 事件含 id (递增) / event (类型) / data (JSON)
- EventBuffer 缓存最近 N 个事件, 客户端断线重连时从 Last-Event-ID 起重放
- 心跳事件不计入 id

参考: HTML5 Server-Sent Events spec + EventSource Last-Event-ID 头
"""
from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional


@dataclass
class SSEEvent:
    """单条 SSE 事件"""
    event_id: int
    event_type: str
    payload: Any
    created_at: float

    def to_sse_lines(self) -> str:
        """编码为 SSE 文本格式"""
        return sse_format(
            event_type=self.event_type,
            payload=self.payload,
            event_id=self.event_id,
        )


def sse_format(
    event_type: str,
    payload: Any,
    event_id: Optional[int] = None,
) -> str:
    """格式化为 SSE 文本帧

    格式:
        id: 42
        event: chunk
        data: {"type": "chunk", "payload": "hello"}
        <空行>

    心跳用 sse_heartbeat() 而非本函数。
    """
    body = {"type": event_type, "payload": payload}
    data_line = "data: " + json.dumps(body, ensure_ascii=False)

    lines: List[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(data_line)
    return "\n".join(lines) + "\n\n"


def sse_heartbeat() -> str:
    """SSE 心跳帧 (注释行, 不触发 onmessage)"""
    return ": heartbeat\n\n"


# ================================================================
# 断线重连缓存
# ================================================================
class EventBuffer:
    """SSE 事件缓存 - 支持 Last-Event-ID 重连

    用法:
        buffer = EventBuffer(session_id="sess_xxx", capacity=200)
        # 发送时
        evt = buffer.publish("chunk", "hello")
        yield evt.to_sse_lines()

        # 重连时
        for evt in buffer.replay_after(last_event_id=15):
            yield evt.to_sse_lines()

    注意: in-memory 实现, 跨进程重连需替换为 Redis Stream。
    """

    def __init__(self, session_id: str, capacity: int = 200):
        self.session_id = session_id
        self.capacity = capacity
        self._events: Deque[SSEEvent] = deque(maxlen=capacity)
        self._next_id = 1

    def publish(self, event_type: str, payload: Any) -> SSEEvent:
        """发布一条事件并缓存"""
        evt = SSEEvent(
            event_id=self._next_id,
            event_type=event_type,
            payload=payload,
            created_at=time.time(),
        )
        self._events.append(evt)
        self._next_id += 1
        return evt

    def replay_after(self, last_event_id: int) -> List[SSEEvent]:
        """重放 last_event_id 之后的所有事件

        如果 last_event_id 已被淘汰, 返回缓冲区全部 (客户端会重新对齐)。
        """
        if last_event_id <= 0:
            return list(self._events)
        return [e for e in self._events if e.event_id > last_event_id]

    def size(self) -> int:
        return len(self._events)

    @property
    def latest_id(self) -> int:
        return self._next_id - 1


# ================================================================
# 全局 buffer 注册表 (会话级)
# ================================================================
_buffers: Dict[str, EventBuffer] = {}
_BUFFERS_MAX = 1000


def get_or_create_buffer(session_id: str, capacity: int = 200) -> EventBuffer:
    """获取或新建会话级事件缓存"""
    # 简单 LRU 淘汰避免内存泄漏
    if len(_buffers) >= _BUFFERS_MAX:
        oldest = next(iter(_buffers))
        _buffers.pop(oldest, None)
    if session_id not in _buffers:
        _buffers[session_id] = EventBuffer(session_id, capacity=capacity)
    return _buffers[session_id]


def clear_buffer(session_id: str) -> None:
    _buffers.pop(session_id, None)


def parse_last_event_id(header_value: Optional[str]) -> int:
    """解析 Last-Event-ID 头, 失败返回 0"""
    if not header_value:
        return 0
    try:
        return max(0, int(header_value.strip()))
    except (ValueError, AttributeError):
        return 0
