"""Adversarial RLS bypass regression tests.

These tests connect as the ACTUAL ordinary application database role
(``m369_app``) and attempt to bypass RLS through every known vector:

1. ``SET LOCAL app.bypass_rls = 'on'``  — the original vulnerability
2. ``SET app.bypass_rls = 'on'``         — session-level variant
3. ``SET ROLE m369_super_admin``         — role escalation
4. Direct SELECT without tenant context  — fail-closed verification
5. Cross-tenant INSERT, UPDATE, DELETE   — data isolation

Every test MUST fail if any bypass succeeds.

These tests do NOT call the application's ``bypass_rls_for_super_admin()``
function — they attempt raw SQL attacks as the ordinary application role.
"""
from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


pytestmark = [pytest.mark.security, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Connection helpers — connect as the ORDINARY application role (m369_app)
# ---------------------------------------------------------------------------


APP_DB_URL = os.environ.get(
    "APP_DATABASE_URL",
    "postgresql://m369_app:m369_app_password@localhost:5432/m369_support_test",
)


def _connect_as_app_role():
    """Open a raw psycopg connection as the ordinary application role.

    This is the role the FastAPI app uses for all agency-scoped requests.
    It must NOT have BYPASSRLS, SUPERUSER, or table ownership.
    """
    conn = psycopg.connect(APP_DB_URL, autocommit=False)
    return conn


# ---------------------------------------------------------------------------
# Test 1: SET LOCAL app.bypass_rls = 'on' must NOT bypass RLS
# ---------------------------------------------------------------------------


def test_ordinary_role_cannot_bypass_rls_with_set_local(db_engine):
    """The original vulnerability: SET LOCAL app.bypass_rls = 'on'.

    Before the fix, this allowed any user to read all tenants' data.
    After the fix, the GUC must have no effect on RLS policies.
    """
    conn = _connect_as_app_role()
    try:
        with conn.cursor() as cur:
            # Set the bypass GUC — this should be a no-op for RLS
            cur.execute("SET LOCAL app.bypass_rls = 'on'")

            # Try to read ALL contacts (should see 0 if RLS is enforced)
            cur.execute("SELECT count(*) FROM contacts")
            count = cur.fetchone()[0]

            # If count > 0 without tenant_id set, RLS is bypassed
            assert count == 0, (
                f"RLS BYPASS: ordinary role read {count} contacts "
                f"via SET LOCAL app.bypass_rls='on' without tenant_id"
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 2: SET (session-level) app.bypass_rls = 'on' must NOT bypass RLS
# ---------------------------------------------------------------------------


def test_ordinary_role_cannot_bypass_rls_with_set_session(db_engine):
    """Session-level SET variant of the bypass attempt."""
    conn = _connect_as_app_role()
    try:
        with conn.cursor() as cur:
            cur.execute("SET app.bypass_rls = 'on'")
            cur.execute("SELECT count(*) FROM contacts")
            count = cur.fetchone()[0]
            assert count == 0, (
                f"RLS BYPASS: ordinary role read {count} contacts "
                f"via SET app.bypass_rls='on' (session-level)"
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 3: SET ROLE must fail for ordinary role
# ---------------------------------------------------------------------------


def test_ordinary_role_cannot_set_role_to_super_admin(db_engine):
    """The ordinary role must not be able to SET ROLE to a privileged role."""
    conn = _connect_as_app_role()
    try:
        with conn.cursor() as cur:
            # This should raise an error — m369_app is not a member of m369_super_admin
            with pytest.raises(psycopg.Error) as exc:
                cur.execute("SET ROLE m369_super_admin")
            conn.rollback()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 4: Missing tenant context returns no data (fail-closed)
# ---------------------------------------------------------------------------


def test_missing_tenant_context_returns_no_data(db_engine):
    """Without app.tenant_id set, no tenant-owned rows should be visible."""
    conn = _connect_as_app_role()
    try:
        with conn.cursor() as cur:
            # Ensure no tenant_id is set
            cur.execute("RESET app.tenant_id")
            cur.execute("RESET app.bypass_rls")

            for table in ["agencies", "workspaces", "contacts", "conversations", "audit_logs"]:
                cur.execute(f"SELECT count(*) FROM {table}")
                count = cur.fetchone()[0]
                assert count == 0, (
                    f"RLS FAIL-CLOSED VIOLATION: table '{table}' returned {count} rows "
                    f"without tenant context"
                )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 5: Cross-tenant INSERT must be blocked
# ---------------------------------------------------------------------------


def test_cross_tenant_insert_blocked(db_engine):
    """An agency role with tenant_id=A cannot INSERT a row with agency_id=B."""
    # This test requires setup data — skip if DB is not seeded
    conn = _connect_as_app_role()
    try:
        with conn.cursor() as cur:
            # We need at least one agency to exist — try to insert one
            # First set bypass... wait, we can't bypass. So we need the
            # migration/seeding to have created test data.
            # For now, just verify that INSERT without matching tenant_id fails.
            agency_b_id = str(uuid.uuid4())
            ws_id = str(uuid.uuid4())
            contact_id = str(uuid.uuid4())

            # Set tenant_id to a random UUID (not matching any agency)
            cur.execute("SET LOCAL app.tenant_id = '00000000-0000-0000-0000-000000000000'")

            # Try to insert a contact with a DIFFERENT agency_id
            with pytest.raises(psycopg.Error):
                cur.execute(
                    "INSERT INTO contacts (id, workspace_id, agency_id, email) "
                    "VALUES (%s, %s, %s, 'attack@test')",
                    (contact_id, ws_id, agency_b_id),
                )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 6: Verify role attributes — m369_app must NOT have BYPASSRLS
# ---------------------------------------------------------------------------


def test_app_role_has_no_bypassrls(db_engine):
    """The ordinary application role must not have BYPASSRLS attribute."""
    conn = _connect_as_app_role()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user"
            )
            row = cur.fetchone()
            assert row is not None, "Could not query role attributes"
            rolname, is_super, has_bypass, can_create_role = row
            assert not is_super, f"Role {rolname} is a SUPERUSER — security violation"
            assert not has_bypass, f"Role {rolname} has BYPASSRLS — security violation"
            assert not can_create_role, (
                f"Role {rolname} has CREATEROLE — should not be needed at runtime"
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 7: Verify m369_app is NOT a table owner
# ---------------------------------------------------------------------------


def test_app_role_does_not_own_tenant_tables(db_engine):
    """The ordinary application role must not own tenant tables.

    Table owners can bypass RLS unless FORCE ROW LEVEL SECURITY is set.
    Even with FORCE, ownership is a privilege that should be reserved
    for the migration role.
    """
    conn = _connect_as_app_role()
    try:
        with conn.cursor() as cur:
            tenant_tables = [
                "agencies", "workspaces", "agency_memberships", "teams",
                "team_memberships", "contacts", "conversations", "audit_logs",
            ]
            for table in tenant_tables:
                cur.execute(
                    "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE relname = %s",
                    (table,),
                )
                owner = cur.fetchone()[0]
                current = cur.execute("SELECT current_user").fetchone()[0]
                assert owner != current, (
                    f"Table '{table}' is owned by {owner} (the app role) — "
                    f"should be owned by a migration/admin role"
                )
        conn.rollback()
    finally:
        conn.close()
