"""Rate limiting for Super Admin authentication endpoints.

Custom atomic limiter using Redis INCR + EXPIRE. Why not slowapi?

  slowapi's decorator-based approach (`@limiter.limit("20/minute")`) ties
  the limit to a single key function. We need TWO independent limits
  (per-IP AND per-account) on the same endpoint, with different keys.
  slowapi can technically do this with multiple decorators, but its
  storage backend abstraction makes the fail-closed path fragile —
  `storage.check()` is not a real method in the installed version
  (it was an assumption in Package A that turned out to be wrong).

  Instead, we implement a direct Redis-based limiter with:
    - INCR (atomic counter)
    - EXPIRE (TTL on first increment)
    - Lua script for the INCR+EXPIRE combo (true atomicity — no race
      between INCR and EXPIRE even under concurrent load)

FAIL-CLOSED SEMANTICS:
  - In production with rate_limit_enabled=true and
    sa_rate_limit_fail_closed_in_prod=true: if Redis is unreachable,
    the endpoint returns 503 (NOT 429, NOT 200).
  - In test/dev: rate limiting is disabled via RATE_LIMIT_ENABLED=false
    (conftest sets this). Tests that need to verify rate-limit behavior
    inject a fake Redis client via the ``_redis_client`` override.

KEY DESIGN — no secrets in Redis keys:
  - per-IP:   "sa_login:ip:{sha256(ip)[:16]}"
  - per-acct: "sa_login:acct:{sha256(email_lower)[:16]}"
  Passwords, JWTs, MFA secrets NEVER appear in keys or values.
"""
from __future__ import annotations

import hashlib
import ipaddress
from typing import Any

import redis
from fastapi import HTTPException, Request, status

from ..core.config import get_settings


# ---------------------------------------------------------------------------
# Key derivation — SHA-256 hashed, never plaintext
# ---------------------------------------------------------------------------


def _get_trusted_proxies() -> frozenset[str]:
    """Parse the ``trusted_proxy_ips`` setting into a set.

    Empty string → no trusted proxies → X-Forwarded-For is NEVER trusted.
    Each entry is validated with ``ipaddress.ip_address()`` — malformed
    entries are silently dropped (a misconfigured proxy IP is treated as
    "no proxy" rather than "trust everyone").
    """
    s = get_settings()
    raw = s.trusted_proxy_ips.strip()
    if not raw:
        return frozenset()
    result: set[str] = set()
    for ip_str in raw.split(","):
        ip_str = ip_str.strip()
        if not ip_str:
            continue
        try:
            ipaddress.ip_address(ip_str)
            result.add(ip_str)
        except ValueError:
            # Malformed IP in config — skip it. Do NOT crash the app, but
            # also do NOT trust anything until the operator fixes the config.
            pass
    return frozenset(result)


def _validate_ip(ip_str: str) -> str | None:
    """Validate that ``ip_str`` is a parseable IP address.

    Returns the normalized string form if valid, None otherwise.
    Uses ``ipaddress.ip_address()`` which accepts both IPv4 and IPv6.
    Malformed values, empty strings, and non-IP hosts are rejected.
    """
    if not ip_str:
        return None
    try:
        addr = ipaddress.ip_address(ip_str.strip())
        return str(addr)
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    """Return the real client IP for rate-limiting purposes.

    Trust model:
      - If ``trusted_proxy_ips`` is EMPTY: the API receives connections
        directly (no reverse proxy). Use the raw socket peer IP
        (``request.client.host``). X-Forwarded-For is NEVER trusted —
        an attacker could otherwise spoof it.
      - If ``trusted_proxy_ips`` is SET: only when the immediate connection
        comes from one of those proxy IPs do we read X-Forwarded-For.
        We take the LEFTMOST (original client) entry and validate it with
        ``ipaddress.ip_address()``. If the header is missing, empty,
        malformed, or contains a non-IP value, we fall back to the peer IP.

    This prevents an attacker from bypassing per-IP rate limits by
    sending ``X-Forwarded-For: 1.2.3.4`` directly to the API when no
    proxy is configured, or by sending a malformed XFF value that would
    otherwise produce an invalid Redis key.
    """
    peer_ip = request.client.host if request.client else "unknown"
    trusted = _get_trusted_proxies()
    if not trusted:
        # No proxy configured — peer IP is the real client
        return peer_ip
    if peer_ip not in trusted:
        # Connection from an untrusted host — don't trust XFF
        return peer_ip
    # Peer IS a trusted proxy — read X-Forwarded-For
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # Leftmost entry is the original client — validate it
        first = xff.split(",")[0].strip()
        validated = _validate_ip(first)
        if validated:
            return validated
        # XFF was present but malformed — fall back to peer IP rather than
        # trusting an invalid value
    return peer_ip


def _ip_key(ip: str) -> str:
    """Redis key for per-IP rate limiting. SHA-256 of the client IP."""
    return f"sa_login:ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"


def _account_key(email: str) -> str:
    """Redis key for per-account rate limiting. SHA-256 of lowercased email."""
    return f"sa_login:acct:{hashlib.sha256(email.lower().encode()).hexdigest()[:16]}"


# ---------------------------------------------------------------------------
# Redis client singleton
# ---------------------------------------------------------------------------


_redis_client: redis.Redis | None = None
# Test override: set this to a fakeredis.FakeRedis instance to test
# rate-limiting without a real Redis server.
_test_override: redis.Redis | None = None


def set_test_redis_client(client: redis.Redis | None) -> None:
    """Inject a fake Redis client for testing. Pass None to clear."""
    global _test_override
    _test_override = client


def get_redis_client() -> redis.Redis | None:
    """Return the Redis client, or None if rate limiting is disabled.

    In tests, the conftest sets RATE_LIMIT_ENABLED=false, so this returns
    None and rate limiting is skipped entirely. Tests that verify
    rate-limit behavior call ``set_test_redis_client(fakeredis.FakeRedis())``
    first.
    """
    if _test_override is not None:
        return _test_override
    s = get_settings()
    if not s.rate_limit_enabled:
        return None
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            s.redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
    return _redis_client


# ---------------------------------------------------------------------------
# Atomic INCR + EXPIRE via Lua
# ---------------------------------------------------------------------------

# Lua script: atomically increment the counter and set TTL on first increment.
# Returns the new count. The EXPIRE is only set if this is the first increment
# (count == 1 after INCR), so the TTL is the window duration.
_LUA_INCR_EXPIRE = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


def _check_limit(
    client: redis.Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Check + increment a single rate-limit key atomically.

    Returns (allowed, current_count).
    - allowed=True if current_count <= limit
    - allowed=False if current_count > limit (429 should be returned)

    The INCR + EXPIRE is atomic via Lua — no race between INCR and EXPIRE
    even under concurrent load.
    """
    try:
        count = client.eval(_LUA_INCR_EXPIRE, 1, key, window_seconds)
        return (count <= limit, count)
    except redis.RedisError:
        # Redis error during eval — fail-closed in production
        raise


def assert_redis_available_or_fail_closed(request: Request) -> None:
    """Pre-flight: in production with fail-closed, ensure Redis is reachable.

    Returns None if Redis is OK (or if rate limiting is disabled).
    Raises HTTPException(503) if Redis is unreachable in production.
    """
    s = get_settings()
    if not s.rate_limit_enabled:
        return  # disabled entirely (test env)
    if s.environment != "production":
        return  # only enforce in production
    if not s.sa_rate_limit_fail_closed_in_prod:
        return  # operator opted out

    client = get_redis_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable — login temporarily disabled",
        )
    try:
        client.ping()
    except Exception:
        # Catch ALL exceptions (redis.RedisError, ConnectionError, etc.)
        # Fail-closed: never allow login when Redis is unreachable in prod.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter backend unreachable",
        ) from None


def check_login_rate_limit(
    request: Request,
    email: str,
) -> None:
    """Check both per-IP and per-account rate limits for /super-admin/auth/login.

    Raises HTTPException(429) if either limit is exceeded.
    Raises HTTPException(503) if Redis is unreachable in production (fail-closed).
    Does nothing if rate limiting is disabled (test/dev env).

    Limits:
      - per-IP:   sa_login_rate_limit (default "20/minute")
      - per-acct: sa_login_rate_limit (same — both use the same configured value)
    """
    s = get_settings()
    if not s.rate_limit_enabled:
        return  # disabled

    client = get_redis_client()
    if client is None:
        # Should not happen if rate_limit_enabled is true, but be defensive
        if s.environment == "production" and s.sa_rate_limit_fail_closed_in_prod:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter unavailable",
            )
        return

    # Parse the limit string "N/minute" → (N, 60)
    limit_str = s.sa_login_rate_limit
    try:
        parts = limit_str.split("/")
        limit_n = int(parts[0])
        window = parts[1] if len(parts) > 1 else "minute"
        window_seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(window, 60)
    except (ValueError, IndexError):
        limit_n, window_seconds = 20, 60  # safe fallback

    # Per-IP key — uses get_client_ip() which respects the trusted-proxy
    # trust boundary (only reads X-Forwarded-For when the peer is a
    # configured trusted proxy IP).
    ip = get_client_ip(request)
    ip_key = _ip_key(ip)
    # Per-account key
    acct_key = _account_key(email)

    try:
        ip_allowed, ip_count = _check_limit(client, ip_key, limit_n, window_seconds)
        acct_allowed, acct_count = _check_limit(client, acct_key, limit_n, window_seconds)
    except redis.RedisError:
        if s.environment == "production" and s.sa_rate_limit_fail_closed_in_prod:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter backend unreachable",
            ) from None
        # In dev/test: fail-open (log would go here in production)
        return

    if not ip_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts from this IP. Retry after {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )
    if not acct_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts for this account. Retry after {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )


def check_verify_mfa_rate_limit(
    request: Request,
    sa_id: Any,
) -> None:
    """Rate limit for /super-admin/auth/login/verify-mfa.

    Independent from the login rate limit — uses a separate key namespace
    so MFA brute-force attempts don't mix with password attempts.

    Per-IP and per-super_admin_id, both limited.
    """
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

    # MFA verify limit: tighter than login (default 10/minute)
    # Reuse sa_login_rate_limit but with a "mfa_" prefix in the key namespace
    limit_str = s.sa_login_rate_limit
    try:
        parts = limit_str.split("/")
        limit_n = int(parts[0])
        window = parts[1] if len(parts) > 1 else "minute"
        window_seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(window, 60)
    except (ValueError, IndexError):
        limit_n, window_seconds = 20, 60

    # Use half the login limit for MFA (stricter — MFA codes are 6 digits)
    mfa_limit = max(1, limit_n // 2)

    ip = get_client_ip(request)
    ip_key = f"sa_mfa_verify:ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
    sa_key = f"sa_mfa_verify:sa:{hashlib.sha256(str(sa_id).encode()).hexdigest()[:16]}"

    try:
        ip_allowed, _ = _check_limit(client, ip_key, mfa_limit, window_seconds)
        sa_allowed, _ = _check_limit(client, sa_key, mfa_limit, window_seconds)
    except redis.RedisError:
        if s.environment == "production" and s.sa_rate_limit_fail_closed_in_prod:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter backend unreachable",
            ) from None
        return

    if not ip_allowed or not sa_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many MFA attempts. Retry after {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )


__all__ = [
    "set_test_redis_client",
    "get_redis_client",
    "get_client_ip",
    "assert_redis_available_or_fail_closed",
    "check_login_rate_limit",
    "check_verify_mfa_rate_limit",
    "_ip_key",
    "_account_key",
]
