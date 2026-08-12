import hashlib
import hmac
import json
import time
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from app.core.config import Settings


class StripeBilling:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.stripe_secret_key
            and self.settings.stripe_webhook_secret
            and self.settings.stripe_pro_price_id
        )

    async def checkout(
        self,
        user_id: str,
        email: str | None,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
        customer_id: str | None = None,
    ) -> str:
        self._validate_return_url(success_url)
        self._validate_return_url(cancel_url)
        if not self.configured:
            raise HTTPException(status_code=503, detail="Billing is not configured.")
        form = {
            "mode": "subscription",
            "line_items[0][price]": self.settings.stripe_pro_price_id or "",
            "line_items[0][quantity]": "1",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": user_id,
            "subscription_data[metadata][user_id]": user_id,
        }
        if customer_id:
            form["customer"] = customer_id
        elif email:
            form["customer_email"] = email
        payload = await self._post("/v1/checkout/sessions", form, idempotency_key)
        url = payload.get("url")
        if not isinstance(url, str) or not url.startswith("https://checkout.stripe.com/"):
            raise HTTPException(
                status_code=502, detail="Billing provider returned an invalid checkout URL."
            )
        return url

    async def portal(self, customer_id: str) -> str:
        if not self.configured:
            raise HTTPException(status_code=503, detail="Billing is not configured.")
        payload = await self._post(
            "/v1/billing_portal/sessions",
            {
                "customer": customer_id,
                "return_url": self.settings.stripe_portal_return_url or self.settings.web_origin,
            },
        )
        url = payload.get("url")
        if not isinstance(url, str) or not url.startswith("https://billing.stripe.com/"):
            raise HTTPException(
                status_code=502, detail="Billing provider returned an invalid portal URL."
            )
        return url

    def verify_webhook(self, body: bytes, signature: str) -> dict[str, object]:
        if not self.settings.stripe_webhook_secret:
            raise HTTPException(status_code=503, detail="Billing is not configured.")
        parts = [item.split("=", 1) for item in signature.split(",") if "=" in item]
        timestamp = next((value for key, value in parts if key == "t"), "")
        supplied = [value for key, value in parts if key == "v1"]
        if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 300:
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")
        expected = hmac.new(
            self.settings.stripe_webhook_secret.encode(),
            timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in supplied):
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")
        try:
            event = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc
        if not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="Invalid webhook payload.")
        return event

    async def _post(
        self, path: str, data: dict[str, str], idempotency_key: str | None = None
    ) -> dict[str, object]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        async with httpx.AsyncClient(base_url="https://api.stripe.com", timeout=10) as client:
            response = await client.post(
                path,
                data=data,
                auth=(self.settings.stripe_secret_key or "", ""),
                headers=headers,
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Billing provider request failed.")
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _validate_return_url(self, value: str) -> None:
        expected = urlsplit(self.settings.web_origin)
        candidate = urlsplit(value)
        if (candidate.scheme, candidate.netloc) != (expected.scheme, expected.netloc):
            raise HTTPException(
                status_code=422, detail="Billing return URLs must use the configured web origin."
            )
