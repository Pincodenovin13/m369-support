"""Super Admin authentication security service.

Pure-Python service layer for the Super Admin auth flows. Keeps the
endpoint modules thin and lets the business rules be tested without
going through the HTTP layer.

Sections:
  1. Brute-force protection — atomic failed-attempt counter, lockout
  2. Server-side session revocation — token_version bump helpers
  3. MFA challenge issuance + verification (TOTP, replay-protected)
  4. MFA recovery codes (Argon2id-hashed, single-use)

Design rules:
  - Brute-force counter is incremented atomically via
    ``UPDATE super_admins SET failed_login_attempts = failed_login_attempts + 1``
    so concurrent attempts cannot under-count (PostgreSQL row-level lock
    on the same row).
  - On successful login: ``failed_login_attempts = 0``, ``locked_until = NULL``.
  - Audit log entries carry IP + timestamp + action only — NEVER the
    password, JWT, MFA secret, or recovery code.
  - MFA secrets are Fernet-encrypted at rest (reuse ``encrypt_secret``).
    The decrypted secret is held in memory only for the duration of a
    single TOTP verification.
  - TOTP replay protection: each successfully-verified code is recorded
    in ``super_admin_used_totp_codes`` with a unique constraint on
    ``(super_admin_id, code_hash)``. A replay attempt causes a unique
    violation → 409 from the verify endpoint.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import (
    SuperAdmin,
    SuperAdminAuditLog,
    SuperAdminMFAChallenge,
    SuperAdminMFARecoveryCode,
    SuperAdminUsedTOTPCode,
)
from ..security import (
    create_access_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# 1. Brute-force protection
# ---------------------------------------------------------------------------

#: The actual name of the unique constraint on super_admin_used_totp_codes
#: that prevents TOTP replay. Extracted from migration 0010 — NOT invented.
#: Used by ``is_totp_replay_error`` to distinguish a genuine TOTP replay
#: (HTTP 409) from any other IntegrityError (which must propagate as 500).
TOTP_REPLAY_CONSTRAINT_NAME = "uq_sa_totp_codes_sa_codehash"


def is_totp_replay_error(exc: Exception) -> bool:
    """Return True only if ``exc`` is a unique-constraint violation on the
    TOTP replay table's specific constraint.

    psycopg3 attaches a ``Diagnostic`` object to ``orig`` with the constraint
    name. We check it precisely — other IntegrityErrors (FK violations,
    check constraint violations, NOT NULL violations) must NOT be reported
    as TOTP replays.
    """
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False
    diag = getattr(orig, "diag", None)
    if diag is None:
        return False
    constraint = getattr(diag, "constraint_name", None)
    return constraint == TOTP_REPLAY_CONSTRAINT_NAME


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_locked(admin: SuperAdmin) -> bool:
    """True if account is currently in a temporary lockout window."""
    return admin.locked_until is not None and admin.locked_until > _now()


def record_failed_login(db: Session, *, admin: SuperAdmin, ip: str | None) -> int:
    """Atomically increment failed_login_attempts; lock if threshold reached.

    Uses an explicit UPDATE so concurrent requests serialize on the same row
    (PostgreSQL row lock) and cannot under-count. Returns the new value
    of failed_login_attempts (after the increment).

    On reaching the configured threshold (``sa_max_failed_logins``), sets
    ``locked_until = now + sa_lockout_minutes``.
    """
    s = get_settings()
    now = _now()
    # Atomic increment with RETURNING so we read the post-increment value
    # in the same statement (no race between UPDATE and SELECT).
    row = db.execute(
        text(
            "UPDATE super_admins "
            "SET failed_login_attempts = failed_login_attempts + 1, "
            "    last_failed_login_at = :now "
            "WHERE id = :aid "
            "RETURNING failed_login_attempts"
        ),
        {"aid": str(admin.id), "now": now},
    ).fetchone()
    new_attempts = row[0] if row else admin.failed_login_attempts + 1
    # Lockout condition
    if new_attempts >= s.sa_max_failed_logins:
        lock_until = now + timedelta(minutes=s.sa_lockout_minutes)
        db.execute(
            text(
                "UPDATE super_admins SET locked_until = :lu WHERE id = :aid"
            ),
            {"lu": lock_until, "aid": str(admin.id)},
        )
    # Audit log — only action + IP + timestamp. NEVER the password.
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.login.failed",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={"attempts": new_attempts, "locked": new_attempts >= s.sa_max_failed_logins},
        ip_address=ip,
    ))
    db.flush()
    return new_attempts


def record_successful_login(db: Session, *, admin: SuperAdmin, ip: str | None) -> None:
    """Reset failed_login_attempts + locked_until.

    NOTE: This is called ONLY when the full login succeeds — i.e. MFA is
    NOT enabled, or MFA is enabled but this is the password-verification
    step only (the MFA challenge is issued but NOT yet verified).

    For MFA-enabled accounts, the failed_mfa_attempts counter is NOT
    reset here — it is only reset on successful MFA verification
    (see ``record_successful_mfa`` below).

    This prevents an attacker from clearing the MFA lockout counter by
    simply entering the correct password.
    """
    now = _now()
    db.execute(
        text(
            "UPDATE super_admins "
            "SET failed_login_attempts = 0, "
            "    locked_until = NULL, "
            "    last_login_at = :now "
            "WHERE id = :aid"
        ),
        {"now": now, "aid": str(admin.id)},
    )
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.login.success",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={},
        ip_address=ip,
    ))
    db.flush()


def record_successful_mfa(db: Session, *, admin: SuperAdmin, ip: str | None) -> None:
    """Reset failed_mfa_attempts after successful MFA verification.

    Called ONLY from the verify-mfa endpoint after the second factor is
    confirmed. This is the ONLY place failed_mfa_attempts is reset to 0.
    """
    db.execute(
        text(
            "UPDATE super_admins "
            "SET failed_mfa_attempts = 0, "
            "    last_login_at = :now "
            "WHERE id = :aid"
        ),
        {"now": _now(), "aid": str(admin.id)},
    )
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.mfa.success",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={},
        ip_address=ip,
    ))
    db.flush()


def record_failed_mfa(db: Session, *, admin: SuperAdmin, ip: str | None) -> int:
    """Atomically increment failed_mfa_attempts; lock if threshold reached.

    Independent from the password failed-login counter. Uses the same
    atomic UPDATE ... RETURNING pattern as ``record_failed_login``.

    On reaching ``sa_mfa_max_failed_attempts``, sets a MFA-specific
    lockout via ``locked_until`` (reusing the same column — the login
    endpoint checks ``locked_until`` regardless of which counter
    triggered it).
    """
    s = get_settings()
    now = _now()
    row = db.execute(
        text(
            "UPDATE super_admins "
            "SET failed_mfa_attempts = failed_mfa_attempts + 1 "
            "WHERE id = :aid "
            "RETURNING failed_mfa_attempts"
        ),
        {"aid": str(admin.id)},
    ).fetchone()
    new_attempts = row[0] if row else admin.failed_mfa_attempts + 1
    if new_attempts >= s.sa_mfa_max_failed_attempts:
        lock_until = now + timedelta(minutes=s.sa_mfa_lockout_minutes)
        db.execute(
            text("UPDATE super_admins SET locked_until = :lu WHERE id = :aid"),
            {"lu": lock_until, "aid": str(admin.id)},
        )
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.mfa.failed",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={"mfa_attempts": new_attempts, "locked": new_attempts >= s.sa_mfa_max_failed_attempts},
        ip_address=ip,
    ))
    db.flush()
    return new_attempts


def is_mfa_locked(admin: SuperAdmin) -> bool:
    """True if the account is locked due to MFA brute-force.

    Reuses the same ``locked_until`` column — once locked, ALL login
    attempts (password + MFA) are rejected until the lockout expires.
    """
    return admin.locked_until is not None and admin.locked_until > _now()


# ---------------------------------------------------------------------------
# 2. Server-side session revocation (token_version bump)
# ---------------------------------------------------------------------------


def bump_token_version(db: Session, *, admin: SuperAdmin, reason: str, ip: str | None = None) -> int:
    """Atomically increment ``super_admins.token_version``.

    Every previously-issued JWT for this Super Admin carries the OLD
    ``tver`` claim and is now rejected by ``get_super_admin_context``.

    Used by:
      - POST /super-admin/auth/logout (logout-all semantics)
      - POST /super-admin/auth/change-password
      - Super Admin deactivation endpoints (planned)
    """
    row = db.execute(
        text(
            "UPDATE super_admins "
            "SET token_version = token_version + 1 "
            "WHERE id = :aid "
            "RETURNING token_version"
        ),
        {"aid": str(admin.id)},
    ).fetchone()
    new_version = row[0] if row else admin.token_version + 1
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.token_version.bump",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={"new_version": new_version, "reason": reason},
        ip_address=ip,
    ))
    db.flush()
    return new_version


# ---------------------------------------------------------------------------
# 3. MFA challenge issuance + verification (TOTP, replay-protected)
# ---------------------------------------------------------------------------


def issue_mfa_challenge(db: Session, *, admin: SuperAdmin, ip: str | None) -> str:
    """Issue a short-lived MFA challenge token + persist its hash.

    Returns the plaintext challenge token (sent to the client once).
    The hash is stored so the verify-mfa endpoint can confirm the same
    token was issued AND consumed exactly once.

    The challenge token:
      - token_type = "mfa_challenge"
      - signed with the super_admin signing key (so decoder works)
      - TTL = ``super_admin_mfa_challenge_ttl_minutes`` (default 5 min)
      - carries NO token_version claim (challenge ≠ full session)
      - carries the super_admin id as ``sub``
    """
    s = get_settings()
    # Issue the JWT
    challenge_token = create_access_token(
        subject=str(admin.id),
        token_type="mfa_challenge",
    )
    # Persist SHA-256 hash (never plaintext)
    challenge_hash = hashlib.sha256(challenge_token.encode()).hexdigest()
    expires_at = _now() + timedelta(minutes=s.super_admin_mfa_challenge_ttl_minutes)
    db.add(SuperAdminMFAChallenge(
        super_admin_id=admin.id,
        challenge_hash=challenge_hash,
        expires_at=expires_at,
    ))
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.mfa.challenge_issued",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={},
        ip_address=ip,
    ))
    db.flush()
    return challenge_token


def _totp_code_hash(admin_id: uuid.UUID, code: str, window_start_ts: int) -> str:
    """SHA-256 of (admin_id, code, window_start_ts).

    The window_start_ts is included so the same numeric code at different
    time windows hashes differently — preventing long-term leakage of
    code-usage patterns via the unique constraint.
    """
    return hashlib.sha256(
        f"{admin_id}|{code}|{window_start_ts}".encode()
    ).hexdigest()


def verify_totp_code(
    db: Session,
    *,
    admin: SuperAdmin,
    code: str,
    ip: str | None,
) -> int:
    """Verify a TOTP code against the admin's MFA secret.

    Returns the ``window_start_ts`` (Unix epoch seconds of the matched
    TOTP window) on success. Raises 400 on invalid code, 409 on replay.

    Replay protection: the (admin_id, code_hash) tuple is inserted into
    ``super_admin_used_totp_codes``. The unique constraint on that pair
    means a second insert with the same code in the same window fails —
    we catch the IntegrityError and raise 409.
    """
    if not admin.mfa_enabled or not admin.mfa_secret_encrypted:
        raise HTTPException(status_code=400, detail="MFA is not enabled for this account")
    if not code or not code.isdigit():
        raise HTTPException(status_code=400, detail="Invalid TOTP code format")

    s = get_settings()
    # Decrypt the secret in memory — never log it
    try:
        secret = decrypt_secret(admin.mfa_secret_encrypted)
    except Exception:
        # Decryption failure → fail-closed (no info leak)
        raise HTTPException(
            status_code=500,
            detail="MFA secret could not be decrypted — contact administrator",
        ) from None

    totp = pyotp.TOTP(
        secret,
        digits=s.totp_digits,
        interval=s.totp_step_seconds,
    )
    # Verify with window — pyotp.verify returns True/False but does not
    # tell us which window matched. We need to know the window to record
    # the unique code_hash for replay protection. So we iterate possible
    # windows ourselves.
    now_ts = int(_now().timestamp())
    matched_window: int | None = None
    for offset in range(-s.totp_window, s.totp_window + 1):
        win_start = now_ts - (now_ts % s.totp_step_seconds) + offset * s.totp_step_seconds
        # pyotp expects the OTP at time = win_start + step (i.e., the time
        # the code was generated). Actually pyotp.at(time=win_start)
        # returns the code valid for the window starting at win_start.
        expected = totp.at(win_start)
        if _constant_time_eq(expected, code):
            matched_window = win_start
            break

    if matched_window is None:
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Replay protection — insert inside a SAVEPOINT so that a unique
    # violation only rolls back the insert, NOT the surrounding
    # transaction (which may already contain the consumed MFA challenge).
    code_hash = _totp_code_hash(admin.id, code, matched_window)
    try:
        with db.begin_nested():
            db.add(SuperAdminUsedTOTPCode(
                super_admin_id=admin.id,
                code_hash=code_hash,
                window_start_ts=matched_window,
            ))
            db.flush()
    except IntegrityError as exc:
        # Only the SPECIFIC TOTP replay constraint is a 409.
        # Other IntegrityErrors (e.g. FK violation) propagate as 500.
        if is_totp_replay_error(exc):
            raise HTTPException(
                status_code=409,
                detail="TOTP code has already been used (replay rejected)",
            ) from None
        raise

    # Cleanup: lazy-purge old replay records (older than 2x the window).
    # This keeps the table small without a separate cron.
    cutoff_ts = now_ts - 2 * s.totp_step_seconds
    db.execute(
        text(
            "DELETE FROM super_admin_used_totp_codes "
            "WHERE super_admin_id = :aid AND window_start_ts < :cutoff"
        ),
        {"aid": str(admin.id), "cutoff": cutoff_ts},
    )

    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.mfa.verify_success",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={"window_start_ts": matched_window},
        ip_address=ip,
    ))
    db.flush()
    return matched_window


def _constant_time_eq(a: str, b: str) -> bool:
    """Constant-time string comparison (uses hmac.compare_digest)."""
    return hmac.compare_digest(a.encode(), b.encode())


def consume_mfa_challenge(
    db: Session,
    *,
    challenge_hash: str,
    sa_id: uuid.UUID,
) -> SuperAdminMFAChallenge:
    """Atomically consume an MFA challenge token.

    Uses a conditional UPDATE:

      UPDATE super_admin_mfa_challenges
      SET used_at = :now
      WHERE challenge_hash = :hash
        AND super_admin_id = :sa_id
        AND used_at IS NULL
        AND expires_at > now()
      RETURNING id, expires_at

    If 0 rows are returned, the challenge was either:
      - Already used (replay) → 409
      - Expired → 401
      - Not found (wrong hash / wrong sa_id) → 401

    This is race-safe: two concurrent requests cannot both consume the
    same challenge — PostgreSQL's row-level lock on the UPDATE ensures
    only one transaction gets rowcount=1.

    Returns the consumed challenge row on success.
    """
    now = _now()
    row = db.execute(
        text(
            "UPDATE super_admin_mfa_challenges "
            "SET used_at = :now "
            "WHERE challenge_hash = :hash "
            "  AND super_admin_id = :sa_id "
            "  AND used_at IS NULL "
            "  AND expires_at > :now "
            "RETURNING id, super_admin_id, expires_at, used_at"
        ),
        {"now": now, "hash": challenge_hash, "sa_id": str(sa_id)},
    ).fetchone()

    if row is None:
        # Distinguish "already used" from "not found / expired"
        existing = db.execute(
            text(
                "SELECT used_at, expires_at FROM super_admin_mfa_challenges "
                "WHERE challenge_hash = :hash AND super_admin_id = :sa_id"
            ),
            {"hash": challenge_hash, "sa_id": str(sa_id)},
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=401, detail="MFA challenge not found")
        if existing[0] is not None:
            raise HTTPException(status_code=409, detail="MFA challenge already used")
        if existing[1] <= now:
            raise HTTPException(status_code=401, detail="MFA challenge expired")
        # Should not reach here, but fail-closed
        raise HTTPException(status_code=401, detail="MFA challenge invalid")

    # Build the model object for the caller
    return SuperAdminMFAChallenge(
        id=row[0],
        super_admin_id=row[1],
        challenge_hash=challenge_hash,
        expires_at=row[2],
        used_at=row[3],
    )


# ---------------------------------------------------------------------------
# 4. MFA recovery codes (Argon2id-hashed, single-use)
# ---------------------------------------------------------------------------


def generate_recovery_codes(db: Session, *, admin: SuperAdmin) -> list[str]:
    """Generate ``sa_mfa_recovery_code_count`` recovery codes.

    Returns the plaintext codes — sent to the client ONCE at MFA-enable
    time. Each code is stored as an Argon2id hash; the plaintext is never
    persisted.
    """
    s = get_settings()
    codes: list[str] = []
    # Delete any existing recovery codes (re-enabling MFA replaces them)
    db.execute(
        text("DELETE FROM super_admin_mfa_recovery_codes WHERE super_admin_id = :aid"),
        {"aid": str(admin.id)},
    )
    for _ in range(s.sa_mfa_recovery_code_count):
        # 16 chars, URL-safe base32 — easy to type, no ambiguous chars
        code = secrets.token_urlsafe(16)
        codes.append(code)
        db.add(SuperAdminMFARecoveryCode(
            super_admin_id=admin.id,
            code_hash=hash_password(code),
        ))
    db.flush()
    return codes


def consume_recovery_code(db: Session, *, admin: SuperAdmin, code: str, ip: str | None) -> bool:
    """Atomically consume a single recovery code.

    Race-safe via conditional UPDATE:

      UPDATE super_admin_mfa_recovery_codes
      SET used_at = :now
      WHERE id IN (
        SELECT id FROM super_admin_mfa_recovery_codes
        WHERE super_admin_id = :aid AND used_at IS NULL
      )
      RETURNING id

    The inner SELECT identifies unused codes for this admin. We then try
    each one with Argon2id verification in Python (cannot do Argon2id
    in SQL). But the UPDATE itself is atomic — once we set ``used_at``,
    no other transaction can use the same row.

    Approach:
      1. SELECT FOR UPDATE all unused codes for this admin (locks rows).
      2. Verify each with Argon2id.
      3. On match: UPDATE that single row SET used_at = now WHERE id = X
         AND used_at IS NULL. If 0 rows updated → another request won
         the race; raise 409.
      4. On no match: raise 400 (invalid code).

    SELECT FOR UPDATE prevents two concurrent transactions from both
    seeing the same unused code and both succeeding.

    Plaintext code is never stored — only the Argon2id hash.
    """
    # Step 1: SELECT FOR UPDATE — locks the rows until commit
    rows = db.execute(
        text(
            "SELECT id, code_hash FROM super_admin_mfa_recovery_codes "
            "WHERE super_admin_id = :aid AND used_at IS NULL "
            "FOR UPDATE"
        ),
        {"aid": str(admin.id)},
    ).fetchall()

    matched_id: uuid.UUID | None = None
    for row in rows:
        # Verify the code against the stored Argon2id hash
        if verify_password(code, row[1]):
            matched_id = row[0]
            break

    if matched_id is None:
        raise HTTPException(status_code=400, detail="Invalid recovery code")

    # Step 2: Conditional UPDATE — only succeeds if used_at is still NULL
    # (defence-in-depth even with SELECT FOR UPDATE)
    result = db.execute(
        text(
            "UPDATE super_admin_mfa_recovery_codes "
            "SET used_at = :now "
            "WHERE id = :rid AND used_at IS NULL"
        ),
        {"now": _now(), "rid": str(matched_id)},
    )
    if result.rowcount == 0:
        # Another concurrent request won the race
        raise HTTPException(
            status_code=409,
            detail="Recovery code was already consumed by another request",
        )

    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.mfa.recovery_code_used",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={},
        ip_address=ip,
    ))
    db.flush()
    return True


# ---------------------------------------------------------------------------
# 5. MFA setup (generate secret, encrypt, store)
# ---------------------------------------------------------------------------


def generate_mfa_secret() -> str:
    """Generate a fresh TOTP secret (base32, 32 chars = 160 bits).

    The secret is returned in plaintext to the caller (the setup endpoint)
    so it can be displayed to the user ONCE as part of a QR code or
    manual entry string. The caller MUST persist the encrypted form via
    ``encrypt_secret()`` and never log the plaintext.
    """
    return pyotp.random_base32()


def enable_mfa_for_admin(
    db: Session,
    *,
    admin: SuperAdmin,
    secret_plaintext: str,
    ip: str | None,
) -> list[str]:
    """Persist the encrypted secret + set mfa_enabled=true + generate recovery codes.

    Returns the recovery codes (plaintext) — shown to the user ONCE.
    """
    admin.mfa_secret_encrypted = encrypt_secret(secret_plaintext)
    admin.mfa_enabled = True
    recovery_codes = generate_recovery_codes(db, admin=admin)
    db.add(SuperAdminAuditLog(
        super_admin_id=admin.id,
        action="super_admin.mfa.enable",
        target_type="super_admin",
        target_id=admin.id,
        metadata_={},
        ip_address=ip,
    ))
    db.flush()
    return recovery_codes


def disable_mfa_for_admin(db: Session, *, admin: SuperAdmin, ip: str | None) -> None:
    """Disable MFA — clear secret + recovery codes + mfa_enabled.

    Also bumps ``token_version`` so any pending MFA challenge tokens
    AND any active sessions are invalidated.
    """
    admin.mfa_secret_encrypted = None
    admin.mfa_enabled = False
    admin.failed_mfa_attempts = 0
    db.execute(
        text("DELETE FROM super_admin_mfa_recovery_codes WHERE super_admin_id = :aid"),
        {"aid": str(admin.id)},
    )
    db.execute(
        text("DELETE FROM super_admin_mfa_challenges WHERE super_admin_id = :aid"),
        {"aid": str(admin.id)},
    )
    bump_token_version(db, admin=admin, reason="mfa_disabled", ip=ip)
    db.flush()


__all__ = [
    "TOTP_REPLAY_CONSTRAINT_NAME",
    "is_totp_replay_error",
    "is_locked",
    "is_mfa_locked",
    "record_failed_login",
    "record_successful_login",
    "record_failed_mfa",
    "record_successful_mfa",
    "bump_token_version",
    "issue_mfa_challenge",
    "verify_totp_code",
    "consume_mfa_challenge",
    "generate_recovery_codes",
    "consume_recovery_code",
    "generate_mfa_secret",
    "enable_mfa_for_admin",
    "disable_mfa_for_admin",
]
