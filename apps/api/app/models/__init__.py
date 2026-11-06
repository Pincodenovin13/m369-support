"""SQLAlchemy models for M369 Support.

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
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.database import Base
from ..tenancy.context import TenantOwned


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        server_default=text("now()"),
        onupdate=now_utc,
        nullable=False,
    )


class AgencyOwnedMixin(TenantOwned):
    """Marker for any model that carries ``agency_id``."""

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


# ---------------------------------------------------------------------------
# Super Admin (separate identity, platform-level)
# ---------------------------------------------------------------------------


class SuperAdmin(Base, TimestampMixin):
    """Platform-level administrator. NOT a tenant user.

    Identity table is fully separate from ``User``: separate JWT signing key,
    separate auth flow, separate audit log. A Super Admin bypasses RLS only
    Super Admin operations use a separate database connection with BYPASSRLS role.
    """

    __tablename__ = "super_admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    failed_mfa_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 1 Security Hardening (migration 0010):
    # token_version is bumped on logout-all / password change / deactivation.
    # The JWT carries this as the ``tver`` claim; the request dependency
    # compares token.tver vs super_admins.token_version and rejects mismatches.
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    # Counter of consecutive failed password verifications. Atomically
    # incremented via UPDATE ... SET failed_login_attempts = failed_login_attempts + 1
    # so concurrent attempts cannot under-count.
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    # Audit/observability — only a timestamp, never a password or secret.
    last_failed_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ---------------------------------------------------------------------------
# Agency (tenant root) and workspace
# ---------------------------------------------------------------------------


class Agency(Base, TimestampMixin):
    """Tenant root. Every tenant-owned record traces ownership to an Agency."""

    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    brand_color: Mapped[str] = mapped_column(String(20), default="#FF6B35", server_default="#FF6B35")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="agency", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["AgencyMembership"]] = relationship(
        back_populates="agency", cascade="all, delete-orphan"
    )


class Workspace(Base, TimestampMixin):
    """Sub-organization within an agency."""

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    agency: Mapped[Agency] = relationship(back_populates="workspaces")

    __table_args__ = (
        UniqueConstraint("agency_id", "slug", name="uq_workspaces_agency_slug"),
    )


# ---------------------------------------------------------------------------
# Global user identity + agency membership
# ---------------------------------------------------------------------------


class User(Base, TimestampMixin):
    """Global identity. A user may belong to multiple agencies.

    ``email`` is unique GLOBALLY so a person can use the same email across
    agencies.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["AgencyMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AgencyMembership(Base, TimestampMixin):
    """Links a User to an Agency with a role. A user can be in many agencies.

    Roles (per agency): ``owner``, ``admin``, ``manager``, ``agent``, ``viewer``.
    """

    __tablename__ = "agency_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="agent")

    user: Mapped[User] = relationship(back_populates="memberships")
    agency: Mapped[Agency] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "agency_id", name="uq_memberships_user_agency"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'manager', 'agent', 'viewer')",
            name="ck_memberships_role",
        ),
    )


# ---------------------------------------------------------------------------
# Team (workspace-scoped)
# ---------------------------------------------------------------------------


class Team(Base, TimestampMixin):
    """A team within a workspace. Owned by workspace → agency.

    A unique constraint on ``(id, agency_id)`` is required so that
    ``team_memberships`` can have a composite FK ``(team_id, agency_id) → teams(id, agency_id)``.
    """

    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_teams_workspace_name"),
        UniqueConstraint("id", "agency_id", name="uq_teams_id_agency"),
    )


class TeamMembership(Base, TimestampMixin):
    """User ↔ Team membership. Composite FK prevents cross-agency team assignments."""

    __tablename__ = "team_memberships"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "agency_id"],
            ["teams.id", "teams.agency_id"],
            name="fk_team_memberships_team_agency",
            ondelete="CASCADE",
        ),
    )


# ---------------------------------------------------------------------------
# Contact + Conversation (minimal, for FK + RLS tests)
# ---------------------------------------------------------------------------


class Contact(Base, TimestampMixin):
    """A customer. Workspace-scoped (and therefore agency-scoped transitively)."""

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180), default="", server_default="")

    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_contacts_workspace_email"),
        UniqueConstraint("id", "workspace_id", "agency_id", name="uq_contacts_id_ws_agency"),
    )


class Conversation(Base, TimestampMixin):
    """A conversation. Composite FK on contact ensures cross-workspace refs are blocked."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assigned_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    subject: Mapped[str] = mapped_column(String(255), default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")

    __table_args__ = (
        ForeignKeyConstraint(
            ["contact_id", "workspace_id", "agency_id"],
            ["contacts.id", "contacts.workspace_id", "contacts.agency_id"],
            name="fk_conversations_contact_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assigned_user_id", "agency_id"],
            ["agency_memberships.user_id", "agency_memberships.agency_id"],
            name="fk_conversations_assignee_agency",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["assigned_team_id", "agency_id"],
            ["teams.id", "teams.agency_id"],
            name="fk_conversations_team_agency",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('open', 'pending', 'resolved', 'closed')",
            name="ck_conversations_status",
        ),
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """Security-relevant action log. Agency-scoped; never deleted with agency.

    FK uses ``ON DELETE RESTRICT`` so deleting an agency that still has audit
    logs is blocked. This is intentional: audit history must survive agency
    deletion (regulatory requirement).
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, server_default=text("now()"), nullable=False
    )

    __table_args__ = (Index("ix_audit_logs_agency_created", "agency_id", "created_at"),)


class SuperAdminAuditLog(Base):
    """Separate audit log for Super Admin actions — never mixed with tenant log."""

    __tablename__ = "super_admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    super_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("super_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, server_default=text("now()"), nullable=False
    )


# ---------------------------------------------------------------------------
# Super Admin MFA tables (migration 0010)
# ---------------------------------------------------------------------------


class SuperAdminMFAChallenge(Base):
    """Short-lived challenge token issued AFTER password verification when
    MFA is enabled. The challenge authorizes the bearer to call
    ``/super-admin/auth/login/verify-mfa`` ONLY — it cannot be used on
    any management endpoint.

    The challenge is stored as a SHA-256 hash (``challenge_hash``). The
    plaintext token is sent to the client once and never persisted.
    ``used_at`` is set when consumed; replay is rejected by the
    ``verify-mfa`` endpoint.

    Does NOT inherit TimestampMixin — challenges are immutable once
    created, so an ``updated_at`` column would be misleading. Only
    ``created_at`` is tracked.
    """

    __tablename__ = "super_admin_mfa_challenges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    super_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("super_admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    challenge_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, server_default=text("now()"), nullable=False
    )


class SuperAdminUsedTOTPCode(Base):
    """Single-use TOTP replay protection.

    Each successfully-verified TOTP code is recorded here. The unique
    index on ``(super_admin_id, code_hash)`` prevents two requests with
    the same code in the same window from both succeeding.

    ``code_hash`` = SHA-256 of ``(super_admin_id, code, window_start_ts)``
    so the same numeric code at different time windows hashes differently
    (avoids long-term leakage of code usage patterns).
    """

    __tablename__ = "super_admin_used_totp_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    super_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("super_admins.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    window_start_ts: Mapped[int] = mapped_column(Integer, nullable=False)
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "super_admin_id",
            "code_hash",
            name="uq_sa_totp_codes_sa_codehash",
        ),
    )


class SuperAdminMFARecoveryCode(Base):
    """Single-use recovery code for the case when the TOTP device is lost.

    Stored as Argon2id hash (reusing the password hasher). Never stored
    as plaintext. ``used_at`` is set when consumed; replay is rejected.

    Note: does NOT inherit TimestampMixin — recovery codes are immutable
    once created, so an ``updated_at`` column would be misleading.
    Only ``created_at`` is tracked.
    """

    __tablename__ = "super_admin_mfa_recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    super_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("super_admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, server_default=text("now()"), nullable=False
    )


__all__ = [
    "Agency",
    "AgencyMembership",
    "AuditLog",
    "Contact",
    "Conversation",
    "SuperAdmin",
    "SuperAdminAuditLog",
    "SuperAdminMFAChallenge",
    "SuperAdminUsedTOTPCode",
    "SuperAdminMFARecoveryCode",
    "Team",
    "TeamMembership",
    "User",
    "Workspace",
    "AgencyOwnedMixin",
    "TimestampMixin",
    "new_uuid",
    "now_utc",
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


# Re-export Phase 1 extended models so callers can `from app.models import Message, ...`
from .phase1_extended import (  # noqa: E402
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
