"""Conversations endpoints — list, get, create, update status/assignee."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, get_current_user, require_role
from ...models import (
    AgencyMembership,
    Contact,
    Conversation,
    Team,
    User,
    Workspace,
)
from ...schemas import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    PaginatedResponse,
)
from ...services.audit import write_audit

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _check_workspace_membership(db: Session, workspace_id: uuid.UUID, agency_id: uuid.UUID) -> Workspace:
    ws = db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.agency_id == agency_id,
        )
    )
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.get("", response_model=PaginatedResponse[ConversationOut])
def list_conversations(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status", pattern=r"^(open|pending|resolved|closed)$"),
    assigned_user_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Conversation).where(Conversation.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(Conversation).where(Conversation.agency_id == agency_id)
    if workspace_id is not None:
        stmt = stmt.where(Conversation.workspace_id == workspace_id)
        count_stmt = count_stmt.where(Conversation.workspace_id == workspace_id)
    if status_ is not None:
        stmt = stmt.where(Conversation.status == status_)
        count_stmt = count_stmt.where(Conversation.status == status_)
    if assigned_user_id is not None:
        stmt = stmt.where(Conversation.assigned_user_id == assigned_user_id)
        count_stmt = count_stmt.where(Conversation.assigned_user_id == assigned_user_id)
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Conversation.created_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    return PaginatedResponse[ConversationOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: uuid.UUID,
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
):
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.agency_id == agency_id,
        )
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager", "agent")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_workspace_membership(db, payload.workspace_id, agency_id)
    # Contact must exist + belong to same workspace (composite FK enforces too)
    contact = db.scalar(
        select(Contact).where(
            Contact.id == payload.contact_id,
            Contact.workspace_id == payload.workspace_id,
            Contact.agency_id == agency_id,
        )
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found in this workspace")
    # Optional assignee validation — must be a member of this agency
    if payload.assigned_user_id is not None:
        m = db.scalar(
            select(AgencyMembership).where(
                AgencyMembership.user_id == payload.assigned_user_id,
                AgencyMembership.agency_id == agency_id,
            )
        )
        if m is None:
            raise HTTPException(status_code=400, detail="Assigned user is not a member of this agency")
    if payload.assigned_team_id is not None:
        t = db.scalar(
            select(Team).where(
                Team.id == payload.assigned_team_id,
                Team.agency_id == agency_id,
            )
        )
        if t is None:
            raise HTTPException(status_code=400, detail="Assigned team not found in this agency")
    conv = Conversation(
        workspace_id=payload.workspace_id,
        agency_id=agency_id,
        contact_id=payload.contact_id,
        assigned_user_id=payload.assigned_user_id,
        assigned_team_id=payload.assigned_team_id,
        subject=payload.subject,
        status="open",
    )
    db.add(conv)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="conversation.create",
        target_type="conversation",
        target_id=conv.id,
        metadata={"workspace_id": str(payload.workspace_id), "contact_id": str(payload.contact_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(conv)
    return conv


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager", "agent")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.agency_id == agency_id,
        )
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    changes: dict = {}
    if payload.status is not None and payload.status != conv.status:
        conv.status = payload.status
        changes["status"] = payload.status
    if payload.subject is not None and payload.subject != conv.subject:
        conv.subject = payload.subject
        changes["subject"] = payload.subject
    if payload.assigned_user_id is not None and payload.assigned_user_id != conv.assigned_user_id:
        m = db.scalar(
            select(AgencyMembership).where(
                AgencyMembership.user_id == payload.assigned_user_id,
                AgencyMembership.agency_id == agency_id,
            )
        )
        if m is None:
            raise HTTPException(status_code=400, detail="Assigned user is not a member of this agency")
        conv.assigned_user_id = payload.assigned_user_id
        changes["assigned_user_id"] = str(payload.assigned_user_id)
    if payload.assigned_team_id is not None and payload.assigned_team_id != conv.assigned_team_id:
        t = db.scalar(
            select(Team).where(
                Team.id == payload.assigned_team_id,
                Team.agency_id == agency_id,
            )
        )
        if t is None:
            raise HTTPException(status_code=400, detail="Assigned team not found in this agency")
        conv.assigned_team_id = payload.assigned_team_id
        changes["assigned_team_id"] = str(payload.assigned_team_id)
    if changes:
        write_audit(
            db,
            agency_id=agency_id,
            actor_user_id=user.id,
            action="conversation.update",
            target_type="conversation",
            target_id=conv.id,
            metadata=changes,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    db.commit()
    db.refresh(conv)
    return conv
