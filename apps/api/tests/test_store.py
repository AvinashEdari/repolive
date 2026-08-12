from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.store import (
    AnalysisPersistenceError,
    AnalysisStore,
    AnonymousLimitExceeded,
    AuthenticatedLimitExceeded,
    analyses,
    anonymous_usage,
    api_keys,
    authenticated_usage,
    webhook_events,
)
from app.schemas.analysis import AnalysisReport, DeterministicAnalysis, QualitySignals
from app.schemas.repository import RepositoryMetadata, RepositoryReference, RepositorySnapshot


def empty_report(commit_sha: str = "commit-1", version: str = "1") -> AnalysisReport:
    return AnalysisReport(
        analysis_version=version,
        snapshot=RepositorySnapshot(
            repository=RepositoryReference(
                owner="a", name="b", canonical_url="https://github.com/a/b"
            ),
            metadata=RepositoryMetadata(
                commit_sha=commit_sha,
                description=None,
                default_branch="main",
                stars=0,
                forks=0,
                open_issues=0,
                size_kib=0,
                archived=False,
                license_spdx=None,
                primary_language=None,
                last_pushed_at=None,
            ),
            files=[],
        ),
        analysis=DeterministicAnalysis(
            languages=[],
            technologies=[],
            important_files=[],
            project_types=["General software repository"],
            dependencies=[],
            runtimes=[],
            quality=QualitySignals(
                has_readme=False,
                has_license=False,
                has_tests=False,
                has_ci=False,
                has_container_config=False,
                has_environment_example=False,
            ),
            scores=[],
        ),
    )


def test_store_persists_public_report_and_enforces_limit() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    first = store.save(empty_report(), "browser", 1)

    assert first.public_id is not None
    assert store.get(first.public_id) == first
    cached = store.save(empty_report(), "another-browser", 1)
    assert cached.public_id == first.public_id
    assert cached.cache_status == "cached"
    with pytest.raises(AnonymousLimitExceeded):
        store.save(empty_report(commit_sha="commit-2"), "browser", 1)


def test_analysis_version_invalidates_cached_report() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    first = store.save(empty_report(version="1"), "browser", 2)
    second = store.save(empty_report(version="2"), "browser", 2)
    assert first.public_id != second.public_id


def test_authenticated_history_is_private_idempotent_and_removable() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    first = store.save(empty_report(), "browser", 2, "user-a")
    cached = store.save(empty_report(), "another", 2, "user-a")
    store.save(empty_report(), "another", 2, "user-b")
    assert cached.cache_status == "cached"
    history = store.list_for_user("user-a")
    assert len(history) == 1
    assert history[0]["public_id"] == first.public_id
    assert store.remove_for_user("user-a", str(first.public_id)) is True
    assert store.list_for_user("user-a") == []
    assert len(store.list_for_user("user-b")) == 1
    assert store.get(str(first.public_id)) is not None


def test_authenticated_analyses_do_not_consume_anonymous_allowance() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    store.save(empty_report(), "shared-browser", 1, "user-a")
    store.save(empty_report(commit_sha="commit-2"), "shared-browser", 1, "user-a")

    anonymous = store.save(empty_report(commit_sha="commit-3"), "shared-browser", 1)
    assert anonymous.public_id is not None
    with pytest.raises(AnonymousLimitExceeded):
        store.save(empty_report(commit_sha="commit-4"), "shared-browser", 1)


def test_authenticated_new_analysis_limit_and_free_cache_reuse() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    first = store.save(empty_report(), "browser", 1, "user-a", 1)
    cached = store.save(empty_report(), "browser", 1, "user-a", 1)
    assert cached.public_id == first.public_id
    assert cached.cache_status == "cached"
    with pytest.raises(AuthenticatedLimitExceeded):
        store.save(empty_report(commit_sha="commit-2"), "browser", 1, "user-a", 1)


def test_failed_history_link_rolls_back_the_analysis_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = AnalysisStore("sqlite:///:memory:")

    def fail_link(*args: object) -> None:
        del args
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(store, "_link_user", fail_link)
    with pytest.raises(AnalysisPersistenceError):
        store.save(empty_report(), "browser", 1, "user-a")

    with store.engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(analyses)).scalar_one() == 0


def test_database_ping_uses_live_connection() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    store.ping()


def test_non_public_analysis_is_never_returned_by_public_lookup() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    stored = store.save(empty_report(), "browser", 5, "user-a")
    with store.engine.begin() as connection:
        connection.execute(
            analyses.update()
            .where(analyses.c.public_id == stored.public_id)
            .values(visibility="private", owner_user_id="user-a")
        )

    assert store.get(str(stored.public_id)) is None
    assert store.list_for_user("user-a")[0]["public_id"] == stored.public_id


def test_retention_dry_run_and_cleanup_preserve_owned_reports() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    unowned = store.save(empty_report(), "old-browser", 5)
    owned = store.save(empty_report(commit_sha="commit-owned"), "browser", 5, "user-a")
    cutoff = datetime.now(UTC) - timedelta(days=30)
    old = cutoff - timedelta(days=1)
    with store.engine.begin() as connection:
        connection.execute(analyses.update().values(created_at=old))
        connection.execute(anonymous_usage.update().values(updated_at=old))
        connection.execute(authenticated_usage.update().values(updated_at=old))
        connection.execute(
            webhook_events.insert().values(event_id="evt_old", event_type="test", processed_at=old)
        )
        connection.execute(
            api_keys.insert().values(
                key_id="old-key",
                user_id="user-a",
                name="Old",
                key_hash="a" * 64,
                prefix="rl_live_old",
                request_count=0,
                active=False,
                created_at=old,
                quota_reset_at=cutoff,
            )
        )

    assert store.retention_candidates(cutoff) == {
        "anonymous_usage": 1,
        "authenticated_usage": 1,
        "webhook_events": 1,
        "revoked_api_keys": 1,
        "unowned_analyses": 1,
    }
    assert store.get(str(unowned.public_id)) is not None

    removed = store.apply_retention(cutoff)
    assert removed["unowned_analyses"] == 1
    assert store.get(str(unowned.public_id)) is None
    assert store.get(str(owned.public_id)) is not None


def test_postgres_engine_uses_bounded_healthy_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_create_engine(url: str, **options: object) -> object:
        captured["url"] = url
        captured.update(options)
        return sentinel

    monkeypatch.setattr("app.db.store.create_engine", fake_create_engine)
    store = AnalysisStore(
        "postgresql+psycopg://user:secret@db.example/repolive",
        create_schema=False,
        pool_size=7,
        max_overflow=3,
        pool_timeout=9,
        pool_recycle=240,
        connect_timeout=8,
    )
    assert store.engine is sentinel
    assert captured["pool_pre_ping"] is True
    assert captured["pool_size"] == 7
    assert captured["max_overflow"] == 3
    assert captured["pool_timeout"] == 9
    assert captured["pool_recycle"] == 240
    assert captured["connect_args"] == {"connect_timeout": 8}
