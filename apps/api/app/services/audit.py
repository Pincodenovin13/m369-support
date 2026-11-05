"""Audit logging helper.

Writes a row to ``audit_logs`` (agency-scoped). Designed to be called from
inside a request handler after a successful mutation. The caller is
responsible for ensuring the tenant context is set on the session so the
insert satisfies RLS (``agency_id`` matches ``app.tenant_id``).

The ``metadata`` dict is JSON-encoded by PostgreSQL (the column is JSONB).
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def write_audit(
    db: Session,
    *,
    agency_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Insert an audit log row. Does NOT commit — caller's transaction owns the commit."""
    row = AuditLog(
        agency_id=agency_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_=metadata or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(row)
    db.flush()  # make row visible in same transaction; commit is caller's job
    return row


__all__ = ["write_audit"]
