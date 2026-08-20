from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

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
    free_authenticated_analysis_limit: int = Field(default=50, ge=1, le=10_000)
    max_request_body_bytes: int = Field(default=24_576, ge=512, le=1024 * 1024)
    max_repository_files: int = Field(default=10_000, ge=1)
    max_repository_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    max_repository_path_bytes: int = Field(default=1024, ge=64, le=4096)
    max_evidence_files: int = Field(default=40, ge=1, le=200)
    max_evidence_file_bytes: int = Field(default=256 * 1024, ge=1)
    max_evidence_total_bytes: int = Field(default=2 * 1024 * 1024, ge=1)
    analytics_endpoint: str | None = None
    analytics_write_key: str | None = None
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_pro_price_id: str | None = None
    stripe_portal_return_url: str | None = None
    admin_user_ids: str = ""
    api_key_pepper: str | None = None
    github_app_id: str | None = None
    github_app_private_key: str | None = None
    preview_execution_enabled: bool = False
    preview_runtime_provider: Literal["disabled", "local_docker"] = "disabled"
    preview_queue_provider: Literal["disabled", "database"] = "disabled"
    preview_router_base_url: str | None = None
    preview_worker_id: str = "local-worker"
    preview_max_concurrent_per_user: int = Field(default=1, ge=1, le=10)
    preview_period_limit: int = Field(default=5, ge=1, le=1000)
    preview_build_timeout_seconds: int = Field(default=60, ge=10, le=900)
    preview_runtime_seconds: int = Field(default=600, ge=30, le=3600)
    preview_memory_mb: int = Field(default=128, ge=64, le=2048)
    preview_cpu_count: float = Field(default=0.5, gt=0, le=4)
    preview_pids_limit: int = Field(default=64, ge=16, le=512)
    preview_log_bytes: int = Field(default=65536, ge=4096, le=1048576)

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.preview_execution_enabled:
            if (
                self.preview_runtime_provider == "disabled"
                or self.preview_queue_provider == "disabled"
            ):
                raise ValueError("Preview execution requires runtime and queue providers.")
            if not self.preview_router_base_url:
                raise ValueError("Preview execution requires PREVIEW_ROUTER_BASE_URL.")
            if self.app_env == "production" and self.preview_runtime_provider == "local_docker":
                raise ValueError("The local Docker preview runtime is forbidden in production.")
        if self.app_env != "production":
            return self
        hosts = [host.strip() for host in self.allowed_hosts.split(",")]
        database_scheme = urlsplit(self.database_url).scheme
        if database_scheme not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError("Production requires a PostgreSQL DATABASE_URL.")
        web_origin = urlsplit(self.web_origin)
        if (
            web_origin.scheme != "https"
            or not web_origin.hostname
            or web_origin.username
            or web_origin.password
            or web_origin.path not in {"", "/"}
            or web_origin.query
            or web_origin.fragment
        ):
            raise ValueError("Production WEB_ORIGIN must use HTTPS.")
        if (
            not hosts
            or any(not host for host in hosts)
            or any("*" in host or "://" in host or "/" in host or ":" in host for host in hosts)
            or "localhost" in hosts
            or "127.0.0.1" in hosts
        ):
            raise ValueError("Production ALLOWED_HOSTS must name deployed hosts explicitly.")
        supabase_url = urlsplit(self.supabase_url or "")
        if (
            supabase_url.scheme != "https"
            or not supabase_url.hostname
            or supabase_url.username
            or supabase_url.password
            or supabase_url.path not in {"", "/"}
            or supabase_url.query
            or supabase_url.fragment
        ):
            raise ValueError("Production requires an HTTPS SUPABASE_URL.")
        analytics_values = [self.analytics_endpoint, self.analytics_write_key]
        if any(analytics_values) and not all(analytics_values):
            raise ValueError("Analytics production configuration must be complete.")
        if self.analytics_endpoint and urlsplit(self.analytics_endpoint).scheme != "https":
            raise ValueError("Production ANALYTICS_ENDPOINT must use HTTPS.")
        stripe_values = [
            self.stripe_secret_key,
            self.stripe_webhook_secret,
            self.stripe_pro_price_id,
        ]
        if any(stripe_values) and not all(stripe_values):
            raise ValueError("Stripe production configuration must be complete.")
        if self.stripe_portal_return_url:
            portal_origin = urlsplit(self.stripe_portal_return_url)
            if (portal_origin.scheme, portal_origin.netloc) != (
                web_origin.scheme,
                web_origin.netloc,
            ):
                raise ValueError("STRIPE_PORTAL_RETURN_URL must use WEB_ORIGIN.")
        github_app_values = [self.github_app_id, self.github_app_private_key]
        if any(github_app_values) and not all(github_app_values):
            raise ValueError("GitHub App production configuration must be complete.")
        if not self.api_key_pepper or len(self.api_key_pepper) < 32:
            raise ValueError("Production API_KEY_PEPPER must contain at least 32 characters.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
