"""Day 4 - A: add debate_logs table (Multi-Agent Debate log).

Revision ID: 20260623_0003
Revises: 20260620_0002
Create Date: 2026-06-23

A-owned tables added here:
  debate_logs

Rationale:
  B baseline (20260618_0001) covers the 12 B-owned tables.
  B 0002 (20260620_0002) adds the rag-index persistence pair.
  Per API-CONTRACT.md the schema is split A 5 + B 12 = 17 tables;
  this migration adds the first A-owned table: debate_logs.
  Remaining A tables (resources / chat_sessions / agent_traces /
  artifacts) are added in later migrations on demand.

NOTE:
  Keep this file pure ASCII so tools that read it with the locale
  codec (e.g. tests/b/test_operations_infrastructure.py read_text)
  do not blow up on Chinese Windows (CP936/GBK).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260623_0003"
down_revision: Union[str, None] = "20260620_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # debate_logs - Multi-Agent Debate log entries
    op.create_table(
        "debate_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("round_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expert_name", sa.String(64), nullable=False),
        sa.Column("draft_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("critic_score", sa.Float(), nullable=False, server_default="0"),
        # SQLite stores bool as 0/1 integer
        sa.Column("critic_passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critic_issues", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("verdict", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_debate_logs_session_id", "debate_logs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_debate_logs_session_id", table_name="debate_logs")
    op.drop_table("debate_logs")
