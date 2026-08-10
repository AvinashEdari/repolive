import httpx
import pytest

from app.core.config import Settings
from app.providers.base import InvalidRepositoryUrl, RepositoryProviderError
from app.providers.github import GitHubRepositoryProvider

provider = GitHubRepositoryProvider()


@pytest.mark.parametrize(
    ("url", "owner", "name"),
    [
        ("https://github.com/fastapi/fastapi", "fastapi", "fastapi"),
        ("https://www.github.com/openai/openai-python.git", "openai", "openai-python"),
    ],
)
def test_parse_valid_url(url: str, owner: str, name: str) -> None:
    result = provider.parse_url(url)
    assert (result.owner, result.name) == (owner, name)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://gitlab.com/a/b",
        "https://github.com/a/b/issues",
        "https://user:secret@github.com/a/b",
        "https://github.com/a/b?tab=readme",
        "https://github.com/a/%2e%2e",
    ],
)
def test_rejects_unsafe_or_unsupported_url(url: str) -> None:
    with pytest.raises(InvalidRepositoryUrl):
        provider.parse_url(url)


@pytest.mark.asyncio
async def test_fetches_bounded_repository_snapshot() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/openai/openai-python":
            return httpx.Response(
                200,
                json={
                    "description": "Python client",
                    "default_branch": "main",
                    "stargazers_count": 10,
                    "forks_count": 2,
                    "open_issues_count": 1,
                    "size": 42,
                    "archived": False,
                    "license": {"spdx_id": "Apache-2.0"},
                    "language": "Python",
                    "pushed_at": "2026-08-01T12:00:00Z",
                },
            )
        return httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {"path": "README.md", "type": "blob", "size": 100},
                    {"path": "src", "type": "tree"},
                    {"path": "src/client.py", "type": "blob", "size": 200},
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        github = GitHubRepositoryProvider(Settings(), client)
        snapshot = await github.fetch_snapshot(github.parse_url("https://github.com/openai/openai-python"))

    assert snapshot.metadata.primary_language == "Python"
    assert snapshot.metadata.license_spdx == "Apache-2.0"
    assert [file.path for file in snapshot.files] == ["README.md", "src/client.py"]


@pytest.mark.asyncio
async def test_rejects_truncated_tree() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json={"truncated": True, "tree": []})
        return httpx.Response(200, json={"default_branch": "main"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        github = GitHubRepositoryProvider(Settings(), client)
        with pytest.raises(RepositoryProviderError, match="safe recursive response limit"):
            await github.fetch_snapshot(github.parse_url("https://github.com/openai/openai-python"))
