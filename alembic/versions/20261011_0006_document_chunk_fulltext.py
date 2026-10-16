"""add PostgreSQL full-text index for enterprise document chunks.

Revision ID: 20261011_0006
Revises: 20261010_0005
Create Date: 2026-10-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261011_0006"
down_revision: str | None = "20261010_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_content_fts "
            "ON document_chunks USING gin (to_tsvector('simple', content))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_fts")
