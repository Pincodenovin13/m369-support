"""Super Admin — platform settings + agency notes + audit log reader."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ....db.database import get_super_admin_db
from ....dependencies import get_super_admin_context
from ....models import (
    Agency,
    AgencyNote,
    PlatformSetting,
    SuperAdminAuditLog,
)
from ....schemas import (
    AgencyNoteCreate,
    AgencyNoteOut,
    PaginatedResponse,
    PlatformSettingOut,
    PlatformSettingUpsert,
    SuperAdminAuditLogOut,
)


# ---------------------------------------------------------------------------
# Platform Settings
# ---------------------------------------------------------------------------


settings_router = APIRouter(prefix="/super-admin/platform-settings", tags=["Super Admin — Platform Settings"])


def _sa_id(request: Request) -> uuid.UUID:
    return request.state.super_admin_id


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@settings_router.get("", response_model=list[PlatformSettingOut])
def list_settings(
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    items = list(db.scalars(select(PlatformSetting).order_by(PlatformSetting.key.asc())).all())
    return items


@settings_router.put("/{key}", response_model=PlatformSettingOut)
def upsert_setting(
    key: str,
    payload: PlatformSettingUpsert,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Upsert a platform setting by key."""
    existing = db.get(PlatformSetting, key)
    if existing is None:
        s = PlatformSetting(
            key=key,
            value=payload.value,
            value_type=payload.value_type,
            description=payload.description,
            updated_by_super_admin_id=_sa_id(request),
        )
        db.add(s)
        db.flush()
        db.add(SuperAdminAuditLog(
            super_admin_id=_sa_id(request),
            action="platform_setting.create",
            target_type="platform_setting",
            target_id=None,
            metadata_={"key": key, "value_type": payload.value_type},
            ip_address=_ip(request),
        ))
    else:
        old_value = existing.value
        existing.value = payload.value
        existing.value_type = payload.value_type
        if payload.description:
            existing.description = payload.description
        existing.updated_by_super_admin_id = _sa_id(request)
        db.add(SuperAdminAuditLog(
            super_admin_id=_sa_id(request),
            action="platform_setting.update",
            target_type="platform_setting",
            target_id=None,
            metadata_={"key": key, "old_value": old_value[:200], "new_value": payload.value[:200]},
            ip_address=_ip(request),
        ))
    db.commit()
    return db.get(PlatformSetting, key)


@settings_router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(
    key: str,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    s = db.get(PlatformSetting, key)
    if s is None:
        raise HTTPException(status_code=404, detail="Setting not found")
    db.add(SuperAdminAuditLog(
        super_admin_id=_sa_id(request),
        action="platform_setting.delete",
        target_type="platform_setting",
        target_id=None,
        metadata_={"key": key},
        ip_address=_ip(request),
    ))
    db.delete(s)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Agency Notes
# ---------------------------------------------------------------------------


notes_router = APIRouter(prefix="/super-admin/agencies/{agency_id}/notes", tags=["Super Admin — Agency Notes"])


@notes_router.get("", response_model=list[AgencyNoteOut])
def list_notes(
    agency_id: uuid.UUID,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    a = db.get(Agency, agency_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    rows = db.scalars(
        select(AgencyNote)
        .where(AgencyNote.agency_id == agency_id)
        .order_by(AgencyNote.is_pinned.desc(), AgencyNote.created_at.desc())
    ).all()
    return list(rows)


@notes_router.post("", response_model=AgencyNoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    agency_id: uuid.UUID,
    payload: AgencyNoteCreate,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    a = db.get(Agency, agency_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    note = AgencyNote(
        agency_id=agency_id,
        super_admin_id=_sa_id(request),
        note=payload.note,
        is_pinned=payload.is_pinned,
    )
    db.add(note)
    db.flush()
    db.add(SuperAdminAuditLog(
        super_admin_id=_sa_id(request),
        action="agency_note.create",
        target_type="agency_note",
        target_id=note.id,
        metadata_={"agency_id": str(agency_id), "is_pinned": payload.is_pinned},
        ip_address=_ip(request),
    ))
    db.commit()
    db.refresh(note)
    return note


@notes_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    agency_id: uuid.UUID,
    note_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    note = db.scalar(
        select(AgencyNote).where(
            AgencyNote.id == note_id,
            AgencyNote.agency_id == agency_id,
        )
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    db.add(SuperAdminAuditLog(
        super_admin_id=_sa_id(request),
        action="agency_note.delete",
        target_type="agency_note",
        target_id=note_id,
        metadata_={"agency_id": str(agency_id)},
        ip_address=_ip(request),
    ))
    db.delete(note)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Super Admin Audit Log
# ---------------------------------------------------------------------------


audit_router = APIRouter(prefix="/super-admin/audit-logs", tags=["Super Admin — Audit Log"])


@audit_router.get("", response_model=PaginatedResponse[SuperAdminAuditLogOut])
def list_sa_audit_logs(
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
    action: str | None = Query(default=None, max_length=100),
    super_admin_id: uuid.UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(SuperAdminAuditLog)
    count_stmt = select(func.count()).select_from(SuperAdminAuditLog)
    if action is not None:
        stmt = stmt.where(SuperAdminAuditLog.action == action)
        count_stmt = count_stmt.where(SuperAdminAuditLog.action == action)
    if super_admin_id is not None:
        stmt = stmt.where(SuperAdminAuditLog.super_admin_id == super_admin_id)
        count_stmt = count_stmt.where(SuperAdminAuditLog.super_admin_id == super_admin_id)
    if since is not None:
        stmt = stmt.where(SuperAdminAuditLog.created_at >= since)
        count_stmt = count_stmt.where(SuperAdminAuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(SuperAdminAuditLog.created_at <= until)
        count_stmt = count_stmt.where(SuperAdminAuditLog.created_at <= until)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(SuperAdminAuditLog.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[SuperAdminAuditLogOut](items=items, total=total, limit=limit, offset=offset)
