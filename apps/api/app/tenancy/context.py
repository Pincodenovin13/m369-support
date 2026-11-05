"""Tenant context: resolve, set, and enforce agency ownership per request.

The flow:

1. The ``TenantContextMiddleware`` reads the JWT from the cookie or
   ``Authorization`` header, decodes it via the appropriate decoder, and
   stores the resulting ``TenantContext`` in ``request.state.tenant``.

2. The ``get_tenant_context`` FastAPI dependency reads it back.

3. ``set_tenant_context(db, agency_id)`` issues ``SET LOCAL app.tenant_id``
   on the underlying connection. RLS policies on tenant-owned tables filter
   by this setting. ``SET LOCAL`` scopes the variable to the transaction.

4. There is NO bypass mechanism in RLS policies. The previous
   ``app.bypass_rls`` GUC was a security vulnerability — any database user
   could ``SET LOCAL`` it. Super Admin operations use a separate database
   connection with a role that has the BYPASSRLS attribute (see
   ``db/database.py`` → ``super_admin_engine``).

5. ``assert_tenant_owned(record, agency_id)`` is the application-level
   ownership check. It is fail-closed: a record without ``agency_id`` is
   rejected, not silently returned.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session


TENANT_GUC = "app.tenant_id"


@dataclass(frozen=True)
class TenantContext:
    """The tenant scope of a request, derived from the JWT."""

    agency_id: uuid.UUID | None
    user_id: uuid.UUID | None
    is_super_admin: bool
    raw_token: str

    def require_agency_id(self) -> uuid.UUID:
        """Return the agency id or raise 401 — there is no anonymous tenant access."""
        if self.agency_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The session is not bound to an agency",
            )
        return self.agency_id

    def scoped_to(self, agency_id: uuid.UUID) -> "TenantContext":
        """Return a new context scoped to ``agency_id`` (used by Super Admin)."""
        return TenantContext(
            agency_id=agency_id,
            user_id=self.user_id,
            is_super_admin=self.is_super_admin,
            raw_token=self.raw_token,
        )


# ---------------------------------------------------------------------------
# Connection-level tenant context (RLS)
# ---------------------------------------------------------------------------


def set_tenant_context(db: Session, agency_id: uuid.UUID | str) -> None:
    """Issue ``SET LOCAL app.tenant_id = '<uuid>'`` on the connection.

    RLS policies on tenant-owned tables read this variable in their ``USING``
    and ``WITH CHECK`` clauses. ``SET LOCAL`` ensures the variable is reset at
    the end of the transaction, so a pooled connection cannot leak tenant scope
    to the next request.
    """
    db.execute(text(f"SET LOCAL {TENANT_GUC} = '{uuid.UUID(str(agency_id))}'"))


def clear_tenant_context(db: Session) -> None:
    """Reset the connection-level tenant variable (defensive)."""
    db.execute(text(f"RESET {TENANT_GUC}"))


# ---------------------------------------------------------------------------
# Application-level ownership check (defense-in-depth)
# ---------------------------------------------------------------------------


T = TypeVar("T")


class TenantOwned:
    """Protocol-style marker: any model exposing ``agency_id``."""

    agency_id: uuid.UUID | None


def assert_tenant_owned(record: Any, agency_id: uuid.UUID, *, agency_attr: str = "agency_id") -> None:
    """Fail-closed ownership check for a tenant-scoped row.

    Raises 404 (not 403) on mismatch: a tenant that does not own a row must
    learn nothing about it, not even that it exists.
    """
    record_agency = getattr(record, agency_attr, None)
    if record_agency is None or record_agency != agency_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
