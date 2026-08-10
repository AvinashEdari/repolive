from fastapi.testclient import TestClient

from app.api.routes.analyses import get_repository_provider
from app.main import app
from app.providers.base import RepositoryProvider
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


class FakeRepositoryProvider(RepositoryProvider):
    def parse_url(self, url: str) -> RepositoryReference:
        from app.providers.github import GitHubRepositoryProvider

        return GitHubRepositoryProvider().parse_url(url)

    async def fetch_snapshot(self, repository: RepositoryReference) -> RepositorySnapshot:
        return RepositorySnapshot(
            repository=repository,
            metadata=RepositoryMetadata(
                description="Test repository",
                default_branch="main",
                stars=1,
                forks=0,
                open_issues=0,
                size_kib=5,
                archived=False,
                license_spdx=None,
                primary_language="Python",
                last_pushed_at=None,
            ),
            files=[RepositoryFile(path="README.md", size_bytes=10)],
        )

client = TestClient(app)
app.dependency_overrides[get_repository_provider] = FakeRepositoryProvider


def test_analysis_request_validates_repository() -> None:
    response = client.post(
        "/api/v1/analyses", json={"repository_url": "https://github.com/openai/openai-python"}
    )
    assert response.status_code == 200
    assert response.json()["repository"]["canonical_url"] == "https://github.com/openai/openai-python"
    assert response.json()["files"][0]["path"] == "README.md"


def test_analysis_request_rejects_non_github_host() -> None:
    response = client.post(
        "/api/v1/analyses", json={"repository_url": "https://example.com/openai/openai-python"}
    )
    assert response.status_code == 422
