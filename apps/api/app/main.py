import logging
import re
import secrets
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.api.routes.analyses import router as analyses_router
from app.api.routes.health import router as health_router
from app.api.routes.product import router as product_router
from app.core.config import get_settings
from app.observability import bind_request_id, log_event, reset_request_id

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

settings = get_settings()
app = FastAPI(
    title="RepoLive API",
    version="0.1.0",
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[host.strip() for host in settings.allowed_hosts.split(",") if host.strip()],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    supplied_request_id = request.headers.get("x-request-id", "")
    request_id = (
        supplied_request_id
        if _REQUEST_ID.fullmatch(supplied_request_id)
        else secrets.token_urlsafe(12)
    )
    token = bind_request_id(request_id)
    started = time.perf_counter()
    content_length = request.headers.get("content-length")
    if (
        content_length
        and content_length.isdigit()
        and int(content_length) > settings.max_request_body_bytes
    ):
        oversized_response = JSONResponse(
            status_code=413, content={"detail": "Request body is too large."}
        )
        oversized_response.headers["X-Request-ID"] = request_id
        log_event("request_rejected", status=413, method=request.method, reason="body_too_large")
        reset_request_id(token)
        return oversized_response
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > settings.max_request_body_bytes:
            oversized_response = JSONResponse(
                status_code=413, content={"detail": "Request body is too large."}
            )
            oversized_response.headers["X-Request-ID"] = request_id
            log_event(
                "request_rejected",
                status=413,
                method=request.method,
                reason="body_too_large",
            )
            reset_request_id(token)
            return oversized_response
    try:
        response = await call_next(request)
    except Exception:
        log_event(
            "request_failed",
            level=logging.ERROR,
            method=request.method,
            route=_safe_route(request),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        reset_request_id(token)
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.method != "GET" or request.url.path.endswith("/analyses"):
        response.headers["Cache-Control"] = "no-store"
    log_event(
        "request_completed",
        method=request.method,
        route=_safe_route(request),
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    reset_request_id(token)
    return response


def _safe_route(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return route_path if isinstance(route_path, str) else "unmatched"


app.include_router(health_router, prefix="/api/v1")
app.include_router(analyses_router, prefix="/api/v1")
app.include_router(product_router, prefix="/api/v1")
