"""Team and TeamMembership models — workspace-scoped user groups."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class Team(Base, TimestampMixin):
    """A team within a workspace. Owned by workspace -> agency.

    A unique constraint on ``(id, agency_id)`` is required so that
    ``team_memberships`` can have a composite FK ``(team_id, agency_id) -> teams(id, agency_id)``.
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
    """User <-> Team membership. Composite FK prevents cross-agency team assignments."""

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


__all__ = ["Team", "TeamMembership"]
