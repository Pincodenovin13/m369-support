"""User and AgencyMembership models — global identity + tenant membership."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid


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

    # Server-side session revocation (migration 0014). Bumped on logout
    # via atomic UPDATE ... SET token_version = token_version + 1.
    # The JWT carries this value as the ``tver`` claim; the request
    # dependency compares token.tver vs users.token_version and rejects
    # mismatches with 401.
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

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
    agency: Mapped["Agency"] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "agency_id", name="uq_memberships_user_agency"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'manager', 'agent', 'viewer')",
            name="ck_memberships_role",
        ),
    )


__all__ = ["User", "AgencyMembership"]
