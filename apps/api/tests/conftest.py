"""Pytest configuration for the M369 Support API.

Test database:
    The suite uses a real PostgreSQL test database (``TEST_DATABASE_URL``).
    SQLite is intentionally NOT used because RLS policies are Postgres-specific
    and silently substituting SQLite would defeat the security tests.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://m369:m369_dev_password@localhost:5432/m369_support_test",
)
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://m369:m369_dev_password@localhost:5432/m369_support_test",
)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402
from app.models import Agency, AgencyMembership, User  # noqa: E402


TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)


def _test_db_available() -> bool:
    try:
        with test_engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False


HAVE_PG = _test_db_available()


@pytest.fixture(scope="session", autouse=True)
def db_engine():
    if not HAVE_PG:
        pytest.skip("PostgreSQL test database unavailable", allow_module_level=False)
    Base.metadata.drop_all(test_engine)
    _setup_rls(test_engine)
    Base.metadata.create_all(test_engine)
    _setup_rls_policies_only(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    _teardown_rls(test_engine)


def _setup_rls(engine) -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        try:
            conn.exec_driver_sql(
                "DO $$ BEGIN CREATE ROLE m369_super_admin NOLOGIN; "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )
        except Exception:
            pass
        try:
            current_user = conn.exec_driver_sql("SELECT current_user").scalar()
            conn.exec_driver_sql(f"GRANT m369_super_admin TO {current_user}")
        except Exception:
            pass


def _setup_rls_policies_only(engine) -> None:
    tenant_tables = [
        "agencies",
        "workspaces",
        "agency_memberships",
        "teams",
        "team_memberships",
        "contacts",
        "conversations",
        "audit_logs",
    ]
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for table in tenant_tables:
            try:
                conn.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
                conn.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            except Exception:
                pass
        for table in tenant_tables:
            try:
                conn.exec_driver_sql(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
            except Exception:
                pass
        try:
            conn.exec_driver_sql("""
                CREATE POLICY tenant_isolation_agencies ON agencies
                USING (
                    current_setting('app.bypass_rls', true) = 'on'
                    OR id::text = current_setting('app.tenant_id', true)
                )
                WITH CHECK (
                    current_setting('app.bypass_rls', true) = 'on'
                    OR id::text = current_setting('app.tenant_id', true)
                )
            """)
        except Exception:
            pass
        for table in ["workspaces", "agency_memberships", "teams", "team_memberships", "contacts", "conversations", "audit_logs"]:
            try:
                conn.exec_driver_sql(f"""
                    CREATE POLICY tenant_isolation_{table} ON {table}
                    USING (
                        current_setting('app.bypass_rls', true) = 'on'
                        OR agency_id::text = current_setting('app.tenant_id', true)
                    )
                    WITH CHECK (
                        current_setting('app.bypass_rls', true) = 'on'
                        OR agency_id::text = current_setting('app.tenant_id', true)
                    )
                """)
            except Exception:
                pass


def _teardown_rls(engine) -> None:
    tenant_tables = [
        "agencies", "workspaces", "agency_memberships", "teams",
        "team_memberships", "contacts", "conversations", "audit_logs",
    ]
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for table in tenant_tables:
            try:
                conn.exec_driver_sql(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
            except Exception:
                pass
            try:
                conn.exec_driver_sql(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
                conn.exec_driver_sql(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
            except Exception:
                pass


@pytest.fixture
def db_session(db_engine) -> Iterator[Session]:
    """Per-test session with cleanup at start (truncate tenant tables)."""
    tenant_tables = [
        "audit_logs", "conversations", "contacts", "team_memberships",
        "teams", "agency_memberships", "users", "workspaces", "agencies",
    ]
    with db_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        try:
            conn.exec_driver_sql("SET LOCAL app.bypass_rls = 'on'")
        except Exception:
            pass
        for table in tenant_tables:
            try:
                conn.exec_driver_sql(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
            except Exception:
                pass

    conn = db_engine.connect()
    session = Session(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        conn.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register_agency(db_session: Session, name: str, email: str, password: str = "test-password-123") -> tuple[Agency, User, str]:
    from app.tenancy.context import bypass_rls_for_super_admin

    bypass_rls_for_super_admin(db_session)
    agency = Agency(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}")
    user = User(
        email=email.lower(),
        name=f"Owner of {name}",
        password_hash=hash_password(password),
    )
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    db_session.add_all([agency, user, membership])
    db_session.commit()
    bypass_rls_for_super_admin(db_session)
    db_session.refresh(user)
    bypass_rls_for_super_admin(db_session)
    db_session.refresh(agency)

    token = create_access_token(
        subject=str(user.id),
        token_type="agency",
        agency_id=str(agency.id),
    )
    return agency, user, token


@pytest.fixture
def agency_a(db_session: Session):
    return _register_agency(db_session, "Agency A", "owner@agency-a.test")


@pytest.fixture
def agency_b(db_session: Session):
    return _register_agency(db_session, "Agency B", "owner@agency-b.test")
