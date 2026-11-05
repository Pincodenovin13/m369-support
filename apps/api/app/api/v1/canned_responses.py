"""Canned Responses endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, get_current_user, require_role
from ...models import CannedResponse, User, Workspace
from ...schemas import (
    CannedResponseCreate,
    CannedResponseOut,
    CannedResponseUpdate,
    PaginatedResponse,
)
from ...services.audit import write_audit

router = APIRouter(prefix="/canned-responses", tags=["Canned Responses"])


@router.get("", response_model=PaginatedResponse[CannedResponseOut])
def list_canned_responses(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(CannedResponse).where(CannedResponse.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(CannedResponse).where(CannedResponse.agency_id == agency_id)
    if workspace_id is not None:
        stmt = stmt.where(CannedResponse.workspace_id == workspace_id)
        count_stmt = count_stmt.where(CannedResponse.workspace_id == workspace_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(CannedResponse.shortcut.ilike(like) | CannedResponse.content.ilike(like))
        count_stmt = count_stmt.where(CannedResponse.shortcut.ilike(like) | CannedResponse.content.ilike(like))
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(CannedResponse.shortcut.asc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[CannedResponseOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=CannedResponseOut, status_code=status.HTTP_201_CREATED)
def create_canned_response(
    payload: CannedResponseCreate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = db.scalar(
        select(Workspace).where(
            Workspace.id == payload.workspace_id,
            Workspace.agency_id == agency_id,
        )
    )
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    existing = db.scalar(
        select(CannedResponse).where(
            CannedResponse.workspace_id == payload.workspace_id,
            CannedResponse.shortcut == payload.shortcut,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Shortcut already exists in this workspace")
    cr = CannedResponse(
        workspace_id=payload.workspace_id,
        agency_id=agency_id,
        shortcut=payload.shortcut,
        content=payload.content,
    )
    db.add(cr)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="canned_response.create",
        target_type="canned_response",
        target_id=cr.id,
        metadata={"workspace_id": str(payload.workspace_id), "shortcut": payload.shortcut},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(cr)
    return cr


@router.patch("/{cr_id}", response_model=CannedResponseOut)
def update_canned_response(
    cr_id: uuid.UUID,
    payload: CannedResponseUpdate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cr = db.scalar(
        select(CannedResponse).where(CannedResponse.id == cr_id, CannedResponse.agency_id == agency_id)
    )
    if cr is None:
        raise HTTPException(status_code=404, detail="Canned response not found")
    if payload.content is not None and payload.content != cr.content:
        cr.content = payload.content
        write_audit(
            db,
            agency_id=agency_id,
            actor_user_id=user.id,
            action="canned_response.update",
            target_type="canned_response",
            target_id=cr.id,
            metadata={"content_changed": True},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    db.commit()
    db.refresh(cr)
    return cr


@router.delete("/{cr_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_canned_response(
    cr_id: uuid.UUID,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cr = db.scalar(
        select(CannedResponse).where(CannedResponse.id == cr_id, CannedResponse.agency_id == agency_id)
    )
    if cr is None:
        raise HTTPException(status_code=404, detail="Canned response not found")
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="canned_response.delete",
        target_type="canned_response",
        target_id=cr.id,
        metadata={"shortcut": cr.shortcut},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.delete(cr)
    db.commit()
    return None
