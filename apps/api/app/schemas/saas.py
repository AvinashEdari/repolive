from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ApiKeyCreated(BaseModel):
    api_key: str
    key_id: str
    name: str
    prefix: str
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class OrganizationResult(BaseModel):
    organization_id: str
    name: str
    role: Literal["owner", "admin", "member"]
    plan: Literal["free", "pro"]


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str
