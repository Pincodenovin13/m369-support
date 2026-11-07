"""Agency session revocation — token_version tests.

Tests ATK-01 through ATK-16 verify that after logout:
  - Access tokens are rejected (401)
  - Refresh tokens are rejected (401)
  - New tokens carry the correct token_version
  - Concurrent logout is atomic
  - Super Admin auth is unaffected
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.config import get_settings
from app.models import Agency, AgencyMembership, Contact, User, Workspace
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
)


pytestmark = [pytest.mark.security, pytest.mark.integration]


def _h(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


# ---------------------------------------------------------------------------
# ATK-01: Access token with valid tver accepted
# ---------------------------------------------------------------------------


def test_ATK_01_valid_access_token_accepted(client, setup_session, monkeypatch):
    """ATK-01: An access token with correct tver is accepted."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK Agency", slug=f"atk-{uuid.uuid4().hex[:6]}")
    user = User(email="atk01@test.com", name="ATK01", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    token = create_access_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )
    r = client.get("/api/v1/auth/me", headers=_h(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# ATK-02: Access token without tver rejected
# ---------------------------------------------------------------------------


def test_ATK_02_access_token_without_tver_rejected(client, setup_session, monkeypatch):
    """ATK-02: An access token without tver is rejected with 401."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    # Create a token without tver by bypassing the check
    import jwt as pyjwt
    s = get_settings()
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "agency",
        "exp": int((datetime.now(timezone.utc).timestamp())) + 3600,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "agency_id": str(uuid.uuid4()),
        # tver intentionally absent
    }
    token = pyjwt.encode(payload, s.jwt_secret_key, algorithm=s.jwt_algorithm)
    r = client.get("/api/v1/auth/me", headers=_h(token))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# ATK-03: Access token with wrong tver rejected
# ---------------------------------------------------------------------------


def test_ATK_03_access_token_wrong_tver_rejected(client, setup_session, monkeypatch):
    """ATK-03: An access token with wrong tver is rejected with 401."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK3 Agency", slug=f"atk3-{uuid.uuid4().hex[:6]}")
    user = User(email="atk03@test.com", name="ATK03", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    # Token with tver=999 (wrong — user has tver=0)
    token = create_access_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=999,
    )
    r = client.get("/api/v1/auth/me", headers=_h(token))
    assert r.status_code == 401
    assert "revoked" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# ATK-04: Refresh token with valid tver accepted
# ---------------------------------------------------------------------------


def test_ATK_04_valid_refresh_token_accepted(client, setup_session, monkeypatch):
    """ATK-04: A refresh token with correct tver succeeds."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK4 Agency", slug=f"atk4-{uuid.uuid4().hex[:6]}")
    user = User(email="atk04@test.com", name="ATK04", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    refresh = create_refresh_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# ATK-05: Refresh token without tver rejected
# ---------------------------------------------------------------------------


def test_ATK_05_refresh_token_without_tver_rejected(client, setup_session, monkeypatch):
    """ATK-05: A refresh token without tver is rejected with 401."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    # Create a refresh token without tver
    import jwt as pyjwt
    s = get_settings()
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "refresh",
        "exp": int((datetime.now(timezone.utc).timestamp())) + 86400,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "scope": "agency",
        "agency_id": str(uuid.uuid4()),
        # tver intentionally absent
    }
    token = pyjwt.encode(payload, s.jwt_secret_key, algorithm=s.jwt_algorithm)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# ATK-06: Refresh token with wrong tver rejected
# ---------------------------------------------------------------------------


def test_ATK_06_refresh_token_wrong_tver_rejected(client, setup_session, monkeypatch):
    """ATK-06: A refresh token with wrong tver is rejected with 401."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK6 Agency", slug=f"atk6-{uuid.uuid4().hex[:6]}")
    user = User(email="atk06@test.com", name="ATK06", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    refresh = create_refresh_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=999,
    )
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# ATK-07: After logout, old access token → 401
# ---------------------------------------------------------------------------


def test_ATK_07_after_logout_access_token_rejected(client, setup_session, monkeypatch):
    """ATK-07: After logout, the old access token is rejected with 401."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK7 Agency", slug=f"atk7-{uuid.uuid4().hex[:6]}")
    user = User(email="atk07@test.com", name="ATK07", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    # Login
    r_login = client.post("/api/v1/auth/login", json={
        "email": "atk07@test.com", "password": "test-password-123",
        "agency_id": str(agency.id),
    })
    assert r_login.status_code == 200
    token = r_login.cookies.get("access_token")
    assert token is not None

    # Verify token works
    r_me = client.get("/api/v1/auth/me", headers=_h(token))
    assert r_me.status_code == 200

    # Logout
    r_logout = client.post("/api/v1/auth/logout", headers=_h(token))
    assert r_logout.status_code == 204

    # Old access token should now be rejected
    r_after = client.get("/api/v1/auth/me", headers=_h(token))
    assert r_after.status_code == 401
    assert "revoked" in r_after.json()["detail"].lower()


# ---------------------------------------------------------------------------
# ATK-08: After logout, old refresh token → 401
# ---------------------------------------------------------------------------


def test_ATK_08_after_logout_refresh_token_rejected(client, setup_session, monkeypatch):
    """ATK-08: After logout, the old refresh token is rejected with 401."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK8 Agency", slug=f"atk8-{uuid.uuid4().hex[:6]}")
    user = User(email="atk08@test.com", name="ATK08", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    # Login
    r_login = client.post("/api/v1/auth/login", json={
        "email": "atk08@test.com", "password": "test-password-123",
        "agency_id": str(agency.id),
    })
    assert r_login.status_code == 200
    access = r_login.cookies.get("access_token")

    # Get refresh token from cookies — TestClient stores cookies
    # We need to extract the refresh token. Let's issue one manually.
    refresh = create_refresh_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )

    # Logout
    r_logout = client.post("/api/v1/auth/logout", headers=_h(access))
    assert r_logout.status_code == 204

    # Old refresh token should be rejected
    r_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r_refresh.status_code == 401


# ---------------------------------------------------------------------------
# ATK-09: Old refresh token cannot issue new access token
# ---------------------------------------------------------------------------


def test_ATK_09_old_refresh_cannot_issue_new_access(client, setup_session, monkeypatch):
    """ATK-09: An old refresh token cannot issue a new access token."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK9 Agency", slug=f"atk9-{uuid.uuid4().hex[:6]}")
    user = User(email="atk09@test.com", name="ATK09", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    refresh = create_refresh_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )

    # Logout bumps token_version
    access = create_access_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )
    client.post("/api/v1/auth/logout", headers=_h(access))

    # Old refresh should fail
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# ATK-10: Logout returns 204
# ---------------------------------------------------------------------------


def test_ATK_10_logout_returns_204(client, setup_session, monkeypatch):
    """ATK-10: Logout returns HTTP 204."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK10 Agency", slug=f"atk10-{uuid.uuid4().hex[:6]}")
    user = User(email="atk10@test.com", name="ATK10", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    token = create_access_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )
    r = client.post("/api/v1/auth/logout", headers=_h(token))
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# ATK-11: Cookie deletion headers present in logout response
# ---------------------------------------------------------------------------


def test_ATK_11_logout_cookie_deletion_headers(client, setup_session, monkeypatch):
    """ATK-11: Logout response contains Set-Cookie headers for both cookies."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK11 Agency", slug=f"atk11-{uuid.uuid4().hex[:6]}")
    user = User(email="atk11@test.com", name="ATK11", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    token = create_access_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )
    r = client.post("/api/v1/auth/logout", headers=_h(token))
    assert r.status_code == 204

    # Check Set-Cookie headers
    set_cookie_headers = r.headers.get_list("set-cookie")
    cookie_names = [h.split("=")[0].strip().lower() for h in set_cookie_headers]
    assert "access_token" in cookie_names, f"access_token deletion missing: {set_cookie_headers}"
    assert "refresh_token" in cookie_names, f"refresh_token deletion missing: {set_cookie_headers}"


# ---------------------------------------------------------------------------
# ATK-12: Concurrent logout — token_version increments exactly once
# ---------------------------------------------------------------------------


def test_ATK_12_repeated_logout_rejects_old_token(client, setup_session, monkeypatch):
    """ATK-12: Repeated logout — first succeeds (204), second rejected (401).

    After the first logout bumps token_version, the old token's tver no
    longer matches. The second logout attempt is rejected with 401.
    """
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK12 Agency", slug=f"atk12-{uuid.uuid4().hex[:6]}")
    user = User(email="atk12@test.com", name="ATK12", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    token = create_access_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )

    # First logout — succeeds
    r1 = client.post("/api/v1/auth/logout", headers=_h(token))
    assert r1.status_code == 204

    # Second logout — rejected because token_version was bumped
    r2 = client.post("/api/v1/auth/logout", headers=_h(token))
    assert r2.status_code == 401

    # Verify token_version was incremented exactly once
    setup_session.expire_all()
    user2 = setup_session.get(User, user.id)
    assert user2.token_version == 1, f"Expected token_version=1, got {user2.token_version}"


def test_ATK_12b_concurrent_atomic_token_version_increment(
    db_engine,
    setup_session,
):
    """ATK-12b: Two independent PostgreSQL transactions must not lose increments.

    Uses ThreadPoolExecutor + Barrier + two independent engine connections.
    Tests that the SQL UPDATE ... SET token_version = token_version + 1
    is atomic under true parallelism (not sequential TestClient calls).
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import update

    agency = Agency(
        name="ATK12B Agency",
        slug=f"atk12b-{uuid.uuid4().hex[:8]}",
    )
    user = User(
        email=f"atk12b-{uuid.uuid4().hex[:8]}@test.com",
        name="ATK12B",
        password_hash=hash_password("test-password-123"),
    )
    membership = AgencyMembership(
        user=user,
        agency=agency,
        role="owner",
    )

    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    user_id = user.id
    barrier = Barrier(2)

    def atomic_increment():
        with db_engine.begin() as conn:
            barrier.wait(timeout=10)

            result = conn.execute(
                update(User)
                .where(User.id == user_id)
                .values(token_version=User.token_version + 1)
                .returning(User.token_version)
            )

            return result.scalar_one()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(atomic_increment),
            executor.submit(atomic_increment),
        ]
        results = [future.result(timeout=20) for future in futures]

    setup_session.expire_all()
    updated_user = setup_session.get(User, user_id)

    assert updated_user is not None
    assert updated_user.token_version == 2
    assert sorted(results) == [1, 2]


# ---------------------------------------------------------------------------
# ATK-13: Register and Login produce versioned tokens
# ---------------------------------------------------------------------------


def test_ATK_13_register_produces_versioned_token(client, setup_session, monkeypatch):
    """ATK-13: Register produces a token with tver claim."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    r = client.post("/api/v1/auth/register", json={
        "agency_name": "ATK13 Agency",
        "name": "Owner",
        "email": "atk13@test.com",
        "password": "test-password-123",
    })
    assert r.status_code == 201

    # Extract access token from cookie
    token = r.cookies.get("access_token")
    assert token is not None

    # Decode and verify tver
    decoded = decode_access_token(token)
    assert decoded is not None
    assert "tver" in decoded
    assert decoded["tver"] == 0


def test_ATK_13b_login_produces_versioned_token(client, setup_session, monkeypatch):
    """ATK-13b: Login produces a token with tver claim."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK13b Agency", slug=f"atk13b-{uuid.uuid4().hex[:6]}")
    user = User(email="atk13b@test.com", name="ATK13b", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    r = client.post("/api/v1/auth/login", json={
        "email": "atk13b@test.com",
        "password": "test-password-123",
        "agency_id": str(agency.id),
    })
    assert r.status_code == 200

    token = r.cookies.get("access_token")
    assert token is not None

    decoded = decode_access_token(token)
    assert decoded is not None
    assert "tver" in decoded
    assert decoded["tver"] == user.token_version


# ---------------------------------------------------------------------------
# ATK-14: Refresh produces new tokens with current token_version
# ---------------------------------------------------------------------------


def test_ATK_14_refresh_produces_versioned_tokens(client, setup_session, monkeypatch):
    """ATK-14: Refresh produces new tokens with the current token_version."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK14 Agency", slug=f"atk14-{uuid.uuid4().hex[:6]}")
    user = User(email="atk14@test.com", name="ATK14", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    refresh = create_refresh_token(
        subject=str(user.id), token_type="agency",
        agency_id=str(agency.id), token_version=user.token_version,
    )
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200

    # Verify new access token has tver
    new_access = r.json()["access_token"]
    decoded = decode_access_token(new_access)
    assert decoded is not None
    assert "tver" in decoded
    assert decoded["tver"] == user.token_version

    # Verify new refresh token has tver
    new_refresh = r.json()["refresh_token"]
    decoded_r = decode_refresh_token(new_refresh)
    assert decoded_r is not None
    assert "tver" in decoded_r
    assert decoded_r["tver"] == user.token_version


# ---------------------------------------------------------------------------
# ATK-15: Super Admin auth unaffected
# ---------------------------------------------------------------------------


def test_ATK_15_super_admin_unaffected(client, setup_session, monkeypatch):
    """ATK-15: Super Admin login + MFA still works with its own token_version."""
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    from app.models import SuperAdmin
    admin = SuperAdmin(
        email=f"atk15-{uuid.uuid4().hex[:6]}@m369.platform",
        name="ATK15 SA",
        password_hash=hash_password("super-admin-password-123"),
        is_active=True,
    )
    setup_session.add(admin)
    setup_session.commit()
    setup_session.refresh(admin)

    r = client.post("/api/v1/super-admin/auth/login", json={
        "email": admin.email,
        "password": "super-admin-password-123",
    })
    assert r.status_code == 200, f"SA login failed: {r.text}"

    token = r.cookies.get("super_admin_access_token")
    assert token is not None

    r_me = client.get("/api/v1/super-admin/auth/me", headers=_h(token))
    assert r_me.status_code == 200


# ---------------------------------------------------------------------------
# ATK-16: Tenant isolation + RLS still works
# ---------------------------------------------------------------------------


def test_ATK_16_tenant_isolation_intact(client, setup_session, agency_a, agency_b, monkeypatch):
    """ATK-16: Tenant isolation + RLS still works with versioned tokens.

    Creates a contact in Agency B's workspace, then verifies:
    - Agency B can read its own contact (200)
    - Agency A cannot read Agency B's contact (404)
    - No Agency B data leaks in Agency A's response
    """
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    a, _, tok_a = agency_a
    b, _, tok_b = agency_b

    # Create a workspace for Agency B
    workspace_b = Workspace(
        agency_id=b.id,
        name="ATK16 Workspace B",
        slug=f"atk16-b-{uuid.uuid4().hex[:8]}",
    )
    setup_session.add(workspace_b)
    setup_session.commit()
    setup_session.refresh(workspace_b)

    # Create a contact in Agency B's workspace
    contact_b = Contact(
        agency_id=b.id,
        workspace_id=workspace_b.id,
        name="Private Agency B Contact",
        email="private-b@agency-b.com",
    )
    setup_session.add(contact_b)
    setup_session.commit()
    setup_session.refresh(contact_b)

    # Agency B can read its own contact
    response_b = client.get(
        f"/api/v1/contacts/{contact_b.id}",
        headers=_h(tok_b),
    )
    assert response_b.status_code == 200, f"Agency B should access own contact: {response_b.status_code}"

    # Agency A cannot read Agency B's contact (RLS → 404)
    response_a = client.get(
        f"/api/v1/contacts/{contact_b.id}",
        headers=_h(tok_a),
    )
    assert response_a.status_code == 404, f"Agency A should NOT access Agency B's contact: {response_a.status_code}"

    # Verify Agency A's contact list doesn't include Agency B's contact
    response_a_list = client.get("/api/v1/contacts", headers=_h(tok_a))
    assert response_a_list.status_code == 200
    contact_ids = [c["id"] for c in response_a_list.json()["items"]]
    assert str(contact_b.id) not in contact_ids, "Agency B's contact leaked into Agency A's list"


# ---------------------------------------------------------------------------
# ATK-17: Cookie-only refresh
# ---------------------------------------------------------------------------


def test_ATK_17_cookie_only_refresh(client, setup_session, monkeypatch):
    """ATK-17: Cookie-based refresh returns 204 + rotates both cookies.

    Steps:
    1. Login (sets cookies).
    2. POST /auth/refresh with NO JSON body (cookie-only).
    3. Response must be 204.
    4. Response must contain Set-Cookie for both access + refresh.
    5. New access cookie must work for /auth/me.
    """
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    agency = Agency(name="ATK17 Agency", slug=f"atk17-{uuid.uuid4().hex[:6]}")
    user = User(email="atk17@test.com", name="ATK17", password_hash=hash_password("test-password-123"))
    membership = AgencyMembership(user=user, agency=agency, role="owner")
    setup_session.add_all([agency, user, membership])
    setup_session.commit()
    setup_session.refresh(user)

    # Login — sets cookies
    r_login = client.post("/api/v1/auth/login", json={
        "email": "atk17@test.com",
        "password": "test-password-123",
        "agency_id": str(agency.id),
    })
    assert r_login.status_code == 200

    # Cookie-only refresh — no JSON body
    r_refresh = client.post("/api/v1/auth/refresh")
    assert r_refresh.status_code == 204, f"Expected 204, got {r_refresh.status_code}: {r_refresh.text}"

    # Verify Set-Cookie headers for both cookies
    set_cookie_headers = r_refresh.headers.get_list("set-cookie")
    cookie_names = [h.split("=")[0].strip().lower() for h in set_cookie_headers]
    assert "access_token" in cookie_names, f"access_token cookie missing: {set_cookie_headers}"
    assert "refresh_token" in cookie_names, f"refresh_token cookie missing: {set_cookie_headers}"

    # New access cookie must work for /auth/me
    r_me = client.get("/api/v1/auth/me")
    assert r_me.status_code == 200, f"New access cookie failed: {r_me.status_code}"
    assert r_me.json()["email"] == "atk17@test.com"
