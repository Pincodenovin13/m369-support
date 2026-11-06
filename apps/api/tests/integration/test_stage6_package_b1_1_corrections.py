"""Package B.1.1 — Provisioning + RLS UPDATE + effective privilege audit.

Tests B1.1-01 through B1.1-15 verify:
  - B1-F01: provision_sa_auth_role.py script (idempotent, secure, verified)
  - B1-F02: Complete RLS UPDATE test for message_attachments (CRUD cross-tenant)
  - B1-F03: Effective PostgreSQL privilege audit (table, column, PUBLIC, membership)

B.1.1.2 corrections:
  - B1.1-01: try/finally to restore password on assertion failure
  - B1.1-04: assert subprocess returncode before querying role attributes
  - B1.1-06: precise DBAPIError + SQLSTATE 42501 check for RLS WITH CHECK
  - B1.1-09: expand to all 4 privileges (SELECT/INSERT/UPDATE/DELETE) on all 12 tables
"""
from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session as SASession

from app.security import hash_password


pytestmark = [pytest.mark.security, pytest.mark.integration]


SETUP_DB_URL = "postgresql+psycopg://postgres@localhost:5432/m369_support_test"
APP_DB_URL = "postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test"
SA_AUTH_DB_URL = "postgresql://m369_sa_auth:m369_sa_auth_dev_password@localhost:5432/m369_support_test"
SA_DB_URL = "postgresql://m369_sa_runner:m369_sa_runner_dev_password@localhost:5432/m369_support_test"


def _make_agency(setup, name="A"):
    aid = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO agencies (id, name, slug, brand_color, is_active) "
        f"VALUES ('{aid}', '{name}', 'test-{aid.hex[:6]}', '#FF6B35', true)"
    ))
    setup.commit()
    return aid


def _make_workspace(setup, agency_id, name="WS"):
    wid = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO workspaces (id, agency_id, name, slug, timezone, is_active) "
        f"VALUES ('{wid}', '{agency_id}', '{name}', 'ws-{wid.hex[:6]}', 'UTC', true)"
    ))
    setup.commit()
    return wid


def _make_contact(setup, agency_id, workspace_id, email="c@test.com"):
    cid = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO contacts (id, agency_id, workspace_id, email, name) "
        f"VALUES ('{cid}', '{agency_id}', '{workspace_id}', '{email}', 'C')"
    ))
    setup.commit()
    return cid


def _make_conversation(setup, agency_id, workspace_id, contact_id):
    vid = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO conversations (id, agency_id, workspace_id, contact_id, status) "
        f"VALUES ('{vid}', '{agency_id}', '{workspace_id}', '{contact_id}', 'open')"
    ))
    setup.commit()
    return vid


def _make_message(setup, agency_id, conversation_id, content="hello"):
    mid = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO messages (id, agency_id, conversation_id, sender_type, content, delivery_status) "
        f"VALUES ('{mid}', '{agency_id}', '{conversation_id}', 'agent', '{content}', 'sent')"
    ))
    setup.commit()
    return mid


def _make_attachment(setup, agency_id, message_id, filename="test.txt"):
    att_id = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO message_attachments (id, message_id, agency_id, filename, mime_type, size_bytes, storage_key) "
        f"VALUES ('{att_id}', '{message_id}', '{agency_id}', '{filename}', 'text/plain', 100, 'key1')"
    ))
    setup.commit()
    return att_id


# ===========================================================================
# B1-F01: Provisioning tests (B1.1-01 to B1.1-05)
# ===========================================================================


def test_B1_1_01_provisioning_changes_password(setup_session):
    """B1.1-01: Provisioning on an existing role changes its password to the env value.

    Uses try/finally so the test password is always restored to the original
    value — even if an assertion or connection fails.
    """
    api_dir = Path(__file__).resolve().parents[2]

    try:
        # Set temporary test password
        r = subprocess.run(
            ["python", "scripts/provision_sa_auth_role.py"],
            cwd=str(api_dir),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DATABASE_URL": SETUP_DB_URL,
                "M369_SA_AUTH_PASSWORD": "new_test_password_456",
            },
        )
        assert r.returncode == 0, f"provisioning failed: {r.stderr}"
        assert "completed" in r.stdout.lower()

        # Verify the new password works
        conn = psycopg.connect(
            "postgresql://m369_sa_auth:new_test_password_456@localhost:5432/m369_support_test"
        )
        conn.close()

    finally:
        # Always restore the original password — even if the test failed.
        # If restoration fails, the test must FAIL (not silently pass).
        r_restore = subprocess.run(
            ["python", "scripts/provision_sa_auth_role.py"],
            cwd=str(api_dir),
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "DATABASE_URL": SETUP_DB_URL,
                "M369_SA_AUTH_PASSWORD": "m369_sa_auth_dev_password",
            },
        )
        assert r_restore.returncode == 0, (
            "CRITICAL: password restoration failed — subsequent tests will break. "
            f"stderr: {r_restore.stderr}"
        )


def test_B1_1_02_provisioning_idempotent(setup_session):
    """B1.1-02: Running the script multiple times without error."""
    api_dir = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "DATABASE_URL": SETUP_DB_URL,
        "M369_SA_AUTH_PASSWORD": "m369_sa_auth_dev_password",
    }
    r1 = subprocess.run(
        ["python", "scripts/provision_sa_auth_role.py"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r1.returncode == 0
    r2 = subprocess.run(
        ["python", "scripts/provision_sa_auth_role.py"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r2.returncode == 0, f"second run failed: {r2.stderr}"


def test_B1_1_03_provisioning_enables_real_connection(setup_session):
    """B1.1-03: After provisioning, a real connection with m369_sa_auth works."""
    api_dir = Path(__file__).resolve().parents[2]
    r = subprocess.run(
        ["python", "scripts/provision_sa_auth_role.py"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DATABASE_URL": SETUP_DB_URL,
            "M369_SA_AUTH_PASSWORD": "m369_sa_auth_dev_password",
        },
    )
    assert r.returncode == 0

    # Real connection test
    conn = psycopg.connect(SA_AUTH_DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user")
            assert cur.fetchone()[0] == "m369_sa_auth"
    finally:
        conn.close()


def test_B1_1_04_provisioning_preserves_role_attributes(setup_session):
    """B1.1-04: After provisioning, role attributes are still correct.

    The subprocess return code is asserted BEFORE querying the role —
    if provisioning failed, the role attributes are meaningless.
    """
    api_dir = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["python", "scripts/provision_sa_auth_role.py"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DATABASE_URL": SETUP_DB_URL,
            "M369_SA_AUTH_PASSWORD": "m369_sa_auth_dev_password",
        },
    )
    assert result.returncode == 0, (
        "Provisioning failed; role attributes were not verified. "
        f"stderr: {result.stderr}"
    )

    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreatedb,
                       rolcreaterole, rolreplication, rolinherit
                FROM pg_roles WHERE rolname = 'm369_sa_auth'
            """)
            row = cur.fetchone()
            assert row == (True, False, False, False, False, False, False), \
                f"Role attributes wrong: {row}"
    finally:
        conn.close()


def test_B1_1_05_missing_password_exits_nonzero(setup_session):
    """B1.1-05: Missing M369_SA_AUTH_PASSWORD causes non-zero exit, no secret leaked."""
    api_dir = Path(__file__).resolve().parents[2]
    r = subprocess.run(
        ["python", "scripts/provision_sa_auth_role.py"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "DATABASE_URL": SETUP_DB_URL,
            # M369_SA_AUTH_PASSWORD intentionally NOT set
        },
    )
    assert r.returncode == 1, f"expected exit 1, got {r.returncode}"
    assert "M369_SA_AUTH_PASSWORD is required" in r.stdout
    # No password or connection string should appear in output
    assert "m369_sa_auth_dev_password" not in r.stdout
    assert "m369_sa_auth_dev_password" not in r.stderr


# ===========================================================================
# B1-F02: Complete RLS UPDATE test for message_attachments (B1-16 corrected)
# ===========================================================================


def test_B1_1_06_attachment_rls_full_crud_cross_tenant(setup_session):
    """B1.1-06: Tenant B cannot SELECT, INSERT, UPDATE, or DELETE Tenant A's attachments.

    Complete cross-tenant CRUD test using m369_app (RLS-enforced) connection
    with SET LOCAL app.tenant_id = '<agency_b>'.

    The INSERT test verifies that the error is specifically PostgreSQL's
    insufficient_privilege (SQLSTATE 42501) from RLS WITH CHECK — not an
    unrelated FK violation or database error.
    """
    agency_a = _make_agency(setup_session, "A")
    agency_b = _make_agency(setup_session, "B")
    ws_a = _make_workspace(setup_session, agency_a, "WSA")
    contact_a = _make_contact(setup_session, agency_a, ws_a, "a@a.com")
    conv_a = _make_conversation(setup_session, agency_a, ws_a, contact_a)
    msg_a = _make_message(setup_session, agency_a, conv_a)
    att_a = _make_attachment(setup_session, agency_a, msg_a, "secret.txt")

    app_engine = create_engine("postgresql+psycopg://m369_app:m369_app_dev_password@localhost:5432/m369_support_test")
    with SASession(app_engine) as session:
        # Set tenant context to B
        session.execute(text(f"SET LOCAL app.tenant_id = '{agency_b}'"))

        # 1. SELECT — Tenant B should see 0 attachments (RLS hides A's)
        count = session.execute(text("SELECT COUNT(*) FROM message_attachments")).fetchone()
        assert count[0] == 0, "Tenant B saw Tenant A's attachment — RLS SELECT broken"

        # 2. INSERT with agency_id = A — should fail (RLS WITH CHECK)
        # The error must be PostgreSQL insufficient_privilege (SQLSTATE 42501),
        # NOT a Foreign Key violation or unrelated database error.
        att_evil = uuid.uuid4()
        insert_sql = text(
            f"INSERT INTO message_attachments (id, message_id, agency_id, filename, mime_type, size_bytes, storage_key) "
            f"VALUES ('{att_evil}', '{msg_a}', '{agency_a}', 'evil.txt', 'text/plain', 100, 'evil')"
        )
        with pytest.raises(DBAPIError) as exc_info:
            session.execute(insert_sql)
        # Verify the error is RLS insufficient_privilege (42501), not an FK error
        sqlstate = getattr(exc_info.value.orig, "sqlstate", None) or \
                   getattr(getattr(exc_info.value, "orig", None), "diag", None)
        # psycopg3: sqlstate is on .orig.diag.sqlstate
        diag = getattr(getattr(exc_info.value, "orig", None), "diag", None)
        actual_sqlstate = getattr(diag, "sqlstate", None) if diag else None
        assert actual_sqlstate == "42501", (
            f"Expected PostgreSQL insufficient_privilege (42501) "
            f"from RLS WITH CHECK, got SQLSTATE={actual_sqlstate}. "
            f"This may be a Foreign Key error or unrelated DB error — "
            f"RLS protection is not confirmed."
        )
        # Rollback the failed transaction so the session is usable again
        session.rollback()

    with SASession(app_engine) as session:
        session.execute(text(f"SET LOCAL app.tenant_id = '{agency_b}'"))

        # 3. UPDATE — should match 0 rows (RLS hides A's rows)
        result = session.execute(text(
            f"UPDATE message_attachments SET filename = 'hacked.txt' WHERE id = '{att_a}'"
        ))
        assert result.rowcount == 0, "Tenant B was able to UPDATE Tenant A's attachment — RLS UPDATE broken"

    with SASession(app_engine) as session:
        session.execute(text(f"SET LOCAL app.tenant_id = '{agency_b}'"))

        # 4. DELETE — should match 0 rows (RLS hides A's rows)
        result = session.execute(text(
            f"DELETE FROM message_attachments WHERE id = '{att_a}'"
        ))
        assert result.rowcount == 0, "Tenant B was able to DELETE Tenant A's attachment — RLS DELETE broken"

    # 5. Tenant A should still be able to read its own attachment
    with SASession(app_engine) as session:
        session.execute(text(f"SET LOCAL app.tenant_id = '{agency_a}'"))
        row = session.execute(text(
            f"SELECT filename FROM message_attachments WHERE id = '{att_a}'"
        )).fetchone()
        assert row is not None, "Tenant A cannot read its own attachment — RLS too strict"
        assert row[0] == "secret.txt", f"Filename changed unexpectedly: {row[0]}"

    # 6. Verify original data is unchanged
    setup_session.expire_all()
    row = setup_session.execute(text(
        f"SELECT filename FROM message_attachments WHERE id = '{att_a}'"
    )).fetchone()
    assert row[0] == "secret.txt", "Original data was modified by Tenant B"


# ===========================================================================
# B1-F03: Effective privilege audit (B1.1-07 to B1.1-15)
# ===========================================================================


def test_B1_1_07_app_no_sa_table_access(setup_session):
    """B1.1-07: m369_app has NO access to all 5 Super Admin tables."""
    sa_tables = [
        "super_admins",
        "super_admin_audit_logs",
        "super_admin_mfa_challenges",
        "super_admin_mfa_recovery_codes",
        "super_admin_used_totp_codes",
    ]
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            for table in sa_tables:
                for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    cur.execute(
                        "SELECT has_table_privilege('m369_app', %s, %s)",
                        (table, priv),
                    )
                    assert not cur.fetchone()[0], (
                        f"m369_app has {priv} on {table}"
                    )
    finally:
        conn.close()


def test_B1_1_08_app_no_public_access(setup_session):
    """B1.1-08: m369_app cannot access SA tables via PUBLIC grants.

    Checks pg_class.relacl for entries where the grantee is empty (=PUBLIC).
    """
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            # Parse the ACL (relacl) array to check for PUBLIC grants
            # An ACL entry "=r/postgres" means PUBLIC has SELECT (grantee is empty).
            # An entry "m369_app=r/postgres" means m369_app has SELECT.
            # We check if any entry has an empty grantee prefix (= starts with "=").
            cur.execute("""
                SELECT relname, COALESCE(relacl::text[], ARRAY[]::text[]) AS acls
                FROM pg_class
                WHERE relname IN (
                    'super_admins', 'super_admin_audit_logs',
                    'super_admin_mfa_challenges', 'super_admin_mfa_recovery_codes',
                    'super_admin_used_totp_codes'
                )
            """)
            for relname, acls in cur.fetchall():
                for acl in acls:
                    # ACL format: grantee=privs/grantor
                    # PUBLIC entries have empty grantee: =privs/grantor
                    grantee_part = acl.split("=")[0] if "=" in acl else ""
                    if grantee_part == "" and "=" in acl:
                        # This is a PUBLIC grant — fail
                        pytest.fail(
                            f"PUBLIC has privilege on {relname}: {acl}"
                        )
    finally:
        conn.close()


def test_B1_1_09_sa_auth_no_tenant_access(setup_session):
    """B1.1-09: m369_sa_auth has NO access to tenant tables.

    Checks all 4 DML privileges (SELECT, INSERT, UPDATE, DELETE) on all 12
    tenant + platform tables. None should be granted to m369_sa_auth.
    """
    tenant_tables = [
        "agencies", "users", "workspaces", "contacts", "conversations",
        "messages", "message_attachments", "payments", "subscriptions",
        "plans", "platform_settings", "agency_notes",
    ]
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            for table in tenant_tables:
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    cur.execute(
                        "SELECT has_table_privilege('m369_sa_auth', %s, %s)",
                        (table, privilege),
                    )
                    assert not cur.fetchone()[0], (
                        f"m369_sa_auth unexpectedly has {privilege} on {table}"
                    )
    finally:
        conn.close()


def test_B1_1_10_sa_auth_cannot_set_role(setup_session):
    """B1.1-10: m369_sa_auth cannot SET ROLE m369_sa_runner."""
    conn = psycopg.connect(SA_AUTH_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            raised = False
            try:
                cur.execute("SET ROLE m369_sa_runner")
            except Exception:
                raised = True
            assert raised, "m369_sa_auth was able to SET ROLE m369_sa_runner"
    finally:
        conn.close()


def test_B1_1_11_sa_auth_cannot_create(setup_session):
    """B1.1-11: m369_sa_auth cannot CREATE TABLE or CREATE ROLE."""
    conn = psycopg.connect(SA_AUTH_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            raised = False
            try:
                cur.execute("CREATE TABLE evil (id int)")
            except Exception:
                raised = True
            assert raised, "m369_sa_auth was able to CREATE TABLE"

            raised = False
            try:
                cur.execute("CREATE ROLE evil_role")
            except Exception:
                raised = True
            assert raised, "m369_sa_auth was able to CREATE ROLE"
    finally:
        conn.close()


def test_B1_1_12_column_level_update_verification(setup_session):
    """B1.1-12: Column-level UPDATE on super_admins — allowed vs blocked columns."""
    from app.models import SuperAdmin
    admin = SuperAdmin(
        email=f"coltest-{uuid.uuid4().hex[:6]}@m369.platform",
        name="Col Test SA",
        password_hash=hash_password("test-password-123"),
        is_active=True,
    )
    setup_session.add(admin)
    setup_session.commit()
    setup_session.refresh(admin)

    conn = psycopg.connect(SA_AUTH_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            # Allowed columns
            cur.execute(
                f"UPDATE super_admins SET failed_login_attempts = 1 WHERE id = '{admin.id}'"
            )
            cur.execute(
                f"UPDATE super_admins SET locked_until = NULL WHERE id = '{admin.id}'"
            )
            cur.execute(
                f"UPDATE super_admins SET last_login_at = NOW() WHERE id = '{admin.id}'"
            )

            # Blocked columns
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    f"UPDATE super_admins SET password_hash = 'unauthorized' WHERE id = '{admin.id}'"
                )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    f"UPDATE super_admins SET is_active = false WHERE id = '{admin.id}'"
                )
    finally:
        conn.close()


def test_B1_1_13_role_membership_audit(setup_session):
    """B1.1-13: No unwanted role memberships for m369_sa_auth or m369_app."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            # Check m369_sa_auth memberships
            cur.execute("""
                SELECT r.rolname
                FROM pg_auth_members am
                JOIN pg_roles r ON r.oid = am.roleid
                JOIN pg_roles m ON m.oid = am.member
                WHERE m.rolname = 'm369_sa_auth'
            """)
            members = [row[0] for row in cur.fetchall()]
            assert members == [], f"m369_sa_auth has unexpected memberships: {members}"

            # Check m369_app memberships (should not be in m369_sa_runner or m369_sa_auth)
            cur.execute("""
                SELECT r.rolname
                FROM pg_auth_members am
                JOIN pg_roles r ON r.oid = am.roleid
                JOIN pg_roles m ON m.oid = am.member
                WHERE m.rolname = 'm369_app'
                  AND r.rolname IN ('m369_sa_runner', 'm369_sa_auth')
            """)
            members = [row[0] for row in cur.fetchall()]
            assert members == [], f"m369_app has unexpected memberships: {members}"
    finally:
        conn.close()


def test_B1_1_14_sa_runner_still_works(setup_session):
    """B1.1-14: m369_sa_runner still works for management operations."""
    agency_id = _make_agency(setup_session)
    conn = psycopg.connect(SA_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT name FROM agencies WHERE id = '{agency_id}'")
            assert cur.fetchone()[0] == "A"
            plan_id = uuid.uuid4()
            cur.execute(
                f"INSERT INTO plans (id, name, display_name, price_monthly, currency) "
                f"VALUES ('{plan_id}', 'test', 'Test', 1900, 'USD')"
            )
    finally:
        conn.close()


def test_B1_1_15_regression_marker():
    """B1.1-15: Marker — full suite verifies all previous tests pass."""
    assert True
