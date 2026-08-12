import pytest
from fastapi.testclient import TestClient

from app.analysis.diagnosis import diagnose_error
from app.analysis.pipeline import AnalysisPipeline
from app.api.routes.analyses import get_repository_provider
from app.db.store import AnalysisStore, get_analysis_store
from app.main import app
from app.schemas.analysis import AnalysisReport
from app.schemas.product import DiscoveryItem
from app.schemas.repository import (
    RepositoryFile,
    RepositoryMetadata,
    RepositoryReference,
    RepositorySnapshot,
)


def report(owner: str, name: str, manifest: str, content: str) -> AnalysisReport:
    return AnalysisPipeline().analyze(
        RepositorySnapshot(
            repository=RepositoryReference(
                owner=owner, name=name, canonical_url=f"https://github.com/{owner}/{name}"
            ),
            metadata=RepositoryMetadata(
                commit_sha=f"{owner}-{name}",
                description=f"{name} project",
                default_branch="main",
                stars=10,
                forks=1,
                open_issues=0,
                size_kib=10,
                archived=False,
                license_spdx="MIT",
                primary_language="Python",
                last_pushed_at=None,
            ),
            files=[RepositoryFile(path=manifest, size_bytes=len(content), text_content=content)],
        )
    )


def test_diagnosis_uses_error_pattern_and_repository_context() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    stored = store.save(
        report("a", "python-app", "pyproject.toml", '[project]\ndependencies=["fastapi>=0.100"]'),
        "browser-a",
        5,
    )
    app.dependency_overrides[get_analysis_store] = lambda: store
    try:
        response = TestClient(app).post(
            f"/api/v1/analyses/{stored.public_id}/diagnose",
            json={"error_text": "ModuleNotFoundError: No module named 'fastapi'"},
        )
    finally:
        app.dependency_overrides.pop(get_analysis_store)
    assert response.status_code == 200
    assert response.json()["category"] == "missing_dependency"
    assert response.json()["confidence"] == "high"
    assert any("pyproject.toml" in item for item in response.json()["evidence"])
    assert "ModuleNotFoundError" not in str(response.json())


def test_unknown_diagnosis_is_honest_and_input_is_bounded() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    stored = store.save(report("a", "plain", "README.md", "hello"), "browser-a", 5)
    app.dependency_overrides[get_analysis_store] = lambda: store
    try:
        client = TestClient(app)
        unknown = client.post(
            f"/api/v1/analyses/{stored.public_id}/diagnose", json={"error_text": "something odd"}
        )
        oversized = client.post(
            f"/api/v1/analyses/{stored.public_id}/diagnose", json={"error_text": "x" * 20_001}
        )
    finally:
        app.dependency_overrides.pop(get_analysis_store)
    assert unknown.json()["category"] == "unknown"
    assert unknown.json()["confidence"] == "low"
    assert oversized.status_code == 422


@pytest.mark.parametrize(
    ("error_text", "category"),
    [
        ("ModuleNotFoundError: No module named 'demo'", "missing_dependency"),
        ("tool: command not found", "missing_executable"),
        ("unsupported Python version 3.8", "incompatible_runtime"),
        ("environment variable API_KEY is required", "missing_environment_variable"),
        ("npm ERR! dependency resolution failed", "package_manager_issue"),
        ("Permission denied", "permission_issue"),
        ("EADDRINUSE: address already in use", "port_conflict"),
        ("postgres connection failed", "database_connection_failure"),
        ("cannot open shared object file", "missing_system_library"),
        ("could not resolve host", "network_download_problem"),
    ],
)
def test_diagnosis_supports_bounded_categories(error_text: str, category: str) -> None:
    result = diagnose_error(error_text, report("a", "plain", "README.md", "hello"))
    assert result.category == category


def test_comparison_uses_two_cached_reports() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    left = store.save(
        report("a", "python-app", "pyproject.toml", '[project]\ndependencies=["fastapi>=0.100"]'),
        "browser-a",
        5,
    )
    right = store.save(
        report("b", "node-app", "package.json", '{"dependencies":{"react":"^19"}}'),
        "browser-b",
        5,
    )
    app.dependency_overrides[get_analysis_store] = lambda: store
    try:
        response = TestClient(app).post(
            "/api/v1/comparisons",
            json={"left_public_id": left.public_id, "right_public_id": right.public_id},
        )
    finally:
        app.dependency_overrides.pop(get_analysis_store)
    assert response.status_code == 200
    assert response.json()["left_repository"] == "a/python-app"
    assert response.json()["right_repository"] == "b/node-app"
    assert {item["name"] for item in response.json()["dimensions"]} >= {
        "Purpose",
        "Languages",
        "Health scores",
    }
    assert response.json()["left_only_dependencies"] == ["fastapi"]
    assert response.json()["right_only_dependencies"] == ["react"]


class DiscoveryProvider:
    async def search_repositories(self, query: str, limit: int) -> list[DiscoveryItem]:
        assert query == "topic:fastapi language:Python web api"
        assert limit == 3
        return [
            DiscoveryItem(
                full_name="fastapi/fastapi",
                url="https://github.com/fastapi/fastapi",
                description="Framework",
                primary_language="Python",
                topics=["fastapi"],
                stars=1,
                updated_at=None,
                license_spdx="MIT",
                score=80,
                ranking_reasons=["Transparent reason"],
            )
        ]


def test_discovery_is_bounded_and_explainable() -> None:
    app.dependency_overrides[get_repository_provider] = DiscoveryProvider
    try:
        response = TestClient(app).get(
            "/api/v1/discover?topic=fastapi&language=Python&project_type=web%20api&limit=3"
        )
        missing = TestClient(app).get("/api/v1/discover")
        excessive = TestClient(app).get("/api/v1/discover?topic=python&limit=11")
    finally:
        app.dependency_overrides.pop(get_repository_provider)
    assert response.status_code == 200
    assert response.json()["items"][0]["ranking_reasons"] == ["Transparent reason"]
    assert "One bounded" in response.json()["cost"]
    assert missing.status_code == 422
    assert excessive.status_code == 422
