"""Super Admin auth schemas: login, MFA challenge/verify/setup/enable/disable, recovery codes."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SuperAdminCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    initial: bool = Field(default=False)


class SuperAdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class SuperAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    is_active: bool


# ---------------------------------------------------------------------------
# Super Admin MFA schemas (Phase 1 Security Hardening / Package A)
# ---------------------------------------------------------------------------


class SuperAdminMFARequiredResponse(BaseModel):
    """Response when login password check succeeds but MFA is required.

    The client must submit a TOTP code (or recovery code) along with the
    ``mfa_challenge`` token to ``/super-admin/auth/login/verify-mfa`` to
    obtain a full Super Admin access token.

    The challenge token is short-lived (default 5 min) and CAN ONLY be
    used at the verify-mfa endpoint — every management endpoint rejects
    it via ``get_super_admin_context`` (which calls ``decode_super_admin_token``
    and never ``decode_mfa_challenge_token``).
    """

    mfa_required: bool = True
    mfa_challenge: str
    expires_in_seconds: int


class SuperAdminVerifyMFARequest(BaseModel):
    """Submit a TOTP code or recovery code with the MFA challenge token."""

    mfa_challenge: str = Field(min_length=1)
    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=1, max_length=64)


class SuperAdminMFASetupResponse(BaseModel):
    """MFA setup response — secret + otpauth URL.

    The secret is returned in plaintext ONCE so the client can render a
    QR code. It is NOT yet active — the client must submit a valid TOTP
    code at ``/super-admin/auth/mfa/enable`` to activate MFA.

    After activation, the plaintext secret is NEVER again returned by
    any API endpoint.
    """

    secret: str
    otpauth_url: str


class SuperAdminMFAEnableRequest(BaseModel):
    """Activate MFA — re-confirm password and submit a TOTP proof."""

    # A stolen long-lived access token alone must not be enough to bind an
    # attacker-controlled authenticator to the administrator account.
    password: str = Field(min_length=1, max_length=128)
    secret: str = Field(min_length=16, max_length=64)
    code: str = Field(min_length=6, max_length=8)


class SuperAdminMFADisableRequest(BaseModel):
    """Disable MFA — requires a TOTP code or recovery code.

    Disabling MFA cannot be done with just the password — the caller
    must prove possession of a second factor.
    """

    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=1, max_length=64)


class SuperAdminRecoveryCodesOut(BaseModel):
    """Recovery codes — returned ONCE at MFA-enable time.

    Plaintext is never stored. Each code is single-use; replay rejected.
    """

    recovery_codes: list[str]


__all__ = [
    "SuperAdminCreate",
    "SuperAdminLoginRequest",
    "SuperAdminOut",
    "SuperAdminMFARequiredResponse",
    "SuperAdminVerifyMFARequest",
    "SuperAdminMFASetupResponse",
    "SuperAdminMFAEnableRequest",
    "SuperAdminMFADisableRequest",
    "SuperAdminRecoveryCodesOut",
]
