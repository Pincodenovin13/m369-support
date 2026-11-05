"""Schemas for Contacts, Conversations, Messages."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


class ContactCreate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    name: str = Field(default="", max_length=180)
    workspace_id: uuid.UUID


class ContactUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, max_length=180)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    agency_id: uuid.UUID
    email: str | None
    phone: str | None
    name: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


class ConversationCreate(BaseModel):
    workspace_id: uuid.UUID
    contact_id: uuid.UUID
    subject: str = Field(default="", max_length=255)
    assigned_user_id: uuid.UUID | None = None
    assigned_team_id: uuid.UUID | None = None


class ConversationUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(open|pending|resolved|closed)$")
    assigned_user_id: uuid.UUID | None = None
    assigned_team_id: uuid.UUID | None = None
    subject: str | None = Field(default=None, max_length=255)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    agency_id: uuid.UUID
    contact_id: uuid.UUID
    assigned_user_id: uuid.UUID | None
    assigned_team_id: uuid.UUID | None
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class MessageCreate(BaseModel):
    """Send a message in a conversation.

    ``sender_type='agent'`` requires an authenticated agency user
    (the API enforces this — sender_user_id is set to current_user.id).
    ``sender_type='contact'`` is reserved for the widget ingestion path
    (separate endpoint, not agency-scoped).
    """

    conversation_id: uuid.UUID
    content: str = Field(min_length=1, max_length=20000)
    is_internal: bool = False
    reply_to_message_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    agency_id: uuid.UUID
    sender_type: str
    sender_user_id: uuid.UUID | None
    content: str
    is_internal: bool
    delivery_status: str | None
    created_at: datetime


__all__ = [
    "ContactCreate",
    "ContactUpdate",
    "ContactOut",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationOut",
    "MessageCreate",
    "MessageOut",
]
