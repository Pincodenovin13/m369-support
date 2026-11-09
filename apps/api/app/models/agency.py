"""Agency and Workspace models — tenant root and sub-organization."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid


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


__all__ = ["Agency", "Workspace"]
