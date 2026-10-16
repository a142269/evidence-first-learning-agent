"""A3 Learning Agent System — SQLAlchemy ORM models (B-owned 12 tables)."""
from __future__ import annotations

import time

import sqlalchemy as sa
from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


def _now() -> float:
    return time.time()


def _embedding_column_type():
    """Use pgvector in PostgreSQL while preserving SQLite demo compatibility."""
    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:  # pragma: no cover - only before optional deps are installed
        return JSON()
    return Vector(1024).with_variant(JSON(), "sqlite")


class RegisteredAccountRecord(Base):
    """可登录的注册账号。

    学习画像以 ``user_id`` 为主键，但登录凭据必须独立持久化；否则服务
    重启后会出现“画像还在、账号不存在”的断裂状态。
    """

    __tablename__ = "registered_accounts"
    account: Mapped[str] = mapped_column(String(128), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[float] = mapped_column(Float, default=_now)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)


class AuthSessionRecord(Base):
    """Opaque bearer tokens are stored only as SHA-256 digests."""

    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    builtin: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    created_at: Mapped[float] = mapped_column(Float, default=_now)


class LoginAttemptRecord(Base):
    """Shared account-scoped login throttle; the key is a one-way digest."""

    __tablename__ = "login_attempts"
    account_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[float] = mapped_column(Float, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[float] = mapped_column(Float, nullable=False, default=0)


class CourseGrantRecord(Base):
    __tablename__ = "course_grants"
    account: Mapped[str] = mapped_column(String(128), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    granted_at: Mapped[float] = mapped_column(Float, default=_now)


class ProfileRecord(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile_data: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[float] = mapped_column(Float, default=_now)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)


class ProfileSnapshotRecord(Base):
    """画像快照 — 每次画像更新留档，作为「随学随新」的可追溯证据（A 拥有）"""
    __tablename__ = "profile_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    profile_data: Mapped[dict] = mapped_column(JSON, default=dict)
    changed_keys: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(64), default="manual")  # chat / manual / agent
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (sa.Index("ix_snapshot_user_time", "user_id", "created_at"),)


class RealtimeStateRecord(Base):
    __tablename__ = "realtime_states"
    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    state_data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (sa.Index("ix_rt_state_user", "user_id"),)


class LearnerArchetypeRecord(Base):
    __tablename__ = "learner_archetypes"
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    archetype_code: Mapped[str] = mapped_column(String(64), index=True)
    archetype_data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (sa.Index("ix_archetype_code", "archetype_code"),)


class KnowledgePointRecord(Base):
    __tablename__ = "knowledge_points"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    course: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("course", "name", name="uq_kp_course_name"),
        sa.Index("ix_kp_course_name", "course", "name"),
    )


class KnowledgeRelationRecord(Base):
    __tablename__ = "kp_relations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(32), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation_type", name="uq_kp_relation"),
        sa.Index("ix_kpr_source", "source_id", "relation_type"),
        sa.Index("ix_kpr_target", "target_id", "relation_type"),
    )


class DinaStateRecord(Base):
    __tablename__ = "dina_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(String(128), index=True)
    mastery: Mapped[float] = mapped_column(Float, default=0.5)
    slip: Mapped[float] = mapped_column(Float, default=0.1)
    guess: Mapped[float] = mapped_column(Float, default=0.2)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_dina_user_kp"),
        sa.Index("ix_dina_user_kp", "user_id", "knowledge_point_id"),
    )


class BktStateRecord(Base):
    __tablename__ = "bkt_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(String(128), index=True)
    p_learned: Mapped[float] = mapped_column(Float, default=0.2)
    p_transit: Mapped[float] = mapped_column(Float, default=0.1)
    p_slip: Mapped[float] = mapped_column(Float, default=0.1)
    p_guess: Mapped[float] = mapped_column(Float, default=0.2)
    history: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_bkt_user_kp"),
        sa.Index("ix_bkt_user_kp", "user_id", "knowledge_point_id"),
    )


class Sm2ScheduleRecord(Base):
    __tablename__ = "sm2_schedule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    item_type: Mapped[str] = mapped_column(String(32), default="knowledge_point")
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    easiness: Mapped[float] = mapped_column(Float, default=2.5)
    due_at: Mapped[float] = mapped_column(Float, default=_now)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_sm2_user_item"),
        sa.Index("ix_sm2_user_due", "user_id", "due_at"),
    )


class LearningPathRecord(Base):
    __tablename__ = "learning_paths"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(256), default="学习路径")
    stages: Mapped[list] = mapped_column(JSON, default=list)
    current_stage: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (sa.Index("ix_path_user_created", "user_id", "created_at"),)


class AssessmentRecord(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    record_type: Mapped[str] = mapped_column(String(32), default="activity", index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic: Mapped[str] = mapped_column(String(256), default="")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    timestamp: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        sa.Index("ix_assessment_user_time", "user_id", "timestamp"),
        sa.Index("ix_assessment_user_type", "user_id", "record_type"),
    )


class MistakeRecord(Base):
    __tablename__ = "mistakes"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    knowledge_point_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    question_data: Mapped[dict] = mapped_column(JSON, default=dict)
    error_type: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    analysis: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=_now)
    resolved_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        sa.Index("ix_mistake_user_unresolved", "user_id", "resolved_at"),
        sa.Index("ix_mistake_user_type", "user_id", "error_type"),
        sa.Index("ix_mistake_user_kp", "user_id", "knowledge_point_id"),
    )


class GamificationProfileRecord(Base):
    __tablename__ = "gamification_profiles"
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    achievements: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)


class ResourceRecord(Base):
    """Agent 生成的学习资源 — 替代 resources API 的内存 _resources 字典（A 补全）"""
    __tablename__ = "resources"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    type: Mapped[str] = mapped_column(String(64), index=True, default="document")
    title: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    content_type: Mapped[str] = mapped_column(String(32), default="markdown")
    agent_name: Mapped[str] = mapped_column(String(128), default="")
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)


class ChatHistoryRecord(Base):
    """聊天历史记录 — 跨会话持久化，刷新不丢"""
    __tablename__ = "chat_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    role: Mapped[str] = mapped_column(String(32), default="user")  # user / assistant
    content: Mapped[str] = mapped_column(Text, default="")
    agent_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        sa.Index("ix_chat_history_session_time", "session_id", "created_at"),
    )


# ================================================================
# RAG index persistence (B-owned) — replaces JSON index file
# ================================================================
class KnowledgeChunkRecord(Base):
    """知识块元数据 — 替代 rag_service 的内存 _raw_chunks 列表"""
    __tablename__ = "knowledge_chunks"
    chunk_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    source: Mapped[str] = mapped_column(String(256), index=True)
    course: Mapped[str] = mapped_column(String(128), index=True)
    title_hint: Mapped[str] = mapped_column(String(256), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[float] = mapped_column(Float, default=_now)

    __table_args__ = (
        sa.Index("ix_chunk_course_source", "course", "source"),
        sa.UniqueConstraint("chunk_id", name="uq_chunk_id"),
    )


class ChunkVectorRecord(Base):
    """TF-IDF 向量 + norm — 索引计算结果落库，冷启动免重算"""
    __tablename__ = "chunk_vectors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_chunks.chunk_id", ondelete="CASCADE"), index=True
    )
    vector: Mapped[dict] = mapped_column(JSON, default=dict)   # {token: tfidf_weight}
    norm: Mapped[float] = mapped_column(Float, default=0.0)
    doc_freq: Mapped[dict] = mapped_column(JSON, default=dict)  # 旧字段；新索引不重复存全局 DF

    __table_args__ = (
        sa.UniqueConstraint("chunk_id", name="uq_vector_chunk"),
    )


# ================================================================
# 师生协作（A 拥有）— 课程群聊 + 配置型 Agent
# ================================================================
class KnowledgeDocumentRecord(Base):
    """教师上传的知识库文档 — 状态机: uploaded → parsing → indexed / failed / rejected"""
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    course: Mapped[str] = mapped_column(String(128), index=True)
    filename: Mapped[str] = mapped_column(String(256), default="")
    storage_key: Mapped[str] = mapped_column(String(512), default="")   # 转换后 .md 的 kb 相对路径
    raw_storage_key: Mapped[str] = mapped_column(String(512), default="")  # 原件 kb 相对路径
    file_type: Mapped[str] = mapped_column(String(16), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    audit: Mapped[dict] = mapped_column(JSON, default=dict)             # KnowledgeGuard 审核报告
    error_msg: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (
        sa.Index("ix_kb_doc_course_time", "course", "created_at"),
    )


class IngestionTaskRecord(Base):
    """Durable upload identity across Celery retries and API replay."""

    __tablename__ = "ingestion_tasks"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    uploader: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    course_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    document_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=_now)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)

    __table_args__ = (sa.Index("uq_ingestion_uploader_key", "uploader", "idempotency_digest", unique=True),)


class GroupChatMessageRecord(Base):
    """课程群聊消息 — room_id = course:student_id，学生/教师/Agent 共享同一房间"""
    __tablename__ = "group_chat_messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(256), index=True)
    sender_id: Mapped[str] = mapped_column(String(128), default="")
    sender_name: Mapped[str] = mapped_column(String(128), default="")
    sender_role: Mapped[str] = mapped_column(String(32), default="student")  # student/teacher/agent/system
    content: Mapped[str] = mapped_column(Text, default="")
    # text / teacher_message / agent_reply / resource_card / path_card / system_notice
    message_type: Mapped[str] = mapped_column(String(32), default="text", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        sa.Index("ix_group_chat_room_time", "room_id", "created_at"),
    )


# Mobile course groups intentionally use separate tables from the legacy
# course:student_id collaboration rooms.  This keeps the web teacher console's
# existing room parsing and message contract unchanged.
class MobileCourseRoomRecord(Base):
    __tablename__ = "mobile_course_rooms"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    course: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    avatar_key: Mapped[str] = mapped_column(String(64), default="book-open")
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[float] = mapped_column(Float, default=_now)


class MobileRoomMemberRecord(Base):
    __tablename__ = "mobile_room_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("mobile_course_rooms.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(32), default="student")
    joined_at: Mapped[float] = mapped_column(Float, default=_now)

    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_mobile_room_member"),
        sa.Index("ix_mobile_member_user_room", "user_id", "room_id"),
    )


class MobileRoomMessageRecord(Base):
    __tablename__ = "mobile_room_messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("mobile_course_rooms.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[str] = mapped_column(String(128), index=True)
    sender_name: Mapped[str] = mapped_column(String(128), default="")
    sender_role: Mapped[str] = mapped_column(String(32), default="student")
    content: Mapped[str] = mapped_column(Text, default="")
    message_type: Mapped[str] = mapped_column(String(32), default="text", index=True)
    client_message_id: Mapped[str] = mapped_column(String(128), default="")
    reply_to_id: Mapped[str | None] = mapped_column(
        ForeignKey("mobile_room_messages.id", ondelete="SET NULL"), nullable=True
    )
    mentions: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        UniqueConstraint(
            "room_id", "sender_id", "client_message_id",
            name="uq_mobile_message_client_id",
        ),
        sa.Index("ix_mobile_message_room_time", "room_id", "created_at", "id"),
    )


class MobileRoomReadRecord(Base):
    __tablename__ = "mobile_room_reads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("mobile_course_rooms.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    last_message_id: Mapped[str] = mapped_column(String(64), default="")
    last_read_at: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_mobile_room_read"),
    )


class AgentConfigRecord(Base):
    """配置型 Agent — 教师可增删改，由统一 ConfigurableAgent 执行；内置 Agent 只可改展示信息与启用状态"""
    __tablename__ = "agent_configs"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(128), default="")
    avatar: Mapped[str] = mapped_column(String(256), default="")
    role_desc: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    allowed_tools: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[int] = mapped_column(Integer, default=1)   # SQLite: 0/1
    builtin: Mapped[int] = mapped_column(Integer, default=0)   # 内置 Agent 不可删除/不可改 prompt
    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[float] = mapped_column(Float, default=_now)
    updated_at: Mapped[float] = mapped_column(Float, default=_now, onupdate=_now)


class ReviewEventRecord(Base):
    """Persisted review activity used by student and teacher analytics."""

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    item_type: Mapped[str] = mapped_column(String(32), default="knowledge_point")
    rating: Mapped[int] = mapped_column(Integer, default=0)
    before_mastery: Mapped[float | None] = mapped_column(Float, nullable=True)
    after_mastery: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    reviewed_at: Mapped[float] = mapped_column(Float, default=_now, index=True)
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        sa.Index("ix_review_event_user_time", "user_id", "reviewed_at"),
    )


class AgentRunRecord(Base):
    """Persisted summary of one workflow or agent orchestration run."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    user_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    workflow_type: Mapped[str] = mapped_column(String(64), index=True, default="workflow")
    agents: Mapped[list] = mapped_column(JSON, default=list)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    artifact_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True, default="success")
    execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        sa.Index("ix_agent_run_user_time", "user_id", "created_at"),
        sa.Index("ix_agent_run_lease", "status", "lease_expires_at"),
        sa.Index("uq_agent_run_idempotency", "user_id", "idempotency_digest", unique=True),
    )


# ================================================================
# Enterprise Agent/RAG audit data.  These tables intentionally coexist with
# the SQLite-compatible V1 data model: the migration uses pgvector when the
# production PostgreSQL path is selected, while local demos can still use JSON.
# ================================================================
class DocumentVersionRecord(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    parser_name: Mapped[str] = mapped_column(String(64), default="")
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version"),
    )


class DocumentChunkRecord(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list | None] = mapped_column(_embedding_column_type(), nullable=True)
    metadata_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        UniqueConstraint("document_version_id", "ordinal", name="uq_document_chunk_ordinal"),
    )


class RetrievalLogRecord(Base):
    __tablename__ = "retrieval_logs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    retriever: Mapped[str] = mapped_column(String(64), default="hybrid_rrf")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (sa.Index("ix_retrieval_run_time", "run_id", "created_at"),)


class AgentCheckpointRecord(Base):
    __tablename__ = "agent_checkpoints"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    thread_id: Mapped[str] = mapped_column(String(128), index=True)
    node_name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)
    resumed_at: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        sa.Index("ix_checkpoint_thread_time", "thread_id", "created_at"),
        sa.Index("uq_checkpoint_run_sequence", "run_id", "sequence", unique=True),
    )


class EvaluationResultRecord(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    suite_name: Mapped[str] = mapped_column(String(128), index=True)
    case_id: Mapped[str] = mapped_column(String(128), index=True)
    run_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=_now, index=True)

    __table_args__ = (
        UniqueConstraint("suite_name", "case_id", "run_id", name="uq_evaluation_case_run"),
    )


# ================================================================
# A-owned tables
# ================================================================
class DebateLogRecord(Base):
    """Multi-Agent Debate 辩论日志 — A 拥有"""
    __tablename__ = "debate_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    round_num: Mapped[int] = mapped_column(Integer, default=1)
    expert_name: Mapped[str] = mapped_column(String(64))
    draft_preview: Mapped[str] = mapped_column(Text, default="")
    critic_score: Mapped[float] = mapped_column(Float, default=0.0)
    critic_passed: Mapped[bool] = mapped_column(Integer, default=0)  # SQLite: 0/1
    critic_issues: Mapped[list] = mapped_column(JSON, default=list)
    verdict: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[float] = mapped_column(Float, default=_now)
