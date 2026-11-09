"""Workspace endpoints — create and list workspaces within the current agency."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, require_role
from ...models import Workspace
from ...schemas import WorkspaceCreate, WorkspaceOut

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
):
    """List all workspaces in the current agency.

    RLS on ``workspaces`` ensures only the current agency's rows are visible.
    """
    return db.scalars(
        select(Workspace).where(Workspace.agency_id == agency_id).order_by(Workspace.created_at.desc())
    ).all()


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    agency_id=Depends(require_role("owner", "admin")),
    db: Session = Depends(get_db),
):
    """Create a workspace within the current agency.

    Composite unique constraint ``uq_workspaces_agency_slug`` prevents duplicate
    slugs within an agency. RLS would also block cross-agency insert attempts.
    """
    existing = db.scalar(
        select(Workspace).where(
            Workspace.agency_id == agency_id,
            Workspace.slug == payload.slug,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="That slug is already in use in this agency")

    workspace = Workspace(
        agency_id=agency_id,
        name=payload.name,
        slug=payload.slug,
        timezone=payload.timezone,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace
