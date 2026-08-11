import pytest

from app.db.store import AnalysisStore, AnonymousLimitExceeded
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
    assert store.save(empty_report(), "another-browser", 1) == first
    with pytest.raises(AnonymousLimitExceeded):
        store.save(empty_report(commit_sha="commit-2"), "browser", 1)


def test_analysis_version_invalidates_cached_report() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    first = store.save(empty_report(version="1"), "browser", 2)
    second = store.save(empty_report(version="2"), "browser", 2)
    assert first.public_id != second.public_id


def test_database_ping_uses_live_connection() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    store.ping()


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
