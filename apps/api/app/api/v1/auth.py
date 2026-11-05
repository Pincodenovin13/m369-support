"""Authentication endpoints.

Phase 1 implements:
    - POST /api/v1/auth/register  — first-agency registration
    - POST /api/v1/auth/login     — password login, issues agency JWT pair
    - POST /api/v1/auth/refresh   — exchange refresh token for new access token
    - POST /api/v1/auth/logout    — client-side cookie clear
    - GET  /api/v1/auth/me        — current user + memberships

Registration is gated: if any agency exists, registration is closed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
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
    access = create_access_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(agency_id),
    )
    refresh = create_refresh_token(subject=str(user.id), token_type="agency")
    return access, refresh


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
    """Login with email + password. Issues access + refresh tokens."""
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    membership = db.scalar(
        select(AgencyMembership).where(AgencyMembership.user_id == user.id)
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="User has no agency membership")

    agency = db.get(Agency, membership.agency_id)
    if agency is None or not agency.is_active:
        raise HTTPException(status_code=403, detail="Agency is not active")

    access, refresh = _issue_tokens_for(user, agency.id)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    _set_auth_cookies(response, access, refresh)
    return user


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for a new access token."""
    decoded = decode_refresh_token(payload.refresh_token, expected_scope="agency")
    if decoded is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        user_id = uuid.UUID(decoded["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed refresh token") from None

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    membership = db.scalar(select(AgencyMembership).where(AgencyMembership.user_id == user.id))
    if membership is None:
        raise HTTPException(status_code=403, detail="User has no agency membership")

    access = create_access_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(membership.agency_id),
    )
    new_refresh = create_refresh_token(subject=str(user.id), token_type="agency")
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=get_settings().jwt_access_token_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """Clear the auth cookies.

    Note: JWT revocation requires a server-side denylist (Phase 2).
    """
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserWithMembershipsOut)
def me(user: User = Depends(get_current_user)):
    """Return the current user with all their agency memberships."""
    return user
