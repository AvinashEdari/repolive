"""Add authenticated new-analysis usage counters."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_authenticated_usage"
down_revision: str | None = "0002_user_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authenticated_usage",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("analysis_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("authenticated_usage")
