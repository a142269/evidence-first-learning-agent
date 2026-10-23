"""Confirmation-gated long-term learner memory and its audit trail."""
from alembic import op
import sqlalchemy as sa

revision = "20261023_0012"
down_revision = "20261014_0011"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("user_memories"):
        return
    op.create_table("user_memories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_run_id", sa.String(128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("expires_at", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False))
    op.create_index("ix_user_memories_user_id", "user_memories", ["user_id"])
    op.create_index("ix_user_memories_status", "user_memories", ["status"])
    op.create_index("ix_user_memories_source_run_id", "user_memories", ["source_run_id"])
    op.create_index("ix_user_memories_expires_at", "user_memories", ["expires_at"])
    op.create_index("uq_user_memory_active", "user_memories", ["user_id", "kind"], unique=True,
                    sqlite_where=sa.text("status = 'active'"),
                    postgresql_where=sa.text("status = 'active'"))
    op.create_table("memory_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("memory_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False))
    op.create_index("ix_memory_events_memory_id", "memory_events", ["memory_id"])
    op.create_index("ix_memory_events_created_at", "memory_events", ["created_at"])


def downgrade():
    bind = sa.inspect(op.get_bind())
    if bind.has_table("memory_events"):
        op.drop_index("ix_memory_events_created_at", table_name="memory_events")
        op.drop_index("ix_memory_events_memory_id", table_name="memory_events")
        op.drop_table("memory_events")
    if bind.has_table("user_memories"):
        op.drop_index("uq_user_memory_active", table_name="user_memories")
        op.drop_index("ix_user_memories_expires_at", table_name="user_memories")
        op.drop_index("ix_user_memories_source_run_id", "user_memories")
        op.drop_index("ix_user_memories_status", table_name="user_memories")
        op.drop_index("ix_user_memories_user_id", table_name="user_memories")
        op.drop_table("user_memories")
