"""Super Admin auth — separate from agency auth.

Separate JWT signing key, separate cookie name, separate audit log.

Phase 1 Security Hardening / Package A adds:
  - Per-request account-state validation (in ``get_super_admin_context``)
  - Server-side session revocation via ``token_version``
  - Brute-force protection (atomic counter, lockout, no email leak)
  - Rate limiting on login (slowapi, fail-closed in production)
  - Real TOTP-based MFA (setup → enable → 2-step login → replay-protected verify)
  - Recovery codes (Argon2id-hashed, single-use)
  - Logout bumps ``token_version`` (logout-all semantics)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ....core.config import get_settings
from ....db.database import get_db, get_super_admin_db
from ....dependencies import get_super_admin_context
from ....models import SuperAdmin, SuperAdminAuditLog, SuperAdminMFAChallenge
from ....schemas import (
    SuperAdminLoginRequest,
    SuperAdminMFAEnableRequest,
    SuperAdminMFADisableRequest,
    SuperAdminMFARequiredResponse,
    SuperAdminMFASetupResponse,
    SuperAdminOut,
    SuperAdminRecoveryCodesOut,
    SuperAdminVerifyMFARequest,
)
from ....security import (
    create_access_token,
    decode_mfa_challenge_token,
    verify_password,
)
from ....services import sa_auth
from ....services.rate_limit import assert_redis_available_or_fail_closed

router = APIRouter(prefix="/super-admin/auth", tags=["Super Admin Authentication"])


def _set_super_admin_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        key="super_admin_access_token",
        value=token,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=s.jwt_access_token_minutes * 60,
        path="/",
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _generic_login_error() -> HTTPException:
    """Return the same error for unknown email AND wrong password.

    This is critical: if the error message differs (e.g. "user not found"
    vs "wrong password"), an attacker can enumerate valid emails.
    The response is identical in both cases: 401, "Incorrect email or password".
    """
    return HTTPException(status_code=401, detail="Incorrect email or password")


# ---------------------------------------------------------------------------
# Login (with brute-force protection + rate limit + MFA-aware)
# ---------------------------------------------------------------------------


@router.post("/login")
def login(
    payload: SuperAdminLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Super Admin login.

    Flow:
      1. Fail-closed check: if rate limiting is enabled + production +
         fail-closed-on-redis-down, return 503 if Redis is unreachable.
      2. Look up the SuperAdmin by email (case-insensitive).
      3. If the account is currently locked → 423 Locked.
      4. Verify password. On mismatch:
         - Record failed login (atomic counter increment)
         - Return the SAME error as if the email didn't exist
           (no email enumeration)
      5. On match: clear failed-attempt counter, set last_login_at.
      6. If MFA is enabled: issue short-lived MFA challenge token,
         return 200 with mfa_required=true. Client must call verify-mfa.
      7. If MFA is NOT enabled: issue full super_admin JWT with tver claim,
         set cookie, return SuperAdminOut.

    Audit log entries:
      - super_admin.login.failed (IP + timestamp, NEVER password)
      - super_admin.login.success (IP + timestamp)
      - super_admin.login.locked (when lockout threshold reached)
      - super_admin.mfa.challenge_issued (when MFA challenge issued)
    """
    # 1. Fail-closed Redis check (production only)
    assert_redis_available_or_fail_closed(request)

    # 2. Lookup
    admin = db.scalar(select(SuperAdmin).where(SuperAdmin.email == payload.email.lower()))

    # 3. Locked? — read lock state fresh from DB (defence against stale ORM cache)
    if admin is not None:
        lock_row = db.execute(
            text("SELECT locked_until FROM super_admins WHERE id = :aid"),
            {"aid": str(admin.id)},
        ).fetchone()
        if lock_row and lock_row[0] is not None:
            lock_until_dt = lock_row[0]
            if lock_until_dt > datetime.now(timezone.utc):
                db.add(SuperAdminAuditLog(
                    super_admin_id=admin.id,
                    action="super_admin.login.locked",
                    target_type="super_admin",
                    target_id=admin.id,
                    metadata_={"locked_until": lock_until_dt.isoformat()},
                    ip_address=_ip(request),
                ))
                db.commit()
                raise HTTPException(
                    status_code=423,
                    detail="Account temporarily locked. Try again later.",
                )

    # 4. Verify password — SAME error for unknown email AND wrong password
    password_ok = (
        admin is not None
        and admin.password_hash
        and verify_password(payload.password, admin.password_hash)
    )

    if not password_ok:
        if admin is not None:
            # Record failed attempt (atomic counter increment + audit log)
            sa_auth.record_failed_login(db, admin=admin, ip=_ip(request))
            db.commit()
        # Identical error in both branches — no email enumeration
        raise _generic_login_error()

    # Password is correct. From here on we have a known admin.
    assert admin is not None  # for type-checkers

    # 5. Check account is_active (after password check, so the error message
    # is identical to a wrong password — prevents enumeration of inactive accounts)
    if not admin.is_active:
        # Don't reveal that the account exists-but-inactive — use the
        # generic error. But audit-log the attempt.
        db.add(SuperAdminAuditLog(
            super_admin_id=admin.id,
            action="super_admin.login.inactive_account",
            target_type="super_admin",
            target_id=admin.id,
            metadata_={},
            ip_address=_ip(request),
        ))
        db.commit()
        raise _generic_login_error()

    # 6. Successful password verification — clear counters
    sa_auth.record_successful_login(db, admin=admin, ip=_ip(request))

    # 7. MFA?
    if admin.mfa_enabled:
        challenge_token = sa_auth.issue_mfa_challenge(db, admin=admin, ip=_ip(request))
        db.commit()
        return SuperAdminMFARequiredResponse(
            mfa_required=True,
            mfa_challenge=challenge_token,
            expires_in_seconds=get_settings().super_admin_mfa_challenge_ttl_minutes * 60,
        )

    # 8. No MFA — issue full super_admin JWT with tver claim
    token = create_access_token(
        subject=str(admin.id),
        token_type="super_admin",
        token_version=admin.token_version,
    )
    db.commit()
    _set_super_admin_cookie(response, token)
    # Return a minimal dict that does NOT include password_hash or mfa_secret_encrypted
    return {
        "id": str(admin.id),
        "email": admin.email,
        "name": admin.name,
        "is_active": admin.is_active,
    }


# ---------------------------------------------------------------------------
# Login verify-MFA (2nd step)
# ---------------------------------------------------------------------------


@router.post("/login/verify-mfa", response_model=SuperAdminOut)
def verify_mfa(
    payload: SuperAdminVerifyMFARequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Exchange an MFA challenge + valid TOTP/recovery code for a full SA JWT.

    The challenge token:
      - Must decode with the super_admin signing key + type=mfa_challenge
      - Must match a row in ``super_admin_mfa_challenges`` (by SHA-256 hash)
      - Must not be expired
      - Must not be already used (used_at IS NULL)

    The TOTP code:
      - Must match the admin's MFA secret within the configured window
      - Must not be a replay (unique constraint on (admin_id, code_hash))

    Recovery code:
      - Alternative to TOTP for users who lost their device
      - Single-use; replay rejected

    On success: issue a full super_admin JWT (with tver claim), set cookie.
    """
    # Decode challenge token
    challenge_payload = decode_mfa_challenge_token(payload.mfa_challenge)
    if challenge_payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA challenge")
    try:
        sa_id = uuid.UUID(challenge_payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed MFA challenge") from None

    # Verify the challenge row exists + is unused + not expired
    import hashlib
    challenge_hash = hashlib.sha256(payload.mfa_challenge.encode()).hexdigest()
    challenge_row = db.scalar(
        select(SuperAdminMFAChallenge).where(
            SuperAdminMFAChallenge.super_admin_id == sa_id,
            SuperAdminMFAChallenge.challenge_hash == challenge_hash,
        )
    )
    if challenge_row is None:
        raise HTTPException(status_code=401, detail="MFA challenge not found")
    if challenge_row.used_at is not None:
        raise HTTPException(status_code=409, detail="MFA challenge already used")
    if challenge_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="MFA challenge expired")

    # Load the admin
    admin = db.get(SuperAdmin, sa_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Account not found or deactivated")

    # Verify the second factor
    if payload.recovery_code:
        sa_auth.consume_recovery_code(db, admin=admin, code=payload.recovery_code, ip=_ip(request))
    elif payload.code:
        sa_auth.verify_totp_code(db, admin=admin, code=payload.code, ip=_ip(request))
    else:
        raise HTTPException(status_code=400, detail="Must supply either code or recovery_code")

    # Mark challenge as used (prevents replay)
    challenge_row.used_at = datetime.now(timezone.utc)

    # Issue full super_admin JWT with tver claim
    token = create_access_token(
        subject=str(admin.id),
        token_type="super_admin",
        token_version=admin.token_version,
    )
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.login.success_mfa",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={"recovery_code_used": payload.recovery_code is not None},
        ip_address=_ip(request),
    ))
    db.commit()
    _set_super_admin_cookie(response, token)
    # Return minimal dict — never expose password_hash or mfa_secret_encrypted
    return {
        "id": str(admin.id),
        "email": admin.email,
        "name": admin.name,
        "is_active": admin.is_active,
    }


# ---------------------------------------------------------------------------
# Logout (bumps token_version = logout-all semantics)
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Logout — bumps token_version so all previously-issued tokens are invalidated.

    This is logout-ALL semantics: every device/session of this Super Admin
    is logged out. Cookie is also cleared client-side.

    The bump is required because merely deleting the client cookie leaves
    the JWT valid until expiry — a stolen token would still work.
    """
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None:
        # Already deleted account? Cookie is meaningless; just clear it.
        response.delete_cookie("super_admin_access_token", path="/")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    sa_auth.bump_token_version(db, admin=admin, reason="logout", ip=_ip(request))
    db.commit()
    response.delete_cookie("super_admin_access_token", path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=SuperAdminOut)
def me(
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Return the current Super Admin profile.

    Note: the heavy lifting (token validation, is_active check, token_version
    check) is done by ``get_super_admin_context`` itself. By the time we
    reach here, the admin is guaranteed active + token is fresh.

    Returns ONLY the SuperAdminOut fields (id, email, name, is_active) —
    never password_hash, mfa_secret_encrypted, or internal counters.
    """
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None or not admin.is_active:
        # Should not happen — get_super_admin_context already verified.
        # But be defensive: a race condition between context check and here
        # (admin deactivated by another request) is still fail-closed.
        raise HTTPException(status_code=401, detail="Super Admin not found")
    # Explicitly construct SuperAdminOut to avoid leaking password_hash etc.
    return SuperAdminOut(
        id=admin.id,
        email=admin.email,
        name=admin.name,
        is_active=admin.is_active,
    )


# ---------------------------------------------------------------------------
# MFA setup / enable / disable
# ---------------------------------------------------------------------------


@router.post("/mfa/setup", response_model=SuperAdminMFASetupResponse)
def mfa_setup(
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Generate a new TOTP secret for the current Super Admin.

    The secret is returned ONCE in plaintext so the client can render a
    QR code. MFA is NOT yet enabled — the client must call ``/mfa/enable``
    with a valid TOTP code from this secret to activate MFA.

    The secret is stored encrypted at rest (Fernet, via ``encrypt_secret``).
    """
    import pyotp
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="Super Admin not found")
    if admin.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled — disable first to re-setup")
    secret = sa_auth.generate_mfa_secret()
    # Build otpauth URL — NOT persisted, only returned to client
    s = get_settings()
    totp = pyotp.TOTP(secret, digits=s.totp_digits, interval=s.totp_step_seconds)
    otpauth_url = totp.provisioning_uri(name=admin.email, issuer_name="M369 Support")
    return SuperAdminMFASetupResponse(
        secret=secret,
        otpauth_url=otpauth_url,
    )


@router.post("/mfa/enable", response_model=SuperAdminRecoveryCodesOut)
def mfa_enable(
    payload: SuperAdminMFAEnableRequest,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Activate MFA — submit a TOTP code from the just-setup secret.

    On success:
      - Persists the encrypted secret
      - Sets mfa_enabled=true
      - Generates ``sa_mfa_recovery_code_count`` recovery codes
      - Returns the recovery codes (plaintext, ONE-TIME only)

    After this endpoint returns, the next login will require a TOTP code.
    """
    import pyotp
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="Super Admin not found")
    if admin.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled")
    # Verify the submitted code against the submitted secret
    s = get_settings()
    totp = pyotp.TOTP(payload.secret, digits=s.totp_digits, interval=s.totp_step_seconds)
    if not totp.verify(payload.code, valid_window=s.totp_window):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    recovery_codes = sa_auth.enable_mfa_for_admin(
        db,
        admin=admin,
        secret_plaintext=payload.secret,
        ip=_ip(request),
    )
    db.commit()
    return SuperAdminRecoveryCodesOut(recovery_codes=recovery_codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def mfa_disable(
    payload: SuperAdminMFADisableRequest,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Disable MFA — requires a TOTP code OR recovery code.

    Disabling MFA cannot be done with just the password — the caller must
    prove possession of a second factor. This prevents an attacker who
    stole the password from disabling MFA.
    """
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="Super Admin not found")
    if not admin.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is not enabled")
    if payload.recovery_code:
        sa_auth.consume_recovery_code(db, admin=admin, code=payload.recovery_code, ip=_ip(request))
    elif payload.code:
        sa_auth.verify_totp_code(db, admin=admin, code=payload.code, ip=_ip(request))
    else:
        raise HTTPException(status_code=400, detail="Must supply either code or recovery_code")
    sa_auth.disable_mfa_for_admin(db, admin=admin, ip=_ip(request))
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    # MFA was disabled — clear the access cookie so the user has to log in fresh
    response.delete_cookie("super_admin_access_token", path="/")
    return response
