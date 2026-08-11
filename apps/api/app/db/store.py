import json
import secrets
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import select, text

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


class AnonymousLimitExceeded(RuntimeError):
    """Raised when an anonymous browser exhausts its configured allowance."""


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
        self, report: AnalysisReport, anonymous_id: str, limit: int, user_id: str | None = None
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
                    )
                ).scalar_one_or_none()
                if cached_json is not None:
                    cached = AnalysisReport.model_validate(json.loads(cached_json))
                    if user_id and cached.public_id:
                        self._link_user(connection, user_id, cached.public_id, now)
                    return cached.model_copy(update={"cache_status": "cached"})
                usage = connection.execute(
                    select(anonymous_usage.c.analysis_count).where(
                        anonymous_usage.c.anonymous_id == anonymous_id
                    )
                ).scalar_one_or_none()
                if usage is not None and usage >= limit:
                    raise AnonymousLimitExceeded
                if usage is None:
                    connection.execute(
                        anonymous_usage.insert().values(
                            anonymous_id=anonymous_id, analysis_count=1, updated_at=now
                        )
                    )
                else:
                    connection.execute(
                        anonymous_usage.update()
                        .where(anonymous_usage.c.anonymous_id == anonymous_id)
                        .values(analysis_count=usage + 1, updated_at=now)
                    )
                public_id = secrets.token_urlsafe(12)
                stored_report = report.model_copy(update={"public_id": public_id})
                serialized = stored_report.model_dump_json()
                connection.execute(
                    analyses.insert().values(
                        public_id=public_id,
                        **identity,
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
    def _link_user(connection: Connection, user_id: str, public_id: str, now: datetime) -> None:
        existing = connection.execute(
            select(analysis_user_links.c.public_id).where(
                analysis_user_links.c.user_id == user_id,
                analysis_user_links.c.public_id == public_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            connection.execute(
                analysis_user_links.insert().values(
                    user_id=user_id, public_id=public_id, saved_at=now
                )
            )

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
                select(analyses.c.report_json).where(analyses.c.public_id == public_id)
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
