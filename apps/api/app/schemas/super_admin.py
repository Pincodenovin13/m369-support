"""Schemas for Super Admin operations: agency management, billing, settings."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Agencies (Super Admin view)
# ---------------------------------------------------------------------------


class AgencyAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    brand_color: str
    is_active: bool
    created_at: datetime


class AgencyAdminDetailOut(AgencyAdminOut):
    """Agency detail with subscription summary + member count."""

    subscription_id: uuid.UUID | None = None
    subscription_status: str | None = None
    plan_name: str | None = None
    member_count: int = 0


class AgencyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    is_active: bool | None = None
    brand_color: str | None = Field(default=None, max_length=20)


# ---------------------------------------------------------------------------
# Members (Super Admin view of agency memberships)
# ---------------------------------------------------------------------------


class AgencyMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    agency_id: uuid.UUID
    role: str
    user_email: str | None = None
    user_name: str | None = None
    created_at: datetime


class AgencyMemberRoleUpdate(BaseModel):
    role: str = Field(pattern=r"^(owner|admin|manager|agent|viewer)$")


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    price_monthly: int = Field(ge=0, le=10_000_00)  # cents, max $10,000
    currency: str = Field(default="USD", min_length=3, max_length=3)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)
    features: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)
    trial_days: int = Field(default=7, ge=0, le=365)


class PlanUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    price_monthly: int | None = Field(default=None, ge=0, le=10_000_00)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    features: dict[str, Any] | None = None
    limits: dict[str, Any] | None = None
    trial_days: int | None = Field(default=None, ge=0, le=365)


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    price_monthly: int
    currency: str
    is_active: bool
    sort_order: int
    features: dict[str, Any]
    limits: dict[str, Any]
    trial_days: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    price_monthly_snapshot: int
    currency_snapshot: str
    plan_name_snapshot: str
    plan_features_snapshot: dict[str, Any]
    plan_limits_snapshot: dict[str, Any]
    started_at: datetime
    trial_ends_at: datetime | None
    current_period_ends_at: datetime | None
    cancelled_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime


class SubscriptionStatusUpdate(BaseModel):
    """Super Admin can move a subscription through its lifecycle.

    Allowed transitions are validated server-side via a finite-state
    transition table (see ``services.billing``).
    """

    status: str = Field(pattern=r"^(trial|active|past_due|suspended|cancelled|superseded)$")
    current_period_ends_at: datetime | None = None


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    agency_id: uuid.UUID
    txid: str
    idempotency_key: str | None
    amount_expected: int
    amount_paid: int
    currency: str
    paid_currency: str | None
    paid_amount_raw: int | None
    paid_amount_decimals: int | None
    exchange_rate: float | None
    status: str
    verifying_lease_until: datetime | None
    verified_at: datetime | None
    verified_by_super_admin_id: uuid.UUID | None
    failure_reason: str | None
    payment_method: str
    network: str | None
    metadata_: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PaymentVerifyRequest(BaseModel):
    """Super Admin verifies a payment manually (Phase 1: no on-chain verification).

    ``amount_paid`` is in CENTS of the base currency — the Super Admin must
    convert the on-chain amount using the exchange rate at tx time. The
    service records the raw on-chain values + decimals + rate for audit.
    """

    amount_paid: int = Field(ge=0)  # cents, in base currency
    paid_currency: str | None = Field(default=None, min_length=3, max_length=10)  # ISO 4217 or crypto code (e.g., USDT)
    paid_amount_raw: int | None = Field(default=None, ge=0)
    paid_amount_decimals: int | None = Field(default=None, ge=0, le=18)
    exchange_rate: float | None = Field(default=None, gt=0)
    network: str | None = Field(default=None, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class PaymentRejectRequest(BaseModel):
    failure_reason: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Platform settings
# ---------------------------------------------------------------------------


class PlatformSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    value_type: str
    description: str
    updated_at: datetime


class PlatformSettingUpsert(BaseModel):
    value: str = Field(min_length=0, max_length=10000)
    value_type: str = Field(default="string", pattern=r"^(string|bool|int|json)$")
    description: str = Field(default="", max_length=255)


# ---------------------------------------------------------------------------
# Agency notes
# ---------------------------------------------------------------------------


class AgencyNoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=5000)
    is_pinned: bool = False


class AgencyNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID
    super_admin_id: uuid.UUID | None
    note: str
    is_pinned: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Super Admin audit log
# ---------------------------------------------------------------------------


class SuperAdminAuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    super_admin_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    metadata_: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None
    created_at: datetime


__all__ = [
    "AgencyAdminOut",
    "AgencyAdminDetailOut",
    "AgencyUpdateRequest",
    "AgencyMemberOut",
    "AgencyMemberRoleUpdate",
    "PlanCreate",
    "PlanUpdate",
    "PlanOut",
    "SubscriptionOut",
    "SubscriptionStatusUpdate",
    "PaymentOut",
    "PaymentVerifyRequest",
    "PaymentRejectRequest",
    "PlatformSettingOut",
    "PlatformSettingUpsert",
    "AgencyNoteCreate",
    "AgencyNoteOut",
    "SuperAdminAuditLogOut",
]
