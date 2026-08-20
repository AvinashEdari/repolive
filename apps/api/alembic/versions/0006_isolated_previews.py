"""isolated preview control-plane records

Revision ID: 0006_isolated_previews
Revises: 0005_analysis_visibility
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_isolated_previews"
down_revision: str | None = "0005_analysis_visibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "preview_jobs",
        sa.Column("preview_id", sa.String(32), primary_key=True),
        sa.Column(
            "public_analysis_id",
            sa.String(32),
            sa.ForeignKey("analyses.public_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("repository_name", sa.String(200), nullable=False),
        sa.Column("commit_sha", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("runtime_profile", sa.String(64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column("destroyed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_category", sa.String(64)),
        sa.Column("safe_failure_message", sa.Text),
        sa.Column("sandbox_provider_id", sa.String(128)),
        sa.Column("application_endpoint", sa.String(128)),
        sa.Column("routing_key", sa.String(64), unique=True),
        sa.Column("build_attempt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("resource_policy_version", sa.String(32), nullable=False),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_preview_jobs_public_analysis_id", "preview_jobs", ["public_analysis_id"])
    op.create_index("ix_preview_jobs_user_id", "preview_jobs", ["user_id"])
    op.create_index("ix_preview_jobs_status", "preview_jobs", ["status"])
    op.create_table(
        "preview_events",
        sa.Column("event_id", sa.String(32), primary_key=True),
        sa.Column(
            "preview_id",
            sa.String(32),
            sa.ForeignKey("preview_jobs.preview_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("safe_message", sa.Text, nullable=False),
        sa.Column("fields_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("preview_id", "sequence", name="uq_preview_event_sequence"),
    )
    op.create_index("ix_preview_events_preview_id", "preview_events", ["preview_id"])
    op.create_table(
        "preview_usage",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("preview_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("build_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("runtime_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("preview_usage")
    op.drop_index("ix_preview_events_preview_id", table_name="preview_events")
    op.drop_table("preview_events")
    op.drop_index("ix_preview_jobs_status", table_name="preview_jobs")
    op.drop_index("ix_preview_jobs_user_id", table_name="preview_jobs")
    op.drop_index("ix_preview_jobs_public_analysis_id", table_name="preview_jobs")
    op.drop_table("preview_jobs")
