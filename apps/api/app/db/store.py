import json
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    case,
    create_engine,
    func,
    or_,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import delete, exists, select, text

from app.core.config import get_settings
from app.schemas.analysis import AnalysisReport

metadata = MetaData()
analyses = Table(
    "analyses",
    metadata,
    Column("public_id", String(32), primary_key=True),
    Column("provider", String(32), nullable=False),
    Column("owner", String(100), nullable=False),
    Column("repository_name", String(200), nullable=False),
    Column("commit_sha", String(128), nullable=False),
    Column("analysis_version", String(32), nullable=False),
    Column("visibility", String(16), nullable=False, default="public", index=True),
    Column("owner_user_id", String(128), index=True),
    Column("status", String(32), nullable=False),
    Column("report_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "provider",
        "owner",
        "repository_name",
        "commit_sha",
        "analysis_version",
        name="uq_analysis_identity_version",
    ),
)
anonymous_usage = Table(
    "anonymous_usage",
    metadata,
    Column("anonymous_id", String(128), primary_key=True),
    Column("analysis_count", Integer, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("period_started_at", DateTime(timezone=True)),
)
authenticated_usage = Table(
    "authenticated_usage",
    metadata,
    Column("user_id", String(128), primary_key=True),
    Column("analysis_count", Integer, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("period_started_at", DateTime(timezone=True)),
)
analysis_user_links = Table(
    "analysis_user_links",
    metadata,
    Column("user_id", String(128), primary_key=True),
    Column(
        "public_id",
        String(32),
        ForeignKey("analyses.public_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("saved_at", DateTime(timezone=True), nullable=False),
)
subscriptions = Table(
    "subscriptions",
    metadata,
    Column("user_id", String(128), primary_key=True),
    Column("plan", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("stripe_customer_id", String(128), unique=True),
    Column("stripe_subscription_id", String(128), unique=True),
    Column("current_period_end", DateTime(timezone=True)),
    Column("provider_event_created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
webhook_events = Table(
    "webhook_events",
    metadata,
    Column("event_id", String(128), primary_key=True),
    Column("event_type", String(128), nullable=False),
    Column("processed_at", DateTime(timezone=True), nullable=False),
)
api_keys = Table(
    "api_keys",
    metadata,
    Column("key_id", String(32), primary_key=True),
    Column("user_id", String(128), nullable=False, index=True),
    Column("name", String(80), nullable=False),
    Column("key_hash", String(64), nullable=False, unique=True),
    Column("prefix", String(16), nullable=False),
    Column("request_count", Integer, nullable=False, default=0),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_used_at", DateTime(timezone=True)),
    Column("quota_reset_at", DateTime(timezone=True), nullable=False),
)
organizations = Table(
    "organizations",
    metadata,
    Column("organization_id", String(32), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("owner_user_id", String(128), nullable=False, index=True),
    Column("plan", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
organization_members = Table(
    "organization_members",
    metadata,
    Column(
        "organization_id",
        String(32),
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("user_id", String(128), primary_key=True),
    Column("role", String(16), nullable=False),
    Column("joined_at", DateTime(timezone=True), nullable=False),
)
organization_analyses = Table(
    "organization_analyses",
    metadata,
    Column(
        "organization_id",
        String(32),
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "public_id",
        String(32),
        ForeignKey("analyses.public_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("shared_at", DateTime(timezone=True), nullable=False),
)
github_installations = Table(
    "github_installations",
    metadata,
    Column("installation_id", String(64), primary_key=True),
    Column("owner_user_id", String(128), nullable=False, index=True),
    Column("account_login", String(100), nullable=False),
    Column("account_type", String(32), nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
operational_metrics = Table(
    "operational_metrics",
    metadata,
    Column("metric", String(64), primary_key=True),
    Column("value", Integer, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


class AnonymousLimitExceeded(RuntimeError):
    """Raised when an anonymous browser exhausts its configured allowance."""


class AuthenticatedLimitExceeded(RuntimeError):
    """Raised when an account exhausts its configured new-analysis allowance."""


class AnalysisPersistenceError(RuntimeError):
    """Raised when a completed report cannot be stored safely."""


class AnalysisStore:
    def __init__(
        self,
        database_url: str,
        create_schema: bool = True,
        pool_size: int = 5,
        max_overflow: int = 5,
        pool_timeout: int = 10,
        pool_recycle: int = 300,
        connect_timeout: int = 10,
    ) -> None:
        is_sqlite = database_url.startswith("sqlite")
        connect_args = (
            {"check_same_thread": False, "timeout": connect_timeout}
            if is_sqlite
            else {"connect_timeout": connect_timeout}
        )
        if database_url == "sqlite:///:memory:":
            self.engine = create_engine(
                database_url, connect_args=connect_args, poolclass=StaticPool
            )
        else:
            self.engine = create_engine(
                database_url,
                connect_args=connect_args,
                pool_pre_ping=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
            )
        if create_schema:
            metadata.create_all(self.engine)

    def save(
        self,
        report: AnalysisReport,
        anonymous_id: str,
        anonymous_limit: int,
        user_id: str | None = None,
        authenticated_limit: int = 50,
    ) -> AnalysisReport:
        now = datetime.now(UTC)
        identity = self._identity(report)
        try:
            with self.engine.begin() as connection:
                cached_json = connection.execute(
                    select(analyses.c.report_json).where(
                        analyses.c.provider == identity["provider"],
                        analyses.c.owner == identity["owner"],
                        analyses.c.repository_name == identity["repository_name"],
                        analyses.c.commit_sha == identity["commit_sha"],
                        analyses.c.analysis_version == identity["analysis_version"],
                        analyses.c.visibility == "public",
                    )
                ).scalar_one_or_none()
                if cached_json is not None:
                    cached = AnalysisReport.model_validate(json.loads(cached_json))
                    if user_id and cached.public_id:
                        self._link_user(connection, user_id, cached.public_id, now)
                    return cached.model_copy(update={"cache_status": "cached"})
                if user_id is None:
                    if not self._consume_allowance(
                        connection,
                        anonymous_usage,
                        "anonymous_id",
                        anonymous_id,
                        anonymous_limit,
                        now,
                    ):
                        raise AnonymousLimitExceeded
                elif not self._consume_allowance(
                    connection,
                    authenticated_usage,
                    "user_id",
                    user_id,
                    authenticated_limit,
                    now,
                ):
                    raise AuthenticatedLimitExceeded
                public_id = secrets.token_urlsafe(12)
                stored_report = report.model_copy(update={"public_id": public_id})
                serialized = stored_report.model_dump_json()
                connection.execute(
                    analyses.insert().values(
                        public_id=public_id,
                        **identity,
                        visibility="public",
                        owner_user_id=None,
                        status=stored_report.status,
                        report_json=serialized,
                        created_at=now,
                    )
                )
                if user_id:
                    self._link_user(connection, user_id, public_id, now)
        except SQLAlchemyError as exc:
            raise AnalysisPersistenceError("Analysis persistence failed.") from exc
        return stored_report

    @staticmethod
    def _consume_allowance(
        connection: Connection,
        table: Table,
        identifier_column: str,
        identifier: str,
        limit: int,
        now: datetime,
    ) -> bool:
        cutoff = now - timedelta(days=30)
        values = {
            identifier_column: identifier,
            "analysis_count": 1,
            "updated_at": now,
            "period_started_at": now,
        }
        identifier_field = table.c[identifier_column]
        expired = or_(table.c.period_started_at.is_(None), table.c.period_started_at < cutoff)
        next_count = case((expired, 1), else_=table.c.analysis_count + 1)
        next_period = case((expired, now), else_=table.c.period_started_at)
        if connection.dialect.name == "postgresql":
            postgresql_statement = postgresql_insert(table).values(**values)
            result = connection.execute(
                postgresql_statement.on_conflict_do_update(
                    index_elements=[identifier_field],
                    set_={
                        "analysis_count": next_count,
                        "updated_at": now,
                        "period_started_at": next_period,
                    },
                    where=or_(table.c.analysis_count < limit, expired),
                )
            )
            return bool(result.rowcount)
        if connection.dialect.name == "sqlite":
            sqlite_statement = sqlite_insert(table).values(**values)
            result = connection.execute(
                sqlite_statement.on_conflict_do_update(
                    index_elements=[identifier_field],
                    set_={
                        "analysis_count": next_count,
                        "updated_at": now,
                        "period_started_at": next_period,
                    },
                    where=or_(table.c.analysis_count < limit, expired),
                )
            )
            return bool(result.rowcount)
        current = connection.execute(
            select(table.c.analysis_count, table.c.period_started_at).where(
                identifier_field == identifier
            )
        ).one_or_none()
        if current is not None and current.period_started_at and current.period_started_at < cutoff:
            current = None
            connection.execute(table.delete().where(identifier_field == identifier))
        if current is not None and current.analysis_count >= limit:
            return False
        if current is None:
            connection.execute(table.insert().values(**values))
        else:
            connection.execute(
                table.update()
                .where(identifier_field == identifier)
                .values(analysis_count=current.analysis_count + 1, updated_at=now)
            )
        return True

    @staticmethod
    def _link_user(connection: Connection, user_id: str, public_id: str, now: datetime) -> None:
        values = {"user_id": user_id, "public_id": public_id, "saved_at": now}
        if connection.dialect.name == "postgresql":
            postgresql_statement = postgresql_insert(analysis_user_links).values(**values)
            connection.execute(postgresql_statement.on_conflict_do_nothing())
            return
        if connection.dialect.name == "sqlite":
            sqlite_statement = sqlite_insert(analysis_user_links).values(**values)
            connection.execute(sqlite_statement.on_conflict_do_nothing())
            return
        connection.execute(analysis_user_links.insert().values(**values))

    def list_for_user(self, user_id: str) -> list[dict[str, object]]:
        query = (
            select(analyses, analysis_user_links.c.saved_at)
            .join(analysis_user_links, analyses.c.public_id == analysis_user_links.c.public_id)
            .where(analysis_user_links.c.user_id == user_id)
            .order_by(analysis_user_links.c.saved_at.desc())
        )
        with self.engine.connect() as connection:
            rows = connection.execute(query).mappings().all()
        return [
            {
                "public_id": row["public_id"],
                "owner": row["owner"],
                "repository_name": row["repository_name"],
                "commit_sha": row["commit_sha"],
                "saved_at": row["saved_at"],
                "scores": AnalysisReport.model_validate(
                    json.loads(row["report_json"])
                ).analysis.scores,
            }
            for row in rows
        ]

    def remove_for_user(self, user_id: str, public_id: str) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                analysis_user_links.delete().where(
                    analysis_user_links.c.user_id == user_id,
                    analysis_user_links.c.public_id == public_id,
                )
            )
        return bool(result.rowcount)

    def get(self, public_id: str) -> AnalysisReport | None:
        with self.engine.connect() as connection:
            serialized = connection.execute(
                select(analyses.c.report_json).where(
                    analyses.c.public_id == public_id,
                    analyses.c.visibility == "public",
                )
            ).scalar_one_or_none()
        if serialized is None:
            return None
        return AnalysisReport.model_validate(json.loads(serialized))

    def ping(self) -> None:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise AnalysisPersistenceError("Database readiness check failed.") from exc

    def increment_metric(self, metric: str) -> None:
        if metric not in {
            "analysis_completed",
            "analysis_failed",
            "cache_reused",
            "provider_failed",
            "quota_exceeded",
        }:
            raise ValueError("Unsupported operational metric.")
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            values = {"metric": metric, "value": 1, "updated_at": now}
            if connection.dialect.name == "postgresql":
                postgresql_statement = postgresql_insert(operational_metrics).values(**values)
                connection.execute(
                    postgresql_statement.on_conflict_do_update(
                        index_elements=[operational_metrics.c.metric],
                        set_={"value": operational_metrics.c.value + 1, "updated_at": now},
                    )
                )
            else:
                sqlite_statement = sqlite_insert(operational_metrics).values(**values)
                connection.execute(
                    sqlite_statement.on_conflict_do_update(
                        index_elements=[operational_metrics.c.metric],
                        set_={"value": operational_metrics.c.value + 1, "updated_at": now},
                    )
                )

    def operational_summary(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(operational_metrics.c.metric, operational_metrics.c.value)
            ).all()
        return {str(metric): int(value) for metric, value in rows}

    def retention_candidates(self, before: datetime) -> dict[str, int]:
        """Count records eligible for retention cleanup without changing the database."""
        with self.engine.connect() as connection:
            return self._retention_counts(connection, before)

    def apply_retention(self, before: datetime) -> dict[str, int]:
        """Delete explicitly eligible operational data in one transaction."""
        try:
            with self.engine.begin() as connection:
                counts = self._retention_counts(connection, before)
                connection.execute(
                    delete(anonymous_usage).where(anonymous_usage.c.updated_at < before)
                )
                connection.execute(
                    delete(authenticated_usage).where(authenticated_usage.c.updated_at < before)
                )
                connection.execute(
                    delete(webhook_events).where(webhook_events.c.processed_at < before)
                )
                connection.execute(
                    delete(api_keys).where(
                        api_keys.c.active.is_(False),
                        func.coalesce(api_keys.c.last_used_at, api_keys.c.created_at) < before,
                    )
                )
                owned = exists().where(analysis_user_links.c.public_id == analyses.c.public_id)
                connection.execute(delete(analyses).where(analyses.c.created_at < before, ~owned))
                return counts
        except SQLAlchemyError as exc:
            raise AnalysisPersistenceError("Retention cleanup failed.") from exc

    @staticmethod
    def _retention_counts(connection: Connection, before: datetime) -> dict[str, int]:
        owned = exists().where(analysis_user_links.c.public_id == analyses.c.public_id)
        return {
            "anonymous_usage": connection.execute(
                select(func.count())
                .select_from(anonymous_usage)
                .where(anonymous_usage.c.updated_at < before)
            ).scalar_one(),
            "authenticated_usage": connection.execute(
                select(func.count())
                .select_from(authenticated_usage)
                .where(authenticated_usage.c.updated_at < before)
            ).scalar_one(),
            "webhook_events": connection.execute(
                select(func.count())
                .select_from(webhook_events)
                .where(webhook_events.c.processed_at < before)
            ).scalar_one(),
            "revoked_api_keys": connection.execute(
                select(func.count())
                .select_from(api_keys)
                .where(
                    api_keys.c.active.is_(False),
                    func.coalesce(api_keys.c.last_used_at, api_keys.c.created_at) < before,
                )
            ).scalar_one(),
            "unowned_analyses": connection.execute(
                select(func.count())
                .select_from(analyses)
                .where(analyses.c.created_at < before, ~owned)
            ).scalar_one(),
        }

    @staticmethod
    def _identity(report: AnalysisReport) -> dict[str, str]:
        repository = report.snapshot.repository
        return {
            "provider": repository.provider.lower(),
            "owner": repository.owner.lower(),
            "repository_name": repository.name.lower(),
            "commit_sha": report.snapshot.metadata.commit_sha,
            "analysis_version": report.analysis_version,
        }


@lru_cache
def get_analysis_store() -> AnalysisStore:
    settings = get_settings()
    return AnalysisStore(
        settings.database_url,
        create_schema=settings.app_env != "production",
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
        connect_timeout=settings.database_connect_timeout_seconds,
    )
