"""enterprise agent/rag audit tables and pgvector HNSW index.

Revision ID: 20261010_0005
Revises: 20260716_0004
Create Date: 2026-10-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261010_0005"
down_revision: str | None = "20260716_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class Vector1024(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw):  # type: ignore[no-untyped-def]
        return "vector(1024)"


def _ensure_knowledge_documents_table() -> None:
    """Backfill a V1 table that was historically created by ``init_db`` only.

    Earlier SQLite demos invoked ``Base.metadata.create_all`` at application
    startup, so ``knowledge_documents`` never received its own Alembic
    revision.  A fresh PostgreSQL deployment has no such table before this
    migration, while V2 document versions need a foreign key to it.
    """
    bind = op.get_bind()
    if sa.inspect(bind).has_table("knowledge_documents"):
        return
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("course", sa.String(128), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False, server_default=""),
        sa.Column("storage_key", sa.String(512), nullable=False, server_default=""),
        sa.Column("raw_storage_key", sa.String(512), nullable=False, server_default=""),
        sa.Column("file_type", sa.String(16), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("audit", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_msg", sa.Text(), nullable=False, server_default=""),
        sa.Column("uploaded_by", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_knowledge_documents_course", "knowledge_documents", ["course"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index("ix_knowledge_documents_created_at", "knowledge_documents", ["created_at"])
    op.create_index(
        "ix_kb_doc_course_time", "knowledge_documents", ["course", "created_at"]
    )


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    embedding_type = Vector1024() if is_postgres else sa.JSON()

    # The pgvector image ships the extension binary but does not enable it in
    # a fresh database.  Make a clean CI/deployment database self-contained.
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    _ensure_knowledge_documents_table()

    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(64),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("parser_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("document_id", "version", name="uq_document_version"),
    )
    op.create_index("ix_document_versions_document", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_status", "document_versions", ["status"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "document_version_id",
            sa.String(128),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", embedding_type, nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("document_version_id", "ordinal", name="uq_document_chunk_ordinal"),
    )
    op.create_index("ix_document_chunks_version", "document_chunks", ["document_version_id"])
    op.create_index("ix_document_chunks_hash", "document_chunks", ["content_hash"])
    if is_postgres:
        op.execute(
            "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )

    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("retriever", sa.String(64), nullable=False, server_default="hybrid_rrf"),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_retrieval_logs_run", "retrieval_logs", ["run_id"])
    op.create_index("ix_retrieval_logs_query", "retrieval_logs", ["query_hash"])
    op.create_index("ix_retrieval_run_time", "retrieval_logs", ["run_id", "created_at"])

    op.create_table(
        "agent_checkpoints",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("thread_id", sa.String(128), nullable=False),
        sa.Column("node_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("state_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("resumed_at", sa.Float(), nullable=True),
    )
    op.create_index("ix_agent_checkpoints_run", "agent_checkpoints", ["run_id"])
    op.create_index("ix_agent_checkpoints_thread", "agent_checkpoints", ["thread_id"])
    op.create_index("ix_checkpoint_thread_time", "agent_checkpoints", ["thread_id", "created_at"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("suite_name", sa.String(128), nullable=False),
        sa.Column("case_id", sa.String(128), nullable=False),
        sa.Column("run_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("suite_name", "case_id", "run_id", name="uq_evaluation_case_run"),
    )
    op.create_index("ix_evaluation_results_suite", "evaluation_results", ["suite_name"])
    op.create_index("ix_evaluation_results_case", "evaluation_results", ["case_id"])
    op.create_index("ix_evaluation_results_run", "evaluation_results", ["run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_table("evaluation_results")
    op.drop_table("agent_checkpoints")
    op.drop_table("retrieval_logs")
    op.drop_table("document_chunks")
    op.drop_table("document_versions")
