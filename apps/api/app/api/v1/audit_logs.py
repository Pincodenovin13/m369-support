"""Audit log read endpoint — agency-scoped, paginated, filterable."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...dependencies import get_current_agency_id
from ...models import AuditLog
from ...schemas import AuditLogOut, PaginatedResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Log"])


@router.get("", response_model=PaginatedResponse[AuditLogOut])
def list_audit_logs(
    agency_id=Depends(get_current_agency_id),
    db: Session = Depends(get_db),
    action: str | None = Query(default=None, max_length=100),
    target_type: str | None = Query(default=None, max_length=80),
    actor_user_id: uuid.UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List audit log entries for the current agency.

    RLS on ``audit_logs`` enforces agency isolation. Filterable by:
    ``action`` (exact), ``target_type`` (exact), ``actor_user_id`` (exact),
    ``since``/``until`` (inclusive timestamps).
    """
    stmt = select(AuditLog).where(AuditLog.agency_id == agency_id)
    count_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.agency_id == agency_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if target_type is not None:
        stmt = stmt.where(AuditLog.target_type == target_type)
        count_stmt = count_stmt.where(AuditLog.target_type == target_type)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
        count_stmt = count_stmt.where(AuditLog.actor_user_id == actor_user_id)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
        count_stmt = count_stmt.where(AuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.created_at <= until)
        count_stmt = count_stmt.where(AuditLog.created_at <= until)
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all())
    return PaginatedResponse[AuditLogOut](items=items, total=total, limit=limit, offset=offset)
