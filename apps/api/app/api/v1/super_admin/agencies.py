"""Super Admin — agency management.

Reads/writes through the ``super_admin_engine`` (BYPASSRLS) so the Super
Admin can see and modify every tenant's data.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ....db.database import get_super_admin_db
from ....dependencies import get_super_admin_context
from ....models import (
    Agency,
    AgencyMembership,
    AgencyNote,
    Subscription,
    SuperAdminAuditLog,
    User,
)
from ....schemas import (
    AgencyAdminDetailOut,
    AgencyAdminOut,
    AgencyMemberOut,
    AgencyMemberRoleUpdate,
    AgencyUpdateRequest,
    PaginatedResponse,
)


router = APIRouter(prefix="/super-admin/agencies", tags=["Super Admin — Agencies"])


def _sa_id(request: Request) -> uuid.UUID:
    return request.state.super_admin_id


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=PaginatedResponse[AgencyAdminDetailOut])
def list_agencies(
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
    search: str | None = Query(default=None, max_length=120),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List all agencies with their subscription summary + member count.

    RLS is bypassed via the m369_sa_runner connection.
    """
    stmt = select(Agency)
    count_stmt = select(func.count()).select_from(Agency)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Agency.name.ilike(like) | Agency.slug.ilike(like))
        count_stmt = count_stmt.where(Agency.name.ilike(like) | Agency.slug.ilike(like))
    if is_active is not None:
        stmt = stmt.where(Agency.is_active == is_active)
        count_stmt = count_stmt.where(Agency.is_active == is_active)
    total = db.scalar(count_stmt) or 0
    agencies = list(db.scalars(stmt.order_by(Agency.created_at.desc()).limit(limit).offset(offset)).all())

    # Bulk-load subscriptions + member counts
    agency_ids = [a.id for a in agencies]
    subs_by_agency: dict[uuid.UUID, Subscription] = {}
    counts_by_agency: dict[uuid.UUID, int] = {}
    if agency_ids:
        sub_rows = db.scalars(
            select(Subscription).where(
                Subscription.agency_id.in_(agency_ids),
                Subscription.status.in_(("trial", "active", "past_due", "suspended")),
            )
        ).all()
        for s in sub_rows:
            subs_by_agency[s.agency_id] = s
        count_rows = db.execute(
            select(AgencyMembership.agency_id, func.count())
            .where(AgencyMembership.agency_id.in_(agency_ids))
            .group_by(AgencyMembership.agency_id)
        ).all()
        counts_by_agency = {aid: cnt for aid, cnt in count_rows}

    items: list[AgencyAdminDetailOut] = []
    for a in agencies:
        sub = subs_by_agency.get(a.id)
        items.append(AgencyAdminDetailOut(
            id=a.id,
            name=a.name,
            slug=a.slug,
            brand_color=a.brand_color,
            is_active=a.is_active,
            created_at=a.created_at,
            subscription_id=sub.id if sub else None,
            subscription_status=sub.status if sub else None,
            plan_name=sub.plan_name_snapshot if sub else None,
            member_count=counts_by_agency.get(a.id, 0),
        ))
    return PaginatedResponse[AgencyAdminDetailOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/{agency_id}", response_model=AgencyAdminDetailOut)
def get_agency(
    agency_id: uuid.UUID,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    a = db.get(Agency, agency_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    sub = db.scalar(
        select(Subscription).where(
            Subscription.agency_id == agency_id,
            Subscription.status.in_(("trial", "active", "past_due", "suspended")),
        )
    )
    member_count = db.scalar(
        select(func.count()).select_from(AgencyMembership).where(AgencyMembership.agency_id == agency_id)
    ) or 0
    return AgencyAdminDetailOut(
        id=a.id,
        name=a.name,
        slug=a.slug,
        brand_color=a.brand_color,
        is_active=a.is_active,
        created_at=a.created_at,
        subscription_id=sub.id if sub else None,
        subscription_status=sub.status if sub else None,
        plan_name=sub.plan_name_snapshot if sub else None,
        member_count=member_count,
    )


@router.patch("/{agency_id}", response_model=AgencyAdminOut)
def update_agency(
    agency_id: uuid.UUID,
    payload: AgencyUpdateRequest,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    a = db.get(Agency, agency_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    changes: dict = {}
    if payload.name is not None and payload.name != a.name:
        a.name = payload.name
        changes["name"] = payload.name
    if payload.is_active is not None and payload.is_active != a.is_active:
        a.is_active = payload.is_active
        changes["is_active"] = payload.is_active
    if payload.brand_color is not None and payload.brand_color != a.brand_color:
        a.brand_color = payload.brand_color
        changes["brand_color"] = payload.brand_color
    if changes:
        db.add(SuperAdminAuditLog(
            super_admin_id=_sa_id(request),
            action="agency.update",
            target_type="agency",
            target_id=agency_id,
            metadata_=changes,
            ip_address=_ip(request),
        ))
    db.commit()
    db.refresh(a)
    return a


@router.post("/{agency_id}/suspend", response_model=AgencyAdminOut)
def suspend_agency(
    agency_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Suspend an agency by flipping ``is_active`` to false.

    All subsequent agency-scoped requests from this agency's users will
    return 403 ("Agency is not active") via the ``get_current_agency_id``
    dependency.
    """
    a = db.get(Agency, agency_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    if not a.is_active:
        return a  # idempotent
    a.is_active = False
    db.add(SuperAdminAuditLog(
        super_admin_id=_sa_id(request),
        action="agency.suspend",
        target_type="agency",
        target_id=agency_id,
        metadata_={},
        ip_address=_ip(request),
    ))
    db.commit()
    db.refresh(a)
    return a


@router.post("/{agency_id}/activate", response_model=AgencyAdminOut)
def activate_agency(
    agency_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Re-activate a previously suspended agency."""
    a = db.get(Agency, agency_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    if a.is_active:
        return a  # idempotent
    a.is_active = True
    db.add(SuperAdminAuditLog(
        super_admin_id=_sa_id(request),
        action="agency.activate",
        target_type="agency",
        target_id=agency_id,
        metadata_={},
        ip_address=_ip(request),
    ))
    db.commit()
    db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{agency_id}/members", response_model=list[AgencyMemberOut])
def list_agency_members(
    agency_id: uuid.UUID,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    a = db.get(Agency, agency_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    rows = db.scalars(
        select(AgencyMembership).where(AgencyMembership.agency_id == agency_id)
    ).all()
    out: list[AgencyMemberOut] = []
    for m in rows:
        u = db.get(User, m.user_id)
        out.append(AgencyMemberOut(
            id=m.id,
            user_id=m.user_id,
            agency_id=m.agency_id,
            role=m.role,
            user_email=u.email if u else None,
            user_name=u.name if u else None,
            created_at=m.created_at,
        ))
    return out


@router.patch("/{agency_id}/members/{user_id}", response_model=AgencyMemberOut)
def update_member_role(
    agency_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: AgencyMemberRoleUpdate,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    m = db.scalar(
        select(AgencyMembership).where(
            AgencyMembership.user_id == user_id,
            AgencyMembership.agency_id == agency_id,
        )
    )
    if m is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    old_role = m.role
    if old_role == payload.role:
        return _membership_out(db, m)
    m.role = payload.role
    db.add(SuperAdminAuditLog(
        super_admin_id=_sa_id(request),
        action="agency.member.role_change",
        target_type="agency_membership",
        target_id=m.id,
        metadata_={"old": old_role, "new": payload.role, "user_id": str(user_id)},
        ip_address=_ip(request),
    ))
    db.commit()
    db.refresh(m)
    return _membership_out(db, m)


def _membership_out(db: Session, m: AgencyMembership) -> AgencyMemberOut:
    u = db.get(User, m.user_id)
    return AgencyMemberOut(
        id=m.id,
        user_id=m.user_id,
        agency_id=m.agency_id,
        role=m.role,
        user_email=u.email if u else None,
        user_name=u.name if u else None,
        created_at=m.created_at,
    )
