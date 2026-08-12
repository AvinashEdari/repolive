from app.analysis.pipeline import AnalysisPipeline
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


def test_setup_and_compatibility_are_derived_from_evidence() -> None:
    snapshot = RepositorySnapshot(
        repository=RepositoryReference(owner="a", name="b", canonical_url="https://github.com/a/b"),
        metadata=RepositoryMetadata(
            description="A web application",
            default_branch="main",
            stars=1,
            forks=0,
            open_issues=0,
            size_kib=1,
            archived=False,
            license_spdx="MIT",
            primary_language="TypeScript",
            last_pushed_at=None,
        ),
        files=[
            RepositoryFile(
                path="package.json",
                text_content='{"engines":{"node":">=22"},"scripts":{"dev":"next dev"}}',
            ),
            RepositoryFile(path="package-lock.json"),
            RepositoryFile(path="Dockerfile"),
            RepositoryFile(path=".env.example", text_content="DATABASE_URL=\nINVALID-NAME=\n"),
            RepositoryFile(path="README.md"),
            RepositoryFile(path="LICENSE"),
        ],
    )

    analysis = AnalysisPipeline().analyze(snapshot).analysis
    assert analysis.purpose_summary == "A web application"
    assert any(
        step.command == "npm install" and step.origin == "derived" for step in analysis.setup_steps
    )
    assert any(
        step.command == "next dev" and step.origin == "repository" for step in analysis.setup_steps
    )
    assert any(item.name == "Environment variable: DATABASE_URL" for item in analysis.prerequisites)
    assert any(item.subject == "Container runtime" for item in analysis.compatibility)
    assert any("CPU" in item.label for item in analysis.unknowns)
    assert any("README" in item.label for item in analysis.strengths)


def test_missing_evidence_is_reported_without_inventing_commands() -> None:
    snapshot = RepositorySnapshot(
        repository=RepositoryReference(owner="a", name="b", canonical_url="https://github.com/a/b"),
        metadata=RepositoryMetadata(
            description=None,
            default_branch="main",
            stars=0,
            forks=0,
            open_issues=0,
            size_kib=0,
            archived=True,
            license_spdx=None,
            primary_language=None,
            last_pushed_at=None,
        ),
        files=[],
    )
    analysis = AnalysisPipeline().analyze(snapshot).analysis
    assert analysis.setup_steps == []
    assert len(analysis.missing_essentials) == 4
    assert any("archived" in item.label for item in analysis.risks)


def test_readme_setup_commands_are_bounded_and_marked_untrusted() -> None:
    snapshot = RepositorySnapshot(
        repository=RepositoryReference(owner="a", name="b", canonical_url="https://github.com/a/b"),
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
        files=[
            RepositoryFile(
                path="README.md",
                text_content=(
                    "# Demo\n## Setup\n```bash\n$ npm install\nnpm start\n```\n"
                    "## Usage\n```bash\nignored --outside-setup\n```"
                ),
            )
        ],
    )
    steps = AnalysisPipeline().analyze(snapshot).analysis.setup_steps
    assert [step.command for step in steps] == ["npm install", "npm start"]
    assert all(step.origin == "repository" for step in steps)


def test_multiple_node_lockfiles_are_reported_as_a_risk() -> None:
    snapshot = RepositorySnapshot(
        repository=RepositoryReference(owner="a", name="b", canonical_url="https://github.com/a/b"),
        metadata=RepositoryMetadata(
            description=None,
            default_branch="main",
            stars=0,
            forks=0,
            open_issues=0,
            size_kib=0,
            archived=False,
            license_spdx=None,
            primary_language="TypeScript",
            last_pushed_at=None,
        ),
        files=[RepositoryFile(path="yarn.lock"), RepositoryFile(path="package-lock.json")],
    )
    risks = AnalysisPipeline().analyze(snapshot).analysis.risks
    conflict = next(item for item in risks if "Multiple Node.js lockfiles" in item.label)
    assert conflict.evidence == ["package-lock.json", "yarn.lock"]
