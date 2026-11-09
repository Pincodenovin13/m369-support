"""Application configuration via pydantic-settings.

All secrets are loaded from environment variables. ``.env.example`` documents
the available variables and their default (dev-only) values. Production
deployments override these via the container's environment.

SECURITY: When ``ENVIRONMENT=production``, dev defaults for JWT secrets,
encryption key, and database URL are rejected — the app will refuse to start
unless real secrets are provided via environment variables.
"""

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parents[2]

# In the local repository APP_DIR is usually <repo>/apps/api.
# In the Docker image APP_DIR is /app and has only one parent.
# Avoid indexing a parent that does not exist.
REPO_ROOT = (
    APP_DIR.parents[1]
    if len(APP_DIR.parents) > 1
    else APP_DIR
)


# Sentinel values that must NEVER appear in production
_DEV_DEFAULTS = {
    "dev-only-change-this-to-64-char-random-string-in-production-please",
    "dev-only-super-admin-secret-change-this-too-in-production-please",
    "dev-only-change-this-key-please-32-bytes-base64",
    "dev-only-change-this-key-please-32-bytes-base64-url-safe",
}

# Known dev-only database password fragments
_DEV_DB_PASSWORD_FRAGMENTS = (
    "m369_app_dev_password",
    "change-this-local-runtime-password",
    "change-this-local-development-password",
)


class Settings(BaseSettings):
    """Centralised settings. A single instance per process via ``get_settings``."""

    # --- Application ---
    app_name: str = "M369 Support API"
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # --- Database ---
    # Runtime: m369_app (least-privilege, NO BYPASSRLS, NO SUPERUSER)
    # Migration/bootstrap: separate privileged connection (e.g., postgres)
    database_url: str = Field(
        default="postgresql+psycopg://m369_app:m369_app_dev_password@localhost:5432/m369_support"
    )
    test_database_url: str = Field(
        default="postgresql+psycopg://postgres@localhost:5432/m369_support_test"
    )
    # Super Admin operations: separate engine, BYPASSRLS but NOSUPERUSER.
    # NEVER shared with the migration service. In dev the URL is derived
    # from database_url; production MUST override via env var.
    database_url_super_admin: str = Field(
        default="postgresql+psycopg://m369_sa_runner:m369_sa_runner_dev_password@localhost:5432/m369_support"
    )
    # Super Admin authentication-only connection (Package B.1).
    # Uses m369_sa_auth — a dedicated least-privilege role that does NOT
    # have BYPASSRLS. Used ONLY by /super-admin/auth/login and
    # /super-admin/auth/login/verify-mfa. All other SA endpoints use
    # database_url_super_admin (m369_sa_runner, BYPASSRLS).
    database_url_super_admin_auth: str = Field(
        default=(
            "postgresql+psycopg://"
            "m369_sa_auth:m369_sa_auth_dev_password"
            "@localhost:5432/m369_support"
        )
    )

    # --- Database RLS tenant-context signing ---
    tenant_context_secret: str = Field(default="dev-only-m369-tenant-context-secret-change-before-production-0001", validation_alias="M369_TENANT_CONTEXT_SECRET")

    # --- JWT ---
    jwt_secret_key: str = Field(
        default="dev-only-change-this-to-64-char-random-string-in-production-please"
    )
    jwt_super_admin_secret_key: str = Field(
        default="dev-only-super-admin-secret-change-this-too-in-production-please"
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_minutes: int = Field(default=60 * 24 * 7)
    jwt_refresh_token_days: int = Field(default=30)
    jwt_issuer: str = Field(default="m369.support")
    jwt_audience: str = Field(default="m369.support.api")

    # --- Argon2id password hashing ---
    argon2_time_cost: int = Field(default=3)
    argon2_memory_cost: int = Field(default=65536)
    argon2_parallelism: int = Field(default=2)

    # --- Encryption (Fernet for secrets at rest) ---
    encryption_key: str = Field(default="dev-only-change-this-key-please-32-bytes-base64")

    # --- CORS / cookies ---
    frontend_url: str = Field(default="http://localhost:3000")
    backend_url: str = Field(default="http://localhost:8000")
    cookie_secure: bool = Field(default=False)
    cookie_samesite: str = Field(default="lax")

    # --- Rate limiting ---
    rate_limit_enabled: bool = Field(default=True)
    redis_url: str = Field(default="redis://localhost:6379/0")
    # Comma-separated list of trusted reverse-proxy IPs. When the API is
    # deployed behind Caddy/Nginx/etc., the real client IP is in the
    # X-Forwarded-For header — but we must ONLY trust that header when the
    # immediate connection comes from a known proxy. An attacker can
    # otherwise spoof X-Forwarded-For to bypass per-IP rate limits.
    # Empty string = API receives connections directly (no proxy) → use
    # the raw socket peer IP.
    trusted_proxy_ips: str = Field(default="")

    # --- Super Admin authentication hardening (Package A) ---
    # Brute-force protection on /super-admin/auth/login
    sa_max_failed_logins: int = Field(default=5, ge=1, le=20)
    sa_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    # Rate limit applied to /super-admin/auth/login (per-IP + per-account).
    # Format: "N/minute" — slowapi parses it.
    sa_login_rate_limit: str = Field(default="20/minute")
    # If Redis is unreachable in production and rate_limit_enabled=true,
    # the login endpoint returns 503 (fail-closed) rather than silently
    # allowing unbounded attempts.
    sa_rate_limit_fail_closed_in_prod: bool = Field(default=True)
    # MFA challenge token TTL (minutes). Short by design.
    super_admin_mfa_challenge_ttl_minutes: int = Field(default=5, ge=1, le=30)
    # MFA brute-force protection (separate from password brute-force)
    sa_mfa_max_failed_attempts: int = Field(default=5, ge=1, le=20)
    sa_mfa_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    # TOTP configuration. RFC 6238 defaults: 30-second step, 6 digits.
    # We allow ±1 window (i.e., accept the previous, current, or next
    # 30-second code) to tolerate clock drift between client and server.
    totp_step_seconds: int = Field(default=30, ge=15, le=120)
    totp_digits: int = Field(default=6, ge=6, le=8)
    totp_window: int = Field(default=1, ge=0, le=5)
    # Number of recovery codes generated at MFA-enable time.
    sa_mfa_recovery_code_count: int = Field(default=8, ge=4, le=16)

    # --- Agency authentication rate limiting (Package B.1.2) ---
    # Separate from Super Admin rate limits — different key namespaces.
    agency_login_ip_rate_limit: str = Field(default="30/minute")
    agency_login_account_rate_limit: str = Field(default="5/minute")
    agency_register_ip_rate_limit: str = Field(default="3/hour")

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", APP_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def _reject_dev_defaults_in_production(self) -> "Settings":
        """When ENVIRONMENT=production, refuse to start with dev defaults."""
        if self.environment != "production":
            return self

        violations: list[str] = []
        if len(self.tenant_context_secret.encode("utf-8")) < 32 or self.tenant_context_secret.startswith("dev-only-"):
            violations.append("M369_TENANT_CONTEXT_SECRET is missing, too short, or a dev default")
        if self.jwt_secret_key in _DEV_DEFAULTS:
            violations.append("JWT_SECRET_KEY is a dev default")
        if self.jwt_super_admin_secret_key in _DEV_DEFAULTS:
            violations.append("JWT_SUPER_ADMIN_SECRET_KEY is a dev default")
        if self.encryption_key in _DEV_DEFAULTS:
            violations.append("ENCRYPTION_KEY is a dev default")
        if any(frag in self.database_url for frag in _DEV_DB_PASSWORD_FRAGMENTS):
            violations.append("DATABASE_URL contains a dev-only password")
        if "m369_sa_runner_dev_password" in self.database_url_super_admin:
            violations.append("DATABASE_URL_SUPER_ADMIN contains a dev-only password")
        if "m369_sa_auth_dev_password" in self.database_url_super_admin_auth:
            violations.append("DATABASE_URL_SUPER_ADMIN_AUTH contains a dev-only password")
        if not self.cookie_secure:
            violations.append("COOKIE_SECURE is false")
        if self.environment == "production" and not self.rate_limit_enabled:
            violations.append("RATE_LIMIT_ENABLED is false in production")
        if violations:
            print(
                "FATAL: production environment detected but dev defaults are still set:\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\nSet real secrets via environment variables before starting.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance. FastAPI uses this in dependencies."""
    return Settings()
