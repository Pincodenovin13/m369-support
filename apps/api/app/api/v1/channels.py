"""Channels endpoints — list, create, update, delete.

Phase 1 supports 'widget' channel type (other types are validated by the
CHECK constraint but no credential schema is implemented yet).
"""
from __future__ import annotations

import uuid
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id, get_current_user, require_role
from ...models import Channel, User, Workspace
from ...schemas import (
    ChannelCreate,
    ChannelOut,
    ChannelUpdate,
    PaginatedResponse,
)
from ...services.audit import write_audit

router = APIRouter(prefix="/channels", tags=["Channels"])


def _generate_public_id() -> str:
    """32-char URL-safe public id for widget embed."""
    return secrets.token_urlsafe(24)


@router.get("", response_model=PaginatedResponse[ChannelOut])
def list_channels(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Channel).where(Channel.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(Channel).where(Channel.agency_id == agency_id)
    if workspace_id is not None:
        stmt = stmt.where(Channel.workspace_id == workspace_id)
        count_stmt = count_stmt.where(Channel.workspace_id == workspace_id)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(Channel.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[ChannelOut](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def create_channel(
    payload: ChannelCreate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin")),
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
        select(Channel).where(
            Channel.workspace_id == payload.workspace_id,
            Channel.type == payload.type,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"A {payload.type} channel already exists in this workspace")
    channel = Channel(
        workspace_id=payload.workspace_id,
        agency_id=agency_id,
        type=payload.type,
        name=payload.name,
        config=payload.config,
        is_enabled=payload.is_enabled,
        public_id=_generate_public_id() if payload.type == "widget" else None,
    )
    db.add(channel)
    db.flush()
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="channel.create",
        target_type="channel",
        target_id=channel.id,
        metadata={"workspace_id": str(payload.workspace_id), "type": payload.type},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(channel)
    return channel


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(
    channel_id: uuid.UUID,
    payload: ChannelUpdate,
    request: Request,
    agency_id=Depends(require_role("owner", "admin")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.scalar(
        select(Channel).where(Channel.id == channel_id, Channel.agency_id == agency_id)
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    changes: dict = {}
    if payload.name is not None and payload.name != channel.name:
        channel.name = payload.name
        changes["name"] = payload.name
    if payload.config is not None and payload.config != channel.config:
        channel.config = payload.config
        changes["config"] = True  # don't log potentially sensitive config
    if payload.is_enabled is not None and payload.is_enabled != channel.is_enabled:
        channel.is_enabled = payload.is_enabled
        changes["is_enabled"] = payload.is_enabled
    if changes:
        write_audit(
            db,
            agency_id=agency_id,
            actor_user_id=user.id,
            action="channel.update",
            target_type="channel",
            target_id=channel.id,
            metadata=changes,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: uuid.UUID,
    request: Request,
    agency_id=Depends(require_role("owner", "admin")),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.scalar(
        select(Channel).where(Channel.id == channel_id, Channel.agency_id == agency_id)
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    write_audit(
        db,
        agency_id=agency_id,
        actor_user_id=user.id,
        action="channel.delete",
        target_type="channel",
        target_id=channel.id,
        metadata={"type": channel.type, "workspace_id": str(channel.workspace_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.delete(channel)
    db.commit()
    return None
