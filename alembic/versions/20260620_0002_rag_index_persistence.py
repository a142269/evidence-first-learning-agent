"""rag index persistence — knowledge_chunks + chunk_vectors

Revision ID: 20260620_0002
Revises: 20260618_0001
Create Date: 2026-06-20 18:30:00

Adds two B-owned tables to replace the JSON index file used by rag_service:
  - knowledge_chunks: chunk metadata (id/source/course/title/text/content_hash)
  - chunk_vectors: TF-IDF vector + norm + doc_freq snapshot per chunk

This enables incremental index updates and crash-safe persistence.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260620_0002"
down_revision: Union[str, None] = "20260618_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── knowledge_chunks ──
    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.String(256), primary_key=True),
        sa.Column("source", sa.String(256), nullable=False),
        sa.Column("course", sa.String(128), nullable=False),
        sa.Column("title_hint", sa.String(256), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("chunk_id", name="uq_chunk_id"),
    )
    op.create_index("ix_chunk_source", "knowledge_chunks", ["source"])
    op.create_index("ix_chunk_course", "knowledge_chunks", ["course"])
    op.create_index("ix_chunk_content_hash", "knowledge_chunks", ["content_hash"])
    op.create_index("ix_chunk_course_source", "knowledge_chunks", ["course", "source"])

    # ── chunk_vectors ──
    op.create_table(
        "chunk_vectors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chunk_id",
            sa.String(256),
            sa.ForeignKey("knowledge_chunks.chunk_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vector", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("norm", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("doc_freq", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("chunk_id", name="uq_vector_chunk"),
    )
    op.create_index("ix_vector_chunk_id", "chunk_vectors", ["chunk_id"])


def downgrade() -> None:
    op.drop_table("chunk_vectors")
    op.drop_table("knowledge_chunks")
