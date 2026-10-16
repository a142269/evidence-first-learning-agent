"""Durable per-run V2 event order without rewriting historical checkpoints."""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0009"
down_revision = "20261014_0008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    run_columns = {item["name"] for item in sa.inspect(bind).get_columns("agent_runs")}
    checkpoint_columns = {item["name"] for item in sa.inspect(bind).get_columns("agent_checkpoints")}
    if "event_sequence" not in run_columns:
        op.add_column("agent_runs", sa.Column("event_sequence", sa.Integer(),
                                              nullable=False, server_default="0"))
    if "idempotency_digest" not in run_columns:
        op.add_column("agent_runs", sa.Column("idempotency_digest", sa.String(64), nullable=True))
    if "request_fingerprint" not in run_columns:
        op.add_column("agent_runs", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    run_indexes = {item["name"] for item in sa.inspect(bind).get_indexes("agent_runs")}
    if "uq_agent_run_idempotency" not in run_indexes:
        op.create_index("uq_agent_run_idempotency", "agent_runs",
                        ["user_id", "idempotency_digest"], unique=True)
    if "sequence" not in checkpoint_columns:
        op.add_column("agent_checkpoints", sa.Column("sequence", sa.Integer(), nullable=True))
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("agent_checkpoints")}
    if "uq_checkpoint_run_sequence" not in indexes:
        op.create_index("uq_checkpoint_run_sequence", "agent_checkpoints",
                        ["run_id", "sequence"], unique=True)


def downgrade():
    op.drop_index("uq_agent_run_idempotency", table_name="agent_runs")
    op.drop_column("agent_runs", "request_fingerprint")
    op.drop_column("agent_runs", "idempotency_digest")
    op.drop_index("uq_checkpoint_run_sequence", table_name="agent_checkpoints")
    op.drop_column("agent_checkpoints", "sequence")
    op.drop_column("agent_runs", "event_sequence")
