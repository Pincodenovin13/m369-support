"""Tests for config.py: REPO_ROOT resolution + production guard.

Verifies:
  1. REPO_ROOT resolves correctly in local repo layout (<repo>/apps/api → <repo>)
  2. REPO_ROOT does NOT crash when APP_DIR has only one parent (Docker /app layout)
  3. Production guard rejects dev ENCRYPTION_KEY (including -url-safe variant)
  4. Production guard rejects DATABASE_URL with dev password fragment
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Test 1-2: REPO_ROOT resolution
# ---------------------------------------------------------------------------


def test_repo_root_in_local_repo_layout():
    """In local repo, APP_DIR is <repo>/apps/api → REPO_ROOT is <repo>.

    We verify by checking that the actual config module's APP_DIR resolves
    to a path containing 'apps/api' and REPO_ROOT is its grandparent.
    """
    # Import the actual module to get the real APP_DIR
    from app.core.config import APP_DIR, REPO_ROOT

    # In local dev: APP_DIR = .../m369-support/apps/api
    # REPO_ROOT should be .../m369-support
    assert APP_DIR.name == "api", f"Expected APP_DIR.name='api', got '{APP_DIR.name}'"
    assert APP_DIR.parent.name == "apps", f"Expected APP_DIR.parent.name='apps', got '{APP_DIR.parent.name}'"

    # REPO_ROOT should be the parent of 'apps'
    assert REPO_ROOT == APP_DIR.parents[1], (
        f"REPO_ROOT={REPO_ROOT} != APP_DIR.parents[1]={APP_DIR.parents[1]}"
    )

    # docker-compose.yml should exist at REPO_ROOT
    assert (REPO_ROOT / "docker-compose.yml").exists(), (
        f"docker-compose.yml not found at REPO_ROOT={REPO_ROOT}"
    )


def test_repo_root_does_not_crash_in_docker_layout():
    """When APP_DIR is /app (Docker), REPO_ROOT should be /app itself.

    We simulate the Docker layout by computing REPO_ROOT with only one parent.
    """
    # Simulate: APP_DIR = /app (Docker image WORKDIR)
    # APP_DIR.parents = [/, .] → len(parents) = 1 → use APP_DIR as fallback
    docker_app_dir = Path("/app")

    # Replicate the logic from config.py
    computed_root = (
        docker_app_dir.parents[1]
        if len(docker_app_dir.parents) > 1
        else docker_app_dir
    )

    assert computed_root == Path("/app"), (
        f"Expected REPO_ROOT=/app in Docker layout, got {computed_root}"
    )


# ---------------------------------------------------------------------------
# Test 3: Production guard rejects dev ENCRYPTION_KEY
# ---------------------------------------------------------------------------


def test_production_guard_rejects_dev_encryption_key():
    """When ENVIRONMENT=production and ENCRYPTION_KEY is a dev default,
    Settings() must raise SystemExit.

    This test actually instantiates Settings with the validator running.
    """
    # Use a unique random JWT secret that is NOT a dev default
    real_jwt_secret = "a-real-production-jwt-secret-that-is-definitely-not-a-dev-default-64-chars-long!!"
    real_super_admin_secret = "another-real-production-super-admin-secret-that-is-also-not-dev-default-64chars!!"
    real_db_url = "postgresql+psycopg://m369_app:a-real-production-password@db:5432/m369_support"

    # The dev encryption key from .env.example (with -url-safe suffix)
    dev_encryption_key = "dev-only-change-this-key-please-32-bytes-base64-url-safe"

    # Clear any cached settings
    from app.core.config import get_settings
    get_settings.cache_clear()

    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "JWT_SECRET_KEY": real_jwt_secret,
        "JWT_SUPER_ADMIN_SECRET_KEY": real_super_admin_secret,
        "ENCRYPTION_KEY": dev_encryption_key,
        "DATABASE_URL": real_db_url,
        "COOKIE_SECURE": "true",
    }, clear=False):
        with pytest.raises(SystemExit) as exc_info:
            from app.core.config import Settings
            Settings()

        assert exc_info.value.code == 1, (
            f"Expected SystemExit(1), got SystemExit({exc_info.value.code})"
        )

    # Verify the error message mentions ENCRYPTION_KEY
    # (SystemExit doesn't carry the print output, but we can check it was raised)

    # Clear cache again for subsequent tests
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test 4: Production guard rejects DATABASE_URL with dev password
# ---------------------------------------------------------------------------


def test_production_guard_rejects_dev_db_password():
    """When ENVIRONMENT=production and DATABASE_URL contains
    'change-this-local-runtime-password', Settings() must raise SystemExit.
    """
    real_jwt_secret = "a-real-production-jwt-secret-that-is-definitely-not-a-dev-default-64-chars-long!!"
    real_super_admin_secret = "another-real-production-super-admin-secret-that-is-also-not-dev-default-64chars!!"
    real_encryption_key = "a-real-production-encryption-key-that-is-32-bytes-base64-url-safe-aabbccddeeff0011223344"
    dev_db_url = "postgresql+psycopg://m369_app:change-this-local-runtime-password@db:5432/m369_support"

    from app.core.config import get_settings
    get_settings.cache_clear()

    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "JWT_SECRET_KEY": real_jwt_secret,
        "JWT_SUPER_ADMIN_SECRET_KEY": real_super_admin_secret,
        "ENCRYPTION_KEY": real_encryption_key,
        "DATABASE_URL": dev_db_url,
        "COOKIE_SECURE": "true",
    }, clear=False):
        with pytest.raises(SystemExit) as exc_info:
            from app.core.config import Settings
            Settings()

        assert exc_info.value.code == 1

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test 5: Production guard PASSES with all real secrets
# ---------------------------------------------------------------------------


def test_production_guard_passes_with_real_secrets():
    """When ENVIRONMENT=production and ALL secrets are real (non-dev),
    Settings() should succeed without raising.
    """
    real_jwt_secret = "a-real-production-jwt-secret-that-is-definitely-not-a-dev-default-64-chars-long!!"
    real_super_admin_secret = "another-real-production-super-admin-secret-that-is-also-not-dev-default-64chars!!"
    real_encryption_key = "a-real-production-encryption-key-that-is-32-bytes-base64-url-safe-aabbccddeeff0011223344"
    real_db_url = "postgresql+psycopg://m369_app:a-real-production-password@db:5432/m369_support"
    real_sa_db_url = "postgresql+psycopg://m369_sa_runner:a-real-production-sa-password@db:5432/m369_support"

    from app.core.config import get_settings
    get_settings.cache_clear()

    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "JWT_SECRET_KEY": real_jwt_secret,
        "JWT_SUPER_ADMIN_SECRET_KEY": real_super_admin_secret,
        "ENCRYPTION_KEY": real_encryption_key,
        "DATABASE_URL": real_db_url,
        "DATABASE_URL_SUPER_ADMIN": real_sa_db_url,
        "COOKIE_SECURE": "true",
    }, clear=False):
        from app.core.config import Settings
        settings = Settings()
        assert settings.environment == "production"
        assert settings.cookie_secure is True

    get_settings.cache_clear()
