"""Persistence for the student mobile course-group experience.

The mobile tables are deliberately isolated from the legacy group-chat tables
used by the web teacher console.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any
import uuid

from sqlalchemy.exc import IntegrityError

from backend.app.core.database import SessionLocal
from backend.app.core.models import (
    MobileCourseRoomRecord,
    MobileRoomMemberRecord,
    MobileRoomMessageRecord,
    MobileRoomReadRecord,
)

DEFAULT_ROOM_ID = "mobile-ai-course-2026"
MOBILE_AGENT_MEMBERS = (
    ("agent-planner", "智狐 · 规划伙伴", "agent"),
    ("agent-content", "阿匠 · 资源伙伴", "agent"),
    ("ai-assistant", "智灵 · 讲解伙伴", "agent"),
    ("agent-quiz", "小龙 · 练习伙伴", "agent"),
    ("agent-evaluation", "团团 · 评估伙伴", "agent"),
    ("agent-safety", "球球 · 守护伙伴", "agent"),
)
MOBILE_TEACHER_MEMBER = ("teacher", "王老师", "teacher")
MOBILE_DEFAULT_MEMBERS = (
    ("demo-student-1", "杜同学", "student"),
    ("demo-student-21", "林同学", "student"),
    MOBILE_TEACHER_MEMBER,
    *MOBILE_AGENT_MEMBERS,
)
MOBILE_DIRECT_PEERS = (*MOBILE_AGENT_MEMBERS, MOBILE_TEACHER_MEMBER)
_DIRECT_WELCOME_MESSAGES = {
    "agent-planner": "你好，我是智狐。需要规划学习目标和进度时，可以直接问我。",
    "agent-content": "你好，我是阿匠。需要整理课程资料或学习内容时，可以直接找我。",
    "ai-assistant": "你好，我是智灵。知识点没听懂或想继续追问，都可以发给我。",
    "agent-quiz": "你好，我是小龙。想做练习、变式题或巩固知识时，可以直接找我。",
    "agent-evaluation": "你好，我是团团。需要分析作答和改进方向时，可以发给我。",
    "agent-safety": "你好，我是球球。我可以帮助检查学习内容并提供安全提醒。",
    "teacher": "你好，我是王老师。有课程学习问题可以给我留言。",
}
_MOBILE_AGENT_ORDER = {
    user_id: index for index, (user_id, _name, _role) in enumerate(MOBILE_AGENT_MEMBERS)
}
VALID_MOBILE_MESSAGE_TYPES = frozenset(
    {"text", "resource_card", "agent_reply", "system_notice"}
)


def _room_dict(row: MobileCourseRoomRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "course": row.course,
        "name": row.name,
        "description": row.description,
        "avatar_key": row.avatar_key,
        "created_at": row.created_at,
    }


def _member_dict(row: MobileRoomMemberRecord) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "display_name": row.display_name,
        "role": row.role,
        "joined_at": row.joined_at,
    }


def _message_dict(row: MobileRoomMessageRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "room_id": row.room_id,
        "sender_id": row.sender_id,
        "sender_name": row.sender_name,
        "sender_role": row.sender_role,
        "content": row.content,
        "message_type": row.message_type,
        "client_message_id": row.client_message_id,
        "reply_to_id": row.reply_to_id,
        "mentions": list(row.mentions or []),
        "payload": dict(row.payload or {}),
        "created_at": row.created_at,
    }


def _direct_room_id(student_id: str, peer_id: str) -> str:
    digest = hashlib.sha256(f"{student_id}\0{peer_id}".encode()).hexdigest()[:24]
    return f"mobile-dm-{digest}"


def _room_type(room: MobileCourseRoomRecord) -> str:
    return "direct" if room.avatar_key.startswith("dm:") else "group"


class MobileChatRepository:
    def ensure_defaults(self) -> dict[str, int]:
        """Create the demo course group and memberships idempotently."""
        created = {"rooms": 0, "members": 0, "messages": 0}
        now = time.time()
        with SessionLocal() as db:
            room = db.get(MobileCourseRoomRecord, DEFAULT_ROOM_ID)
            if room is None:
                room = MobileCourseRoomRecord(
                    id=DEFAULT_ROOM_ID,
                    course="artificial_intelligence",
                    name="人工智能课程协作群",
                    description="同学、教师与学习助理共同参与的课程群",
                    avatar_key="bot",
                    created_by="system",
                    created_at=now,
                )
                db.add(room)
                created["rooms"] += 1
            for user_id, display_name, role in MOBILE_DEFAULT_MEMBERS:
                exists = (
                    db.query(MobileRoomMemberRecord)
                    .filter_by(room_id=DEFAULT_ROOM_ID, user_id=user_id)
                    .first()
                )
                if exists is None:
                    db.add(MobileRoomMemberRecord(
                        room_id=DEFAULT_ROOM_ID,
                        user_id=user_id,
                        display_name=display_name,
                        role=role,
                        joined_at=now,
                    ))
                    created["members"] += 1
                elif exists.display_name != display_name or exists.role != role:
                    exists.display_name = display_name
                    exists.role = role
            welcome = (
                db.query(MobileRoomMessageRecord)
                .filter_by(
                    room_id=DEFAULT_ROOM_ID,
                    sender_id="system",
                    client_message_id="seed-welcome-v1",
                )
                .first()
            )
            if welcome is None:
                db.add(MobileRoomMessageRecord(
                    id=f"mm_{uuid.uuid4().hex[:16]}",
                    room_id=DEFAULT_ROOM_ID,
                    sender_id="system",
                    sender_name="系统通知",
                    sender_role="system",
                    content="欢迎进入人工智能课程协作群，可以 @AI 发起学习讨论。",
                    message_type="system_notice",
                    client_message_id="seed-welcome-v1",
                    mentions=[],
                    payload={},
                    created_at=now,
                ))
                created["messages"] += 1
            db.commit()
        return created

    def ensure_student_direct_rooms(
        self, student_id: str, student_name: str,
    ) -> dict[str, int]:
        """Lazily create one isolated DM per Agent and teacher for a student."""
        created = {"rooms": 0, "members": 0, "messages": 0}
        now = time.time()
        with SessionLocal() as db:
            for index, (peer_id, peer_name, peer_role) in enumerate(MOBILE_DIRECT_PEERS):
                room_id = _direct_room_id(student_id, peer_id)
                room = db.get(MobileCourseRoomRecord, room_id)
                if room is None:
                    room = MobileCourseRoomRecord(
                        id=room_id,
                        course="artificial_intelligence",
                        name=peer_name.split(" · ", maxsplit=1)[0],
                        description=(
                            peer_name.split(" · ", maxsplit=1)[1]
                            if " · " in peer_name
                            else "课程教师"
                        ),
                        avatar_key=f"dm:{peer_id}",
                        created_by=student_id,
                        created_at=now + index * 0.001,
                    )
                    db.add(room)
                    created["rooms"] += 1
                else:
                    room.name = peer_name.split(" · ", maxsplit=1)[0]
                    room.avatar_key = f"dm:{peer_id}"

                direct_members = (
                    (student_id, student_name, "student"),
                    (peer_id, peer_name, peer_role),
                )
                for user_id, display_name, role in direct_members:
                    membership = (
                        db.query(MobileRoomMemberRecord)
                        .filter_by(room_id=room_id, user_id=user_id)
                        .first()
                    )
                    if membership is None:
                        db.add(MobileRoomMemberRecord(
                            room_id=room_id,
                            user_id=user_id,
                            display_name=display_name,
                            role=role,
                            joined_at=now + index * 0.001,
                        ))
                        created["members"] += 1
                    else:
                        membership.display_name = display_name
                        membership.role = role

                welcome = (
                    db.query(MobileRoomMessageRecord)
                    .filter_by(
                        room_id=room_id,
                        sender_id=peer_id,
                        client_message_id="seed-dm-welcome-v1",
                    )
                    .first()
                )
                if welcome is None:
                    welcome = MobileRoomMessageRecord(
                        id=f"mm_{uuid.uuid4().hex[:16]}",
                        room_id=room_id,
                        sender_id=peer_id,
                        sender_name=peer_name,
                        sender_role=peer_role,
                        content=_DIRECT_WELCOME_MESSAGES[peer_id],
                        message_type="agent_reply" if peer_role == "agent" else "text",
                        client_message_id="seed-dm-welcome-v1",
                        mentions=[student_id],
                        payload={"source": "mobile_direct_seed"},
                        created_at=now + index * 0.001,
                    )
                    db.add(welcome)
                    created["messages"] += 1
                db.flush()

                read = (
                    db.query(MobileRoomReadRecord)
                    .filter_by(room_id=room_id, user_id=student_id)
                    .first()
                )
                if read is None:
                    db.add(MobileRoomReadRecord(
                        room_id=room_id,
                        user_id=student_id,
                        last_message_id=welcome.id,
                        last_read_at=welcome.created_at,
                    ))
            db.commit()
        return created

    def require_member(self, room_id: str, user_id: str) -> MobileRoomMemberRecord:
        with SessionLocal() as db:
            row = (
                db.query(MobileRoomMemberRecord)
                .filter_by(room_id=room_id, user_id=user_id)
                .first()
            )
            if row is None:
                raise PermissionError("mobile_room_membership_required")
            db.expunge(row)
            return row

    def list_members(self, room_id: str, user_id: str) -> list[dict[str, Any]]:
        self.require_member(room_id, user_id)
        with SessionLocal() as db:
            rows = (
                db.query(MobileRoomMemberRecord)
                .filter_by(room_id=room_id)
                .order_by(MobileRoomMemberRecord.role, MobileRoomMemberRecord.joined_at)
                .all()
            )
            members = [_member_dict(row) for row in rows]
            members.sort(key=lambda member: (
                0 if member["role"] == "agent" else 1 if member["role"] == "teacher" else 2,
                _MOBILE_AGENT_ORDER.get(member["user_id"], 99),
                member["display_name"],
            ))
            return members

    def member_ids(self, room_id: str) -> list[str]:
        with SessionLocal() as db:
            return [
                row[0]
                for row in db.query(MobileRoomMemberRecord.user_id)
                .filter_by(room_id=room_id)
                .all()
            ]

    def room_context(self, room_id: str, user_id: str) -> dict[str, Any]:
        self.require_member(room_id, user_id)
        with SessionLocal() as db:
            room = db.get(MobileCourseRoomRecord, room_id)
            if room is None:
                raise PermissionError("mobile_room_membership_required")
            members = (
                db.query(MobileRoomMemberRecord)
                .filter_by(room_id=room_id)
                .all()
            )
            room_type = _room_type(room)
            peer = next((row for row in members if row.user_id != user_id), None)
            return {
                **_room_dict(room),
                "room_type": room_type,
                "peer": _member_dict(peer) if room_type == "direct" and peer else None,
            }

    def list_rooms(self, user_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            memberships = (
                db.query(MobileRoomMemberRecord)
                .filter_by(user_id=user_id)
                .order_by(MobileRoomMemberRecord.joined_at.desc())
                .all()
            )
            result: list[dict[str, Any]] = []
            for membership in memberships:
                room = db.get(MobileCourseRoomRecord, membership.room_id)
                if room is None:
                    continue
                latest = (
                    db.query(MobileRoomMessageRecord)
                    .filter_by(room_id=room.id)
                    .order_by(
                        MobileRoomMessageRecord.created_at.desc(),
                        MobileRoomMessageRecord.id.desc(),
                    )
                    .first()
                )
                read = (
                    db.query(MobileRoomReadRecord)
                    .filter_by(room_id=room.id, user_id=user_id)
                    .first()
                )
                last_read_at = read.last_read_at if read else 0.0
                unread = (
                    db.query(MobileRoomMessageRecord)
                    .filter(
                        MobileRoomMessageRecord.room_id == room.id,
                        MobileRoomMessageRecord.created_at > last_read_at,
                        MobileRoomMessageRecord.sender_id != user_id,
                    )
                    .count()
                )
                member_count = (
                    db.query(MobileRoomMemberRecord).filter_by(room_id=room.id).count()
                )
                room_type = _room_type(room)
                peer = None
                if room_type == "direct":
                    peer_row = (
                        db.query(MobileRoomMemberRecord)
                        .filter(
                            MobileRoomMemberRecord.room_id == room.id,
                            MobileRoomMemberRecord.user_id != user_id,
                        )
                        .first()
                    )
                    peer = _member_dict(peer_row) if peer_row else None
                result.append({
                    **_room_dict(room),
                    "room_type": room_type,
                    "peer": peer,
                    "member_count": member_count,
                    "unread_count": unread,
                    "last_message": _message_dict(latest) if latest else None,
                })
            result.sort(
                key=lambda item: (item.get("last_message") or {}).get("created_at", 0),
                reverse=True,
            )
            return result

    def list_messages(
        self, room_id: str, user_id: str, cursor: str = "", limit: int = 30,
    ) -> dict[str, Any]:
        self.require_member(room_id, user_id)
        with SessionLocal() as db:
            query = db.query(MobileRoomMessageRecord).filter_by(room_id=room_id)
            if cursor:
                anchor = db.get(MobileRoomMessageRecord, cursor)
                if anchor is None or anchor.room_id != room_id:
                    raise ValueError("invalid_message_cursor")
                query = query.filter(
                    (MobileRoomMessageRecord.created_at < anchor.created_at)
                    | (
                        (MobileRoomMessageRecord.created_at == anchor.created_at)
                        & (MobileRoomMessageRecord.id < anchor.id)
                    )
                )
            rows = (
                query.order_by(
                    MobileRoomMessageRecord.created_at.desc(),
                    MobileRoomMessageRecord.id.desc(),
                )
                .limit(limit + 1)
                .all()
            )
            has_more = len(rows) > limit
            page = rows[:limit]
            page.reverse()
            return {
                "items": [_message_dict(row) for row in page],
                "next_cursor": page[0].id if has_more and page else None,
                "has_more": has_more,
            }

    def append_message(
        self,
        *,
        room_id: str,
        sender_id: str,
        sender_name: str,
        sender_role: str,
        content: str,
        message_type: str,
        client_message_id: str,
        reply_to_id: str | None = None,
        mentions: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.require_member(room_id, sender_id) if sender_role != "system" else None
        with SessionLocal() as db:
            existing = (
                db.query(MobileRoomMessageRecord)
                .filter_by(
                    room_id=room_id,
                    sender_id=sender_id,
                    client_message_id=client_message_id,
                )
                .first()
            )
            if existing is not None:
                return _message_dict(existing)
            if reply_to_id:
                reply = db.get(MobileRoomMessageRecord, reply_to_id)
                if reply is None or reply.room_id != room_id:
                    raise ValueError("reply_message_not_in_room")
            row = MobileRoomMessageRecord(
                id=f"mm_{uuid.uuid4().hex[:16]}",
                room_id=room_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_role=sender_role,
                content=content,
                message_type=message_type,
                client_message_id=client_message_id,
                reply_to_id=reply_to_id,
                mentions=list(mentions or []),
                payload=dict(payload or {}),
                created_at=time.time(),
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = (
                    db.query(MobileRoomMessageRecord)
                    .filter_by(
                        room_id=room_id,
                        sender_id=sender_id,
                        client_message_id=client_message_id,
                    )
                    .one()
                )
                return _message_dict(existing)
            db.refresh(row)
            return _message_dict(row)

    def mark_read(self, room_id: str, user_id: str, message_id: str) -> dict[str, Any]:
        self.require_member(room_id, user_id)
        with SessionLocal() as db:
            message = db.get(MobileRoomMessageRecord, message_id)
            if message is None or message.room_id != room_id:
                raise ValueError("read_message_not_in_room")
            row = (
                db.query(MobileRoomReadRecord)
                .filter_by(room_id=room_id, user_id=user_id)
                .first()
            )
            if row is None:
                row = MobileRoomReadRecord(room_id=room_id, user_id=user_id)
                db.add(row)
            if message.created_at >= (row.last_read_at or 0.0):
                row.last_message_id = message.id
                row.last_read_at = message.created_at
            db.commit()
            return {
                "room_id": room_id,
                "last_message_id": row.last_message_id,
                "last_read_at": row.last_read_at,
            }


_repo: MobileChatRepository | None = None


def get_mobile_chat_repo() -> MobileChatRepository:
    global _repo
    if _repo is None:
        _repo = MobileChatRepository()
    return _repo


def seed_mobile_course_groups() -> dict[str, int]:
    repo = get_mobile_chat_repo()
    created = repo.ensure_defaults()
    for student_id, student_name, role in MOBILE_DEFAULT_MEMBERS:
        if role != "student":
            continue
        direct = repo.ensure_student_direct_rooms(student_id, student_name)
        for key, count in direct.items():
            created[key] += count
    return created
