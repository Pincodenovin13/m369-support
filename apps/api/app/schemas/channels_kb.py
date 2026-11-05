"""Schemas for Channels, KB, Canned Responses."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


class ChannelCreate(BaseModel):
    workspace_id: uuid.UUID
    type: str = Field(pattern=r"^(widget|email|whatsapp_cloud|telegram|instagram|messenger)$")
    name: str = Field(min_length=1, max_length=160)
    config: dict = Field(default_factory=dict)
    is_enabled: bool = True


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    config: dict | None = None
    is_enabled: bool | None = None


class ChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    agency_id: uuid.UUID
    type: str
    name: str
    config: dict
    is_enabled: bool
    public_id: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# KB
# ---------------------------------------------------------------------------


class KBCategoryCreate(BaseModel):
    workspace_id: uuid.UUID
    name: str = Field(min_length=1, max_length=180)
    parent_id: uuid.UUID | None = None
    position: int = Field(default=0, ge=0)


class KBCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    agency_id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None
    position: int
    created_at: datetime


class KBArticleCreate(BaseModel):
    workspace_id: uuid.UUID
    category_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    content_md: str = Field(min_length=1, max_length=50000)
    is_published: bool = False


class KBArticleUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_md: str | None = Field(default=None, min_length=1, max_length=50000)
    is_published: bool | None = None


class KBArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    agency_id: uuid.UUID
    category_id: uuid.UUID | None
    title: str
    slug: str
    content_md: str
    is_published: bool
    views_count: int
    helpful_count: int
    not_helpful_count: int
    author_id: uuid.UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Canned Responses
# ---------------------------------------------------------------------------


class CannedResponseCreate(BaseModel):
    workspace_id: uuid.UUID
    shortcut: str = Field(min_length=1, max_length=60, pattern=r"^[a-zA-Z0-9_\-.]+$")
    content: str = Field(min_length=1, max_length=4000)


class CannedResponseUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=4000)


class CannedResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    agency_id: uuid.UUID
    shortcut: str
    content: str
    created_at: datetime


__all__ = [
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
]
