"""Add fenced V2 execution leases without altering existing run results."""
from alembic import op
import sqlalchemy as sa

revision = "20261013_0007"
down_revision = "20261011_0006"
branch_labels = None
depends_on = None


def upgrade():
    # Older demos created agent_runs only via create_all at app startup.
    # A fresh Alembic-only deployment needs this historical table backfilled.
    if not sa.inspect(op.get_bind()).has_table("agent_runs"):
        op.create_table("agent_runs",
            sa.Column("id", sa.String(128), primary_key=True),
            sa.Column("session_id", sa.String(128), nullable=False, server_default=""),
            sa.Column("user_id", sa.String(128), nullable=False, server_default=""),
            sa.Column("workflow_type", sa.String(64), nullable=False, server_default="workflow"),
            sa.Column("agents", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("artifact_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="success"),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.Float(), nullable=False),
        )
        for column in ("session_id", "user_id", "workflow_type", "status", "created_at"):
            op.create_index(f"ix_agent_runs_{column}", "agent_runs", [column])
        op.create_index("ix_agent_run_user_time", "agent_runs", ["user_id", "created_at"])
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("agent_runs")}
    if "execution_id" not in columns:
        op.add_column("agent_runs", sa.Column("execution_id", sa.String(64), nullable=True))
    if "lease_expires_at" not in columns:
        op.add_column("agent_runs", sa.Column("lease_expires_at", sa.Float(), nullable=True))
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("agent_runs")}
    if "ix_agent_run_lease" not in indexes:
        op.create_index("ix_agent_run_lease", "agent_runs", ["status", "lease_expires_at"])


def downgrade():
    # Retain historical agent_runs and its data, even if this revision backfilled it.
    op.drop_index("ix_agent_run_lease", table_name="agent_runs")
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_column("lease_expires_at")
        batch.drop_column("execution_id")
