"""Super Admin — subscriptions."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ....db.database import get_super_admin_db
from ....dependencies import get_super_admin_context
from ....models import Subscription
from ....schemas import PaginatedResponse, SubscriptionOut, SubscriptionStatusUpdate
from ....services.billing import update_subscription_status

router = APIRouter(prefix="/super-admin/subscriptions", tags=["Super Admin — Subscriptions"])


def _sa_id(request: Request) -> uuid.UUID:
    return request.state.super_admin_id


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=PaginatedResponse[SubscriptionOut])
def list_subscriptions(
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
    agency_id: uuid.UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status", pattern=r"^(trial|active|past_due|suspended|cancelled|superseded)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Subscription)
    count_stmt = select(func.count()).select_from(Subscription)
    if agency_id is not None:
        stmt = stmt.where(Subscription.agency_id == agency_id)
        count_stmt = count_stmt.where(Subscription.agency_id == agency_id)
    if status_ is not None:
        stmt = stmt.where(Subscription.status == status_)
        count_stmt = count_stmt.where(Subscription.status == status_)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(Subscription.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[SubscriptionOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    s = db.get(Subscription, subscription_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return s


@router.patch("/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionStatusUpdate,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    # Lock the row before checking the state machine to serialize concurrent
    # status transitions and prevent stale-state overwrites.
    s = db.scalar(select(Subscription).where(Subscription.id == subscription_id).with_for_update())
    if s is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    update_subscription_status(
        db,
        subscription=s,
        new_status=payload.status,
        super_admin_id=_sa_id(request),
        current_period_ends_at=payload.current_period_ends_at,
        ip_address=_ip(request),
    )
    db.commit()
    db.refresh(s)
    return s
