import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.engine import Connection, RowMapping

from app.db.store import AnalysisStore, analyses, analysis_user_links, metadata
from app.previews.models import ALLOWED_TRANSITIONS, PreviewEvent, PreviewStatus, PreviewView

preview_jobs = Table(
    "preview_jobs",
    metadata,
    Column("preview_id", String(32), primary_key=True),
    Column(
        "public_analysis_id",
        String(32),
        ForeignKey("analyses.public_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("user_id", String(128), nullable=False, index=True),
    Column("provider", String(32), nullable=False),
    Column("owner", String(100), nullable=False),
    Column("repository_name", String(200), nullable=False),
    Column("commit_sha", String(128), nullable=False),
    Column("status", String(32), nullable=False, index=True),
    Column("runtime_profile", String(64), nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("queued_at", DateTime(timezone=True)),
    Column("started_at", DateTime(timezone=True)),
    Column("ready_at", DateTime(timezone=True)),
    Column("expires_at", DateTime(timezone=True)),
    Column("stopped_at", DateTime(timezone=True)),
    Column("destroyed_at", DateTime(timezone=True)),
    Column("failure_category", String(64)),
    Column("safe_failure_message", Text),
    Column("sandbox_provider_id", String(128)),
    Column("routing_key", String(64), unique=True),
    Column("build_attempt", Integer, nullable=False, default=0),
    Column("resource_policy_version", String(32), nullable=False),
    Column("lease_owner", String(128)),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("heartbeat_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
preview_events = Table(
    "preview_events",
    metadata,
    Column("event_id", String(32), primary_key=True),
    Column(
        "preview_id",
        String(32),
        ForeignKey("preview_jobs.preview_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("sequence", Integer, nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("safe_message", Text, nullable=False),
    Column("fields_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("preview_id", "sequence", name="uq_preview_event_sequence"),
)
preview_usage = Table(
    "preview_usage",
    metadata,
    Column("user_id", String(128), primary_key=True),
    Column("period_start", DateTime(timezone=True), nullable=False),
    Column("preview_count", Integer, nullable=False, default=0),
    Column("build_seconds", Integer, nullable=False, default=0),
    Column("runtime_seconds", Integer, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


class PreviewConflict(RuntimeError):
    pass


class PreviewQuotaExceeded(RuntimeError):
    pass


class PreviewStore:
    def __init__(self, store: AnalysisStore) -> None:
        self.store = store

    def create(
        self,
        analysis_id: str,
        user_id: str,
        profile: str,
        policy_version: str,
        period_limit: int,
        concurrent_limit: int,
    ) -> PreviewView:
        now = datetime.now(UTC)
        period = now - timedelta(days=30)
        with self.store.engine.begin() as connection:
            owned = (
                connection.execute(
                    select(analyses).where(
                        analyses.c.public_id == analysis_id, analyses.c.owner_user_id.is_(None)
                    )
                )
                .mappings()
                .one_or_none()
            )
            linked = connection.execute(
                select(func.count())
                .select_from(analysis_user_links)
                .where(
                    analysis_user_links.c.public_id == analysis_id,
                    analysis_user_links.c.user_id == user_id,
                )
            ).scalar_one()
            if owned is None or not linked:
                raise KeyError(analysis_id)
            active = connection.execute(
                select(func.count())
                .select_from(preview_jobs)
                .where(
                    preview_jobs.c.user_id == user_id,
                    preview_jobs.c.status.in_(
                        [
                            "requested",
                            "policy_check",
                            "queued",
                            "cloning",
                            "building",
                            "starting",
                            "ready",
                            "stopping",
                        ]
                    ),
                )
            ).scalar_one()
            if active >= concurrent_limit:
                raise PreviewConflict("Concurrent preview limit reached.")
            usage = (
                connection.execute(select(preview_usage).where(preview_usage.c.user_id == user_id))
                .mappings()
                .one_or_none()
            )
            count = (
                0
                if usage is None or usage["period_start"] < period
                else int(usage["preview_count"])
            )
            if count >= period_limit:
                raise PreviewQuotaExceeded("Preview allowance exhausted.")
            if usage is None:
                connection.execute(
                    preview_usage.insert().values(
                        user_id=user_id,
                        period_start=now,
                        preview_count=1,
                        build_seconds=0,
                        runtime_seconds=0,
                        updated_at=now,
                    )
                )
            elif usage["period_start"] < period:
                connection.execute(
                    preview_usage.update()
                    .where(preview_usage.c.user_id == user_id)
                    .values(period_start=now, preview_count=1, updated_at=now)
                )
            else:
                connection.execute(
                    preview_usage.update()
                    .where(preview_usage.c.user_id == user_id)
                    .values(preview_count=preview_usage.c.preview_count + 1, updated_at=now)
                )
            preview_id = secrets.token_urlsafe(12)
            routing_key = secrets.token_urlsafe(24)
            connection.execute(
                preview_jobs.insert().values(
                    preview_id=preview_id,
                    public_analysis_id=analysis_id,
                    user_id=user_id,
                    provider=owned["provider"],
                    owner=owned["owner"],
                    repository_name=owned["repository_name"],
                    commit_sha=owned["commit_sha"],
                    status="requested",
                    runtime_profile=profile,
                    requested_at=now,
                    routing_key=routing_key,
                    build_attempt=0,
                    resource_policy_version=policy_version,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._event(connection, preview_id, "requested", "Preview request accepted.", {})
        return self.get(preview_id, user_id)

    def transition(
        self, preview_id: str, target: PreviewStatus, message: str, **values: object
    ) -> bool:
        now = datetime.now(UTC)
        sources = [
            source.value for source, targets in ALLOWED_TRANSITIONS.items() if target in targets
        ]
        if not sources:
            return False
        with self.store.engine.begin() as connection:
            result = connection.execute(
                preview_jobs.update()
                .where(preview_jobs.c.preview_id == preview_id, preview_jobs.c.status.in_(sources))
                .values(status=target.value, updated_at=now, **values)
            )
            if not result.rowcount:
                return False
            self._event(connection, preview_id, target.value, message, {})
        return True

    def get(self, preview_id: str, user_id: str) -> PreviewView:
        with self.store.engine.connect() as connection:
            row = (
                connection.execute(
                    select(preview_jobs).where(
                        preview_jobs.c.preview_id == preview_id, preview_jobs.c.user_id == user_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise KeyError(preview_id)
        return self._view(row)

    def events(self, preview_id: str, user_id: str) -> list[PreviewEvent]:
        self.get(preview_id, user_id)
        with self.store.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(preview_events)
                    .where(preview_events.c.preview_id == preview_id)
                    .order_by(preview_events.c.sequence)
                )
                .mappings()
                .all()
            )
        return [
            PreviewEvent(
                event_id=r["event_id"],
                sequence=r["sequence"],
                event_type=r["event_type"],
                safe_message=r["safe_message"],
                fields=json.loads(r["fields_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def claim(self, worker_id: str, lease_seconds: int = 30) -> dict[str, object] | None:
        now = datetime.now(UTC)
        with self.store.engine.begin() as connection:
            row = (
                connection.execute(
                    select(preview_jobs)
                    .where(
                        preview_jobs.c.status == "queued",
                        (
                            preview_jobs.c.lease_expires_at.is_(None)
                            | (preview_jobs.c.lease_expires_at < now)
                        ),
                    )
                    .order_by(preview_jobs.c.queued_at)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            result = connection.execute(
                preview_jobs.update()
                .where(
                    preview_jobs.c.preview_id == row["preview_id"],
                    preview_jobs.c.status == "queued",
                    (
                        preview_jobs.c.lease_expires_at.is_(None)
                        | (preview_jobs.c.lease_expires_at < now)
                    ),
                )
                .values(
                    lease_owner=worker_id,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    heartbeat_at=now,
                )
            )
            return dict(row) if result.rowcount else None

    @staticmethod
    def _event(
        connection: Connection, preview_id: str, kind: str, message: str, fields: dict[str, object]
    ) -> None:
        sequence = connection.execute(
            select(func.coalesce(func.max(preview_events.c.sequence), 0) + 1).where(
                preview_events.c.preview_id == preview_id
            )
        ).scalar_one()
        connection.execute(
            preview_events.insert().values(
                event_id=secrets.token_urlsafe(12),
                preview_id=preview_id,
                sequence=sequence,
                event_type=kind,
                safe_message=message,
                fields_json=json.dumps(fields),
                created_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _view(row: RowMapping) -> PreviewView:
        status = PreviewStatus(row["status"])
        url = None
        from app.core.config import get_settings

        base = get_settings().preview_router_base_url
        if status == PreviewStatus.READY and base:
            url = f"{base.rstrip('/')}/{row['routing_key']}"
        return PreviewView(
            preview_id=row["preview_id"],
            public_analysis_id=row["public_analysis_id"],
            status=status,
            runtime_profile=row["runtime_profile"],
            commit_sha=row["commit_sha"],
            requested_at=row["requested_at"],
            started_at=row["started_at"],
            ready_at=row["ready_at"],
            expires_at=row["expires_at"],
            stopped_at=row["stopped_at"],
            destroyed_at=row["destroyed_at"],
            safe_failure_message=row["safe_failure_message"],
            preview_url=url,
            retryable=status in {PreviewStatus.FAILED, PreviewStatus.TIMED_OUT}
            and row["build_attempt"] < 2,
        )
