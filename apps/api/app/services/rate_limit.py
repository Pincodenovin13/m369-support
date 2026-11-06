"""Rate limiting setup for Super Admin endpoints.

Uses ``slowapi`` with a Redis backend in production and an in-memory
fallback for tests + development.

FAIL-CLOSED SEMANTICS:
  - In production (``ENVIRONMENT=production``) with ``rate_limit_enabled=true``
    and ``sa_rate_limit_fail_closed_in_prod=true``: if the Redis backend
    is unreachable, the login endpoint returns 503 Service Unavailable
    rather than silently allowing unbounded attempts.
  - In test/dev: rate limiting is opt-in via ``rate_limit_enabled=false``
    (set in conftest.py). This lets the test suite drive many requests
    without hitting limits.

KEY DESIGN: Redis keys are derived from IP + email hash only — never from
the password, JWT, or MFA secret. The key format is:
  - per-IP:   "sa_login:ip:<sha256(ip)>"
  - per-acct: "sa_login:acct:<sha256(email_lower)>"
Both are incremented on every login attempt; if either exceeds its
limit, the request is rejected with 429.
"""
from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..core.config import get_settings


def _ip_key(request: Request) -> str:
    """Key for per-IP rate limiting. SHA-256 of the client IP so the Redis
    key itself never contains the IP in plaintext."""
    ip = get_remote_address(request) or "unknown"
    return f"sa_login:ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"


def _account_key(email: str) -> str:
    """Key for per-account rate limiting. SHA-256 of the lowercased email
    so the Redis key never contains the email in plaintext."""
    return f"sa_login:acct:{hashlib.sha256(email.lower().encode()).hexdigest()[:16]}"


def _build_limiter() -> Limiter | None:
    """Build the slowapi Limiter, or return None if rate limiting is disabled."""
    s = get_settings()
    if not s.rate_limit_enabled:
        return None
    # slowapi's storage_uri arg takes a redis URL. In tests/dev we disable
    # rate_limit_enabled (set in conftest) so no Redis connection is made.
    return Limiter(
        key_func=get_remote_address,
        storage_uri=s.redis_url,
        default_limits=[],  # No global default — only explicit @limiter.limit
    )


# Singleton limiter (may be None in tests/dev)
limiter: Limiter | None = _build_limiter()


def assert_redis_available_or_fail_closed(request: Request) -> None:
    """Pre-flight check: in production with fail-closed enabled, ensure the
    Redis backend is reachable. If not, return 503 (fail-closed).

    Called by the login endpoint before doing any password verification.

    The intent: if Redis is down, an attacker could otherwise send an
    unlimited number of login attempts because the rate limiter cannot
    count them. Fail-closed prevents that.
    """
    s = get_settings()
    if not s.rate_limit_enabled:
        return  # disabled entirely (test env)
    if not s.sa_rate_limit_fail_closed_in_prod:
        return  # operator opted out of fail-closed (NOT recommended in prod)
    if s.environment != "production":
        return  # only enforce in production
    if limiter is None:
        # Should not happen if rate_limit_enabled is true, but be defensive
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable — login temporarily disabled",
        )
    # Check Redis connectivity by sending a PING-equivalent. slowapi exposes
    # the underlying storage; we just call a no-op on it.
    storage = getattr(limiter, "_storage", None)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter backend unavailable",
        )
    try:
        # slowapi's Storage has a `check()` method that returns True/False
        # without raising. If not present, we catch the AttributeError and
        # treat as unavailable (fail-closed).
        ok = storage.check()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter backend unreachable",
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter backend unreachable",
        ) from None


__all__ = ["limiter", "assert_redis_available_or_fail_closed", "_ip_key", "_account_key"]
