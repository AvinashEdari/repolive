from app.compatibility import MachineProfile, evaluate_machine
from app.schemas.analysis import (
    AnalysisReport,
    DeterministicAnalysis,
    QualitySignals,
    RuntimeFinding,
)
from app.schemas.repository import RepositoryMetadata, RepositoryReference, RepositorySnapshot


def empty_report() -> AnalysisReport:
    return AnalysisReport(
        snapshot=RepositorySnapshot(
            repository=RepositoryReference(
                owner="a", name="b", canonical_url="https://github.com/a/b"
            ),
            metadata=RepositoryMetadata(
                commit_sha="abc",
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
            project_types=[],
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


def test_runtime_compatibility_is_evidence_backed() -> None:
    report = empty_report().model_copy(deep=True)
    report.analysis.runtimes = [
        RuntimeFinding(runtime="Python", version_constraint=">=3.11", evidence=["pyproject.toml"])
    ]
    compatible = evaluate_machine(
        report,
        MachineProfile(operating_system="Linux", cpu_architecture="x86_64", python_version="3.12"),
    )
    incompatible = evaluate_machine(
        report,
        MachineProfile(operating_system="Linux", cpu_architecture="x86_64", python_version="3.10"),
    )
    assert compatible.status == "compatible"
    assert compatible.conditions[0].evidence == ["pyproject.toml"]
    assert incompatible.status == "incompatible"


def test_missing_machine_and_repository_evidence_remains_unknown() -> None:
    result = evaluate_machine(
        empty_report(), MachineProfile(operating_system="Windows", cpu_architecture="arm64")
    )
    assert result.status == "unknown"
    assert result.conditions == []
