"""SQLAlchemy models for M369 Support.

This module is the public re-export surface for all models. Callers should
import from here: ``from app.models import User, Agency, ...``

Alembic's ``env.py`` does ``from app import models`` to register all models
on ``Base.metadata`` for migration autogeneration. This re-export module
ensures all domain modules are imported when the package is loaded.

Design notes:

- ``User`` is a *global* identity. A user may belong to multiple agencies via
  ``AgencyMembership`` rows. This avoids duplicate email/password across
  agencies and supports future "switch agency" UX.
- ``Agency`` is the tenant root. Every tenant-owned table carries
  ``agency_id`` (and possibly ``workspace_id`` for finer scoping).
- ``Workspace`` is a sub-organization within an agency.
- ``SuperAdmin`` is a *separate* identity table from ``User``. It does not
  carry ``agency_id`` and is the only role permitted to bypass RLS.
- Composite foreign keys enforce cross-tenant integrity: e.g. a
  ``Conversation`` cannot reference a ``Contact`` from another workspace
  because the FK is ``(workspace_id, contact_id)`` and the parent's PK is
  ``(workspace_id, id)``.

Domain modules:
    - base         : Base, new_uuid, now_utc, TimestampMixin, AgencyOwnedMixin
    - super_admin  : SuperAdmin, SuperAdminAuditLog, MFA tables
    - agency       : Agency, Workspace
    - user         : User, AgencyMembership
    - team         : Team, TeamMembership
    - conversation : Contact, Conversation, AuditLog
    - phase1_extended : Message, Channel, KB, CannedResponse, Plan, Subscription, Payment, etc.
"""
from __future__ import annotations

# Base + mixins + utilities
from .base import AgencyOwnedMixin, Base, TimestampMixin, new_uuid, now_utc

# Domain models
from .super_admin import (
    SuperAdmin,
    SuperAdminAuditLog,
    SuperAdminMFAChallenge,
    SuperAdminMFARecoveryCode,
    SuperAdminUsedTOTPCode,
)
from .agency import Agency, Workspace
from .user import AgencyMembership, User
from .team import Team, TeamMembership
from .conversation import AuditLog, Contact, Conversation

# Phase 1 extended models (migration 0006+)
from .phase1_extended import (
    AgencyNote,
    Channel,
    CannedResponse,
    KBArticle,
    KBCategory,
    Message,
    MessageAttachment,
    Payment,
    Plan,
    PlatformSetting,
    Subscription,
)


__all__ = [
    # Base + mixins
    "Base",
    "new_uuid",
    "now_utc",
    "TimestampMixin",
    "AgencyOwnedMixin",
    # Super Admin
    "SuperAdmin",
    "SuperAdminAuditLog",
    "SuperAdminMFAChallenge",
    "SuperAdminUsedTOTPCode",
    "SuperAdminMFARecoveryCode",
    # Agency + workspace
    "Agency",
    "Workspace",
    # User + membership
    "User",
    "AgencyMembership",
    # Team
    "Team",
    "TeamMembership",
    # Contact + conversation + audit
    "Contact",
    "Conversation",
    "AuditLog",
    # Phase 1 extended (migration 0006)
    "Message",
    "MessageAttachment",
    "Channel",
    "KBCategory",
    "KBArticle",
    "CannedResponse",
    "Plan",
    "Subscription",
    "Payment",
    "PlatformSetting",
    "AgencyNote",
]
