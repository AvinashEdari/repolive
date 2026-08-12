import json
import logging

from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonFormatter, bind_request_id, reset_request_id


def test_json_formatter_emits_safe_structured_fields_and_request_id() -> None:
    record = logging.LogRecord("repolive", logging.INFO, "", 0, "analysis_completed", (), None)
    record.safe_fields = {"analysis_id": "public-id", "duration_ms": 12.5}
    token = bind_request_id("request-123")
    try:
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_id(token)
    assert payload["event"] == "analysis_completed"
    assert payload["request_id"] == "request-123"
    assert payload["analysis_id"] == "public-id"
    assert "authorization" not in payload
    assert "cookie" not in payload


def test_request_id_is_accepted_when_safe_and_generated_when_malformed() -> None:
    client = TestClient(app)
    supplied = client.get("/api/v1/health", headers={"X-Request-ID": "safe-request-123"})
    assert supplied.headers["x-request-id"] == "safe-request-123"

    generated = client.get("/api/v1/health", headers={"X-Request-ID": "bad value\nsecret"})
    assert generated.status_code == 200
    assert generated.headers["x-request-id"] != "bad value\nsecret"
    assert len(generated.headers["x-request-id"]) >= 8
