"""Persistent opaque sessions and per-account course grants."""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0008"
down_revision = "20261013_0007"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Historical demos created this table with create_all, not Alembic.
    if not sa.inspect(bind).has_table("registered_accounts"):
        op.create_table("registered_accounts",
            sa.Column("account", sa.String(128), primary_key=True),
            sa.Column("password_hash", sa.String(128), nullable=False),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("display_name", sa.String(128), nullable=False),
            sa.Column("created_at", sa.Float(), nullable=False),
            sa.Column("updated_at", sa.Float(), nullable=False))
    if not sa.inspect(bind).has_table("auth_sessions"):
        op.create_table("auth_sessions",
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column("account", sa.String(128), nullable=False),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("display_name", sa.String(128), nullable=False),
            sa.Column("builtin", sa.Boolean(), nullable=False),
            sa.Column("expires_at", sa.Float(), nullable=False),
            sa.Column("created_at", sa.Float(), nullable=False))
        op.create_index("ix_auth_sessions_account", "auth_sessions", ["account"])
        op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    if not sa.inspect(bind).has_table("course_grants"):
        op.create_table("course_grants",
            sa.Column("account", sa.String(128), primary_key=True),
            sa.Column("course_id", sa.String(128), primary_key=True),
            sa.Column("granted_at", sa.Float(), nullable=False))


def downgrade():
    op.drop_table("course_grants")
    op.drop_table("auth_sessions")
    # Keep existing accounts and upgraded hashes. Rolling back invalidates sessions/grants.
