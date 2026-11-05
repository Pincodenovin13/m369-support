"""Adversarial RLS bypass regression tests.

Every test creates two real agencies (A and B), each with a workspace and
contact. Then it connects as the actual runtime role ``m369_app`` and
attempts to bypass RLS. If any test sees Agency B's data while scoped to
Agency A, it FAILS — proving RLS is broken.

These tests do NOT use ``except: pass``. Failures are surfaced.
"""
from __future__ import annotations

import os
import uuid

import psycopg
import psycopg.errors
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


pytestmark = [pytest.mark.security, pytest.mark.integration]


APP_DB_URL = "postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test"


def _seed_two_agencies(setup_session: Session):
    """Insert Agency A + Agency B, each with a workspace and a contact.

    Returns a dict with all UUIDs needed by the tests.
    """
    agency_a_id = uuid.uuid4()
    agency_b_id = uuid.uuid4()
    ws_a_id = uuid.uuid4()
    ws_b_id = uuid.uuid4()
    contact_a_id = uuid.uuid4()
    contact_b_id = uuid.uuid4()

    setup_session.execute(text(
        f"INSERT INTO agencies (id, name, slug, brand_color, is_active) "
        f"VALUES ('{agency_a_id}', 'Agency A', 'agency-a-{uuid.uuid4().hex[:6]}', '#FF6B35', true)"
    ))
    setup_session.execute(text(
        f"INSERT INTO agencies (id, name, slug, brand_color, is_active) "
        f"VALUES ('{agency_b_id}', 'Agency B', 'agency-b-{uuid.uuid4().hex[:6]}', '#FF6B35', true)"
    ))
    setup_session.execute(text(
        f"INSERT INTO workspaces (id, agency_id, name, slug, timezone, is_active) "
        f"VALUES ('{ws_a_id}', '{agency_a_id}', 'WS A', 'ws-a-{uuid.uuid4().hex[:6]}', 'UTC', true)"
    ))
    setup_session.execute(text(
        f"INSERT INTO workspaces (id, agency_id, name, slug, timezone, is_active) "
        f"VALUES ('{ws_b_id}', '{agency_b_id}', 'WS B', 'ws-b-{uuid.uuid4().hex[:6]}', 'UTC', true)"
    ))
    setup_session.execute(text(
        f"INSERT INTO contacts (id, workspace_id, agency_id, email, name) "
        f"VALUES ('{contact_a_id}', '{ws_a_id}', '{agency_a_id}', 'a@agency-a.test', 'A')"
    ))
    setup_session.execute(text(
        f"INSERT INTO contacts (id, workspace_id, agency_id, email, name) "
        f"VALUES ('{contact_b_id}', '{ws_b_id}', '{agency_b_id}', 'b@agency-b.test', 'B')"
    ))
    setup_session.commit()

    return {
        "agency_a_id": str(agency_a_id),
        "agency_b_id": str(agency_b_id),
        "ws_a_id": str(ws_a_id),
        "ws_b_id": str(ws_b_id),
        "contact_a_id": str(contact_a_id),
        "contact_b_id": str(contact_b_id),
    }


# ---------------------------------------------------------------------------
# Test 1: SET LOCAL app.bypass_rls = 'on' must NOT expose Agency B data
# ---------------------------------------------------------------------------


def test_set_local_bypass_rls_does_not_leak_cross_tenant(db_engine, setup_session):
    """Agency A sets tenant_id, then attempts SET LOCAL app.bypass_rls='on'.

    With RLS policies that only check app.tenant_id (no bypass GUC),
    Agency A should still see ONLY its own contact — never Agency B's.
    """
    ids = _seed_two_agencies(setup_session)

    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (ids["agency_a_id"],))
            cur.execute("SET LOCAL app.bypass_rls = 'on'")

            cur.execute("SELECT email FROM contacts ORDER BY email")
            visible = {row[0] for row in cur.fetchall()}

            assert "a@agency-a.test" in visible, (
                f"Agency A should see its own contact, got: {visible}"
            )
            assert "b@agency-b.test" not in visible, (
                f"RLS BYPASS: app.bypass_rls='on' exposed Agency B's contact. "
                f"Visible: {visible}"
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 2: SET (session-level) app.bypass_rls = 'on' must NOT leak
# ---------------------------------------------------------------------------


def test_set_session_bypass_rls_does_not_leak_cross_tenant(db_engine, setup_session):
    """Session-level SET variant of the bypass attempt."""
    ids = _seed_two_agencies(setup_session)

    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, false)", (ids["agency_a_id"],))
            cur.execute("SET app.bypass_rls = 'on'")

            cur.execute("SELECT email FROM contacts ORDER BY email")
            visible = {row[0] for row in cur.fetchall()}

            assert "a@agency-a.test" in visible, (
                f"Agency A should see its own contact, got: {visible}"
            )
            assert "b@agency-b.test" not in visible, (
                f"RLS BYPASS: session SET exposed Agency B's contact. "
                f"Visible: {visible}"
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 3: SET ROLE m369_super_admin must be rejected with InsufficientPrivilege
# ---------------------------------------------------------------------------


def test_set_role_to_super_admin_rejected(db_engine, setup_session):
    """m369_app must NOT be able to SET ROLE to m369_super_admin.

    Uses strict pytest.raises — no except-swallowing.
    """
    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as exc_info:
                cur.execute("SET ROLE m369_super_admin")

            # Verify the error is specifically about role membership
            assert "m369_super_admin" in str(exc_info.value) or "role" in str(exc_info.value).lower(), (
                f"Unexpected error: {exc_info.value}"
            )

            # After the failed SET ROLE, current_user must still be m369_app
            conn.rollback()
            cur.execute("SELECT current_user")
            current = cur.fetchone()[0]
            assert current == "m369_app", (
                f"current_user after rejected SET ROLE is {current}, expected m369_app"
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 4: Missing tenant context returns no tenant data
# ---------------------------------------------------------------------------


def test_missing_tenant_context_returns_no_data(db_engine, setup_session):
    """Without app.tenant_id, no tenant-owned rows should be visible."""
    _seed_two_agencies(setup_session)

    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
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
# Test 5: Cross-tenant INSERT must be blocked by RLS (SQLSTATE 42501)
# ---------------------------------------------------------------------------


def test_cross_tenant_insert_blocked_by_rls(db_engine, setup_session):
    """Agency A (tenant_id=A) tries to INSERT a contact belonging to Agency B.

    The insert must fail with RLS WITH CHECK violation (SQLSTATE 42501),
    NOT a foreign-key violation (SQLSTATE 23503).
    """
    ids = _seed_two_agencies(setup_session)

    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (ids["agency_a_id"],))

            new_contact_id = str(uuid.uuid4())
            with pytest.raises(psycopg.errors.Error) as exc_info:
                cur.execute(
                    "INSERT INTO contacts (id, workspace_id, agency_id, email, name) "
                    "VALUES (%s, %s, %s, 'attack@agency-b.test', 'Attack')",
                    (new_contact_id, ids["ws_b_id"], ids["agency_b_id"]),
                )

            sqlstate = exc_info.value.diag.sqlstate
            assert sqlstate == "42501", (
                f"Expected RLS violation (42501), got {sqlstate}: {exc_info.value}. "
                f"FK violation (23503) would mean the test is invalid — "
                f"real Agency B records must exist."
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 6: Cross-tenant UPDATE must be blocked (0 rows affected)
# ---------------------------------------------------------------------------


def test_cross_tenant_update_blocked_by_rls(db_engine, setup_session):
    """Agency A tries to UPDATE Agency B's contact. RLS hides the row → 0 affected."""
    ids = _seed_two_agencies(setup_session)

    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (ids["agency_a_id"],))

            cur.execute(
                "UPDATE contacts SET name = 'Hacked' WHERE email = 'b@agency-b.test'"
            )
            assert cur.rowcount == 0, (
                f"RLS BYPASS: UPDATE affected {cur.rowcount} rows belonging to Agency B"
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 7: Cross-tenant DELETE must be blocked (0 rows affected)
# ---------------------------------------------------------------------------


def test_cross_tenant_delete_blocked_by_rls(db_engine, setup_session):
    """Agency A tries to DELETE Agency B's contact. RLS hides the row → 0 affected."""
    ids = _seed_two_agencies(setup_session)

    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (ids["agency_a_id"],))

            cur.execute("DELETE FROM contacts WHERE email = 'b@agency-b.test'")
            assert cur.rowcount == 0, (
                f"RLS BYPASS: DELETE affected {cur.rowcount} rows belonging to Agency B"
            )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 8: Verify m369_app role attributes
# ---------------------------------------------------------------------------


def test_app_role_attributes(db_engine, setup_session):
    """m369_app must NOT have rolsuper, rolbypassrls, or rolcreaterole."""
    conn = psycopg.connect(APP_DB_URL)
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
            assert not can_create_role, f"Role {rolname} has CREATEROLE — should not be needed at runtime"
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 9: Verify m369_app does NOT own tenant tables
# ---------------------------------------------------------------------------


def test_app_role_does_not_own_tenant_tables(db_engine, setup_session):
    """Table owner must NOT be m369_app. Owner bypasses RLS without FORCE."""
    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            tenant_tables = [
                "agencies", "workspaces", "agency_memberships", "teams",
                "team_memberships", "contacts", "conversations", "audit_logs",
            ]
            cur.execute("SELECT current_user")
            current_user = cur.fetchone()[0]

            for table in tenant_tables:
                cur.execute(
                    "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE relname = %s",
                    (table,),
                )
                row = cur.fetchone()
                assert row is not None, f"Table '{table}' does not exist — migration may have failed"
                owner = row[0]
                assert owner != current_user, (
                    f"Table '{table}' is owned by {owner} (the app role) — "
                    f"should be owned by migration role (postgres)"
                )
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Test 10: Verify no LOGIN role has membership in m369_super_admin
# ---------------------------------------------------------------------------


def test_no_login_role_in_super_admin(db_engine, setup_session):
    """No LOGIN role should be a member of m369_super_admin.

    If a LOGIN role had membership, it could SET ROLE and bypass RLS.
    """
    conn = psycopg.connect(APP_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.rolname, r.rolcanlogin
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.member
                JOIN pg_roles parent ON parent.oid = m.roleid
                WHERE parent.rolname = 'm369_super_admin'
            """)
            members = cur.fetchall()
            login_members = [m[0] for m in members if m[1]]
            assert login_members == [], (
                f"LOGIN roles with m369_super_admin membership: {login_members}. "
                f"No login path to BYPASSRLS should exist."
            )
        conn.rollback()
    finally:
        conn.close()
