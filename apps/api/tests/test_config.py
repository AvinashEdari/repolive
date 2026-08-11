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
        field: value,
    }
    with pytest.raises(ValidationError, match=message):
        Settings(**options)
