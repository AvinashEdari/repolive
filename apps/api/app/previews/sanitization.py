import re

_ANSI = re.compile(r"\x1b(?:[@-_]|\[[0-?]*[ -/]*[@-~])")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SECRET = re.compile(
    r"(?i)(authorization|cookie|token|secret|password|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)"
)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^/@\s]+@")


def sanitize_log(value: str, limit: int) -> str:
    safe = _ANSI.sub("", value)
    safe = _CONTROL.sub("", safe)
    safe = _SECRET.sub(r"\1\2[REDACTED]", safe)
    safe = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", safe)
    if len(safe.encode("utf-8")) > limit:
        safe = safe.encode("utf-8")[:limit].decode("utf-8", errors="ignore") + "\n[TRUNCATED]"
    return safe
