import base64

import httpx
import pytest

from app.core.config import Settings
from app.providers.base import (
    InvalidRepositoryUrl,
    RepositoryProviderError,
    RepositoryRateLimitError,
)
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
        "https://github.com/../b",
        "https://github.com/./b",
    ],
)
def test_rejects_unsafe_or_unsupported_url(url: str) -> None:
    with pytest.raises(InvalidRepositoryUrl):
        provider.parse_url(url)


@pytest.mark.asyncio
async def test_rejects_unsafe_repository_paths() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "commit"})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={"truncated": False, "tree": [{"path": "../package.json", "type": "blob"}]},
            )
        return httpx.Response(200, json={"default_branch": "main"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        with pytest.raises(RepositoryProviderError, match="unsafe repository path"):
            await GitHubRepositoryProvider(Settings(), client).fetch_snapshot(
                provider.parse_url("https://github.com/a/b")
            )


@pytest.mark.asyncio
async def test_search_uses_one_official_api_call_and_transparent_ranking() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "owner/relevant",
                        "description": "fastapi starter",
                        "language": "Python",
                        "topics": ["fastapi"],
                        "stargazers_count": 5,
                        "updated_at": "2026-08-01T12:00:00Z",
                        "license": {"spdx_id": "MIT"},
                        "archived": False,
                        "fork": False,
                    },
                    {
                        "full_name": "owner/popular",
                        "description": "unrelated",
                        "language": "Python",
                        "topics": [],
                        "stargazers_count": 1_000_000,
                        "updated_at": "2026-08-01T12:00:00Z",
                        "license": None,
                        "archived": False,
                        "fork": False,
                    },
                ]
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        results = await GitHubRepositoryProvider(Settings(), client).search_repositories(
            "topic:fastapi language:Python fastapi", 2
        )

    assert len(requests) == 1
    assert requests[0].url.path == "/search/repositories"
    assert results[0].full_name == "owner/relevant"
    assert results[0].ranking_reasons
    assert results[0].url == "https://github.com/owner/relevant"


def test_rate_limit_retry_after_is_bounded() -> None:
    response = httpx.Response(429, headers={"retry-after": "99999"})
    with pytest.raises(RepositoryRateLimitError) as caught:
        provider._raise_for_status(response)
    assert caught.value.retry_after_seconds == 3600


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
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "commit-123"})
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
        snapshot = await github.fetch_snapshot(
            github.parse_url("https://github.com/openai/openai-python")
        )

    assert snapshot.metadata.primary_language == "Python"
    assert snapshot.metadata.commit_sha == "commit-123"
    assert snapshot.metadata.license_spdx == "Apache-2.0"
    assert [file.path for file in snapshot.files] == ["README.md", "src/client.py"]


@pytest.mark.asyncio
async def test_rejects_truncated_tree() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "commit-123"})
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json={"truncated": True, "tree": []})
        return httpx.Response(200, json={"default_branch": "main"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        github = GitHubRepositoryProvider(Settings(), client)
        with pytest.raises(RepositoryProviderError, match="safe recursive response limit"):
            await github.fetch_snapshot(github.parse_url("https://github.com/openai/openai-python"))


@pytest.mark.asyncio
async def test_fetches_only_allowlisted_bounded_evidence_content() -> None:
    package = b'{"dependencies":{"react":"^19.0.0"}}'

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "commit-123"})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {"path": "package.json", "type": "blob", "size": len(package), "sha": "a"},
                        {"path": "src/app.ts", "type": "blob", "size": 100, "sha": "b"},
                    ],
                },
            )
        if request.url.path == "/repos/a/b/git/blobs/a":
            return httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": f"{base64.b64encode(package).decode()}\n",
                },
            )
        return httpx.Response(200, json={"default_branch": "main"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        github = GitHubRepositoryProvider(Settings(), client)
        result = await github.fetch_snapshot(github.parse_url("https://github.com/a/b"))

    assert result.files[0].text_content == package.decode()
    assert result.files[1].text_content is None


@pytest.mark.asyncio
async def test_missing_evidence_blob_returns_partial_snapshot_warning() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "commit-123"})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [{"path": "package.json", "type": "blob", "size": 10, "sha": "gone"}],
                },
            )
        if request.url.path.endswith("/git/blobs/gone"):
            return httpx.Response(404)
        return httpx.Response(200, json={"default_branch": "main"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        github = GitHubRepositoryProvider(Settings(), client)
        result = await github.fetch_snapshot(github.parse_url("https://github.com/a/b"))

    assert result.files[0].text_content is None
    assert result.ingestion_warnings == ["Evidence content was unavailable: package.json"]


@pytest.mark.asyncio
async def test_malformed_commit_response_is_rejected() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"default_branch": "main"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        github = GitHubRepositoryProvider(Settings(), client)
        with pytest.raises(RepositoryProviderError, match="commit metadata"):
            await github.fetch_snapshot(github.parse_url("https://github.com/a/b"))


@pytest.mark.asyncio
async def test_symlinks_and_submodules_are_not_hydrated_as_evidence() -> None:
    requested_blobs = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "commit"})
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {
                            "path": "package.json",
                            "type": "blob",
                            "mode": "120000",
                            "sha": "link",
                        },
                        {"path": "vendor", "type": "commit", "sha": "submodule"},
                    ],
                },
            )
        if "/git/blobs/" in request.url.path:
            requested_blobs.append(request.url.path)
        return httpx.Response(200, json={"default_branch": "main"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        result = await GitHubRepositoryProvider(Settings(), client).fetch_snapshot(
            GitHubRepositoryProvider().parse_url("https://github.com/a/b")
        )

    assert result.files == []
    assert requested_blobs == []
