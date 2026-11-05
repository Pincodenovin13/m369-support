"""Schemas for Teams, TeamMemberships."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    agency_id: uuid.UUID
    name: str
    is_default: bool
    created_at: datetime


class TeamMembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: uuid.UUID
    user_id: uuid.UUID
    agency_id: uuid.UUID


class TeamMembershipAdd(BaseModel):
    user_id: uuid.UUID


__all__ = ["TeamCreate", "TeamOut", "TeamMembershipOut", "TeamMembershipAdd"]
