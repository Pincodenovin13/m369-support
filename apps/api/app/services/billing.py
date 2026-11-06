"""Billing service: subscription lifecycle + payment verification.

Pure-Python service layer that the Super Admin API endpoints call into.
Keeps the endpoint modules thin and lets the business rules be tested
without going through the HTTP layer.

Subscription lifecycle (Phase 1):

    trial ─→ active ─→ past_due ─→ suspended ─→ cancelled
                  │            ↑
                  └→ cancelled ↑

    (any) ─→ superseded   (only via plan-change, not direct update)

Allowed transitions are enforced via the ``ALLOWED_TRANSITIONS`` table
below — trying to move from e.g. ``cancelled`` back to ``active`` is
rejected with 400.

Payment verification is idempotent:

  - The ``payments.txid`` column is UNIQUE — a duplicate verify of the
    same txid returns the existing row's status without mutating.
  - The verifying Super Admin's id is recorded in
    ``verified_by_super_admin_id``.
  - ``amount_paid`` is INTEGER cents — never FLOAT. The raw on-chain
    amount + decimals + exchange_rate are stored separately so the
    calculation can be re-audited later.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import Payment, Subscription, SuperAdminAuditLog


# ---------------------------------------------------------------------------
# Subscription lifecycle
# ---------------------------------------------------------------------------


# Allowed "from" → set of allowed "to" states.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "trial":     frozenset({"active", "past_due", "cancelled"}),
    "active":    frozenset({"past_due", "suspended", "cancelled"}),
    "past_due":  frozenset({"active", "suspended", "cancelled"}),
    "suspended": frozenset({"active", "cancelled"}),
    "cancelled": frozenset(),  # terminal — no transitions out
    "superseded": frozenset(),  # terminal — only set by plan-change
}


def assert_transition_allowed(current: str, target: str) -> None:
    """Raise 400 if the transition is not in ``ALLOWED_TRANSITIONS``."""
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subscription cannot move from '{current}' to '{target}'",
        )


def update_subscription_status(
    db: Session,
    *,
    subscription: Subscription,
    new_status: str,
    super_admin_id: uuid.UUID,
    current_period_ends_at: datetime | None = None,
    ip_address: str | None = None,
) -> Subscription:
    """Apply a status transition + audit it. Caller commits."""
    assert_transition_allowed(subscription.status, new_status)
    old_status = subscription.status
    subscription.status = new_status
    if current_period_ends_at is not None:
        subscription.current_period_ends_at = current_period_ends_at
    if new_status == "cancelled":
        subscription.cancelled_at = datetime.now(timezone.utc)
    db.flush()
    db.add(SuperAdminAuditLog(
        super_admin_id=super_admin_id,
        action="subscription.update_status",
        target_type="subscription",
        target_id=subscription.id,
        metadata_={"old": old_status, "new": new_status},
        ip_address=ip_address,
    ))
    return subscription


# ---------------------------------------------------------------------------
# Payment verification (idempotent)
# ---------------------------------------------------------------------------


def verify_payment(
    db: Session,
    *,
    payment: Payment,
    super_admin_id: uuid.UUID,
    amount_paid_cents: int,
    paid_currency: str | None = None,
    paid_amount_raw: int | None = None,
    paid_amount_decimals: int | None = None,
    exchange_rate: float | None = None,
    network: str | None = None,
    note: str | None = None,
    ip_address: str | None = None,
) -> Payment:
    """Verify a payment. Idempotent — re-verifying returns the same row.

    Idempotency rules:
      - If the payment is already ``verified``, return it as-is (no mutation).
      - If the payment is ``rejected`` or ``expired``, raise 409 — those
        are terminal states and cannot be re-verified.
      - If the payment is ``pending`` or ``verifying``, mark it ``verified``.

    The ``amount_paid_cents`` argument is the BASE-currency amount the
    Super Admin calculated using the exchange rate at tx time. The raw
    on-chain amount + decimals + rate are stored separately for audit.
    """
    if payment.status == "verified":
        return payment  # already verified — idempotent
    if payment.status in {"rejected", "expired"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment is in terminal state '{payment.status}' — cannot re-verify",
        )

    now = datetime.now(timezone.utc)
    payment.amount_paid = amount_paid_cents
    if paid_currency is not None:
        payment.paid_currency = paid_currency
    if paid_amount_raw is not None:
        payment.paid_amount_raw = paid_amount_raw
    if paid_amount_decimals is not None:
        payment.paid_amount_decimals = paid_amount_decimals
    if exchange_rate is not None:
        payment.exchange_rate = exchange_rate
    if network is not None:
        payment.network = network
    payment.status = "verified"
    payment.verified_at = now
    payment.verified_by_super_admin_id = super_admin_id

    db.flush()
    db.add(SuperAdminAuditLog(
        super_admin_id=super_admin_id,
        action="payment.verify",
        target_type="payment",
        target_id=payment.id,
        metadata_={
            "amount_paid_cents": amount_paid_cents,
            "paid_currency": paid_currency,
            "paid_amount_raw": paid_amount_raw,
            "paid_amount_decimals": paid_amount_decimals,
            "exchange_rate": float(exchange_rate) if exchange_rate is not None else None,
            "network": network,
            "note": note,
        },
        ip_address=ip_address,
    ))
    return payment


def reject_payment(
    db: Session,
    *,
    payment: Payment,
    super_admin_id: uuid.UUID,
    failure_reason: str,
    ip_address: str | None = None,
) -> Payment:
    """Reject a payment. Idempotent — re-rejecting is a no-op."""
    if payment.status == "rejected":
        return payment
    if payment.status == "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment is already verified — cannot reject",
        )
    if payment.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment is expired — cannot reject",
        )
    payment.status = "rejected"
    payment.failure_reason = failure_reason
    db.flush()
    db.add(SuperAdminAuditLog(
        super_admin_id=super_admin_id,
        action="payment.reject",
        target_type="payment",
        target_id=payment.id,
        metadata_={"failure_reason": failure_reason},
        ip_address=ip_address,
    ))
    return payment


__all__ = [
    "ALLOWED_TRANSITIONS",
    "assert_transition_allowed",
    "update_subscription_status",
    "verify_payment",
    "reject_payment",
]
