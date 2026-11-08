"""Contact, Conversation, and AuditLog models — customer interactions + audit trail."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid, now_utc


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
            ["workspace_id", "agency_id"],
            ["workspaces.id", "workspaces.agency_id"],
            name="fk_conversations_workspace_agency",
            ondelete="CASCADE",
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


__all__ = ["Contact", "Conversation", "AuditLog"]
