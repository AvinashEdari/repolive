import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Protocol

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class ErrorMonitor(Protocol):
    """Optional provider boundary; implementations must redact secrets before export."""

    def capture(self, event: str, fields: dict[str, object]) -> None: ...


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            payload["request_id"] = request_id
        fields = getattr(record, "safe_fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


logger = logging.getLogger("repolive")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

_error_monitor: ErrorMonitor | None = None


def set_error_monitor(monitor: ErrorMonitor | None) -> None:
    global _error_monitor
    _error_monitor = monitor


def bind_request_id(request_id: str) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)


def log_event(event: str, *, level: int = logging.INFO, **fields: object) -> None:
    logger.log(level, event, extra={"safe_fields": fields})
    if level >= logging.ERROR and _error_monitor is not None:
        _error_monitor.capture(event, fields)
