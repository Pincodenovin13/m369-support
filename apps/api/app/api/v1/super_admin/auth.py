"""Super Admin auth — separate from agency auth.

Separate JWT signing key, separate cookie name, separate audit log.

Phase 1 Security Hardening / Package A + A.1 corrections:
  - Per-request account-state validation (in ``get_super_admin_context``)
  - Server-side session revocation via ``token_version``
  - Brute-force protection (atomic counter, lockout, no email leak)
  - Real Redis-based rate limiting (custom atomic INCR+EXPIRE, fail-closed)
  - Real TOTP-based MFA (setup → enable → 2-step login → replay-protected verify)
  - Atomic MFA challenge consumption (conditional UPDATE, race-safe)
  - Atomic recovery code consumption (SELECT FOR UPDATE + conditional UPDATE)
  - Independent MFA lockout (failed_mfa_attempts, not cleared on password success)
  - Logout bumps ``token_version`` (logout-all semantics)

Package A.1 corrections vs Package A:
  - Rate limit is now REAL (custom Redis limiter, not slowapi decorator)
  - Both /login AND /login/verify-mfa are rate-limited (independent keys)
  - MFA challenge consumption is atomic (UPDATE ... WHERE used_at IS NULL)
  - Recovery code consumption is atomic (SELECT FOR UPDATE + conditional UPDATE)
  - MFA lockout is independent from password lockout
  - Password success does NOT clear failed_mfa_attempts
  - Only MFA success clears failed_mfa_attempts
  - TOTP IntegrityError → 409; other DB errors → 500 (not misreported as replay)
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ....core.config import get_settings
from ....db.database import get_super_admin_auth_db, get_super_admin_db
from ....dependencies import get_super_admin_context
from ....models import SuperAdmin, SuperAdminAuditLog
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
from ....services.rate_limit import (
    assert_redis_available_or_fail_closed,
    check_login_rate_limit,
    check_verify_mfa_rate_limit,
)

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
    """Return the same error for unknown, wrong-password, inactive, and locked accounts.

    This is critical: differing status codes or messages let an attacker
    enumerate valid emails or infer account state. The response is always
    401, "Incorrect email or password".
    """
    return HTTPException(status_code=401, detail="Incorrect email or password")


def _sa_out_dict(admin: SuperAdmin) -> dict:
    """Return a minimal dict — never expose password_hash or mfa_secret_encrypted."""
    return {
        "id": str(admin.id),
        "email": admin.email,
        "name": admin.name,
        "is_active": admin.is_active,
    }


# ---------------------------------------------------------------------------
# Login (with brute-force protection + rate limit + MFA-aware)
# ---------------------------------------------------------------------------


@router.post("/login")
def login(
    payload: SuperAdminLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_super_admin_auth_db),
):
    """Super Admin login.

    Flow:
      1. Fail-closed Redis check (production only).
      2. Rate limit check (per-IP + per-account, independent, Redis-based).
      3. Look up the SuperAdmin by email (case-insensitive).
      4. If the account is currently locked → the same generic 401 response.
      5. Verify password. On mismatch:
         - Record failed login (atomic counter increment)
         - Return the SAME error as if the email didn't exist (no enumeration)
      6. On match:
         - If MFA is enabled: issue MFA challenge, return mfa_required=true.
           Do NOT call record_successful_login yet — password success is
           only the first step; failed_mfa_attempts must NOT be cleared.
         - If MFA is NOT enabled: call record_successful_login (clears
           failed_login_attempts + locked_until), issue JWT, return.
    """
    # 1. Fail-closed Redis check (production only)
    assert_redis_available_or_fail_closed(request)

    # 2. Rate limit check (per-IP + per-account, independent)
    check_login_rate_limit(request, payload.email)

    # 3. Lookup
    admin = db.scalar(select(SuperAdmin).where(SuperAdmin.email == payload.email.lower()))

    # 4. Locked? — read lock state fresh from DB (defence against stale ORM cache)
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
                # Do not disclose whether an email belongs to a locked account.
                # Match the response used for unknown-user and wrong-password failures.
                raise _generic_login_error()

    # 5. Verify password — SAME error for unknown email AND wrong password
    password_ok = (
        admin is not None
        and admin.password_hash
        and verify_password(payload.password, admin.password_hash)
    )

    if not password_ok:
        if admin is not None:
            sa_auth.record_failed_login(db, admin=admin, ip=_ip(request))
            db.commit()
        raise _generic_login_error()

    # Password is correct. From here on we have a known admin.
    assert admin is not None

    # 6. Check account is_active (after password check, same error as wrong password)
    if not admin.is_active:
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

    # 7. MFA?
    if admin.mfa_enabled:
        # Do NOT call record_successful_login here — password success is only
        # the first step. failed_mfa_attempts must NOT be cleared until the
        # second factor is verified. Only set last_login_at.
        db.execute(
            text("UPDATE super_admins SET last_login_at = :now WHERE id = :aid"),
            {"now": datetime.now(timezone.utc), "aid": str(admin.id)},
        )
        challenge_token = sa_auth.issue_mfa_challenge(db, admin=admin, ip=_ip(request))
        db.commit()
        return SuperAdminMFARequiredResponse(
            mfa_required=True,
            mfa_challenge=challenge_token,
            expires_in_seconds=get_settings().super_admin_mfa_challenge_ttl_minutes * 60,
        )

    # 8. No MFA — full login success
    sa_auth.record_successful_login(db, admin=admin, ip=_ip(request))
    token = create_access_token(
        subject=str(admin.id),
        token_type="super_admin",
        token_version=admin.token_version,
    )
    db.commit()
    _set_super_admin_cookie(response, token)
    return _sa_out_dict(admin)


# ---------------------------------------------------------------------------
# Login verify-MFA (2nd step) — atomic challenge consumption
# ---------------------------------------------------------------------------


@router.post("/login/verify-mfa", response_model=SuperAdminOut)
def verify_mfa(
    payload: SuperAdminVerifyMFARequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_super_admin_auth_db),
):
    """Exchange an MFA challenge + valid TOTP/recovery code for a full SA JWT.

    Race-safe via atomic conditional UPDATE on the challenge row:

      UPDATE super_admin_mfa_challenges
      SET used_at = :now
      WHERE challenge_hash = :hash
        AND super_admin_id = :sa_id
        AND used_at IS NULL
        AND expires_at > now()
      RETURNING ...

    Two concurrent requests with the same challenge token cannot both
    succeed — PostgreSQL's row-level lock ensures only one gets
    rowcount=1; the other gets 409 (challenge already used).

    The TOTP code is replay-protected via a unique constraint on
    (super_admin_id, code_hash). Recovery codes are consumed atomically
    via SELECT FOR UPDATE + conditional UPDATE.

    On success: clears failed_mfa_attempts, issues full super_admin JWT.
    On failure: increments failed_mfa_attempts (independent lockout).
    """
    # Decode challenge token
    challenge_payload = decode_mfa_challenge_token(payload.mfa_challenge)
    if challenge_payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA challenge")
    try:
        sa_id = uuid.UUID(challenge_payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed MFA challenge") from None

    # Exactly one second factor is required. Validate before consuming the
    # challenge so malformed requests do not leave ambiguous challenge state.
    if bool(payload.code) == bool(payload.recovery_code):
        raise HTTPException(status_code=400, detail="Supply exactly one of code or recovery_code")

    # Rate limit (per-IP + per-super_admin_id, independent from login limit)
    check_verify_mfa_rate_limit(request, sa_id)

    # Compute challenge hash
    challenge_hash = hashlib.sha256(payload.mfa_challenge.encode()).hexdigest()

    # Load the admin first — needed for MFA lock check + second factor verify
    admin = db.get(SuperAdmin, sa_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Account not found or deactivated")

    # Check MFA lock (reuses locked_until — independent counter but same column)
    if sa_auth.is_mfa_locked(admin):
        db.add(SuperAdminAuditLog(
            super_admin_id=admin.id,
            action="super_admin.mfa.locked",
            target_type="super_admin",
            target_id=admin.id,
            metadata_={"locked_until": admin.locked_until.isoformat() if admin.locked_until else None},
            ip_address=_ip(request),
        ))
        db.commit()
        raise HTTPException(
            status_code=423,
            detail="Account temporarily locked due to MFA failures. Try again later.",
        )

    # ATOMICALLY consume the challenge — this is the race-safe step.
    # If this succeeds, no other request can use the same challenge.
    # If the second factor fails after this, the challenge is already
    # consumed (used_at set) — the user must re-login to get a new one.
    # This is the correct security trade-off: we'd rather force a re-login
    # than allow a race where two requests both pass the challenge check.
    sa_auth.consume_mfa_challenge(db, challenge_hash=challenge_hash, sa_id=sa_id)

    # Verify the second factor
    try:
        if payload.recovery_code:
            sa_auth.consume_recovery_code(db, admin=admin, code=payload.recovery_code, ip=_ip(request))
        elif payload.code:
            sa_auth.verify_totp_code(db, admin=admin, code=payload.code, ip=_ip(request))
        else:
            raise HTTPException(status_code=400, detail="Must supply either code or recovery_code")
    except HTTPException as exc:
        # Second factor failed — record it + rollback the challenge consumption
        # (so the user can retry with the same challenge if they typed wrong).
        # Wait — we already consumed the challenge above. If we rollback,
        # the challenge becomes available again, which is a race window.
        # Trade-off: we DON'T rollback. The challenge is consumed. The user
        # must re-login. This is the safer choice.
        # But we DO record the MFA failure + commit it (separate from the
        # challenge consumption which is already in the txn).
        if exc.status_code in (400, 409):
            sa_auth.record_failed_mfa(db, admin=admin, ip=_ip(request))
            db.commit()
        raise

    # Second factor succeeded — clear failed_mfa_attempts + issue JWT
    sa_auth.record_successful_mfa(db, admin=admin, ip=_ip(request))
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
    return _sa_out_dict(admin)


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
    """Logout — bumps token_version so all previously-issued tokens are invalidated."""
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is not None:
        sa_auth.bump_token_version(db, admin=admin, reason="logout", ip=_ip(request))
        db.commit()
    response.delete_cookie("super_admin_access_token", path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=SuperAdminOut)
def me(
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Return the current Super Admin profile (minimal fields only)."""
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Super Admin not found")
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
    """Generate a new TOTP secret for the current Super Admin."""
    import pyotp
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="Super Admin not found")
    if admin.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled — disable first to re-setup")
    secret = sa_auth.generate_mfa_secret()
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
    """Activate MFA — submit a TOTP code from the just-setup secret."""
    import pyotp
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="Super Admin not found")
    if admin.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled")
    # A stolen authenticated session must not be able to brute-force the
    # six-digit enrollment proof. Share the dedicated MFA IP/account quota.
    check_verify_mfa_rate_limit(request, sa_id)
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
    # Enabling MFA invalidates every session issued before MFA enrollment.
    # The administrator must sign in again and complete the MFA challenge.
    sa_auth.bump_token_version(db, admin=admin, reason="mfa_enabled", ip=_ip(request))
    db.commit()
    return SuperAdminRecoveryCodesOut(recovery_codes=recovery_codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def mfa_disable(
    payload: SuperAdminMFADisableRequest,
    request: Request,
    db: Session = Depends(get_super_admin_db),
    ctx=Depends(get_super_admin_context),
):
    """Disable MFA — requires a TOTP code OR recovery code."""
    sa_id: uuid.UUID = request.state.super_admin_id
    admin = db.get(SuperAdmin, sa_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="Super Admin not found")
    if not admin.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is not enabled")
    # Require exactly one factor and throttle every disable attempt.
    if bool(payload.code) == bool(payload.recovery_code):
        raise HTTPException(status_code=400, detail="Supply exactly one of code or recovery_code")
    check_verify_mfa_rate_limit(request, sa_id)
    if payload.recovery_code:
        sa_auth.consume_recovery_code(db, admin=admin, code=payload.recovery_code, ip=_ip(request))
    elif payload.code:
        sa_auth.verify_totp_code(db, admin=admin, code=payload.code, ip=_ip(request))
    else:
        raise HTTPException(status_code=400, detail="Must supply either code or recovery_code")
    sa_auth.disable_mfa_for_admin(db, admin=admin, ip=_ip(request))
    # Disabling MFA also revokes all existing sessions; a fresh login is required.
    sa_auth.bump_token_version(db, admin=admin, reason="mfa_disabled", ip=_ip(request))
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie("super_admin_access_token", path="/")
    return response
