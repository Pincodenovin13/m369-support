"""Auth schemas: register, login, refresh, token, user, membership, agency, workspace."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Self-service agency registration."""

    agency_name: str = Field(min_length=2, max_length=180)
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    agency_id: uuid.UUID | None = Field(
        default=None,
        description="Optional: specify which agency to log in to. Required if user belongs to multiple agencies.",
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    is_active: bool


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    role: str


class UserWithMembershipsOut(UserOut):
    memberships: list[MembershipOut] = []


class AgencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    brand_color: str
    is_active: bool
    created_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    timezone: str = Field(default="UTC", max_length=64)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    name: str
    slug: str
    timezone: str
    is_active: bool
    created_at: datetime


__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "UserOut",
    "MembershipOut",
    "UserWithMembershipsOut",
    "AgencyOut",
    "WorkspaceCreate",
    "WorkspaceOut",
]
