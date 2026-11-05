"""Super Admin — payments.

Phase 1: payments are verified manually by a Super Admin. There is no
on-chain or webhook integration — that's Phase 2. The verify endpoint
accepts the Super Admin's conversion of the on-chain amount to base
currency cents, plus the raw values + decimals + rate for audit.

Idempotency: the ``payments.txid`` column is UNIQUE. Re-verifying an
already-verified payment is a no-op (returns the existing row).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ....db.database import get_super_admin_db
from ....dependencies import get_super_admin_context
from ....models import Payment
from ....schemas import (
    PaginatedResponse,
    PaymentOut,
    PaymentRejectRequest,
    PaymentVerifyRequest,
)
from ....services.billing import reject_payment, verify_payment

router = APIRouter(prefix="/super-admin/payments", tags=["Super Admin — Payments"])


def _sa_id(request: Request) -> uuid.UUID:
    return request.state.super_admin_id


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=PaginatedResponse[PaymentOut])
def list_payments(
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
    agency_id: uuid.UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status", pattern=r"^(pending|verifying|verified|rejected|expired)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Payment)
    count_stmt = select(func.count()).select_from(Payment)
    if agency_id is not None:
        stmt = stmt.where(Payment.agency_id == agency_id)
        count_stmt = count_stmt.where(Payment.agency_id == agency_id)
    if status_ is not None:
        stmt = stmt.where(Payment.status == status_)
        count_stmt = count_stmt.where(Payment.status == status_)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(Payment.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[PaymentOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    p = db.get(Payment, payment_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return p


@router.post("/{payment_id}/verify", response_model=PaymentOut)
def verify_payment_endpoint(
    payment_id: uuid.UUID,
    payload: PaymentVerifyRequest,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Manually verify a payment. Idempotent — re-verifying returns same row.

    Stores both the base-currency amount_paid (cents, INTEGER — never FLOAT)
    AND the raw on-chain values + decimals + exchange_rate for audit.
    """
    p = db.get(Payment, payment_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    verify_payment(
        db,
        payment=p,
        super_admin_id=_sa_id(request),
        amount_paid_cents=payload.amount_paid,
        paid_currency=payload.paid_currency,
        paid_amount_raw=payload.paid_amount_raw,
        paid_amount_decimals=payload.paid_amount_decimals,
        exchange_rate=payload.exchange_rate,
        network=payload.network,
        note=payload.note,
        ip_address=_ip(request),
    )
    db.commit()
    db.refresh(p)
    return p


@router.post("/{payment_id}/reject", response_model=PaymentOut)
def reject_payment_endpoint(
    payment_id: uuid.UUID,
    payload: PaymentRejectRequest,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    p = db.get(Payment, payment_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    reject_payment(
        db,
        payment=p,
        super_admin_id=_sa_id(request),
        failure_reason=payload.failure_reason,
        ip_address=_ip(request),
    )
    db.commit()
    db.refresh(p)
    return p
