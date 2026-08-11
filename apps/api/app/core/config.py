from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    web_origin: str = "http://localhost:3000"
    github_token: str | None = None
    free_anonymous_analysis_limit: int = Field(default=5, ge=1, le=100)
    max_repository_files: int = Field(default=10_000, ge=1)
    max_repository_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    max_evidence_files: int = Field(default=40, ge=1, le=200)
    max_evidence_file_bytes: int = Field(default=256 * 1024, ge=1)
    max_evidence_total_bytes: int = Field(default=2 * 1024 * 1024, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
