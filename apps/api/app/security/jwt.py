"""Security primitives: password hashing (Argon2id), JWT, Fernet encryption.

Token classes:
    - ``agency``      : for agency staff (User). Signed with ``jwt_secret_key``.
    - ``super_admin`` : for Super Admin. Signed with ``jwt_super_admin_secret_key``.
    - ``refresh``     : long-lived refresh token.

Each decoder only accepts its own ``type`` claim, so a token of one class cannot
be replayed as the other even if both happen to be valid signatures on the same key set.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from pydantic import BaseModel

from ..core.config import get_settings


# ---------------------------------------------------------------------------
# Password hashing — Argon2id
# ---------------------------------------------------------------------------


def _password_hasher() -> PasswordHasher:
    s = get_settings()
    return PasswordHasher(
        time_cost=s.argon2_time_cost,
        memory_cost=s.argon2_memory_cost,
        parallelism=s.argon2_parallelism,
        type=Type.ID,  # argon2id — RFC 9106 recommended
    )


_hasher = _password_hasher()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id. Returns a string suitable for DB storage."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored Argon2id hash. Returns ``False`` on mismatch."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


TokenType = Literal["agency", "super_admin", "refresh"]


class TokenPayload(BaseModel):
    """The shape of every JWT we issue.

    ``exp`` and ``iat`` are integer Unix timestamps — PyJWT's default decoders
    expect integers, not ISO strings.
    """

    sub: str
    type: TokenType
    exp: int
    iat: int
    iss: str
    aud: str
    jti: str
    agency_id: str | None = None


def _signing_key(token_type: TokenType) -> str:
    s = get_settings()
    if token_type == "super_admin":
        return s.jwt_super_admin_secret_key
    return s.jwt_secret_key


def create_access_token(
    *,
    subject: str,
    token_type: TokenType = "agency",
    agency_id: str | None = None,
    expires_in: timedelta | None = None,
) -> str:
    """Issue a signed JWT. ``token_type`` controls the signing key and decoder."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp_delta = expires_in or timedelta(minutes=s.jwt_access_token_minutes)
    now_ts = int(now.timestamp())
    exp_ts = int((now + exp_delta).timestamp())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "exp": exp_ts,
        "iat": now_ts,
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
    }
    if agency_id is not None:
        payload["agency_id"] = agency_id
    return jwt.encode(payload, _signing_key(token_type), algorithm=s.jwt_algorithm)


def create_refresh_token(*, subject: str, token_type: TokenType = "agency") -> str:
    """Long-lived refresh token. Shares the signing key with its access sibling."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    now_ts = int(now.timestamp())
    exp_ts = int((now + timedelta(days=s.jwt_refresh_token_days)).timestamp())
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": exp_ts,
        "iat": now_ts,
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "scope": token_type,
    }
    return jwt.encode(payload, _signing_key(token_type), algorithm=s.jwt_algorithm)


def _decode(token: str, expected_type: TokenType) -> dict[str, Any] | None:
    """Decode a JWT, accepting only the expected ``type`` claim."""
    s = get_settings()
    try:
        payload = jwt.decode(
            token,
            _signing_key(expected_type),
            algorithms=[s.jwt_algorithm],
            issuer=s.jwt_issuer,
            audience=s.jwt_audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "type"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode an agency access token. Returns ``None`` for any other token class."""
    return _decode(token, "agency")


def decode_super_admin_token(token: str) -> dict[str, Any] | None:
    """Decode a super-admin access token."""
    return _decode(token, "super_admin")


def decode_refresh_token(token: str, expected_scope: TokenType = "agency") -> dict[str, Any] | None:
    """Decode a refresh token. ``expected_scope`` must match the access class it refreshes."""
    payload = _decode(token, "refresh")
    if payload is None or payload.get("scope") != expected_scope:
        return None
    return payload


# ---------------------------------------------------------------------------
# Encryption-at-rest (Fernet) for secrets stored in the DB
# ---------------------------------------------------------------------------


def _fernet() -> Fernet:
    raw = get_settings().encryption_key.encode()
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    """Encrypt a secret string for storage. Returns a Fernet token as string."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    """Decrypt a stored Fernet token."""
    return _fernet().decrypt(value.encode()).decode()
