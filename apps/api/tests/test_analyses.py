import pytest
from fastapi.testclient import TestClient

from app.api.routes.analyses import get_analysis_store, get_repository_provider
from app.auth import AuthUser, get_optional_user
from app.main import app
from app.providers.base import (
    RepositoryConnectivityError,
    RepositoryNotFoundError,
    RepositoryProvider,
    RepositoryRateLimitError,
    RepositoryTooLargeError,
)
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


class FakeAnalysisStore:
    def __init__(self) -> None:
        self.reports: dict[str, object] = {}

    def save(
        self,
        report: object,
        anonymous_id: str,
        anonymous_limit: int,
        user_id: str | None = None,
        authenticated_limit: int = 50,
    ) -> object:
        del anonymous_id, anonymous_limit, user_id, authenticated_limit
        stored = report.model_copy(update={"public_id": "public-test-id"})
        self.reports["public-test-id"] = stored
        return stored

    def get(self, public_id: str) -> object | None:
        return self.reports.get(public_id)

    def list_for_user(self, user_id: str) -> list[dict[str, object]]:
        del user_id
        return []

    def remove_for_user(self, user_id: str, public_id: str) -> bool:
        del user_id, public_id
        return True


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
fake_store = FakeAnalysisStore()
app.dependency_overrides[get_repository_provider] = FakeRepositoryProvider
app.dependency_overrides[get_analysis_store] = lambda: fake_store


def test_analysis_request_validates_repository() -> None:
    response = client.post(
        "/api/v1/analyses", json={"repository_url": "https://github.com/openai/openai-python"}
    )
    assert response.status_code == 200
    assert (
        response.json()["snapshot"]["repository"]["canonical_url"]
        == "https://github.com/openai/openai-python"
    )
    assert response.json()["snapshot"]["files"][0]["path"] == "README.md"
    assert "text_content" not in response.json()["snapshot"]["files"][0]
    assert response.json()["analysis"]["important_files"][0]["role"] == "Primary documentation"
    assert response.json()["public_id"] == "public-test-id"
    assert response.cookies.get("repolive_anonymous_id")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie

    shared = client.get("/api/v1/analyses/public-test-id")
    assert shared.status_code == 200
    assert shared.json()["public_id"] == "public-test-id"


def test_analysis_request_rejects_non_github_host() -> None:
    response = client.post(
        "/api/v1/analyses", json={"repository_url": "https://example.com/openai/openai-python"}
    )
    assert response.status_code == 422


def test_unknown_public_analysis_is_not_found() -> None:
    response = client.get("/api/v1/analyses/missing")
    assert response.status_code == 404


def test_history_requires_authentication_and_accepts_verified_user() -> None:
    assert client.get("/api/v1/analyses/me/history").status_code == 401
    app.dependency_overrides[get_optional_user] = lambda: AuthUser("user-1", "a@example.com")
    try:
        assert client.get("/api/v1/analyses/me/history").json() == []
        assert client.delete("/api/v1/analyses/me/history/public-test-id").status_code == 204
    finally:
        app.dependency_overrides.pop(get_optional_user)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (RepositoryNotFoundError("missing"), 404),
        (RepositoryRateLimitError("limited"), 429),
        (RepositoryTooLargeError("large"), 413),
        (RepositoryConnectivityError("offline"), 504),
    ],
)
def test_provider_failures_have_specific_api_contracts(
    error: Exception, expected_status: int
) -> None:
    class FailingProvider(FakeRepositoryProvider):
        async def fetch_snapshot(self, repository: RepositoryReference) -> RepositorySnapshot:
            del repository
            raise error

    app.dependency_overrides[get_repository_provider] = FailingProvider
    try:
        response = client.post(
            "/api/v1/analyses", json={"repository_url": "https://github.com/a/b"}
        )
    finally:
        app.dependency_overrides[get_repository_provider] = FakeRepositoryProvider
    assert response.status_code == expected_status


def test_oversized_request_body_is_rejected_before_validation() -> None:
    response = client.post(
        "/api/v1/analyses",
        content="x" * 25_000,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_oversized_request_body_without_content_length_is_rejected() -> None:
    def body() -> object:
        yield b"x" * 25_000

    response = client.post(
        "/api/v1/analyses",
        content=body(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_malformed_anonymous_cookie_is_rotated() -> None:
    malformed_client = TestClient(app)
    malformed_client.cookies.set("repolive_anonymous_id", "x" * 500)
    response = malformed_client.post(
        "/api/v1/analyses",
        json={"repository_url": "https://github.com/openai/openai-python"},
    )
    assert response.status_code == 200
    assert response.cookies["repolive_anonymous_id"] != "x" * 500


@pytest.mark.parametrize("public_id", ["../secret", "short", "x" * 33, "bad%2Fvalue"])
def test_public_id_routes_reject_malformed_values(public_id: str) -> None:
    assert client.get(f"/api/v1/analyses/{public_id}").status_code == 404
    machine = {"operating_system": "Linux", "cpu_architecture": "x86_64"}
    assert (
        client.post(f"/api/v1/analyses/{public_id}/compatibility", json=machine).status_code == 404
    )


def test_security_and_cache_headers_are_present() -> None:
    response = client.get("/api/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["permissions-policy"] == "camera=(), geolocation=(), microphone=()"
