"""Authentication & tenant context tests.

Tests the full flow: JWT → membership verification → agency active check → RLS.
All tests use real PostgreSQL with real seeded data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
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

    # Create a user with memberships in both agencies
    user = _create_user_with_memberships(
        setup_session,
        "multi@example.com",
        [(agency_a_obj, "agent"), (agency_b_obj, "agent")],
    )
    # Set a real password
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

    # User is only in agency A
    user = _create_user_with_memberships(
        setup_session,
        "single@example.com",
        [(agency_a_obj, "agent")],
    )
    from app.security import hash_password
    user.password_hash = hash_password("test-password-123")
    setup_session.commit()

    # Try to login specifying agency B
    r = client.post("/api/v1/auth/login", json={
        "email": "single@example.com",
        "password": "test-password-123",
        "agency_id": str(agency_b_obj.id),
    })
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# B. Agency Selection — Refresh
# ---------------------------------------------------------------------------


def test_refresh_preserves_agency_context(client: TestClient, setup_session: Session, agency_a):
    """Refresh token for agency A must produce an access token for agency A."""
    agency, owner, _ = agency_a

    # Login to get tokens
    r = client.post("/api/v1/auth/login", json={
        "email": "owner@agency-a.com",
        "password": "test-password-123",
    })
    assert r.status_code == 200

    # Extract refresh token from cookies
    refresh_token = r.cookies.get("refresh_token")
    assert refresh_token is not None

    # Refresh
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"

    # The new access token should work for agency A
    new_access = r2.json()["access_token"]
    r3 = client.get("/api/v1/agencies/current", headers={"Authorization": f"Bearer {new_access}"})
    assert r3.status_code == 200, f"Expected 200, got {r3.status_code}: {r3.text}"
    assert r3.json()["id"] == str(agency.id)


def test_refresh_rejects_wrong_scope(client: TestClient, setup_session: Session):
    """Super Admin refresh token must not work on /auth/refresh (agency scope)."""
    from app.security import create_refresh_token

    sa_refresh = create_refresh_token(subject=str(uuid.uuid4()), token_type="super_admin")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": sa_refresh})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


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

    # Deactivate the agency
    agency.is_active = False
    setup_session.commit()

    r = client.get(
        "/api/v1/agencies/current",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert "not active" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# C. Super Admin token on agency endpoints
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
# B. Membership verification — cross-agency token
# ---------------------------------------------------------------------------


def test_token_with_wrong_agency_id_rejected(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Token scoped to agency A cannot access agency B's resources.

    This is enforced by RLS (the DB session SET LOCAL app.tenant_id = A)
    and by get_current_agency_id (membership check).
    """
    agency_a_obj, owner_a, token_a = agency_a
    agency_b_obj, _, _ = agency_b

    # Create a resource in agency B
    from app.models import Workspace
    ws_b = Workspace(agency_id=agency_b_obj.id, name="WS B", slug=f"ws-b-{uuid.uuid4().hex[:6]}")
    setup_session.add(ws_b)
    setup_session.commit()

    # User A tries to list workspaces — should only see agency A's workspaces
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
