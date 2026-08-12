import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.routes.saas import service
from app.auth import AuthUser, require_user
from app.billing import StripeBilling
from app.core.config import Settings
from app.db.store import AnalysisStore, api_keys, get_analysis_store, subscriptions
from app.entitlements import entitlements_for
from app.main import app
from app.saas import SaasService


def test_entitlements_are_centralized_and_fail_closed_to_free() -> None:
    assert entitlements_for(None).plan == "free"
    assert entitlements_for("unexpected").private_repositories is False
    assert entitlements_for("pro").api_requests > entitlements_for("free").api_requests


def test_api_keys_are_returned_once_hashed_and_revocable() -> None:
    service = SaasService(AnalysisStore("sqlite:///:memory:"), "pepper")
    plaintext, created = service.create_api_key("user-a", "Automation")
    assert plaintext.startswith("rl_live_")
    assert plaintext not in str(service.list_api_keys("user-a"))
    assert service.authenticate_api_key(plaintext) == "user-a"
    assert service.revoke_api_key("user-a", str(created["key_id"])) is True
    assert service.authenticate_api_key(plaintext) is None


def test_api_key_quota_increment_is_conditionally_enforced() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    service = SaasService(store, "pepper")
    plaintext, created = service.create_api_key("user-a", "Automation")
    with store.engine.begin() as connection:
        connection.execute(
            api_keys.update().where(api_keys.c.key_id == created["key_id"]).values(request_count=99)
        )
    assert service.authenticate_api_key(plaintext) == "user-a"
    assert service.authenticate_api_key(plaintext) is None


def test_admin_summary_and_organization_owner_membership() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    service = SaasService(store, "pepper")
    organization = service.create_organization("user-a", "Example team")
    store.increment_metric("provider_failed")
    assert organization["role"] == "owner"
    assert service.admin_summary()["organizations"] == 1
    assert service.admin_summary()["provider_failed"] == 1


def test_subscription_events_are_idempotent_and_update_entitlements() -> None:
    service = SaasService(AnalysisStore("sqlite:///:memory:"), "pepper")
    assert (
        service.process_subscription_event(
            "evt_1",
            "customer.subscription.updated",
            "user-a",
            "cus_1",
            "sub_1",
            "active",
            datetime.now(UTC),
        )
        is True
    )
    assert (
        service.process_subscription_event(
            "evt_1",
            "customer.subscription.updated",
            "user-a",
            "cus_1",
            "sub_1",
            "active",
            datetime.now(UTC),
        )
        is False
    )
    assert service.plan_for("user-a").plan == "pro"
    assert (
        service.process_subscription_event(
            "evt_2",
            "customer.subscription.deleted",
            "user-a",
            "cus_1",
            "sub_1",
            "canceled",
            datetime.now(UTC) + timedelta(seconds=1),
        )
        is True
    )
    assert service.plan_for("user-a").plan == "free"


def test_older_subscription_event_cannot_overwrite_newer_state() -> None:
    service = SaasService(AnalysisStore("sqlite:///:memory:"), "pepper")
    newest = datetime.now(UTC)
    assert service.process_subscription_event(
        "evt_new", "customer.subscription.updated", "user-a", "cus_1", "sub_1", "active", newest
    )
    assert service.process_subscription_event(
        "evt_old",
        "customer.subscription.deleted",
        "user-a",
        "cus_1",
        "sub_1",
        "canceled",
        newest - timedelta(minutes=1),
    )
    assert service.plan_for("user-a").plan == "pro"


def test_stripe_webhook_signature_is_verified() -> None:
    settings = Settings(stripe_webhook_secret="whsec_test")
    billing = StripeBilling(settings)
    body = json.dumps({"id": "evt_1", "type": "test", "data": {"object": {}}}).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        b"whsec_test", timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    assert billing.verify_webhook(body, f"t={timestamp},v1={signature}")["id"] == "evt_1"
    with pytest.raises(HTTPException, match="Invalid webhook signature"):
        billing.verify_webhook(body, f"t={timestamp},v1=wrong")


def test_billing_return_urls_cannot_leave_configured_origin() -> None:
    billing = StripeBilling(Settings(web_origin="https://repolive.example"))
    with pytest.raises(HTTPException, match="configured web origin"):
        billing._validate_return_url("https://evil.example/success")


def test_admin_endpoint_is_server_authorized() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    app.dependency_overrides[require_user] = lambda: AuthUser("not-admin")
    app.dependency_overrides[service] = lambda: SaasService(store, "pepper")
    try:
        response = TestClient(app).get("/api/v1/admin/summary")
    finally:
        app.dependency_overrides.pop(require_user)
        app.dependency_overrides.pop(service)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_saas_identifiers_and_names_are_normalized_and_bounded() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    app.dependency_overrides[require_user] = lambda: AuthUser("user-a")
    app.dependency_overrides[get_analysis_store] = lambda: store
    app.dependency_overrides[service] = lambda: SaasService(store, "pepper")
    try:
        client = TestClient(app)
        blank_key = client.post("/api/v1/me/api-keys", json={"name": "   "})
        blank_org = client.post("/api/v1/organizations", json={"name": "   "})
        malformed_revoke = client.delete("/api/v1/me/api-keys/not-valid!")
        malformed_report = client.get(
            "/api/v1/external/reports/not-valid!", headers={"X-API-Key": "rl_live_invalid"}
        )
    finally:
        app.dependency_overrides.pop(require_user)
        app.dependency_overrides.pop(get_analysis_store)
        app.dependency_overrides.pop(service)
    assert blank_key.status_code == 422
    assert blank_org.status_code == 422
    assert malformed_revoke.status_code == 404
    assert malformed_report.status_code == 404


def test_billing_is_unavailable_without_credentials() -> None:
    app.dependency_overrides[require_user] = lambda: AuthUser("user-a", "person@example.com")
    try:
        response = TestClient(app).post(
            "/api/v1/billing/checkout",
            headers={"Idempotency-Key": "checkout-test-1"},
            json={
                "success_url": "http://localhost:3000/account?success=1",
                "cancel_url": "http://localhost:3000/account?cancel=1",
            },
        )
    finally:
        app.dependency_overrides.pop(require_user)
    assert response.status_code == 503
    assert response.json() == {"detail": "Billing is not configured."}


def test_billing_status_is_honest_without_credentials() -> None:
    response = TestClient(app).get("/api/v1/billing/status")
    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "checkout_mode": "hosted",
        "card_data_handled_by": "stripe",
    }


def test_checkout_rejects_duplicate_billable_subscription() -> None:
    store = AnalysisStore("sqlite:///:memory:")
    now = datetime.now(UTC)
    with store.engine.begin() as connection:
        connection.execute(
            subscriptions.insert().values(
                user_id="user-a",
                plan="pro",
                status="past_due",
                stripe_customer_id="cus_1",
                stripe_subscription_id="sub_1",
                provider_event_created_at=now,
                updated_at=now,
            )
        )
    app.dependency_overrides[require_user] = lambda: AuthUser("user-a", "person@example.com")
    app.dependency_overrides[get_analysis_store] = lambda: store
    try:
        response = TestClient(app).post(
            "/api/v1/billing/checkout",
            headers={"Idempotency-Key": "checkout-test-2"},
            json={
                "success_url": "http://localhost:3000/account?success=1",
                "cancel_url": "http://localhost:3000/account?cancel=1",
            },
        )
    finally:
        app.dependency_overrides.pop(require_user)
        app.dependency_overrides.pop(get_analysis_store)
    assert response.status_code == 409
    assert "already has a subscription" in response.json()["detail"]
