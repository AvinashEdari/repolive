"""Add a fail-closed visibility boundary for future private analyses."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_analysis_visibility"
down_revision: str | None = "0004_saas_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("visibility", sa.String(16), nullable=False, server_default="public"),
    )
    op.add_column("analyses", sa.Column("owner_user_id", sa.String(128)))
    op.create_index("ix_analyses_visibility", "analyses", ["visibility"])
    op.create_index("ix_analyses_owner_user_id", "analyses", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_analyses_owner_user_id", table_name="analyses")
    op.drop_index("ix_analyses_visibility", table_name="analyses")
    op.drop_column("analyses", "owner_user_id")
    op.drop_column("analyses", "visibility")
