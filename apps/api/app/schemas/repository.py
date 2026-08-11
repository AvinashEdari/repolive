from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RepositoryReference(BaseModel):
    provider: str = "github"
    owner: str = Field(min_length=1, max_length=39)
    name: str = Field(min_length=1, max_length=100)
    canonical_url: str


class AnalysisRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=500)


class RepositoryMetadata(BaseModel):
    description: str | None
    default_branch: str
    stars: int = Field(ge=0)
    forks: int = Field(ge=0)
    open_issues: int = Field(ge=0)
    size_kib: int = Field(ge=0)
    archived: bool
    license_spdx: str | None
    primary_language: str | None
    last_pushed_at: datetime | None


class RepositoryFile(BaseModel):
    path: str
    size_bytes: int | None = Field(default=None, ge=0)
    content_id: str | None = Field(default=None, exclude=True)
    text_content: str | None = Field(default=None, exclude=True)


class RepositorySnapshot(BaseModel):
    repository: RepositoryReference
    metadata: RepositoryMetadata
    files: list[RepositoryFile]
    status: Literal["ingested"] = "ingested"
