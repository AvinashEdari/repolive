"""Create analysis and anonymous usage tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("repository_name", sa.String(length=200), nullable=False),
        sa.Column("commit_sha", sa.String(length=128), nullable=False),
        sa.Column("analysis_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("public_id"),
        sa.UniqueConstraint(
            "provider",
            "owner",
            "repository_name",
            "commit_sha",
            "analysis_version",
            name="uq_analysis_identity_version",
        ),
    )
    op.create_table(
        "anonymous_usage",
        sa.Column("anonymous_id", sa.String(length=128), nullable=False),
        sa.Column("analysis_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("anonymous_id"),
    )


def downgrade() -> None:
    op.drop_table("anonymous_usage")
    op.drop_table("analyses")
