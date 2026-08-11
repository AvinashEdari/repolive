import pytest

from app.db.store import AnalysisStore, AnonymousLimitExceeded
from app.schemas.analysis import AnalysisReport, DeterministicAnalysis, QualitySignals
from app.schemas.repository import RepositoryMetadata, RepositoryReference, RepositorySnapshot


def empty_report() -> AnalysisReport:
    return AnalysisReport(
        snapshot=RepositorySnapshot(
            repository=RepositoryReference(
                owner="a", name="b", canonical_url="https://github.com/a/b"
            ),
            metadata=RepositoryMetadata(
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
    with pytest.raises(AnonymousLimitExceeded):
        store.save(empty_report(), "browser", 1)
