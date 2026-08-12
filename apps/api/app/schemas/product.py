from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ErrorDiagnosisRequest(BaseModel):
    error_text: str = Field(min_length=1, max_length=20_000)


class ErrorDiagnosis(BaseModel):
    category: Literal[
        "missing_dependency",
        "missing_executable",
        "incompatible_runtime",
        "missing_environment_variable",
        "package_manager_issue",
        "permission_issue",
        "port_conflict",
        "database_connection_failure",
        "missing_system_library",
        "network_download_problem",
        "unknown",
    ]
    label: str
    confidence: Literal["high", "medium", "low"]
    evidence: list[str]
    safe_next_checks: list[str]
    unknowns: list[str]
    disclaimer: str = "Deterministic diagnosis is a starting point, not a confirmed root cause."


class ComparisonRequest(BaseModel):
    left_public_id: str = Field(min_length=8, max_length=32)
    right_public_id: str = Field(min_length=8, max_length=32)

    @model_validator(mode="after")
    def different_reports(self) -> "ComparisonRequest":
        if self.left_public_id == self.right_public_id:
            raise ValueError("Choose two different analyses.")
        return self


class ComparisonDimension(BaseModel):
    name: str
    left: str
    right: str
    explanation: str


class RepositoryComparison(BaseModel):
    left_public_id: str
    right_public_id: str
    left_repository: str
    right_repository: str
    dimensions: list[ComparisonDimension]
    shared_dependencies: list[str]
    left_only_dependencies: list[str]
    right_only_dependencies: list[str]
    summary: list[str]
    unknowns: list[str]


class DiscoveryItem(BaseModel):
    full_name: str
    url: str
    description: str | None
    primary_language: str | None
    topics: list[str]
    stars: int = Field(ge=0)
    updated_at: datetime | None
    license_spdx: str | None
    score: int = Field(ge=0, le=100)
    ranking_reasons: list[str]


class DiscoveryResponse(BaseModel):
    query: str
    items: list[DiscoveryItem]
    cost: str = "One bounded GitHub repository-search request; no repository code was fetched."
