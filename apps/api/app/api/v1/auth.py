"""Authentication endpoints.

Phase 1 implements:
    - POST /api/v1/auth/register  — first-agency registration
    - POST /api/v1/auth/login     — password login, issues agency JWT pair
    - POST /api/v1/auth/refresh   — exchange refresh token for new access token
    - POST /api/v1/auth/logout    — client-side cookie clear
    - GET  /api/v1/auth/me        — current user + memberships

Registration is gated: if any agency exists, registration is closed.

Login and Refresh no longer silently select the first membership.
Login requires an explicit ``agency_id`` when the user belongs to multiple
agencies. Refresh revalidates the ``agency_id`` stored in the refresh token
against an active membership.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...db.database import get_db
from ...dependencies import get_current_user
from ...models import Agency, AgencyMembership, User
from ...schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserWithMembershipsOut,
)
from ...security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from ...slugs import unique_slug

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    s = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=s.jwt_access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=s.jwt_refresh_token_days * 86400,
        path="/api/v1/auth",
    )


def _issue_tokens_for(user: User, agency_id: uuid.UUID) -> tuple[str, str]:
    """Issue access + refresh tokens scoped to ``agency_id``.

    Both tokens carry ``agency_id`` — the refresh token is bound to the
    agency selected at login and cannot be used to switch agencies.
    """
    access = create_access_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(agency_id),
    )
    refresh = create_refresh_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(agency_id),
    )
    return access, refresh


def _resolve_membership(
    db: Session,
    user: User,
    requested_agency_id: uuid.UUID | None,
) -> tuple[uuid.UUID, str]:
    """Resolve which membership to use for login.

    Uses the ``get_user_memberships_for_login`` SECURITY DEFINER function
    (migration 0003) to read memberships/agency status without RLS —
    needed because tenant_id is not yet set during login.

    Returns: (agency_id, role)
    """
    rows = db.execute(
        text("SELECT agency_id, is_active, role FROM get_user_memberships_for_login(:uid)"),
        {"uid": str(user.id)},
    ).all()

    if len(rows) == 0:
        raise HTTPException(status_code=403, detail="User has no agency membership")

    # Filter to active agencies
    active = [(r.agency_id, r.role) for r in rows if r.is_active]
    if len(active) == 0:
        raise HTTPException(status_code=403, detail="Agency is not active")

    if len(active) == 1:
        agency_id, role = active[0]
        if requested_agency_id is not None and agency_id != requested_agency_id:
            raise HTTPException(status_code=403, detail="User is not a member of the requested agency")
        return agency_id, role

    # Multiple active memberships — require explicit selection
    if requested_agency_id is None:
        available = [
            {"agency_id": str(aid), "role": role}
            for aid, role in active
        ]
        raise HTTPException(
            status_code=400,
            detail={
                "message": "User belongs to multiple agencies. Specify agency_id.",
                "available_agencies": available,
            },
        )

    # Find the requested agency in active memberships
    for aid, role in active:
        if aid == requested_agency_id:
            return aid, role

    raise HTTPException(status_code=403, detail="User is not a member of the requested agency")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Register the first agency + its owner.

    Open only if no agency exists. After the first agency, registration is
    closed — a Super Admin (Phase 9+) is required to create additional agencies.
    """
    existing_agency = db.scalar(select(Agency).limit(1))
    if existing_agency is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is closed. Ask a Super Admin to create a new agency.",
        )

    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A user with that email already exists")

    agency = Agency(
        name=payload.agency_name.strip(),
        slug=unique_slug(db, Agency, "slug", payload.agency_name.strip()),
    )
    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    db.add_all([agency, user, membership])
    db.commit()
    db.refresh(user)

    access, refresh = _issue_tokens_for(user, agency.id)
    _set_auth_cookies(response, access, refresh)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Login with email + password. Issues access + refresh tokens.

    If the user belongs to multiple agencies, ``agency_id`` must be specified.
    If omitted, returns 400 with a list of available agencies.
    """
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    membership, agency = _resolve_membership(db, user, payload.agency_id)
    agency_id = membership

    access, refresh = _issue_tokens_for(user, agency_id)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    _set_auth_cookies(response, access, refresh)
    return user


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for a new access token.

    The ``agency_id`` is read **only** from the signed refresh token —
    never from the request body. This prevents switching agencies via
    refresh.

    The token's agency_id is validated against:
    - User is active
    - User still has an active membership in that agency
    - The agency is still active
    """
    decoded = decode_refresh_token(payload.refresh_token, expected_scope="agency")
    if decoded is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        user_id = uuid.UUID(decoded["sub"])
        token_agency_id = uuid.UUID(decoded["agency_id"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed refresh token") from None

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Revalidate membership using the SECURITY DEFINER function
    rows = db.execute(
        text("SELECT agency_id, is_active, role FROM get_user_memberships_for_login(:uid)"),
        {"uid": str(user.id)},
    ).all()

    # Find the membership matching the token's agency_id
    matching = [r for r in rows if r.agency_id == token_agency_id and r.is_active]
    if not matching:
        raise HTTPException(
            status_code=403,
            detail="Membership for this agency is no longer active or has been removed",
        )

    access = create_access_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(token_agency_id),
    )
    new_refresh = create_refresh_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(token_agency_id),
    )
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=get_settings().jwt_access_token_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """Clear the auth cookies.

    SECURITY LIMITATION: This does NOT revoke the JWT server-side. The token
    remains valid until its natural expiry. Server-side revocation requires
    a Redis-backed denylist (planned for Phase 2). Clients must not rely on
    logout alone for session termination in high-security scenarios.
    """
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserWithMembershipsOut)
def me(user: User = Depends(get_current_user)):
    """Return the current user with all their agency memberships."""
    return user
