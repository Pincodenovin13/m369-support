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
REPO_ROOT = APP_DIR.parents[1]


# Sentinel values that must NEVER appear in production
_DEV_DEFAULTS = {
    "dev-only-change-this-to-64-char-random-string-in-production-please",
    "dev-only-super-admin-secret-change-this-too-in-production-please",
    "dev-only-change-this-key-please-32-bytes-base64",
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
        if self.jwt_secret_key in _DEV_DEFAULTS:
            violations.append("JWT_SECRET_KEY is a dev default")
        if self.jwt_super_admin_secret_key in _DEV_DEFAULTS:
            violations.append("JWT_SUPER_ADMIN_SECRET_KEY is a dev default")
        if self.encryption_key in _DEV_DEFAULTS:
            violations.append("ENCRYPTION_KEY is a dev default")
        if any(frag in self.database_url for frag in _DEV_DB_PASSWORD_FRAGMENTS):
            violations.append("DATABASE_URL contains a dev-only password")
        if not self.cookie_secure:
            violations.append("COOKIE_SECURE is false")
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
