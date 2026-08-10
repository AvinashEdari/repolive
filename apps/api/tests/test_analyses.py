from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_analysis_request_validates_repository() -> None:
    response = client.post(
        "/api/v1/analyses", json={"repository_url": "https://github.com/openai/openai-python"}
    )
    assert response.status_code == 202
    assert response.json()["repository"]["canonical_url"] == "https://github.com/openai/openai-python"


def test_analysis_request_rejects_non_github_host() -> None:
    response = client.post(
        "/api/v1/analyses", json={"repository_url": "https://example.com/openai/openai-python"}
    )
    assert response.status_code == 422

