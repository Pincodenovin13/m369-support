"""Contacts endpoints — list, get, create, update.

Workspace-scoped within the current agency. Cross-workspace reads inside
the same agency are permitted (a manager may see all contacts in the
agency); cross-agency reads are blocked by RLS.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, get_current_user, require_role
from ...models import Contact, User, Workspace
from ...schemas import (
    ContactCreate,
    ContactOut,
    ContactUpdate,
    PaginatedResponse,
)
from ...services.audit import write_audit

router = APIRouter(prefix="/contacts", tags=["Contacts"])


def _get_workspace_or_404(db: Session, workspace_id: uuid.UUID, agency_id: uuid.UUID) -> Workspace:
    ws = db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.agency_id == agency_id,
        )
    )
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.get("", response_model=PaginatedResponse[ContactOut])
def list_contacts(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List contacts in the current agency.

    RLS on ``contacts`` already filters to the current agency; we add an
    explicit ``agency_id`` predicate to give the planner a tight index seek.
    """
    stmt = select(Contact).where(Contact.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(Contact).where(Contact.agency_id == agency_id)
    if workspace_id is not None:
        stmt = stmt.where(Contact.workspace_id == workspace_id)
        count_stmt = count_stmt.where(Contact.workspace_id == workspace_id)
    if search:
        like = f"%{search}%"
        cond = (
            Contact.name.ilike(like)
            | Contact.email.ilike(like)
            | Contact.phone.ilike(like)
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Contact.created_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    return PaginatedResponse[ContactOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: uuid.UUID,
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
):
    contact = db.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.agency_id == agency_id)
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager", "agent")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_workspace_or_404(db, payload.workspace_id, agency_id)
    # Uniqueness on (workspace_id, email) — only enforced if email is set
    if payload.email:
        existing = db.scalar(
            select(Contact).where(
                Contact.workspace_id == payload.workspace_id,
                Contact.email == payload.email.lower(),
            )
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already exists in this workspace")
    contact = Contact(
        workspace_id=payload.workspace_id,
        agency_id=agency_id,
        email=payload.email.lower() if payload.email else None,
        phone=payload.phone,
        name=payload.name,
    )
    db.add(contact)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="contact.create",
        target_type="contact",
        target_id=contact.id,
        metadata={"workspace_id": str(payload.workspace_id), "email": payload.email or None},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(contact)
    return contact


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager", "agent")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.agency_id == agency_id)
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    changes: dict = {}
    if payload.email is not None and payload.email != contact.email:
        # email change must remain unique within workspace
        existing = db.scalar(
            select(Contact).where(
                Contact.workspace_id == contact.workspace_id,
                Contact.email == payload.email.lower(),
                Contact.id != contact.id,
            )
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already exists in this workspace")
        contact.email = payload.email.lower() or None
        changes["email"] = contact.email
    if payload.phone is not None:
        contact.phone = payload.phone
        changes["phone"] = payload.phone
    if payload.name is not None:
        contact.name = payload.name
        changes["name"] = payload.name
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="contact.update",
        target_type="contact",
        target_id=contact.id,
        metadata=changes,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(contact)
    return contact
