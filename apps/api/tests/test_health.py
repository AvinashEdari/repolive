from fastapi.testclient import TestClient

from app.api.routes.health import get_analysis_store
from app.main import app


class ReadyStore:
    def ping(self) -> None:
        return None


def test_health() -> None:
    app.dependency_overrides[get_analysis_store] = ReadyStore
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert client.get("/api/v1/health/live").json() == {"status": "alive"}
    assert client.get("/api/v1/health/ready").json() == {
        "status": "ready",
        "database": "ok",
    }
