"""Super Admin models: SuperAdmin, SuperAdminAuditLog, MFA tables.

Super Admin is a separate identity from User — separate JWT signing key,
separate auth flow, separate audit log. Super Admin operations use a
separate database connection with a BYPASSRLS role.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid, now_utc


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
    "SuperAdmin",
    "SuperAdminAuditLog",
    "SuperAdminMFAChallenge",
    "SuperAdminUsedTOTPCode",
    "SuperAdminMFARecoveryCode",
]
