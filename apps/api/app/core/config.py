from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    web_origin: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    database_url: str = "sqlite:///./repolive.db"
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=60)
    database_pool_recycle_seconds: int = Field(default=300, ge=30, le=3600)
    database_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)
    analysis_version: str = "1"
    github_token: str | None = None
    supabase_url: str | None = None
    supabase_jwt_audience: str = "authenticated"
    auth_jwks_timeout_seconds: int = Field(default=5, ge=1, le=30)
    github_request_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    free_anonymous_analysis_limit: int = Field(default=5, ge=1, le=100)
    max_repository_files: int = Field(default=10_000, ge=1)
    max_repository_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    max_evidence_files: int = Field(default=40, ge=1, le=200)
    max_evidence_file_bytes: int = Field(default=256 * 1024, ge=1)
    max_evidence_total_bytes: int = Field(default=2 * 1024 * 1024, ge=1)

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.app_env != "production":
            return self
        hosts = {host.strip() for host in self.allowed_hosts.split(",")}
        if self.database_url.startswith("sqlite"):
            raise ValueError("Production requires a PostgreSQL DATABASE_URL.")
        if not self.web_origin.startswith("https://"):
            raise ValueError("Production WEB_ORIGIN must use HTTPS.")
        if "*" in hosts or "localhost" in hosts or "127.0.0.1" in hosts:
            raise ValueError("Production ALLOWED_HOSTS must name deployed hosts explicitly.")
        if not self.supabase_url or not self.supabase_url.startswith("https://"):
            raise ValueError("Production requires an HTTPS SUPABASE_URL.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
