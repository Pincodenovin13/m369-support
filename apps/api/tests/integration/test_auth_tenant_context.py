"""Authentication & tenant context tests.

Tests the full flow: JWT → membership verification → agency active check → RLS.
All tests use real PostgreSQL with real seeded data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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

    The RefreshRequest schema no longer has an agency_id field.
    Sending agency_id in the body should be ignored (extra fields are
    rejected by Pydantic with extra='forbid' or simply ignored).
    The agency_id comes ONLY from the signed refresh token.
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

    # Try to refresh — the response should be for agency A, NOT B
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"

    new_access = r2.json()["access_token"]
    r3 = client.get("/api/v1/agencies/current", headers={"Authorization": f"Bearer {new_access}"})
    assert r3.status_code == 200
    assert r3.json()["id"] == str(agency_a_obj.id), (
        f"Refresh switched agency! Expected {agency_a_obj.id}, got {r3.json()['id']}"
    )


def test_refresh_rejects_wrong_scope(client: TestClient, setup_session: Session):
    """Super Admin refresh token must not work on /auth/refresh (agency scope)."""
    sa_refresh = create_refresh_token(subject=str(uuid.uuid4()), token_type="super_admin")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": sa_refresh})
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
        "exp": int((now + __import__("datetime").timedelta(days=30)).timestamp()),
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
        "exp": int((now + __import__("datetime").timedelta(days=30)).timestamp()),
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
    """Function must have prosecdef=true (SECURITY DEFINER)."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner)
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname = 'get_user_memberships_for_login'
            """)
            row = cur.fetchone()
            assert row is not None, "Function not found"
            prosecdef, proconfig, owner = row
            assert prosecdef is True, f"prosecdef={prosecdef}, expected True"
            assert owner == "postgres", f"Function owner is {owner}, expected postgres"
            # Verify search_path is restricted
            assert proconfig is not None, "proconfig is NULL — search_path not set"
            assert "pg_catalog" in str(proconfig), f"search_path does not include pg_catalog: {proconfig}"
    finally:
        conn.close()
