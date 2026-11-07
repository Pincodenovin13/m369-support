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

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
from ...services.rate_limit import (
    assert_redis_available_or_fail_closed,
    check_login_rate_limit as check_sa_login_rate_limit,
)
from ...slugs import unique_slug
from ...tenancy.context import set_tenant_context

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

    Both tokens also carry ``tver`` (token_version) — the request dependency
    and refresh endpoint compare this against ``users.token_version`` to
    enforce server-side session revocation.
    """
    access = create_access_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(agency_id),
        token_version=user.token_version,
    )
    refresh = create_refresh_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(agency_id),
        token_version=user.token_version,
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
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Register the first agency + its owner.

    Open only if no agency exists. After the first agency, registration is
    closed — a Super Admin is required to create additional agencies.

    Security flow:
      1. Rate-limit check (per-IP registration throttle).
      2. Acquire PostgreSQL advisory lock (prevents concurrent registration).
      3. Call is_initial_agency_registration_open() (SECURITY DEFINER, bypasses
         RLS to check global agency count).
      4. If open: generate agency UUID, set tenant context (SET LOCAL
         app.tenant_id), then INSERT agency + user + membership.
      5. If closed: return 403.
    """
    # 1. Rate-limit: per-IP registration throttle.
    _check_agency_register_rate_limit(request)

    # 2. Advisory lock — prevents concurrent registration across connections.
    #    The lock is transaction-scoped (released on commit/rollback).
    db.execute(text("SELECT pg_advisory_xact_lock(3690369036901)"))

    # 3. Global registration check via SECURITY DEFINER function.
    #    This function bypasses RLS (owned by m369_registration_guard with
    #    BYPASSRLS) so it sees ALL agencies, not just those visible to
    #    the current tenant context.
    is_open = db.scalar(text("SELECT public.is_initial_agency_registration_open()"))
    if not is_open:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is closed. Ask a Super Admin to create a new agency.",
        )

    email = payload.email.lower()
    # Check for existing user with same email (users table has no RLS)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A user with that email already exists")

    # 4. Generate agency UUID explicitly, then set tenant context BEFORE INSERT.
    #    RLS requires app.tenant_id to match the row being inserted.
    agency_id = uuid.uuid4()
    set_tenant_context(db, agency_id)

    agency = Agency(
        id=agency_id,
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
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Login with email + password. Issues access + refresh tokens.

    If the user belongs to multiple agencies, ``agency_id`` must be specified.
    If omitted, returns 400 with a list of available agencies.
    """
    # Rate-limit: per-IP + per-account (independent from Super Admin limits).
    _check_agency_login_rate_limit(request, payload.email)

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

    The ``tver`` claim in the refresh token is compared against
    ``users.token_version``. If the user has logged out (bumped
    token_version), the refresh token is rejected with 401.

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

    # Verify token_version — rejects revoked refresh tokens
    token_version = decoded.get("tver")
    if (
        isinstance(token_version, bool)
        or not isinstance(token_version, int)
        or token_version < 0
        or token_version != user.token_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

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
        token_version=user.token_version,
    )
    new_refresh = create_refresh_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(token_agency_id),
        token_version=user.token_version,
    )
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=get_settings().jwt_access_token_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout — atomically bump ``token_version`` to revoke all sessions.

    After this call, all previously-issued access AND refresh tokens for
    this user are invalid (their ``tver`` claim no longer matches
    ``users.token_version``).

    The bump is done via an atomic SQL UPDATE with RETURNING — no
    Python read-modify-write. This prevents concurrent logout requests
    from racing.

    Cookie deletion headers are set on the same Response object that is
    returned — not on a newly constructed Response (which would lose
    the Set-Cookie headers).
    """
    from sqlalchemy import update

    result = db.execute(
        update(User)
        .where(User.id == user.id)
        .values(token_version=User.token_version + 1)
        .returning(User.token_version)
    )
    new_version = result.scalar_one()
    db.commit()

    # Delete cookies on the SAME response — not a new Response
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserWithMembershipsOut)
def me(user: User = Depends(get_current_user)):
    """Return the current user with all their agency memberships."""
    return user


# ---------------------------------------------------------------------------
# Agency rate-limit helpers (separate namespaces from Super Admin)
# ---------------------------------------------------------------------------


def _check_agency_login_rate_limit(request: Request, email: str) -> None:
    """Per-IP + per-account rate limit for agency /auth/login.

    Uses separate Redis key namespaces from Super Admin:
      agency_login:ip:<sha256(ip)[:16]>
      agency_login:acct:<sha256(email_lower)[:16]>
    """
    from ...services.rate_limit import (
        get_client_ip,
        get_redis_client,
        _check_limit,
        _ip_key,
        _account_key,
    )

    s = get_settings()
    if not s.rate_limit_enabled:
        return

    client = get_redis_client()
    if client is None:
        if s.environment == "production" and s.sa_rate_limit_fail_closed_in_prod:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter unavailable",
            )
        return

    ip = get_client_ip(request)
    ip_k = f"agency_login:{_ip_key(ip)}"
    acct_k = f"agency_login:{_account_key(email)}"

    ip_limit, ip_window = _parse_limit(s.agency_login_ip_rate_limit)
    acct_limit, acct_window = _parse_limit(s.agency_login_account_rate_limit)

    try:
        ip_ok, _ = _check_limit(client, ip_k, ip_limit, ip_window)
        acct_ok, _ = _check_limit(client, acct_k, acct_limit, acct_window)
    except Exception:
        if s.environment == "production" and s.sa_rate_limit_fail_closed_in_prod:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter backend unreachable",
            ) from None
        return

    if not ip_ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts from this IP. Retry after {ip_window}s.",
            headers={"Retry-After": str(ip_window)},
        )
    if not acct_ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts for this account. Retry after {acct_window}s.",
            headers={"Retry-After": str(acct_window)},
        )


def _check_agency_register_rate_limit(request: Request) -> None:
    """Per-IP rate limit for agency /auth/register."""
    from ...services.rate_limit import (
        get_client_ip,
        get_redis_client,
        _check_limit,
        _ip_key,
    )

    s = get_settings()
    if not s.rate_limit_enabled:
        return

    client = get_redis_client()
    if client is None:
        if s.environment == "production" and s.sa_rate_limit_fail_closed_in_prod:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter unavailable",
            )
        return

    ip = get_client_ip(request)
    ip_k = f"agency_register:{_ip_key(ip)}"

    limit_n, window_s = _parse_limit(s.agency_register_ip_rate_limit)

    try:
        ip_ok, _ = _check_limit(client, ip_k, limit_n, window_s)
    except Exception:
        if s.environment == "production" and s.sa_rate_limit_fail_closed_in_prod:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter backend unreachable",
            ) from None
        return

    if not ip_ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration attempts. Retry after {window_s}s.",
            headers={"Retry-After": str(window_s)},
        )


def _parse_limit(limit_str: str) -> tuple[int, int]:
    """Parse 'N/minute' → (N, 60)."""
    try:
        parts = limit_str.split("/")
        n = int(parts[0])
        unit = parts[1] if len(parts) > 1 else "minute"
        seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(unit, 60)
        return n, seconds
    except (ValueError, IndexError):
        return 30, 60
