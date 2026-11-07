"""FastAPI dependencies for tenant resolution and authorization."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db.database import get_db, get_super_admin_db
from ..models import Agency, AgencyMembership, SuperAdmin, User
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
        if is_super_admin:
            user_id = None
            agency_id = None
        else:
            raw_user_id = payload.get("sub")
            raw_agency_id = payload.get("agency_id")

            if not isinstance(raw_user_id, str):
                raise ValueError("Invalid subject")

            if not isinstance(raw_agency_id, str):
                raise ValueError("Missing or invalid agency_id")

            user_id = uuid.UUID(raw_user_id)
            agency_id = uuid.UUID(raw_agency_id)

    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
        ) from None

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
    """Resolve and return the authenticated User. Rejects Super Admin tokens.

    Also verifies ``token_version`` — if the user has logged out (bumped
    token_version), the access token's ``tver`` claim no longer matches
    and the request is rejected with 401.
    """
    if ctx.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin tokens cannot access agency endpoints",
        )
    if ctx.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Decode the raw token to extract tver claim
    payload = decode_access_token(ctx.raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.get(User, ctx.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Verify token_version — rejects revoked access tokens
    token_version = payload.get("tver")
    if (
        isinstance(token_version, bool)
        or not isinstance(token_version, int)
        or token_version < 0
        or token_version != user.token_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked",
        )

    # Set tenant context on the DB session so RLS policies filter automatically.
    # We also stash it in session.info so the after_begin event listener can
    # re-issue SET LOCAL after every commit/rollback (RLS GUC persistence).
    if ctx.agency_id is not None:
        db.info["tenant_id"] = str(ctx.agency_id)
        db.execute(text(f"SET LOCAL app.tenant_id = '{ctx.agency_id}'"))
    return user


def get_current_agency_id(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Return the agency id of the current membership.

    Verifies:
    - User is not a Super Admin (403 if so)
    - Token has agency_id (403 if not)
    - User has an active membership in that agency (403 if not)
    - Agency is active (403 if deactivated)
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
    # Verify the agency is still active
    agency = db.get(Agency, ctx.agency_id)
    if agency is None or not agency.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agency is not active")
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
        # Verify the agency is still active
        agency = db.get(Agency, ctx.agency_id)
        if agency is None or not agency.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agency is not active")
        return ctx.agency_id

    return checker


def get_super_admin_context(
    request: Request,
    db: Session = Depends(get_super_admin_db),
) -> TenantContext:
    """Dependency that requires a valid Super Admin token AND an active account.

    Per-request account validation (Phase 1 Security Hardening / Package A):

    1. Token must decode with the super_admin signing key.
    2. ``sub`` must be a valid UUID identifying a real SuperAdmin row.
    3. ``tver`` claim must equal the DB row's ``token_version`` — this is
       the server-side session revocation mechanism. Logout-all bumps
       ``token_version``; all previously-issued tokens become invalid.
    4. ``is_active`` must be true — deactivated accounts cannot use any
       Super Admin endpoint (not just ``/me``).
    5. On ANY database error, the request is REJECTED (401) — fail-closed.
       A token is never accepted when we cannot verify its account state.

    The DB read uses the dedicated ``super_admin_engine`` (m369_sa_runner,
    BYPASSRLS) so the lookup is not subject to tenant RLS policies — the
    ``super_admins`` table is global and has no RLS policy by design.
    """
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

    # Extract tver claim — fail-closed if absent (legacy tokens without tver
    # are rejected; only tokens issued after this hardening are valid).
    tver_claim = payload.get("tver")

    if (
        isinstance(tver_claim, bool)
        or not isinstance(tver_claim, int)
        or tver_claim < 0
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token version",
        )

    # Per-request account state check. FAIL-CLOSED on any DB error.
    try:
        admin = db.get(SuperAdmin, sa_id)
    except Exception:
        # DB error → 401, never accept token. Audit-free (we cannot write
        # audit logs when the DB is unavailable).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify account state",
        ) from None

    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is deactivated")
    # Server-side session revocation: tver claim must match DB row.
    if admin.token_version != tver_claim:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    ctx = TenantContext(
        agency_id=None,
        user_id=None,
        is_super_admin=True,
        raw_token=token,
    )
    request.state.tenant = ctx
    request.state.super_admin_id = sa_id
    request.state.super_admin_token_version = tver_claim
    return ctx
