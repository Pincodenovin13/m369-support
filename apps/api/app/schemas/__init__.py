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


# ---------------------------------------------------------------------------
# Super Admin MFA schemas (Phase 1 Security Hardening / Package A)
# ---------------------------------------------------------------------------


class SuperAdminMFARequiredResponse(BaseModel):
    """Response when login password check succeeds but MFA is required.

    The client must submit a TOTP code (or recovery code) along with the
    ``mfa_challenge`` token to ``/super-admin/auth/login/verify-mfa`` to
    obtain a full Super Admin access token.

    The challenge token is short-lived (default 5 min) and CAN ONLY be
    used at the verify-mfa endpoint — every management endpoint rejects
    it via ``get_super_admin_context`` (which calls ``decode_super_admin_token``
    and never ``decode_mfa_challenge_token``).
    """

    mfa_required: bool = True
    mfa_challenge: str
    expires_in_seconds: int


class SuperAdminVerifyMFARequest(BaseModel):
    """Submit a TOTP code or recovery code with the MFA challenge token."""

    mfa_challenge: str = Field(min_length=1)
    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=1, max_length=64)


class SuperAdminMFASetupResponse(BaseModel):
    """MFA setup response — secret + otpauth URL.

    The secret is returned in plaintext ONCE so the client can render a
    QR code. It is NOT yet active — the client must submit a valid TOTP
    code at ``/super-admin/auth/mfa/enable`` to activate MFA.

    After activation, the plaintext secret is NEVER again returned by
    any API endpoint.
    """

    secret: str
    otpauth_url: str


class SuperAdminMFAEnableRequest(BaseModel):
    """Activate MFA — submit a TOTP code from the just-setup secret."""

    secret: str = Field(min_length=16, max_length=64)
    code: str = Field(min_length=6, max_length=8)


class SuperAdminMFADisableRequest(BaseModel):
    """Disable MFA — requires a TOTP code or recovery code.

    Disabling MFA cannot be done with just the password — the caller
    must prove possession of a second factor.
    """

    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=1, max_length=64)


class SuperAdminRecoveryCodesOut(BaseModel):
    """Recovery codes — returned ONCE at MFA-enable time.

    Plaintext is never stored. Each code is single-use; replay rejected.
    """

    recovery_codes: list[str]


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
from .super_admin import (
    AgencyAdminDetailOut,
    AgencyAdminOut,
    AgencyMemberOut,
    AgencyMemberRoleUpdate,
    AgencyNoteCreate,
    AgencyNoteOut,
    AgencyUpdateRequest,
    PaymentOut,
    PaymentRejectRequest,
    PaymentVerifyRequest,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    PlatformSettingOut,
    PlatformSettingUpsert,
    SubscriptionOut,
    SubscriptionStatusUpdate,
    SuperAdminAuditLogOut,
)


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
    "SuperAdminMFARequiredResponse",
    "SuperAdminVerifyMFARequest",
    "SuperAdminMFASetupResponse",
    "SuperAdminMFAEnableRequest",
    "SuperAdminMFADisableRequest",
    "SuperAdminRecoveryCodesOut",
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
    # Super Admin (Stage 3)
    "AgencyAdminOut",
    "AgencyAdminDetailOut",
    "AgencyUpdateRequest",
    "AgencyMemberOut",
    "AgencyMemberRoleUpdate",
    "PlanCreate",
    "PlanUpdate",
    "PlanOut",
    "SubscriptionOut",
    "SubscriptionStatusUpdate",
    "PaymentOut",
    "PaymentVerifyRequest",
    "PaymentRejectRequest",
    "PlatformSettingOut",
    "PlatformSettingUpsert",
    "AgencyNoteCreate",
    "AgencyNoteOut",
    "SuperAdminAuditLogOut",
]
