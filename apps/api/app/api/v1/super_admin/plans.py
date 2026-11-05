"""Super Admin — plans CRUD."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ....db.database import get_super_admin_db
from ....dependencies import get_super_admin_context
from ....models import Plan, SuperAdminAuditLog
from ....schemas import PaginatedResponse, PlanCreate, PlanOut, PlanUpdate

router = APIRouter(prefix="/super-admin/plans", tags=["Super Admin — Plans"])


def _sa_id(request: Request) -> uuid.UUID:
    return request.state.super_admin_id


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=PaginatedResponse[PlanOut])
def list_plans(
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Plan)
    count_stmt = select(func.count()).select_from(Plan)
    if is_active is not None:
        stmt = stmt.where(Plan.is_active == is_active)
        count_stmt = count_stmt.where(Plan.is_active == is_active)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(Plan.sort_order.asc(), Plan.created_at.asc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[PlanOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreate,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    existing = db.scalar(select(Plan).where(Plan.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Plan '{payload.name}' already exists")
    plan = Plan(
        name=payload.name,
        display_name=payload.display_name,
        price_monthly=payload.price_monthly,
        currency=payload.currency,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        features=payload.features,
        limits=payload.limits,
        trial_days=payload.trial_days,
    )
    db.add(plan)
    db.flush()
    db.add(SuperAdminAuditLog(
        super_admin_id=_sa_id(request),
        action="plan.create",
        target_type="plan",
        target_id=plan.id,
        metadata_={"name": plan.name, "price_monthly": plan.price_monthly, "currency": plan.currency},
        ip_address=_ip(request),
    ))
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    changes: dict = {}
    for field in ("display_name", "price_monthly", "currency", "is_active", "sort_order", "features", "limits", "trial_days"):
        val = getattr(payload, field)
        if val is not None and val != getattr(plan, field):
            setattr(plan, field, val)
            if field in ("features", "limits"):
                changes[field] = True  # don't log potentially large dict
            else:
                changes[field] = val
    if changes:
        db.add(SuperAdminAuditLog(
            super_admin_id=_sa_id(request),
            action="plan.update",
            target_type="plan",
            target_id=plan.id,
            metadata_=changes,
            ip_address=_ip(request),
        ))
    db.commit()
    db.refresh(plan)
    return plan
