"""Durable idempotency and task status for teacher document ingestion."""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0010"
down_revision = "20261014_0009"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("ingestion_tasks"):
        return
    op.create_table("ingestion_tasks",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("uploader", sa.String(128), nullable=False),
        sa.Column("course_id", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=True),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("document_id", sa.String(128), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False))
    op.create_index("ix_ingestion_tasks_course_id", "ingestion_tasks", ["course_id"])
    op.create_index("ix_ingestion_tasks_status", "ingestion_tasks", ["status"])
    op.create_index("uq_ingestion_uploader_key", "ingestion_tasks",
                    ["uploader", "idempotency_digest"], unique=True)


def downgrade():
    op.drop_table("ingestion_tasks")
