import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.store import (
    AnalysisStore,
    analyses,
    anonymous_usage,
    api_keys,
    authenticated_usage,
    github_installations,
    operational_metrics,
    organization_members,
    organizations,
    subscriptions,
    webhook_events,
)
from app.entitlements import Entitlements, entitlements_for


class SaasService:
    def __init__(self, store: AnalysisStore, pepper: str = "development-only") -> None:
        self.store = store
        self.pepper = pepper

    def plan_for(self, user_id: str) -> Entitlements:
        with self.store.engine.connect() as connection:
            plan = connection.execute(
                select(subscriptions.c.plan).where(
                    subscriptions.c.user_id == user_id,
                    subscriptions.c.status.in_(["active", "trialing"]),
                )
            ).scalar_one_or_none()
        return entitlements_for(plan)

    def create_api_key(self, user_id: str, name: str) -> tuple[str, dict[str, object]]:
        key_id = secrets.token_urlsafe(9)
        secret = secrets.token_urlsafe(32)
        plaintext = f"rl_live_{key_id}_{secret}"
        now = datetime.now(UTC)
        with self.store.engine.begin() as connection:
            connection.execute(
                api_keys.insert().values(
                    key_id=key_id,
                    user_id=user_id,
                    name=name,
                    key_hash=self._hash(plaintext),
                    prefix=plaintext[:16],
                    request_count=0,
                    active=True,
                    created_at=now,
                    quota_reset_at=now + timedelta(days=30),
                )
            )
        return plaintext, {
            "key_id": key_id,
            "name": name,
            "prefix": plaintext[:16],
            "created_at": now,
        }

    def authenticate_api_key(self, plaintext: str) -> str | None:
        if not plaintext.startswith("rl_live_") or len(plaintext) > 160:
            return None
        key_hash = self._hash(plaintext)
        now = datetime.now(UTC)
        with self.store.engine.begin() as connection:
            row = (
                connection.execute(
                    select(api_keys).where(
                        api_keys.c.key_hash == key_hash, api_keys.c.active.is_(True)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            request_count = int(row["request_count"])
            reset_at = row["quota_reset_at"]
            if isinstance(reset_at, datetime) and reset_at.tzinfo is None:
                reset_at = reset_at.replace(tzinfo=UTC)
            if isinstance(reset_at, datetime) and reset_at <= now:
                request_count = 0
                connection.execute(
                    api_keys.update()
                    .where(api_keys.c.key_id == row["key_id"])
                    .values(request_count=0, quota_reset_at=now + timedelta(days=30))
                )
            plan = connection.execute(
                select(subscriptions.c.plan).where(
                    subscriptions.c.user_id == str(row["user_id"]),
                    subscriptions.c.status.in_(["active", "trialing"]),
                )
            ).scalar_one_or_none()
            allowance = entitlements_for(plan).api_requests
            if request_count >= allowance:
                return None
            result = connection.execute(
                api_keys.update()
                .where(
                    api_keys.c.key_id == row["key_id"],
                    api_keys.c.active.is_(True),
                    api_keys.c.request_count < allowance,
                )
                .values(request_count=api_keys.c.request_count + 1, last_used_at=now)
            )
            return str(row["user_id"]) if result.rowcount else None

    def list_api_keys(self, user_id: str) -> list[dict[str, object]]:
        with self.store.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(
                        api_keys.c.key_id,
                        api_keys.c.name,
                        api_keys.c.prefix,
                        api_keys.c.request_count,
                        api_keys.c.active,
                        api_keys.c.created_at,
                        api_keys.c.last_used_at,
                    )
                    .where(api_keys.c.user_id == user_id)
                    .order_by(api_keys.c.created_at.desc())
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        with self.store.engine.begin() as connection:
            result = connection.execute(
                api_keys.update()
                .where(api_keys.c.user_id == user_id, api_keys.c.key_id == key_id)
                .values(active=False)
            )
        return bool(result.rowcount)

    def create_organization(self, user_id: str, name: str) -> dict[str, object]:
        organization_id = secrets.token_urlsafe(9)
        now = datetime.now(UTC)
        with self.store.engine.begin() as connection:
            connection.execute(
                organizations.insert().values(
                    organization_id=organization_id,
                    name=name,
                    owner_user_id=user_id,
                    plan="free",
                    created_at=now,
                )
            )
            connection.execute(
                organization_members.insert().values(
                    organization_id=organization_id, user_id=user_id, role="owner", joined_at=now
                )
            )
        return {"organization_id": organization_id, "name": name, "role": "owner", "plan": "free"}

    def admin_summary(self) -> dict[str, int]:
        with self.store.engine.connect() as connection:
            return {
                "analyses": connection.scalar(select(func.count()).select_from(analyses)) or 0,
                "anonymous_identities": connection.scalar(
                    select(func.count()).select_from(anonymous_usage)
                )
                or 0,
                "authenticated_identities": connection.scalar(
                    select(func.count()).select_from(authenticated_usage)
                )
                or 0,
                "active_subscriptions": connection.scalar(
                    select(func.count())
                    .select_from(subscriptions)
                    .where(subscriptions.c.status.in_(["active", "trialing"]))
                )
                or 0,
                "active_api_keys": connection.scalar(
                    select(func.count()).select_from(api_keys).where(api_keys.c.active.is_(True))
                )
                or 0,
                "organizations": connection.scalar(select(func.count()).select_from(organizations))
                or 0,
                "github_installations": connection.scalar(
                    select(func.count())
                    .select_from(github_installations)
                    .where(github_installations.c.active.is_(True))
                )
                or 0,
                **{
                    str(metric): int(value)
                    for metric, value in connection.execute(
                        select(operational_metrics.c.metric, operational_metrics.c.value)
                    ).all()
                },
            }

    def register_github_installation(
        self, user_id: str, installation_id: str, login: str, account_type: str
    ) -> None:
        now = datetime.now(UTC)
        values = {
            "installation_id": installation_id,
            "owner_user_id": user_id,
            "account_login": login,
            "account_type": account_type,
            "active": True,
            "created_at": now,
        }
        with self.store.engine.begin() as connection:
            existing = connection.execute(
                select(github_installations.c.owner_user_id).where(
                    github_installations.c.installation_id == installation_id
                )
            ).scalar_one_or_none()
            if existing and existing != user_id:
                raise PermissionError("Installation is already linked to another user.")
            if existing:
                connection.execute(
                    github_installations.update()
                    .where(github_installations.c.installation_id == installation_id)
                    .values(active=True, account_login=login, account_type=account_type)
                )
            else:
                connection.execute(github_installations.insert().values(**values))

    def process_subscription_event(
        self,
        event_id: str,
        event_type: str,
        user_id: str,
        customer_id: str | None,
        subscription_id: str | None,
        status: str,
        event_created_at: datetime,
        current_period_end: datetime | None = None,
    ) -> bool:
        now = datetime.now(UTC)
        try:
            with self.store.engine.begin() as connection:
                connection.execute(
                    webhook_events.insert().values(
                        event_id=event_id, event_type=event_type, processed_at=now
                    )
                )
                existing = (
                    connection.execute(
                        select(subscriptions).where(subscriptions.c.user_id == user_id)
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing:
                    previous_created = existing["provider_event_created_at"]
                    if isinstance(previous_created, datetime) and previous_created.tzinfo is None:
                        previous_created = previous_created.replace(tzinfo=UTC)
                    if (
                        isinstance(previous_created, datetime)
                        and event_created_at < previous_created
                    ):
                        return True
                values = {
                    "plan": "pro" if status in {"active", "trialing"} else "free",
                    "status": status,
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "current_period_end": current_period_end,
                    "provider_event_created_at": event_created_at,
                    "updated_at": now,
                }
                if existing:
                    connection.execute(
                        subscriptions.update()
                        .where(subscriptions.c.user_id == user_id)
                        .values(**values)
                    )
                else:
                    connection.execute(subscriptions.insert().values(user_id=user_id, **values))
            return True
        except IntegrityError:
            return False

    def _hash(self, value: str) -> str:
        return hmac.new(self.pepper.encode(), value.encode(), hashlib.sha256).hexdigest()
