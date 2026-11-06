"""Pytest configuration for the M369 Support API.

Architecture:
    - ``setup_engine`` connects as ``postgres`` (superuser) — used for
      schema setup (alembic upgrade) and test data insertion.
    - ``test_engine`` connects as ``m369_app`` (ordinary role, NO BYPASSRLS,
      NO SUPERUSER) — used for actual test assertions. RLS is enforced.
    - Schema is created via the real Alembic migration (``alembic upgrade head``).
    - No ``except: pass`` — all errors are surfaced.
"""
from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Environment — must be set before importing app
# ---------------------------------------------------------------------------

# Runtime: m369_app (least-privilege)
# Setup/migration: postgres (superuser)
# Super Admin runtime: m369_sa_runner (BYPASSRLS, NOSUPERUSER)
M369_APP_DB_URL = "postgresql+psycopg://m369_app:m369_app_dev_password@localhost:5432/m369_support_test"
SETUP_DB_URL = "postgresql+psycopg://postgres@localhost:5432/m369_support_test"
SA_DB_URL = "postgresql+psycopg://m369_sa_runner:m369_sa_runner_dev_password@localhost:5432/m369_support_test"

os.environ["DATABASE_URL"] = M369_APP_DB_URL
os.environ["TEST_DATABASE_URL"] = SETUP_DB_URL
os.environ["DATABASE_URL_SUPER_ADMIN"] = SA_DB_URL
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "test")

# App imports must come AFTER env setup
from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402
from app.models import Agency, AgencyMembership, User  # noqa: E402


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

setup_engine = create_engine(SETUP_DB_URL, pool_pre_ping=True)
test_engine = create_engine(M369_APP_DB_URL, pool_pre_ping=True)


def _test_db_available() -> bool:
    try:
        with setup_engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception as e:
        print(f"[conftest] PostgreSQL unavailable: {e}")
        return False


HAVE_PG = _test_db_available()


# ---------------------------------------------------------------------------
# Session-scoped fixture: run Alembic migration
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db_engine():
    """Run the real Alembic migration against the test database.

    Creates all tables, roles, RLS policies, and grants — exactly as
    they would be in production. No manual schema creation.
    """
    if not HAVE_PG:
        pytest.fail("PostgreSQL test database unavailable — cannot run security tests")

    # Clean slate: drop schema, recreate, ensure m369_app + m369_sa_runner exist
    with setup_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        conn.exec_driver_sql("CREATE SCHEMA public")
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO postgres")

        # Ensure m369_app role exists (provisioned externally — NOT by migration)
        conn.exec_driver_sql(
            "DO $$ BEGIN CREATE ROLE m369_app LOGIN PASSWORD 'm369_app_dev_password' "
            "NOSUPERUSER NOBYPASSRLS NOCREATEROLE; "
            "EXCEPTION WHEN duplicate_object THEN ALTER ROLE m369_app NOSUPERUSER NOBYPASSRLS NOCREATEROLE; END $$"
        )
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO m369_app")

        # Ensure m369_sa_runner exists (LOGIN, BYPASSRLS, NOSUPERUSER)
        # Migration 0008 attempts to create it but cannot set its password,
        # so we provision the password here for tests.
        conn.exec_driver_sql(
            "DO $$ BEGIN CREATE ROLE m369_sa_runner LOGIN PASSWORD 'm369_sa_runner_dev_password' "
            "NOSUPERUSER BYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION; "
            "EXCEPTION WHEN duplicate_object THEN "
            "ALTER ROLE m369_sa_runner LOGIN PASSWORD 'm369_sa_runner_dev_password' "
            "NOSUPERUSER BYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION; END $$"
        )
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO m369_sa_runner")
        # Migration 0011 revokes CREATE on schema from m369_sa_runner.
        # We replicate that here so tests run with the same privileges.
        conn.exec_driver_sql("REVOKE CREATE ON SCHEMA public FROM m369_sa_runner")

    # Run Alembic migration as postgres (superuser — owns tables)
    api_dir = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DATABASE_URL": SETUP_DB_URL,
        },
    )
    if result.returncode != 0:
        pytest.fail(
            f"Alembic migration failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    yield test_engine

    # Teardown: drop schema only (roles persist — managed externally)
    with setup_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        conn.exec_driver_sql("CREATE SCHEMA public")


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_session(db_engine) -> Iterator[Session]:
    """Session connected as postgres (superuser) — for test data setup.

    RLS is NOT enforced for this session (postgres is a superuser).
    Use this for inserting test data. Use ``db_session`` for assertions.
    """
    conn = setup_engine.connect()
    session = Session(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        # Truncate ALL tables for next test (use setup connection as superuser)
        with setup_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.exec_driver_sql(
                "TRUNCATE TABLE "
                "super_admin_mfa_recovery_codes, super_admin_used_totp_codes, super_admin_mfa_challenges, "
                "agency_notes, platform_settings, payments, subscriptions, plans, "
                "canned_responses, kb_articles, kb_categories, channels, "
                "message_attachments, messages, "
                "audit_logs, conversations, contacts, "
                "team_memberships, teams, agency_memberships, users, "
                "workspaces, agencies, super_admins, super_admin_audit_logs "
                "RESTART IDENTITY CASCADE"
            )
            # Re-seed the 4 default plans (migration 0006 originally seeds
            # them with ON CONFLICT DO NOTHING, but TRUNCATE wipes them and
            # the migration doesn't re-run between tests).
            c.exec_driver_sql(
                "INSERT INTO plans (id, name, display_name, price_monthly, currency, is_active, sort_order, features, limits, trial_days) "
                "VALUES "
                "(gen_random_uuid(), 'starter', 'Starter', 1900, 'USD', true, 1, "
                "'{\"channels\":[\"widget\"]}'::jsonb, "
                "'{\"max_seats\":3,\"max_conversations\":500,\"max_workspaces\":1}'::jsonb, 7), "
                "(gen_random_uuid(), 'growth', 'Growth', 4900, 'USD', true, 2, "
                "'{\"channels\":[\"widget\",\"whatsapp_cloud\"]}'::jsonb, "
                "'{\"max_seats\":6,\"max_conversations\":2000,\"max_workspaces\":3}'::jsonb, 7), "
                "(gen_random_uuid(), 'pro', 'Pro', 7900, 'USD', true, 3, "
                "'{\"channels\":[\"widget\",\"whatsapp_cloud\",\"email\",\"telegram\"]}'::jsonb, "
                "'{\"max_seats\":9,\"max_conversations\":6000,\"max_workspaces\":5}'::jsonb, 7), "
                "(gen_random_uuid(), 'vip', 'VIP', 9900, 'USD', true, 4, "
                "'{\"channels\":[\"widget\",\"whatsapp_cloud\",\"email\",\"telegram\",\"instagram\",\"messenger\"],\"whitelabel\":true}'::jsonb, "
                "'{\"max_seats\":12,\"max_conversations\":15000,\"max_workspaces\":99}'::jsonb, 7) "
                "ON CONFLICT (name) DO NOTHING"
            )
        conn.close()


@pytest.fixture
def db_session(db_engine) -> Iterator[Session]:
    """Session connected as m369_app (ordinary role) — RLS enforced.

    Use this for test assertions. Tenant context must be set via
    ``set_tenant_context(db, agency_id)`` before querying tenant-owned data.
    """
    conn = test_engine.connect()
    session = Session(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        conn.close()


@pytest.fixture
def client(setup_session: Session, db_session: Session) -> Iterator[TestClient]:
    """FastAPI TestClient with get_db overridden to use the test session (m369_app).

    For Super Admin endpoints we DON'T override get_super_admin_db — the
    super_admin_engine connects via DATABASE_URL_SUPER_ADMIN env var to
    the real m369_sa_runner role, exercising the actual BYPASSRLS path.
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Super Admin fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sa_engine():
    """Engine connected as m369_sa_runner (BYPASSRLS). Used for SA assertions."""
    return create_engine(SA_DB_URL, pool_pre_ping=True)


@pytest.fixture
def super_admin(setup_session: Session):
    """Create a Super Admin + return (admin, token).

    The token carries ``tver=0`` (token_version claim) — required by the
    hardened ``get_super_admin_context`` dependency. The DB row also has
    ``token_version=0`` (server_default from migration 0010), so the
    request dependency will accept this token.
    """
    from app.models import SuperAdmin
    from app.security import create_access_token, hash_password

    admin = SuperAdmin(
        email=f"sa-{uuid.uuid4().hex[:6]}@m369.platform",
        name="Super Admin",
        password_hash=hash_password("super-admin-password-123"),
        is_active=True,
    )
    setup_session.add(admin)
    setup_session.commit()
    setup_session.refresh(admin)
    # token_version=0 is the default for a fresh admin row
    token = create_access_token(
        subject=str(admin.id),
        token_type="super_admin",
        token_version=admin.token_version,
    )
    return admin, token


@pytest.fixture
def sa_token(super_admin):
    return super_admin[1]


@pytest.fixture
def sa_client(client):
    """Same TestClient, just a clearer name when used for Super Admin tests.

    The TestClient uses cookies to carry the Super Admin token (the auth
    endpoint sets it automatically). For raw header auth, pass the token
    explicitly in the Authorization header.
    """
    return client


def _register_agency(setup_session: Session, name: str, email: str, password: str = "test-password-123") -> tuple[Agency, User, str]:
    """Register an agency + owner using the setup session (postgres, bypasses RLS)."""
    from app.slugs import unique_slug

    agency = Agency(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}")
    user = User(
        email=email.lower(),
        name=f"Owner of {name}",
        password_hash=hash_password(password),
    )
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)
    setup_session.refresh(agency)

    token = create_access_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(agency.id),
    )
    return agency, user, token


@pytest.fixture
def agency_a(setup_session: Session):
    return _register_agency(setup_session, "Agency A", "owner@agency-a.com")


@pytest.fixture
def agency_b(setup_session: Session):
    return _register_agency(setup_session, "Agency B", "owner@agency-b.com")
