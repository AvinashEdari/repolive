from app.analysis.languages import LanguageAnalyzer
from app.analysis.pipeline import AnalysisPipeline
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


def snapshot(files: list[RepositoryFile]) -> RepositorySnapshot:
    return RepositorySnapshot(
        repository=RepositoryReference(
            owner="example", name="project", canonical_url="https://github.com/example/project"
        ),
        metadata=RepositoryMetadata(
            description=None,
            default_branch="main",
            stars=0,
            forks=0,
            open_issues=0,
            size_kib=1,
            archived=False,
            license_spdx=None,
            primary_language=None,
            last_pushed_at=None,
        ),
        files=files,
    )


def test_language_analysis_uses_known_bytes_and_ignores_vendor_directories() -> None:
    result = LanguageAnalyzer().analyze(
        snapshot(
            [
                RepositoryFile(path="src/main.py", size_bytes=300),
                RepositoryFile(path="web/app.ts", size_bytes=100),
                RepositoryFile(path="node_modules/vendor.js", size_bytes=10_000),
            ]
        )
    )

    assert [(item.name, item.share_percent) for item in result] == [
        ("Python", 75.0),
        ("TypeScript", 25.0),
    ]


def test_pipeline_returns_evidence_based_structure_findings() -> None:
    report = AnalysisPipeline().analyze(
        snapshot(
            [
                RepositoryFile(path="README.md", size_bytes=20),
                RepositoryFile(path="package.json", size_bytes=40),
                RepositoryFile(path="next.config.ts", size_bytes=10),
                RepositoryFile(path="Dockerfile", size_bytes=10),
                RepositoryFile(path=".github/workflows/test.yml", size_bytes=10),
            ]
        )
    )

    assert report.status == "analyzed"
    assert {item.name for item in report.analysis.technologies} == {"Docker", "Next.js"}
    assert report.analysis.project_types == [
        "Web application",
        "Containerized application",
        "CI-enabled project",
    ]
    assert {item.role for item in report.analysis.important_files} == {
        "Primary documentation",
        "Node package manifest",
        "Container build definition",
        "GitHub Actions workflow",
    }


def test_unknown_repository_gets_honest_generic_project_type() -> None:
    report = AnalysisPipeline().analyze(
        snapshot([RepositoryFile(path="README"), RepositoryFile(path="notes.txt")])
    )
    assert report.analysis.project_types == ["General software repository"]
    assert report.analysis.languages == []
    assert report.analysis.important_files[0].role == "Primary documentation"


def test_manifest_contents_drive_dependencies_frameworks_runtimes_and_scores() -> None:
    report = AnalysisPipeline().analyze(
        snapshot(
            [
                RepositoryFile(
                    path="package.json",
                    text_content='{"engines":{"node":">=22"},"dependencies":{"react":"^19"}}',
                ),
                RepositoryFile(path="README.md"),
                RepositoryFile(path="LICENSE"),
                RepositoryFile(path="tests/app.test.ts"),
                RepositoryFile(path=".github/workflows/test.yml"),
                RepositoryFile(path="Dockerfile"),
                RepositoryFile(path=".env.example"),
            ]
        )
    )

    assert report.analysis.dependencies[0].name == "react"
    assert any(item.name == "React" for item in report.analysis.technologies)
    assert report.analysis.runtimes[0].version_constraint == ">=22"
    assert report.analysis.quality.has_tests is True
    assert {score.value for score in report.analysis.scores} == {100}
    assert all(
        factor.evidence
        for score in report.analysis.scores
        for factor in score.factors
        if factor.impact == "positive"
    )
