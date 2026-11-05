"""Teams endpoints — list, create, list members, add/remove member."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, get_current_user, require_role
from ...models import AgencyMembership, Team, TeamMembership, User, Workspace
from ...schemas import (
    PaginatedResponse,
    TeamCreate,
    TeamMembershipAdd,
    TeamMembershipOut,
    TeamOut,
)
from ...services.audit import write_audit

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=PaginatedResponse[TeamOut])
def list_teams(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Team).where(Team.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(Team).where(Team.agency_id == agency_id)
    if workspace_id is not None:
        stmt = stmt.where(Team.workspace_id == workspace_id)
        count_stmt = count_stmt.where(Team.workspace_id == workspace_id)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(Team.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[TeamOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
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
    # unique name within workspace
    existing = db.scalar(
        select(Team).where(
            Team.workspace_id == payload.workspace_id,
            Team.name == payload.name,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Team name already exists in this workspace")
    team = Team(workspace_id=payload.workspace_id, agency_id=agency_id, name=payload.name)
    db.add(team)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="team.create",
        target_type="team",
        target_id=team.id,
        metadata={"workspace_id": str(payload.workspace_id), "name": payload.name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(team)
    return team


@router.get("/{team_id}/members", response_model=list[TeamMembershipOut])
def list_team_members(
    team_id: uuid.UUID,
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
):
    team = db.scalar(
        select(Team).where(Team.id == team_id, Team.agency_id == agency_id)
    )
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    rows = db.scalars(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.agency_id == agency_id,
        )
    ).all()
    return list(rows)


@router.post("/{team_id}/members", response_model=TeamMembershipOut, status_code=status.HTTP_201_CREATED)
def add_team_member(
    team_id: uuid.UUID,
    payload: TeamMembershipAdd,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.scalar(
        select(Team).where(Team.id == team_id, Team.agency_id == agency_id)
    )
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    # User must be a member of this agency
    membership = db.scalar(
        select(AgencyMembership).where(
            AgencyMembership.user_id == payload.user_id,
            AgencyMembership.agency_id == agency_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=400, detail="User is not a member of this agency")
    existing = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == payload.user_id,
            TeamMembership.agency_id == agency_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="User is already a member of this team")
    tm = TeamMembership(
        team_id=team_id,
        user_id=payload.user_id,
        agency_id=agency_id,
    )
    db.add(tm)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="team.member.add",
        target_type="team",
        target_id=team_id,
        metadata={"user_id": str(payload.user_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(tm)
    return tm


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    agency_id=Depends(require_role("owner", "admin", "manager")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tm = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
            TeamMembership.agency_id == agency_id,
        )
    )
    if tm is None:
        raise HTTPException(status_code=404, detail="Team membership not found")
    db.delete(tm)
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="team.member.remove",
        target_type="team",
        target_id=team_id,
        metadata={"user_id": str(user_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return None
