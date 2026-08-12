import pytest

from app.analytics import ALLOWED_FIELDS, HttpAnalyticsProvider, capture_product_event
from app.core.config import Settings


def test_analytics_allowlist_excludes_repository_and_secret_fields() -> None:
    assert "repository_url" not in ALLOWED_FIELDS
    assert "error_text" not in ALLOWED_FIELDS
    assert "token" not in ALLOWED_FIELDS


@pytest.mark.asyncio
async def test_optional_analytics_is_noop_without_provider() -> None:
    await HttpAnalyticsProvider(Settings()).capture(
        "analysis_completed", {"status": "success", "repository_url": "secret"}
    )


def test_unknown_analytics_events_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported analytics event"):
        capture_product_event("repository_contents", repository_url="secret")
