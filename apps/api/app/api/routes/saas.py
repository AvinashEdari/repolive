from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import select

from app.auth import AuthUser, require_user
from app.billing import StripeBilling
from app.core.config import get_settings
from app.db.store import AnalysisStore, get_analysis_store, subscriptions
from app.entitlements import Entitlements
from app.github_app import GitHubAppClient
from app.saas import SaasService
from app.schemas.saas import (
    ApiKeyCreate,
    ApiKeyCreated,
    CheckoutRequest,
    OrganizationCreate,
    OrganizationResult,
)

router = APIRouter(tags=["saas"])


def service(store: Annotated[AnalysisStore, Depends(get_analysis_store)]) -> SaasService:
    return SaasService(store, get_settings().api_key_pepper or "development-only")


@router.get("/me/entitlements")
def my_entitlements(
    user: Annotated[AuthUser, Depends(require_user)], saas: Annotated[SaasService, Depends(service)]
) -> Entitlements:
    return saas.plan_for(user.user_id)


@router.post("/me/api-keys", response_model=ApiKeyCreated)
def create_api_key(
    payload: ApiKeyCreate,
    user: Annotated[AuthUser, Depends(require_user)],
    saas: Annotated[SaasService, Depends(service)],
) -> ApiKeyCreated:
    plaintext, metadata = saas.create_api_key(user.user_id, payload.name)
    return ApiKeyCreated.model_validate({"api_key": plaintext, **metadata})


@router.get("/me/api-keys")
def list_api_keys(
    user: Annotated[AuthUser, Depends(require_user)], saas: Annotated[SaasService, Depends(service)]
) -> list[dict[str, object]]:
    return saas.list_api_keys(user.user_id)


@router.delete("/me/api-keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
    saas: Annotated[SaasService, Depends(service)],
) -> Response:
    if not saas.revoke_api_key(user.user_id, key_id):
        raise HTTPException(status_code=404, detail="API key not found.")
    return Response(status_code=204)


@router.get("/external/reports/{public_id}")
def external_report(
    public_id: str,
    x_api_key: Annotated[str, Header()],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
    saas: Annotated[SaasService, Depends(service)],
) -> dict[str, object]:
    if not saas.authenticate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or exhausted API key.")
    report = store.get(public_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {
        "public_id": report.public_id,
        "analysis_version": report.analysis_version,
        "repository": report.snapshot.repository,
        "metadata": report.snapshot.metadata,
        "analysis": report.analysis,
        "status": report.status,
        "cache_status": report.cache_status,
    }


@router.post("/organizations", response_model=OrganizationResult)
def create_organization(
    payload: OrganizationCreate,
    user: Annotated[AuthUser, Depends(require_user)],
    saas: Annotated[SaasService, Depends(service)],
) -> OrganizationResult:
    return OrganizationResult.model_validate(saas.create_organization(user.user_id, payload.name))


@router.get("/admin/summary")
def admin_summary(
    user: Annotated[AuthUser, Depends(require_user)], saas: Annotated[SaasService, Depends(service)]
) -> dict[str, int]:
    admins = {item.strip() for item in get_settings().admin_user_ids.split(",") if item.strip()}
    if user.user_id not in admins:
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return saas.admin_summary()


@router.post("/billing/checkout")
async def billing_checkout(
    payload: CheckoutRequest,
    user: Annotated[AuthUser, Depends(require_user)],
    idempotency_key: Annotated[str, Header(alias="idempotency-key", min_length=8, max_length=64)],
) -> dict[str, str]:
    url = await StripeBilling(get_settings()).checkout(
        user.user_id,
        user.email,
        payload.success_url,
        payload.cancel_url,
        idempotency_key,
    )
    return {"url": url}


@router.post("/billing/portal")
async def billing_portal(
    user: Annotated[AuthUser, Depends(require_user)],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> dict[str, str]:
    with store.engine.connect() as connection:
        customer_id = connection.execute(
            select(subscriptions.c.stripe_customer_id).where(
                subscriptions.c.user_id == user.user_id
            )
        ).scalar_one_or_none()
    if not customer_id:
        raise HTTPException(status_code=404, detail="No billing customer exists for this account.")
    return {"url": await StripeBilling(get_settings()).portal(customer_id)}


@router.post("/billing/webhook")
async def billing_webhook(
    request: Request,
    stripe_signature: Annotated[str, Header(alias="stripe-signature")],
    saas: Annotated[SaasService, Depends(service)],
) -> dict[str, bool]:
    event = StripeBilling(get_settings()).verify_webhook(await request.body(), stripe_signature)
    event_id, event_type, event_created = event.get("id"), event.get("type"), event.get("created")
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if (
        not isinstance(event_id, str)
        or not isinstance(event_type, str)
        or not isinstance(event_created, int)
        or not isinstance(obj, dict)
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook event.")
    metadata = obj.get("metadata", {})
    user_id = metadata.get("user_id") if isinstance(metadata, dict) else None
    if not isinstance(user_id, str):
        return {"processed": False}
    if not event_type.startswith("customer.subscription."):
        return {"processed": False}
    event_status = obj.get("status")
    status_value = event_status if isinstance(event_status, str) else "inactive"
    period_end = obj.get("current_period_end")
    processed = saas.process_subscription_event(
        event_id,
        event_type,
        user_id,
        obj.get("customer") if isinstance(obj.get("customer"), str) else None,
        obj.get("id") if isinstance(obj.get("id"), str) else None,
        status_value,
        datetime.fromtimestamp(event_created, UTC),
        datetime.fromtimestamp(period_end, UTC) if isinstance(period_end, int) else None,
    )
    return {"processed": processed}


@router.get("/github-app/status")
def github_app_status(user: Annotated[AuthUser, Depends(require_user)]) -> dict[str, object]:
    del user
    configured = GitHubAppClient(get_settings()).configured
    return {
        "configured": configured,
        "private_analysis_enabled": False,
        "status": "architecture_ready" if configured else "configuration_required",
        "safety": "Installation tokens are short-lived and repository code is never executed.",
    }


@router.post("/github-app/installations/{installation_id}")
async def link_github_installation(
    installation_id: str,
    github_user_token: Annotated[str, Header(alias="x-github-user-token")],
    user: Annotated[AuthUser, Depends(require_user)],
    saas: Annotated[SaasService, Depends(service)],
) -> dict[str, str]:
    if not installation_id.isdigit() or len(installation_id) > 20:
        raise HTTPException(status_code=422, detail="Invalid installation ID.")
    client = GitHubAppClient(get_settings())
    if not client.configured:
        raise HTTPException(status_code=503, detail="GitHub App is not configured.")
    try:
        account = await client.verify_user_installation(installation_id, github_user_token)
        saas.register_github_installation(
            user.user_id, installation_id, account["login"], account["account_type"]
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(
            status_code=403, detail="GitHub installation authorization failed."
        ) from exc
    return {"installation_id": installation_id, "account_login": account["login"]}
