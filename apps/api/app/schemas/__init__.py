"""Pydantic schemas for M369 Support API.

This module is the public re-export surface for all schemas. Callers should
import from here: ``from app.schemas import RegisterRequest, ...``

Domain modules:
    - auth             : RegisterRequest, LoginRequest, TokenResponse, UserOut, etc.
    - super_admin_auth : SuperAdminCreate, SuperAdminLoginRequest, SuperAdminOut, MFA schemas
    - system           : HealthResponse, ReadinessResponse
    - common           : PaginationParams, PaginatedResponse[T]
    - conversations     : Contact, Conversation, Message schemas
    - teams             : Team schemas
    - channels_kb       : Channel, KBCategory, KBArticle, CannedResponse
    - audit             : AuditLogOut
    - super_admin       : Super Admin management schemas (agencies, plans, subscriptions, payments, settings)
"""
from __future__ import annotations

# Auth / agency / workspace
from .auth import (
    AgencyOut,
    LoginRequest,
    MembershipOut,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserWithMembershipsOut,
    WorkspaceCreate,
    WorkspaceOut,
)

# Super Admin auth + MFA
from .super_admin_auth import (
    SuperAdminCreate,
    SuperAdminLoginRequest,
    SuperAdminMFAEnableRequest,
    SuperAdminMFADisableRequest,
    SuperAdminMFARequiredResponse,
    SuperAdminMFASetupResponse,
    SuperAdminOut,
    SuperAdminRecoveryCodesOut,
    SuperAdminVerifyMFARequest,
)

# System
from .system import HealthResponse, ReadinessResponse

# Common
from .common import DEFAULT_LIMIT, MAX_LIMIT, PaginatedResponse, PaginationParams

# Conversations / contacts / messages
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

# Teams
from .teams import TeamCreate, TeamMembershipAdd, TeamMembershipOut, TeamOut

# Channels / KB / canned
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

# Audit
from .audit import AuditLogOut

# Super Admin management (agencies, plans, subscriptions, payments, settings, notes, audit)
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
    # Auth / agency / workspace
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
    # Super Admin auth + MFA
    "SuperAdminCreate",
    "SuperAdminLoginRequest",
    "SuperAdminOut",
    "SuperAdminMFARequiredResponse",
    "SuperAdminVerifyMFARequest",
    "SuperAdminMFASetupResponse",
    "SuperAdminMFAEnableRequest",
    "SuperAdminMFADisableRequest",
    "SuperAdminRecoveryCodesOut",
    # System
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
    # Super Admin management (Stage 3)
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
