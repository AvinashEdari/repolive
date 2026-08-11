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
