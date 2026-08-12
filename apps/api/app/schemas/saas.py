from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("API key name cannot be blank.")
        return normalized


class ApiKeyCreated(BaseModel):
    api_key: str
    key_id: str
    name: str
    prefix: str
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Organization name must contain at least two characters.")
        return normalized


class OrganizationResult(BaseModel):
    organization_id: str
    name: str
    role: Literal["owner", "admin", "member"]
    plan: Literal["free", "pro"]


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str
