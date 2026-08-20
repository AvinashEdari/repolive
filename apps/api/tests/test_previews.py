from app.analysis.pipeline import AnalysisPipeline
from app.core.config import Settings
from app.db.store import AnalysisStore
from app.previews.models import PreviewStatus
from app.previews.policy import PreviewPolicy
from app.previews.sanitization import sanitize_log
from app.previews.store import PreviewConflict, PreviewStore
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


def report(paths: list[str]):
    return AnalysisPipeline().analyze(
        RepositorySnapshot(
            repository=RepositoryReference(
                owner="example", name="site", canonical_url="https://github.com/example/site"
            ),
            metadata=RepositoryMetadata(
                description=None,
                default_branch="main",
                commit_sha="a" * 40,
                stars=0,
                forks=0,
                open_issues=0,
                size_kib=1,
                archived=False,
                license_spdx=None,
                primary_language="HTML",
                last_pushed_at=None,
            ),
            files=[RepositoryFile(path=path, size_bytes=10) for path in paths],
        )
    )


def test_static_policy_uses_only_trusted_profile() -> None:
    result = PreviewPolicy(Settings()).evaluate(report(["index.html", "styles.css"]))
    assert result.decision == "eligible"
    assert result.detected_profile == "static_html_v1"
    assert result.proposed_build_command == []


def test_policy_rejects_container_manifest_and_non_static_project() -> None:
    assert (
        PreviewPolicy(Settings()).evaluate(report(["index.html", "Dockerfile"])).decision
        == "ineligible"
    )
    assert PreviewPolicy(Settings()).evaluate(report(["src/main.py"])).decision == "ineligible"


def test_logs_strip_control_sequences_redact_and_truncate() -> None:
    value = sanitize_log("\x1b[31mtoken=abc\x00 https://user:pass@example.com " + "x" * 200, 80)
    assert "abc" not in value and "user:pass" not in value and "\x1b" not in value
    assert value.endswith("[TRUNCATED]")


def test_preview_store_enforces_ownership_concurrency_and_transitions() -> None:
    analysis_store = AnalysisStore("sqlite:///:memory:")
    saved = analysis_store.save(
        report(["index.html"]), "anonymous-identifier-long-enough", 5, user_id="user-1"
    )
    assert saved.public_id
    previews = PreviewStore(analysis_store)
    created = previews.create(saved.public_id, "user-1", "static_html_v1", "static-v1", 5, 1)
    assert created.commit_sha == "a" * 40
    assert previews.transition(created.preview_id, PreviewStatus.POLICY_CHECK, "checked")
    assert not previews.transition(created.preview_id, PreviewStatus.READY, "invalid")
    try:
        previews.create(saved.public_id, "user-1", "static_html_v1", "static-v1", 5, 1)
    except PreviewConflict:
        pass
    else:
        raise AssertionError("Concurrent limit must be transactional.")
    try:
        previews.get(created.preview_id, "user-2")
    except KeyError:
        pass
    else:
        raise AssertionError("Ownership must be enforced.")
