import asyncio
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.observability import log_event

ALLOWED_EVENTS = {
    "analysis_submitted",
    "analysis_completed",
    "analysis_failed",
    "cache_reused",
    "share_opened",
    "comparison_performed",
}
ALLOWED_FIELDS = {"authenticated", "cache_status", "category", "provider", "status"}


class AnalyticsProvider(Protocol):
    async def capture(self, event: str, fields: dict[str, object]) -> None: ...


class HttpAnalyticsProvider:
    def __init__(self, settings: Settings) -> None:
        self.endpoint = settings.analytics_endpoint
        self.write_key = settings.analytics_write_key

    async def capture(self, event: str, fields: dict[str, object]) -> None:
        if not self.endpoint or not self.write_key:
            return
        safe = {key: value for key, value in fields.items() if key in ALLOWED_FIELDS}
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.post(
                    self.endpoint,
                    json={"event": event, "properties": safe},
                    headers={"Authorization": f"Bearer {self.write_key}"},
                )
        except httpx.HTTPError:
            log_event("analytics_delivery_failed", provider="optional_http")


def capture_product_event(event: str, **fields: object) -> None:
    if event not in ALLOWED_EVENTS:
        raise ValueError("Unsupported analytics event.")
    provider = HttpAnalyticsProvider(get_settings())
    try:
        asyncio.get_running_loop().create_task(provider.capture(event, fields))
    except RuntimeError:
        asyncio.run(provider.capture(event, fields))
