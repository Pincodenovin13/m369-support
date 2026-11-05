"""Pydantic schemas for M369 Support API.

Modules:
    - common           : PaginationParams, PaginatedResponse[T]
    - conversations     : Contact, Conversation, Message schemas
    - teams             : Team schemas
    - channels_kb       : Channel, KBCategory, KBArticle, CannedResponse
    - audit             : AuditLogOut
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth / agency / workspace / super-admin / health (legacy — kept inline)
# ---------------------------------------------------------------------------


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


class SuperAdminCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    initial: bool = Field(default=False)


class SuperAdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class SuperAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    is_active: bool


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: str


# ---------------------------------------------------------------------------
# Re-exports from feature modules
# ---------------------------------------------------------------------------

from .common import DEFAULT_LIMIT, MAX_LIMIT, PaginatedResponse, PaginationParams
from .conversations import (
    ContactCreate,
    ContactOut,
    ContactUpdate,
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
)
from .teams import TeamCreate, TeamMembershipAdd, TeamMembershipOut, TeamOut
from .channels_kb import (
    CannedResponseCreate,
    CannedResponseOut,
    CannedResponseUpdate,
    ChannelCreate,
    ChannelOut,
    ChannelUpdate,
    KBArticleCreate,
    KBArticleOut,
    KBArticleUpdate,
    KBCategoryCreate,
    KBCategoryOut,
)
from .audit import AuditLogOut


__all__ = [
    # Auth / agency / workspace / super admin / health
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
    "SuperAdminCreate",
    "SuperAdminLoginRequest",
    "SuperAdminOut",
    "HealthResponse",
    "ReadinessResponse",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    # Contacts / conversations / messages
    "ContactCreate",
    "ContactUpdate",
    "ContactOut",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationOut",
    "MessageCreate",
    "MessageOut",
    # Teams
    "TeamCreate",
    "TeamOut",
    "TeamMembershipOut",
    "TeamMembershipAdd",
    # Channels / KB / canned
    "ChannelCreate",
    "ChannelUpdate",
    "ChannelOut",
    "KBCategoryCreate",
    "KBCategoryOut",
    "KBArticleCreate",
    "KBArticleUpdate",
    "KBArticleOut",
    "CannedResponseCreate",
    "CannedResponseUpdate",
    "CannedResponseOut",
    # Audit
    "AuditLogOut",
]
