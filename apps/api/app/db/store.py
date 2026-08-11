import json
import secrets
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import select

from app.schemas.analysis import AnalysisReport

metadata = MetaData()
analyses = Table(
    "analyses",
    metadata,
    Column("public_id", String(32), primary_key=True),
    Column("report_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
anonymous_usage = Table(
    "anonymous_usage",
    metadata,
    Column("anonymous_id", String(128), primary_key=True),
    Column("analysis_count", Integer, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


class AnonymousLimitExceeded(RuntimeError):
    """Raised when an anonymous browser exhausts its configured allowance."""


class AnalysisStore:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        if database_url == "sqlite:///:memory:":
            self.engine = create_engine(
                database_url, connect_args=connect_args, poolclass=StaticPool
            )
        else:
            self.engine = create_engine(database_url, connect_args=connect_args)
        metadata.create_all(self.engine)

    def save(self, report: AnalysisReport, anonymous_id: str, limit: int) -> AnalysisReport:
        public_id = secrets.token_urlsafe(12)
        now = datetime.now(UTC)
        stored_report = report.model_copy(update={"public_id": public_id})
        serialized = stored_report.model_dump_json()
        try:
            with self.engine.begin() as connection:
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
                connection.execute(
                    analyses.insert().values(
                        public_id=public_id, report_json=serialized, created_at=now
                    )
                )
        except IntegrityError as exc:
            raise RuntimeError("Analysis persistence failed.") from exc
        return stored_report

    def get(self, public_id: str) -> AnalysisReport | None:
        with self.engine.connect() as connection:
            serialized = connection.execute(
                select(analyses.c.report_json).where(analyses.c.public_id == public_id)
            ).scalar_one_or_none()
        if serialized is None:
            return None
        return AnalysisReport.model_validate(json.loads(serialized))
