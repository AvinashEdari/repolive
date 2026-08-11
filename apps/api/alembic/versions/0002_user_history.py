"""Add private user analysis history links."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_user_history"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_user_links",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["public_id"], ["analyses.public_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "public_id"),
    )
    op.create_index("ix_user_history_saved", "analysis_user_links", ["user_id", "saved_at"])


def downgrade() -> None:
    op.drop_index("ix_user_history_saved", table_name="analysis_user_links")
    op.drop_table("analysis_user_links")
