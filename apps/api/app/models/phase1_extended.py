"""Phase 1 Backend — Additional models for messages, channels, KB, billing.

Migration 0006 adds:
  - messages (conversation messages)
  - message_attachments (files on messages)
  - channels (channel config per workspace)
  - kb_categories (KB article categories)
  - kb_articles (KB articles)
  - canned_responses (pre-written replies)
  - plans (subscription plans, managed by Super Admin)
  - subscriptions (agency subscriptions with price snapshot)
  - payments (payment transactions, idempotent)
  - platform_settings (Super Admin configurable key-value settings)
  - agency_notes (Super Admin notes on agencies)

All tenant-owned tables carry agency_id for RLS.
Composite FKs prevent cross-tenant references.
Base-currency amounts use INTEGER cents; exchange rates use NUMERIC(18,6);
raw blockchain units use NUMERIC(78,0). Never use FLOAT for persisted money.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.database import Base
from . import new_uuid, now_utc, TimestampMixin, AgencyOwnedMixin


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class Message(Base, TimestampMixin, AgencyOwnedMixin):
    """A single message in a conversation.

    Owned by agency (via agency_id) and linked to a conversation.
    Composite FK on (conversation_id, agency_id) ensures messages
    cannot reference conversations from other agencies.
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)  # contact | agent | system | bot
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # processed content for LLM
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)  # internal note
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # channel-specific id
    delivery_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # sent|delivered|read|failed
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"))
    reaction: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        # Composite FK: conversation must be in the same agency
        ForeignKeyConstraint(
            ["conversation_id", "agency_id"],
            ["conversations.id", "conversations.agency_id"],
            name="fk_messages_conversation_agency",
            ondelete="CASCADE",
        ),
        # Composite FK: reply_to must be in the same agency (tenant boundary)
        # ON DELETE NO ACTION — the simple FK above handles SET NULL on delete
        ForeignKeyConstraint(
            ["reply_to_message_id", "agency_id"],
            ["messages.id", "messages.agency_id"],
            name="fk_messages_reply_to_agency",
            ondelete="NO ACTION",
        ),
        CheckConstraint(
            "sender_type IN ('contact', 'agent', 'system', 'bot')",
            name="ck_messages_sender_type",
        ),
        CheckConstraint(
            "delivery_status IS NULL OR delivery_status IN ('sent', 'delivered', 'read', 'failed')",
            name="ck_messages_delivery_status",
        ),
    )


class MessageAttachment(Base, TimestampMixin):
    """A file attached to a message.

    Owned by agency via ``agency_id`` (added in migration 0011).
    Composite FK ``(message_id, agency_id)`` → ``messages(id, agency_id)``
    prevents cross-tenant attachment references.
    RLS is enabled on this table (migration 0011).
    """

    __tablename__ = "message_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)  # path in object storage
    storage_backend: Mapped[str] = mapped_column(String(20), default="local", server_default="local")
    kind: Mapped[str] = mapped_column(String(20), default="file")  # file | image | audio | video

    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "agency_id"],
            ["messages.id", "messages.agency_id"],
            name="fk_message_attachments_message_agency",
            ondelete="CASCADE",
        ),
    )


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


class Channel(Base, AgencyOwnedMixin, TimestampMixin):
    """Channel configuration per workspace (widget, email, etc.).

    Phase 1 supports 'widget' only. Future phases add email, WhatsApp, etc.
    """

    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # widget | email | whatsapp_cloud | ...
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet-encrypted JSON
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    public_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)  # for widget embed

    __table_args__ = (
        UniqueConstraint("workspace_id", "type", name="uq_channels_workspace_type"),
        ForeignKeyConstraint(
            ["workspace_id", "agency_id"],
            ["workspaces.id", "workspaces.agency_id"],
            name="fk_channels_workspace_agency",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "type IN ('widget', 'email', 'whatsapp_cloud', 'telegram', 'instagram', 'messenger')",
            name="ck_channels_type",
        ),
    )


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------


class KBCategory(Base, AgencyOwnedMixin, TimestampMixin):
    """KB article category, scoped to workspace."""

    __tablename__ = "kb_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_categories.id", ondelete="CASCADE"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_kb_categories_workspace_slug"),
        ForeignKeyConstraint(
            ["workspace_id", "agency_id"],
            ["workspaces.id", "workspaces.agency_id"],
            name="fk_kb_categories_workspace_agency",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["parent_id", "workspace_id", "agency_id"],
            ["kb_categories.id", "kb_categories.workspace_id", "kb_categories.agency_id"],
            name="fk_kb_categories_parent_ws_agency",
            ondelete="CASCADE",
        ),
    )


class KBArticle(Base, AgencyOwnedMixin, TimestampMixin):
    """KB article, scoped to workspace."""

    __tablename__ = "kb_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_categories.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)  # markdown
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")  # rendered
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    views_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    not_helpful_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_kb_articles_workspace_slug"),
        ForeignKeyConstraint(
            ["workspace_id", "agency_id"],
            ["workspaces.id", "workspaces.agency_id"],
            name="fk_kb_articles_workspace_agency",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["category_id", "workspace_id", "agency_id"],
            ["kb_categories.id", "kb_categories.workspace_id", "kb_categories.agency_id"],
            name="fk_kb_articles_category_ws_agency",
            ondelete="NO ACTION",
        ),
        Index("ix_kb_articles_workspace_published", "workspace_id", "is_published"),
    )


# ---------------------------------------------------------------------------
# Canned Responses
# ---------------------------------------------------------------------------


class CannedResponse(Base, AgencyOwnedMixin, TimestampMixin):
    """Pre-written reply, scoped to workspace."""

    __tablename__ = "canned_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    shortcut: Mapped[str] = mapped_column(String(60), nullable=False)
    content: Mapped[str] = mapped_column(String(4000), nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "shortcut", name="uq_canned_responses_workspace_shortcut"),
        ForeignKeyConstraint(
            ["workspace_id", "agency_id"],
            ["workspaces.id", "workspaces.agency_id"],
            name="fk_canned_responses_workspace_agency",
            ondelete="CASCADE",
        ),
    )


# ---------------------------------------------------------------------------
# Plans, Subscriptions, Payments
# ---------------------------------------------------------------------------


class Plan(Base, TimestampMixin):
    """Subscription plan, managed by Super Admin.

    NOT tenant-scoped — plans are platform-wide.
    price_monthly is snapshot at subscription time.
    """

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_monthly: Mapped[int] = mapped_column(Integer, nullable=False)  # in cents (e.g., 1900 = $19.00)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Feature flags as JSON — flexible, extensible without schema changes
    features: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    # Limits as JSON — e.g. {"max_seats": 3, "max_conversations": 500, "max_workspaces": 1}
    limits: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    trial_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7", nullable=False)


class Subscription(Base, TimestampMixin):
    """Agency subscription. Price is snapshot from plan at creation.

    Lifecycle: trial → active → past_due → suspended → cancelled
    One active subscription per agency (enforced by partial unique index).
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="trial", server_default="trial")
    # Price snapshot — frozen at subscription creation
    price_monthly_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)  # cents
    currency_snapshot: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    plan_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_features_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    plan_limits_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=text("now()"))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('trial', 'active', 'past_due', 'suspended', 'cancelled', 'superseded')",
            name="ck_subscriptions_status",
        ),
        # Partial unique: only one active subscription per agency
        Index(
            "uq_subscriptions_agency_active",
            "agency_id",
            unique=True,
            postgresql_where=text("status IN ('trial', 'active', 'past_due', 'suspended')"),
        ),
    )


class Payment(Base, TimestampMixin):
    """Payment transaction. Idempotent — txid is unique.

    Base-currency amounts are integer cents. Exchange rates use NUMERIC(18,6),
    and raw blockchain token units use NUMERIC(78,0) to preserve uint256 precision.
    No persisted financial amount uses FLOAT.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Transaction identity
    txid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)  # external tx id, UNIQUE
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Amounts — NUMERIC, never FLOAT
    amount_expected: Mapped[int] = mapped_column(Integer, nullable=False)  # cents, in base currency
    amount_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # cents, actually paid
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    # For crypto/multi-currency
    paid_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    paid_amount_raw: Mapped[Decimal | None] = mapped_column(Numeric(78, 0), nullable=True)  # exact uint256-compatible raw blockchain integer
    paid_amount_decimals: Mapped[int | None] = mapped_column(Integer, nullable=True)  # e.g. 6 for USDT TRC20
    exchange_rate: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)  # rate at tx time
    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    verifying_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_super_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("super_admins.id", ondelete="SET NULL"), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Metadata
    payment_method: Mapped[str] = mapped_column(String(30), default="crypto_usdt_trc20")  # crypto_usdt_trc20 | crypto_usdt_bep20 | ...
    network: Mapped[str | None] = mapped_column(String(20), nullable=True)  # tron | bsc | ...
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        ForeignKeyConstraint(
            ["subscription_id", "agency_id"],
            ["subscriptions.id", "subscriptions.agency_id"],
            name="fk_payments_subscription_agency",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pending', 'verifying', 'verified', 'rejected', 'expired')",
            name="ck_payments_status",
        ),
        CheckConstraint(
            "amount_paid >= 0 AND amount_expected >= 0",
            name="ck_payments_amounts_nonneg",
        ),
        CheckConstraint(
            "paid_amount_raw IS NULL OR paid_amount_raw >= 0",
            name="ck_payments_raw_amount_nonneg",
        ),
        Index("ix_payments_subscription_status", "subscription_id", "status"),
    )


# ---------------------------------------------------------------------------
# Platform Settings (Super Admin)
# ---------------------------------------------------------------------------


class PlatformSetting(Base):
    """Super Admin configurable key-value settings.

    NOT tenant-scoped — platform-wide.
    Changes are audit-logged via super_admin_audit_logs.
    """

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")  # string|bool|int|json
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, server_default=text("now()"), onupdate=now_utc, nullable=False)
    updated_by_super_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("super_admins.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'bool', 'int', 'json')",
            name="ck_platform_settings_value_type",
        ),
    )


# ---------------------------------------------------------------------------
# Agency Notes (Super Admin)
# ---------------------------------------------------------------------------


class AgencyNote(Base, TimestampMixin):
    """Super Admin note on an agency. Visible only to Super Admins."""

    __tablename__ = "agency_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True)
    super_admin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("super_admins.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


__all__ = [
    # New models
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
