"""Account-scoped login throttle storage."""

from alembic import op
import sqlalchemy as sa

revision = "20261014_0011"
down_revision = "20261014_0010"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("login_attempts"):
        return
    op.create_table(
        "login_attempts",
        sa.Column("account_hash", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.Float(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.Float(), nullable=False),
    )


def downgrade():
    op.drop_table("login_attempts")
