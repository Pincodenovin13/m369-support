"""FastAPI dependencies for tenant resolution and authorization."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..models import AgencyMembership, User
from ..security import decode_access_token, decode_super_admin_token
from ..tenancy.context import TenantContext


def _extract_bearer_or_cookie(request: Request, cookie_name: str = "access_token") -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        return cookie_token
    return None


def get_tenant_context(request: Request) -> TenantContext:
    """Resolve the request's tenant context from the JWT.

    Stores the context on ``request.state.tenant`` so downstream code can
    share the same object.

    Raises 401 for: missing token, expired token, wrong type, bad signature,
    unknown user. Never returns ``None``.
    """
    cached = getattr(request.state, "tenant", None)
    if cached is not None:
        return cached

    token = _extract_bearer_or_cookie(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(token)
    is_super_admin = False
    if payload is None:
        payload = decode_super_admin_token(token)
        if payload is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        is_super_admin = True

    try:
        user_id = uuid.UUID(payload["sub"]) if not is_super_admin else None
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token") from None

    agency_id_str = payload.get("agency_id")
    agency_id = uuid.UUID(agency_id_str) if agency_id_str else None

    ctx = TenantContext(
        agency_id=agency_id,
        user_id=user_id,
        is_super_admin=is_super_admin,
        raw_token=token,
    )
    request.state.tenant = ctx
    return ctx


def get_current_user(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> User:
    """Resolve and return the authenticated User. Rejects Super Admin tokens."""
    if ctx.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin tokens cannot access agency endpoints",
        )
    if ctx.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, ctx.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    # Set tenant context on the DB session so RLS policies filter automatically
    if ctx.agency_id is not None:
        db.execute(text(f"SET LOCAL app.tenant_id = '{ctx.agency_id}'"))
    return user


def get_current_agency_id(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Return the agency id of the current membership.

    For Super Admin, this raises 403 — Super Admin must use dedicated endpoints.
    """
    if ctx.is_super_admin or ctx.agency_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an agency member")
    membership = db.scalar(
        select(AgencyMembership).where(
            AgencyMembership.user_id == user.id,
            AgencyMembership.agency_id == ctx.agency_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this agency")
    return ctx.agency_id


def require_role(*allowed_roles: str):
    """Dependency factory: require the user's membership role to be in ``allowed_roles``."""

    def checker(
        ctx: TenantContext = Depends(get_tenant_context),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> uuid.UUID:
        if ctx.agency_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an agency member")
        membership = db.scalar(
            select(AgencyMembership).where(
                AgencyMembership.user_id == user.id,
                AgencyMembership.agency_id == ctx.agency_id,
            )
        )
        if membership is None or membership.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return ctx.agency_id

    return checker


def get_super_admin_context(request: Request) -> TenantContext:
    """Dependency that requires a Super Admin token."""
    token = request.cookies.get("super_admin_access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Super Admin authentication required")
    payload = decode_super_admin_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Super Admin token")
    try:
        sa_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token") from None

    ctx = TenantContext(
        agency_id=None,
        user_id=None,
        is_super_admin=True,
        raw_token=token,
    )
    request.state.tenant = ctx
    request.state.super_admin_id = sa_id
    return ctx
