import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_local_insecure_defaults() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(app_env="production")


def test_production_accepts_explicit_https_postgres_configuration() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+psycopg://user:password@db.example/repolive",
        web_origin="https://repolive.example",
        allowed_hosts="api.repolive.example",
        supabase_url="https://project.supabase.co",
        api_key_pepper="x" * 32,
    )
    assert settings.app_env == "production"


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///production.db",
        "mysql+pymysql://user:password@db.example/repolive",
        "postgresql+asyncpg://user:password@db.example/repolive",
    ],
)
def test_production_accepts_only_supported_postgresql_driver(database_url: str) -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            app_env="production",
            database_url=database_url,
            web_origin="https://repolive.example",
            allowed_hosts="api.repolive.example",
            supabase_url="https://project.supabase.co",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("web_origin", "https://user:secret@repolive.example", "WEB_ORIGIN"),
        ("web_origin", "https://repolive.example/path", "WEB_ORIGIN"),
        ("supabase_url", "https://project.supabase.co/auth/v1", "SUPABASE_URL"),
        ("supabase_url", "https://project.supabase.co?token=secret", "SUPABASE_URL"),
    ],
)
def test_production_rejects_non_origin_urls(field: str, value: str, message: str) -> None:
    options = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://user:password@db.example/repolive",
        "web_origin": "https://repolive.example",
        "allowed_hosts": "api.repolive.example",
        "supabase_url": "https://project.supabase.co",
        "api_key_pepper": "x" * 32,
        field: value,
    }
    with pytest.raises(ValidationError, match=message):
        Settings(**options)


@pytest.mark.parametrize(
    "allowed_hosts",
    ["", "*", "*.example.com", "https://api.example.com", "api.example.com/path", "a.com,,b.com"],
)
def test_production_requires_exact_nonempty_trusted_hosts(allowed_hosts: str) -> None:
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:password@db.example/repolive",
            web_origin="https://repolive.example",
            allowed_hosts=allowed_hosts,
            supabase_url="https://project.supabase.co",
            api_key_pepper="x" * 32,
        )


def test_production_requires_api_key_pepper_even_when_api_keys_are_unused() -> None:
    with pytest.raises(ValidationError, match="API_KEY_PEPPER"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:password@db.example/repolive",
            web_origin="https://repolive.example",
            allowed_hosts="api.repolive.example",
            supabase_url="https://project.supabase.co",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("analytics_endpoint", "https://analytics.example/capture", "Analytics"),
        ("stripe_pro_price_id", "price_test", "Stripe"),
        ("github_app_private_key", "private-key", "GitHub App"),
    ],
)
def test_production_rejects_partial_optional_integrations(
    field: str, value: str, message: str
) -> None:
    options = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://user:password@db.example/repolive",
        "web_origin": "https://repolive.example",
        "allowed_hosts": "api.repolive.example",
        "supabase_url": "https://project.supabase.co",
        "api_key_pepper": "x" * 32,
        field: value,
    }
    with pytest.raises(ValidationError, match=message):
        Settings(**options)


def test_production_billing_portal_must_return_to_web_origin() -> None:
    with pytest.raises(ValidationError, match="WEB_ORIGIN"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:password@db.example/repolive",
            web_origin="https://repolive.example",
            allowed_hosts="api.repolive.example",
            supabase_url="https://project.supabase.co",
            api_key_pepper="x" * 32,
            stripe_secret_key="sk_test",
            stripe_webhook_secret="whsec_test",
            stripe_pro_price_id="price_test",
            stripe_portal_return_url="https://evil.example/account",
        )
