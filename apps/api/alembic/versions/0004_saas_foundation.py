"""Add SaaS plans, API keys, teams, billing, and GitHub installations."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_saas_foundation"
down_revision: str | None = "0003_authenticated_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("anonymous_usage", sa.Column("period_started_at", sa.DateTime(timezone=True)))
    op.add_column("authenticated_usage", sa.Column("period_started_at", sa.DateTime(timezone=True)))
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stripe_customer_id", sa.String(128), unique=True),
        sa.Column("stripe_subscription_id", sa.String(128), unique=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("provider_event_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "webhook_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "api_keys",
        sa.Column("key_id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("quota_reset_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_table(
        "organizations",
        sa.Column("organization_id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("owner_user_id", sa.String(128), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"])
    op.create_table(
        "organization_members",
        sa.Column(
            "organization_id",
            sa.String(32),
            sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "organization_analyses",
        sa.Column(
            "organization_id",
            sa.String(32),
            sa.ForeignKey("organizations.organization_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "public_id",
            sa.String(32),
            sa.ForeignKey("analyses.public_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "github_installations",
        sa.Column("installation_id", sa.String(64), primary_key=True),
        sa.Column("owner_user_id", sa.String(128), nullable=False),
        sa.Column("account_login", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_github_installations_owner_user_id", "github_installations", ["owner_user_id"]
    )
    op.create_table(
        "operational_metrics",
        sa.Column("metric", sa.String(64), primary_key=True),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("operational_metrics")
    op.drop_index("ix_github_installations_owner_user_id", table_name="github_installations")
    op.drop_table("github_installations")
    op.drop_table("organization_analyses")
    op.drop_table("organization_members")
    op.drop_index("ix_organizations_owner_user_id", table_name="organizations")
    op.drop_table("organizations")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_table("webhook_events")
    op.drop_table("subscriptions")
    op.drop_column("authenticated_usage", "period_started_at")
    op.drop_column("anonymous_usage", "period_started_at")
