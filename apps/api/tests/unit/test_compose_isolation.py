"""Docker Compose environment isolation test.

Parses the docker-compose.yml file and verifies that:
  - API service has NO env_file
  - Migration service has NO env_file
  - API does NOT receive POSTGRES_PASSWORD, M369_APP_PASSWORD, MIGRATION_DATABASE_URL
  - Migration does NOT receive JWT_SECRET_KEY, JWT_SUPER_ADMIN_SECRET_KEY,
    ENCRYPTION_KEY, M369_APP_PASSWORD
  - API's DATABASE_URL uses m369_app (not postgres)
  - Migration's DATABASE_URL uses postgres (not m369_app)

This test parses the YAML structure — it does NOT grep for text.
This test does NOT require a database connection.

If docker-compose.yml or required services are missing, tests FAIL (not skip).
"""
from __future__ import annotations

from pathlib import Path

import pytest

COMPOSE_PATH = Path(__file__).resolve().parents[4] / "docker-compose.yml"


def _load_compose():
    """Load and parse docker-compose.yml.

    FAILS (not skips) if the file is missing or invalid.
    """
    import yaml

    assert COMPOSE_PATH.exists(), (
        f"docker-compose.yml not found at {COMPOSE_PATH} — "
        f"test cannot verify environment isolation without it"
    )
    with open(COMPOSE_PATH) as f:
        compose = yaml.safe_load(f)
    assert compose is not None, "docker-compose.yml is empty or invalid YAML"
    assert "services" in compose, (
        f"docker-compose.yml has no 'services' key — top-level keys: {list(compose.keys())}"
    )
    return compose


def _get_service(compose, name: str) -> dict:
    """Get a service definition from parsed compose.

    FAILS if the service does not exist.
    """
    services = compose["services"]
    assert name in services, (
        f"Service '{name}' not found in docker-compose.yml — "
        f"available services: {list(services.keys())}"
    )
    return services[name]


def _get_environment(service: dict, service_name: str) -> dict:
    """Get the environment dict from a service.

    FAILS if environment is missing or not a dict.
    """
    env = service.get("environment")
    assert env is not None, (
        f"Service '{service_name}' has no 'environment' key — "
        f"all vars must be explicit (no env_file)"
    )
    assert isinstance(env, dict), (
        f"Service '{service_name}' environment is {type(env).__name__}, "
        f"expected dict — top-level keys: {list(service.keys())}"
    )
    return env


def test_api_service_has_no_env_file():
    """API must NOT use env_file — all vars must be explicit."""
    compose = _load_compose()
    api = _get_service(compose, "api")
    assert "env_file" not in api, (
        f"API service has env_file={api['env_file']} — "
        f"this leaks ALL .env vars including POSTGRES_PASSWORD"
    )


def test_migration_service_has_no_env_file():
    """Migration must NOT use env_file — only DATABASE_URL should be set."""
    compose = _load_compose()
    migration = _get_service(compose, "migration")
    assert "env_file" not in migration, (
        f"Migration service has env_file={migration['env_file']} — "
        f"this leaks JWT secrets and other unnecessary vars"
    )


def test_api_does_not_receive_privileged_credentials():
    """API must NOT receive POSTGRES_PASSWORD, M369_APP_PASSWORD, or MIGRATION_DATABASE_URL."""
    compose = _load_compose()
    api = _get_service(compose, "api")
    api_env = _get_environment(api, "api")

    forbidden = ["POSTGRES_PASSWORD", "M369_APP_PASSWORD", "MIGRATION_DATABASE_URL"]
    for var in forbidden:
        assert var not in api_env, (
            f"API service receives {var} — privileged credential leak. "
            f"API environment: {list(api_env.keys())}"
        )


def test_migration_does_not_receive_runtime_secrets():
    """Migration must NOT receive JWT secrets, encryption key, or M369_APP_PASSWORD."""
    compose = _load_compose()
    migration = _get_service(compose, "migration")
    migration_env = _get_environment(migration, "migration")

    forbidden = [
        "JWT_SECRET_KEY",
        "JWT_SUPER_ADMIN_SECRET_KEY",
        "ENCRYPTION_KEY",
        "M369_APP_PASSWORD",
    ]
    for var in forbidden:
        assert var not in migration_env, (
            f"Migration service receives {var} — unnecessary secret leak. "
            f"Migration environment: {list(migration_env.keys())}"
        )


def test_api_database_url_uses_m369_app():
    """API's DATABASE_URL must use m369_app, not postgres."""
    compose = _load_compose()
    api = _get_service(compose, "api")
    api_env = _get_environment(api, "api")
    db_url = api_env.get("DATABASE_URL", "")

    assert "m369_app" in db_url, (
        f"API DATABASE_URL does not use m369_app: {db_url}"
    )
    assert "postgres:" not in db_url.split("@")[0], (
        f"API DATABASE_URL uses postgres credential: {db_url}"
    )


def test_migration_database_url_uses_postgres():
    """Migration's DATABASE_URL must use postgres, not m369_app."""
    compose = _load_compose()
    migration = _get_service(compose, "migration")
    migration_env = _get_environment(migration, "migration")
    db_url = migration_env.get("DATABASE_URL", "")

    assert "postgres" in db_url, (
        f"Migration DATABASE_URL does not use postgres: {db_url}"
    )
    assert "m369_app" not in db_url, (
        f"Migration DATABASE_URL uses m369_app (wrong role): {db_url}"
    )


def test_migration_has_restart_no():
    """Migration service must have restart: 'no' (it's a one-shot runner)."""
    compose = _load_compose()
    migration = _get_service(compose, "migration")
    assert migration.get("restart") == "no", (
        f"Migration restart policy is {migration.get('restart')} — expected 'no'"
    )


def test_api_depends_on_migration_completed():
    """API must wait for migration to complete successfully before starting."""
    compose = _load_compose()
    api = _get_service(compose, "api")
    depends_on = api.get("depends_on", {})
    migration_dep = depends_on.get("migration", {})

    assert migration_dep.get("condition") == "service_completed_successfully", (
        f"API depends_on migration condition is {migration_dep} — "
        f"expected service_completed_successfully"
    )


def test_api_receives_database_url_super_admin():
    """API must receive DATABASE_URL_SUPER_ADMIN (m369_sa_runner).

    This is a separate connection with BYPASSRLS — distinct password from
    m369_app, never shared with the migration service.
    """
    compose = _load_compose()
    api = _get_service(compose, "api")
    api_env = _get_environment(api, "api")
    sa_url = api_env.get("DATABASE_URL_SUPER_ADMIN", "")
    assert sa_url, "API missing DATABASE_URL_SUPER_ADMIN"
    assert "m369_sa_runner" in sa_url, (
        f"DATABASE_URL_SUPER_ADMIN must use m369_sa_runner role: {sa_url}"
    )
    # The credential portion (between :// and @) must be m369_sa_runner, not postgres.
    cred = sa_url.split("://", 1)[1].split("@", 1)[0] if "://" in sa_url else ""
    assert "postgres" not in cred, (
        f"DATABASE_URL_SUPER_ADMIN uses postgres credential: {cred}"
    )


def test_migration_does_not_receive_super_admin_url():
    """Migration service must NOT receive DATABASE_URL_SUPER_ADMIN.

    Only the API process needs BYPASSRLS access. The migration runner
    connects as postgres (which already has all privileges).
    """
    compose = _load_compose()
    migration = _get_service(compose, "migration")
    migration_env = _get_environment(migration, "migration")
    assert "DATABASE_URL_SUPER_ADMIN" not in migration_env, (
        "Migration service has DATABASE_URL_SUPER_ADMIN — credential leak"
    )


def test_db_service_receives_sa_runner_password():
    """DB service must receive M369_SA_RUNNER_PASSWORD via bootstrap SQL."""
    compose = _load_compose()
    db = _get_service(compose, "db")
    db_env = _get_environment(db, "db")
    assert "M369_SA_RUNNER_PASSWORD" in db_env, (
        "DB service missing M369_SA_RUNNER_PASSWORD — bootstrap SQL cannot provision the role"
    )
