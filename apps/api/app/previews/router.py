import re
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.config import get_settings
from app.db.store import get_analysis_store
from app.previews.store import PreviewStore

app = FastAPI(title="RepoLive local preview router", docs_url=None, redoc_url=None)
_ROUTING_KEY = re.compile(r"^[A-Za-z0-9_-]{24,64}$")
_RESPONSE_HEADERS = {"content-type", "content-language", "cache-control", "etag", "last-modified"}


def _routing_key(request: Request) -> str | None:
    configured = urlsplit(get_settings().preview_router_base_url or "")
    host = request.url.hostname or ""
    suffix = f".{configured.hostname}" if configured.hostname else ""
    if not suffix or not host.endswith(suffix):
        return None
    key = host[: -len(suffix)]
    return key if _ROUTING_KEY.fullmatch(key) else None


@app.api_route("/{path:path}", methods=["GET", "HEAD"])
def proxy(path: str, request: Request) -> Response:
    key = _routing_key(request)
    endpoint = PreviewStore(get_analysis_store()).route(key) if key else None
    if endpoint is None:
        return PlainTextResponse("Preview unavailable.", status_code=404)
    target = f"{endpoint}/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    try:
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            upstream = client.request(request.method, target)
    except httpx.HTTPError:
        return PlainTextResponse("Preview unavailable.", status_code=502)
    limit = get_settings().preview_response_max_bytes
    if len(upstream.content) > limit:
        return PlainTextResponse("Preview response is too large.", status_code=413)
    headers = {
        key: value for key, value in upstream.headers.items() if key.lower() in _RESPONSE_HEADERS
    }
    headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
        }
    )
    return Response(upstream.content, status_code=upstream.status_code, headers=headers)
