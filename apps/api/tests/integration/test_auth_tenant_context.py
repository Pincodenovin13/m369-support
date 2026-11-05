"""Authentication & tenant context tests.

Tests the full flow: JWT → membership verification → agency active check → RLS.
All tests use real PostgreSQL with real seeded data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Agency, AgencyMembership, User
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)


pytestmark = [pytest.mark.security, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_user_with_memberships(
    setup_session: Session,
    email: str,
    memberships: list[tuple[Agency, str]],
) -> User:
    """Create a user with multiple agency memberships."""
    user = User(email=email.lower(), name=f"User {email}", password_hash="x", is_active=True)
    for agency, role in memberships:
        m = AgencyMembership(user=user, agency=agency, role=role)
        setup_session.add(m)
    setup_session.add(user)
    setup_session.commit()
    setup_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# B. Agency Selection — Login
# ---------------------------------------------------------------------------


def test_login_single_membership_works_without_agency_id(client: TestClient, setup_session: Session, agency_a):
    """User with one membership can login without specifying agency_id."""
    agency, owner, _ = agency_a
    r = client.post("/api/v1/auth/login", json={
        "email": "owner@agency-a.com",
        "password": "test-password-123",
    })
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


def test_login_multi_membership_requires_agency_id(client: TestClient, setup_session: Session, agency_a, agency_b):
    """User with multiple memberships must specify agency_id."""
    agency_a_obj, _, _ = agency_a
    agency_b_obj, _, _ = agency_b

    user = _create_user_with_memberships(
        setup_session,
        "multi@example.com",
        [(agency_a_obj, "agent"), (agency_b_obj, "agent")],
    )
    from app.security import hash_password
    user.password_hash = hash_password("test-password-123")
    setup_session.commit()

    r = client.post("/api/v1/auth/login", json={
        "email": "multi@example.com",
        "password": "test-password-123",
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    detail = r.json()["detail"]
    assert "available_agencies" in str(detail), f"Response should list available agencies: {detail}"


def test_login_multi_membership_with_agency_id(client: TestClient, setup_session: Session, agency_a, agency_b):
    """User with multiple memberships can login with explicit agency_id."""
    agency_a_obj, _, _ = agency_a
    agency_b_obj, _, _ = agency_b

    user = _create_user_with_memberships(
        setup_session,
        "multi2@example.com",
        [(agency_a_obj, "agent"), (agency_b_obj, "agent")],
    )
    from app.security import hash_password
    user.password_hash = hash_password("test-password-123")
    setup_session.commit()

    r = client.post("/api/v1/auth/login", json={
        "email": "multi2@example.com",
        "password": "test-password-123",
        "agency_id": str(agency_a_obj.id),
    })
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


def test_login_wrong_agency_id_rejected(client: TestClient, setup_session: Session, agency_a, agency_b):
    """User specifying an agency they're not a member of gets 403."""
    agency_a_obj, _, _ = agency_a
    agency_b_obj, _, _ = agency_b

    user = _create_user_with_memberships(
        setup_session,
        "single@example.com",
        [(agency_a_obj, "agent")],
    )
    from app.security import hash_password
    user.password_hash = hash_password("test-password-123")
    setup_session.commit()

    r = client.post("/api/v1/auth/login", json={
        "email": "single@example.com",
        "password": "test-password-123",
        "agency_id": str(agency_b_obj.id),
    })
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# B. Refresh Token — Bound to Agency
# ---------------------------------------------------------------------------


def test_refresh_preserves_agency_context(client: TestClient, setup_session: Session, agency_a):
    """Refresh token for agency A must produce an access token for agency A."""
    agency, owner, _ = agency_a

    r = client.post("/api/v1/auth/login", json={
        "email": "owner@agency-a.com",
        "password": "test-password-123",
    })
    assert r.status_code == 200

    refresh_token = r.cookies.get("refresh_token")
    assert refresh_token is not None

    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"

    new_access = r2.json()["access_token"]
    r3 = client.get("/api/v1/agencies/current", headers={"Authorization": f"Bearer {new_access}"})
    assert r3.status_code == 200, f"Expected 200, got {r3.status_code}: {r3.text}"
    assert r3.json()["id"] == str(agency.id)


def test_refresh_cannot_switch_agency(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Refresh token for agency A must NOT produce access token for agency B.

    Even if agency_id for B is included in the request body, the refresh
    endpoint must ignore it — agency_id comes ONLY from the signed refresh token.
    """
    agency_a_obj, _, _ = agency_a
    agency_b_obj, _, _ = agency_b

    # Create multi-agency user
    user = _create_user_with_memberships(
        setup_session,
        "refresh-switch@example.com",
        [(agency_a_obj, "agent"), (agency_b_obj, "agent")],
    )
    from app.security import hash_password
    user.password_hash = hash_password("test-password-123")
    setup_session.commit()

    # Login as agency A
    r = client.post("/api/v1/auth/login", json={
        "email": "refresh-switch@example.com",
        "password": "test-password-123",
        "agency_id": str(agency_a_obj.id),
    })
    assert r.status_code == 200
    refresh_token = r.cookies.get("refresh_token")
    assert refresh_token is not None

    # Try to refresh — include agency_id for B in the body (should be ignored or rejected)
    r2 = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token,
        "agency_id": str(agency_b_obj.id),  # Attempt to switch to B
    })
    # Pydantic may reject the extra field (422) or ignore it (200)
    # Either way, the result must NOT be an access token for agency B
    if r2.status_code == 200:
        new_access = r2.json()["access_token"]
        r3 = client.get("/api/v1/agencies/current", headers={"Authorization": f"Bearer {new_access}"})
        assert r3.status_code == 200
        assert r3.json()["id"] == str(agency_a_obj.id), (
            f"Refresh switched agency! Expected {agency_a_obj.id}, got {r3.json()['id']}"
        )
    elif r2.status_code == 422:
        # Pydantic rejected the extra field — acceptable
        pass
    else:
        pytest.fail(f"Unexpected status {r2.status_code}: {r2.text}")


def test_refresh_rejects_wrong_scope(client: TestClient, setup_session: Session):
    """A token with scope != 'agency' must not work on /auth/refresh.

    create_refresh_token now rejects token_type='super_admin' with ValueError.
    We craft a token manually with scope='super_admin' to simulate an
    attacker who bypasses the function and signs with the wrong key.
    The refresh endpoint must reject it because the scope doesn't match.
    """
    import jwt as pyjwt
    from app.core.config import get_settings
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "refresh",
        "exp": int((now + timedelta(days=30)).timestamp()),
        "iat": int(now.timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "scope": "super_admin",  # Wrong scope — should be rejected
    }
    # Sign with super_admin key (different from agency key)
    bad_token = pyjwt.encode(payload, s.jwt_super_admin_secret_key, algorithm=s.jwt_algorithm)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": bad_token})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


def test_refresh_rejects_token_without_agency_id(client: TestClient, setup_session: Session, agency_a):
    """A refresh token without agency_id claim must be rejected."""
    # Manually craft a refresh token without agency_id using the internal API
    import jwt as pyjwt
    from app.core.config import get_settings
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "refresh",
        "exp": int((now + timedelta(days=30)).timestamp()),
        "iat": int(now.timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "scope": "agency",
        # NOTE: no agency_id
    }
    bad_token = pyjwt.encode(payload, s.jwt_secret_key, algorithm=s.jwt_algorithm)

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": bad_token})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


def test_refresh_rejects_invalid_agency_id(client: TestClient, setup_session: Session):
    """A refresh token with an invalid (non-UUID) agency_id must be rejected."""
    import jwt as pyjwt
    from app.core.config import get_settings
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "refresh",
        "exp": int((now + timedelta(days=30)).timestamp()),
        "iat": int(now.timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "scope": "agency",
        "agency_id": "not-a-uuid",
    }
    bad_token = pyjwt.encode(payload, s.jwt_secret_key, algorithm=s.jwt_algorithm)

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": bad_token})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


def test_refresh_rejected_after_membership_removed(client: TestClient, setup_session: Session, agency_a):
    """If membership is removed after login, refresh must be rejected."""
    agency, owner, _ = agency_a

    r = client.post("/api/v1/auth/login", json={
        "email": "owner@agency-a.com",
        "password": "test-password-123",
    })
    assert r.status_code == 200
    refresh_token = r.cookies.get("refresh_token")

    # Remove the membership
    membership = setup_session.scalar(
        select(AgencyMembership).where(
            AgencyMembership.user_id == owner.id,
            AgencyMembership.agency_id == agency.id,
        )
    )
    setup_session.delete(membership)
    setup_session.commit()

    # Refresh should fail
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 403, f"Expected 403, got {r2.status_code}: {r2.text}"


def test_refresh_rejected_after_agency_deactivated(client: TestClient, setup_session: Session, agency_a):
    """If agency is deactivated after login, refresh must be rejected."""
    agency, owner, _ = agency_a

    r = client.post("/api/v1/auth/login", json={
        "email": "owner@agency-a.com",
        "password": "test-password-123",
    })
    assert r.status_code == 200
    refresh_token = r.cookies.get("refresh_token")

    # Deactivate the agency
    agency.is_active = False
    setup_session.commit()

    # Refresh should fail
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 403, f"Expected 403, got {r2.status_code}: {r2.text}"


# ---------------------------------------------------------------------------
# C. Inactive User / Inactive Agency
# ---------------------------------------------------------------------------


def test_inactive_user_rejected(client: TestClient, setup_session: Session, agency_a):
    """Inactive user cannot login."""
    agency, _, _ = agency_a
    from app.security import hash_password

    user = User(
        email="inactive@example.com",
        name="Inactive",
        password_hash=hash_password("test-password-123"),
        is_active=False,
    )
    m = AgencyMembership(user=user, agency=agency, role="agent")
    setup_session.add_all([user, m])
    setup_session.commit()

    r = client.post("/api/v1/auth/login", json={
        "email": "inactive@example.com",
        "password": "test-password-123",
    })
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_inactive_agency_rejected_on_login(client: TestClient, setup_session: Session):
    """User cannot login to an inactive agency."""
    from app.security import hash_password

    agency = Agency(name="Inactive Agency", slug=f"inactive-{uuid.uuid4().hex[:6]}", is_active=False)
    user = User(
        email="inactive-agency@example.com",
        name="User",
        password_hash=hash_password("test-password-123"),
    )
    m = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, m])
    setup_session.commit()

    r = client.post("/api/v1/auth/login", json={
        "email": "inactive-agency@example.com",
        "password": "test-password-123",
    })
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert "not active" in r.json()["detail"].lower()


def test_inactive_agency_rejected_on_api_access(client: TestClient, setup_session: Session, agency_a):
    """Even with a valid token, an inactive agency should return 403."""
    agency, owner, owner_token = agency_a

    agency.is_active = False
    setup_session.commit()

    r = client.get(
        "/api/v1/agencies/current",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert "not active" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# C. Super Admin token isolation
# ---------------------------------------------------------------------------


def test_super_admin_token_rejected_on_agency_endpoint(client: TestClient):
    """Super Admin token must not access agency endpoints."""
    sa_token = create_access_token(subject=str(uuid.uuid4()), token_type="super_admin")
    r = client.get(
        "/api/v1/agencies/current",
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_agency_token_rejected_on_super_admin_endpoint(client: TestClient, agency_a):
    """Agency token must not access Super Admin endpoints."""
    _, _, agency_token = agency_a
    r = client.get(
        "/api/v1/super-admin/auth/me",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# B. Cross-agency token rejection
# ---------------------------------------------------------------------------


def test_token_with_wrong_agency_id_rejected(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Token scoped to agency A cannot access agency B's resources."""
    agency_a_obj, owner_a, token_a = agency_a
    agency_b_obj, _, _ = agency_b

    from app.models import Workspace
    ws_b = Workspace(agency_id=agency_b_obj.id, name="WS B", slug=f"ws-b-{uuid.uuid4().hex[:6]}")
    setup_session.add(ws_b)
    setup_session.commit()

    r = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 200
    workspaces = r.json()
    for ws in workspaces:
        assert ws["agency_id"] == str(agency_a_obj.id), (
            f"Agency A saw workspace belonging to agency B: {ws}"
        )


# ---------------------------------------------------------------------------
# FIX 2 — SECURITY DEFINER function ACL tests
# ---------------------------------------------------------------------------

APP_DB_URL = "postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test"


def test_public_cannot_execute_login_helper_function(db_engine):
    """PUBLIC role must NOT have EXECUTE on get_user_memberships_for_login."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT proacl
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname = 'get_user_memberships_for_login'
            """)
            row = cur.fetchone()
            assert row is not None, "Function get_user_memberships_for_login not found"
            acl = row[0]
            if acl is not None:
                # Check that PUBLIC does not have EXECUTE
                # ACL format: {owner=X/owner,m369_app=X/m369_app}
                # We check for "=X/" entries that belong to PUBLIC (no role name before =)
                for acl_entry in acl:
                    # PUBLIC entries look like "=X/" (no grantee before =)
                    # Skip entries that have a grantee (like "m369_app=X/m369_app")
                    if acl_entry.startswith("=X"):
                        pytest.fail(f"PUBLIC has EXECUTE on function — ACL: {acl_entry}")
    finally:
        conn.close()


def test_m369_app_can_execute_login_helper_function(db_engine):
    """m369_app must have EXECUTE on get_user_memberships_for_login."""
    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            # Try calling the function — should succeed
            cur.execute("SELECT count(*) FROM get_user_memberships_for_login('00000000-0000-0000-0000-000000000000')")
            count = cur.fetchone()[0]
            assert count == 0, f"Expected 0 memberships for non-existent user, got {count}"
    except psycopg.errors.InsufficientPrivilege:
        pytest.fail("m369_app cannot execute get_user_memberships_for_login — missing EXECUTE privilege")
    finally:
        conn.close()


def test_login_helper_function_is_security_definer(db_engine):
    """Function must have prosecdef=true (SECURITY DEFINER), restricted search_path,
    and be owned by m369_login_reader (NOT postgres/superuser)."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.proname,
                    pg_get_userbyid(p.proowner) AS function_owner,
                    p.prosecdef,
                    p.proconfig,
                    p.proacl::text
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname = 'get_user_memberships_for_login'
            """)
            row = cur.fetchone()
            assert row is not None, "Function not found"
            proname, owner, prosecdef, proconfig, proacl = row
            assert prosecdef is True, f"prosecdef={prosecdef}, expected True"
            assert owner == "m369_login_reader", (
                f"Function owner is {owner}, expected m369_login_reader — "
                f"postgres (superuser) must NOT own this function"
            )
            assert proconfig is not None, "proconfig is NULL — search_path not set"
            assert "pg_catalog" in str(proconfig), f"search_path does not include pg_catalog: {proconfig}"
    finally:
        conn.close()


def test_login_helper_function_owner_is_least_privilege(db_engine):
    """m369_login_reader must be NOLOGIN, NOSUPERUSER, BYPASSRLS, NOCREATEROLE, NOCREATEDB."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
                FROM pg_roles WHERE rolname = 'm369_login_reader'
            """)
            row = cur.fetchone()
            assert row is not None, "m369_login_reader role not found"
            canlogin, is_super, has_bypass, can_create_role, can_create_db = row
            assert not canlogin, "m369_login_reader must be NOLOGIN"
            assert not is_super, "m369_login_reader must be NOSUPERUSER"
            assert has_bypass, "m369_login_reader must have BYPASSRLS (to read RLS tables)"
            assert not can_create_role, "m369_login_reader must be NOCREATEROLE"
            assert not can_create_db, "m369_login_reader must be NOCREATEDB"
    finally:
        conn.close()


def test_m369_app_is_not_member_of_login_reader(db_engine):
    """NO role must be a member of m369_login_reader — not just m369_app."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.rolname as member_name
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.member
                JOIN pg_roles parent ON parent.oid = m.roleid
                WHERE parent.rolname = 'm369_login_reader'
            """)
            members = cur.fetchall()
            assert len(members) == 0, (
                f"m369_login_reader has members: {[m[0] for m in members]} — "
                f"no role should be a member (prevents SET ROLE escalation)"
            )
    finally:
        conn.close()


def test_login_reader_has_only_select_on_required_tables(db_engine):
    """m369_login_reader must have SELECT only on agency_memberships and agencies.

    Checks ALL tables in schema public — not just a few.
    Also checks NO INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER on any table.
    """
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            # Get ALL table names in public schema
            cur.execute("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            """)
            all_tables = [r[0] for r in cur.fetchall()]
            assert len(all_tables) > 0, "No tables found in public schema — migration may have failed"

            allowed_select_tables = {"agency_memberships", "agencies"}
            all_privs = ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]

            for table in all_tables:
                # SELECT check
                cur.execute(
                    "SELECT has_table_privilege('m369_login_reader', %s, 'SELECT')",
                    (table,),
                )
                has_select = cur.fetchone()[0]
                if table in allowed_select_tables:
                    assert has_select, (
                        f"m369_login_reader should have SELECT on {table} but does not"
                    )
                else:
                    assert not has_select, (
                        f"m369_login_reader has SELECT on {table} — should not have access"
                    )

                # Check all non-SELECT privileges on ALL tables
                for priv in all_privs:
                    cur.execute(
                        "SELECT has_table_privilege('m369_login_reader', %s, %s)",
                        (table, priv),
                    )
                    has_priv = cur.fetchone()[0]
                    assert not has_priv, (
                        f"m369_login_reader has {priv} on {table} — "
                        f"should have NO privileges other than SELECT on agency_memberships and agencies"
                    )
    finally:
        conn.close()


def test_login_reader_has_no_create_on_public_schema(db_engine):
    """m369_login_reader must NOT have CREATE on schema public."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT has_schema_privilege('m369_login_reader', 'public', 'CREATE')")
            assert not cur.fetchone()[0], (
                "m369_login_reader has CREATE on schema public — should not"
            )
            # But should have USAGE
            cur.execute("SELECT has_schema_privilege('m369_login_reader', 'public', 'USAGE')")
            assert cur.fetchone()[0], "m369_login_reader should have USAGE on schema public"
    finally:
        conn.close()
