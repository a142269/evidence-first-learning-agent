"""Add isolated mobile course-group tables.

Revision ID: 20260716_0004
Revises: 20260623_0003
Create Date: 2026-07-16
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0004"
down_revision: str | None = "20260623_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mobile_course_rooms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("course", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("avatar_key", sa.String(64), nullable=False, server_default="book-open"),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_mobile_course_rooms_course", "mobile_course_rooms", ["course"])
    op.create_table(
        "mobile_room_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "room_id",
            sa.String(64),
            sa.ForeignKey("mobile_course_rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("role", sa.String(32), nullable=False, server_default="student"),
        sa.Column("joined_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("room_id", "user_id", name="uq_mobile_room_member"),
    )
    op.create_index("ix_mobile_room_members_room_id", "mobile_room_members", ["room_id"])
    op.create_index("ix_mobile_room_members_user_id", "mobile_room_members", ["user_id"])
    op.create_index("ix_mobile_member_user_room", "mobile_room_members", ["user_id", "room_id"])
    op.create_table(
        "mobile_room_messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(64),
            sa.ForeignKey("mobile_course_rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_id", sa.String(128), nullable=False),
        sa.Column("sender_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("sender_role", sa.String(32), nullable=False, server_default="student"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("message_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("client_message_id", sa.String(128), nullable=False, server_default=""),
        sa.Column(
            "reply_to_id",
            sa.String(64),
            sa.ForeignKey("mobile_room_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mentions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.UniqueConstraint(
            "room_id",
            "sender_id",
            "client_message_id",
            name="uq_mobile_message_client_id",
        ),
    )
    op.create_index("ix_mobile_room_messages_room_id", "mobile_room_messages", ["room_id"])
    op.create_index("ix_mobile_room_messages_sender_id", "mobile_room_messages", ["sender_id"])
    op.create_index(
        "ix_mobile_room_messages_message_type",
        "mobile_room_messages",
        ["message_type"],
    )
    op.create_index("ix_mobile_room_messages_created_at", "mobile_room_messages", ["created_at"])
    op.create_index(
        "ix_mobile_message_room_time",
        "mobile_room_messages",
        ["room_id", "created_at", "id"],
    )
    op.create_table(
        "mobile_room_reads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "room_id",
            sa.String(64),
            sa.ForeignKey("mobile_course_rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("last_message_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("last_read_at", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("room_id", "user_id", name="uq_mobile_room_read"),
    )
    op.create_index("ix_mobile_room_reads_room_id", "mobile_room_reads", ["room_id"])
    op.create_index("ix_mobile_room_reads_user_id", "mobile_room_reads", ["user_id"])


def downgrade() -> None:
    op.drop_table("mobile_room_reads")
    op.drop_table("mobile_room_messages")
    op.drop_table("mobile_room_members")
    op.drop_table("mobile_course_rooms")
