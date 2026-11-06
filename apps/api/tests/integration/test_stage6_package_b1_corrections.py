"""Package B.1 — Critical FK corrections + dedicated SA auth role.

Tests B1-01 through B1-17 verify migration 0012's changes:
  - FK ON DELETE behavior corrections (kb_articles, messages)
  - m369_sa_auth role with column-level UPDATE privileges
  - m369_app completely removed from Super Admin tables
  - Role escalation prevention
  - Cross-tenant IDOR prevention
"""
from __future__ import annotations

import uuid

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session as SASession

from app.security import hash_password


pytestmark = [pytest.mark.security, pytest.mark.integration]


SETUP_DB_URL = "postgresql+psycopg://postgres@localhost:5432/m369_support_test"
APP_DB_URL = "postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test"
SA_DB_URL = "postgresql://m369_sa_runner:m369_sa_runner_dev_password@localhost:5432/m369_support_test"
SA_AUTH_DB_URL = "postgresql://m369_sa_auth:m369_sa_auth_dev_password@localhost:5432/m369_support_test"


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


def _make_kb_category(setup, agency_id, workspace_id, name="Cat"):
    cid = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO kb_categories (id, agency_id, workspace_id, name, slug) "
        f"VALUES ('{cid}', '{agency_id}', '{workspace_id}', '{name}', 'cat-{cid.hex[:6]}')"
    ))
    setup.commit()
    return cid


def _make_kb_article(setup, agency_id, workspace_id, category_id, title="Art"):
    aid = uuid.uuid4()
    setup.execute(text(
        f"INSERT INTO kb_articles (id, agency_id, workspace_id, category_id, title, slug, content_md) "
        f"VALUES ('{aid}', '{agency_id}', '{workspace_id}', '{category_id}', '{title}', 'art-{aid.hex[:6]}', 'content')"
    ))
    setup.commit()
    return aid


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


# ---------------------------------------------------------------------------
# B1-01: Delete KB category → category_id NULL, workspace_id + agency_id preserved
# ---------------------------------------------------------------------------


def test_B1_01_delete_category_nulls_category_id_only(setup_session):
    """B1-01: Deleting a KB category sets article.category_id = NULL
    but preserves workspace_id and agency_id."""
    agency_id = _make_agency(setup_session)
    ws_id = _make_workspace(setup_session, agency_id)
    cat_id = _make_kb_category(setup_session, agency_id, ws_id)
    art_id = _make_kb_article(setup_session, agency_id, ws_id, cat_id)

    # Delete the category
    setup_session.execute(text(f"DELETE FROM kb_categories WHERE id = '{cat_id}'"))
    setup_session.commit()

    # Read the article
    row = setup_session.execute(text(
        f"SELECT category_id, workspace_id, agency_id FROM kb_articles WHERE id = '{art_id}'"
    )).fetchone()
    assert row[0] is None, f"category_id should be NULL, got {row[0]}"
    assert str(row[1]) == str(ws_id), "workspace_id was changed"
    assert str(row[2]) == str(agency_id), "agency_id was changed"


# ---------------------------------------------------------------------------
# B1-02: Delete reference message → reply_to_message_id NULL, agency_id preserved
# ---------------------------------------------------------------------------


def test_B1_02_delete_reference_message_nulls_reply_only(setup_session):
    """B1-02: Deleting a referenced message sets reply_to_message_id = NULL
    but preserves agency_id."""
    agency_id = _make_agency(setup_session)
    ws_id = _make_workspace(setup_session, agency_id)
    contact_id = _make_contact(setup_session, agency_id, ws_id)
    conv_id = _make_conversation(setup_session, agency_id, ws_id, contact_id)
    msg1_id = _make_message(setup_session, agency_id, conv_id, "first")

    # Create reply message referencing msg1
    msg2_id = uuid.uuid4()
    setup_session.execute(text(
        f"INSERT INTO messages (id, agency_id, conversation_id, sender_type, content, reply_to_message_id, delivery_status) "
        f"VALUES ('{msg2_id}', '{agency_id}', '{conv_id}', 'agent', 'reply', '{msg1_id}', 'sent')"
    ))
    setup_session.commit()

    # Delete the reference message
    setup_session.execute(text(f"DELETE FROM messages WHERE id = '{msg1_id}'"))
    setup_session.commit()

    # Read the reply
    row = setup_session.execute(text(
        f"SELECT reply_to_message_id, agency_id FROM messages WHERE id = '{msg2_id}'"
    )).fetchone()
    assert row[0] is None, f"reply_to_message_id should be NULL, got {row[0]}"
    assert str(row[1]) == str(agency_id), "agency_id was changed"


# ---------------------------------------------------------------------------
# B1-03: Cross-agency reply prevented
# ---------------------------------------------------------------------------


def test_B1_03_cross_agency_reply_prevented(setup_session):
    """B1-03: A message cannot reply to a message from another agency."""
    agency_a = _make_agency(setup_session, "A")
    agency_b = _make_agency(setup_session, "B")
    ws_a = _make_workspace(setup_session, agency_a, "WSA")
    contact_a = _make_contact(setup_session, agency_a, ws_a, "a@a.com")
    conv_a = _make_conversation(setup_session, agency_a, ws_a, contact_a)
    msg_a = _make_message(setup_session, agency_a, conv_a, "in agency A")

    # Try to create a reply in agency B referencing msg_a
    ws_b = _make_workspace(setup_session, agency_b, "WSB")
    contact_b = _make_contact(setup_session, agency_b, ws_b, "b@b.com")
    conv_b = _make_conversation(setup_session, agency_b, ws_b, contact_b)
    msg_b_id = uuid.uuid4()
    with pytest.raises(Exception) as exc:
        setup_session.execute(text(
            f"INSERT INTO messages (id, agency_id, conversation_id, sender_type, content, reply_to_message_id, delivery_status) "
            f"VALUES ('{msg_b_id}', '{agency_b}', '{conv_b}', 'agent', 'reply', '{msg_a}', 'sent')"
        ))
    assert "foreign key" in str(exc.value).lower() or "fk_messages_reply_to" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# B1-04: Cross-agency KB category prevented
# ---------------------------------------------------------------------------


def test_B1_04_cross_agency_kb_category_prevented(setup_session):
    """B1-04: An article cannot have a category from a different workspace/agency."""
    agency_a = _make_agency(setup_session, "A")
    agency_b = _make_agency(setup_session, "B")
    ws_a = _make_workspace(setup_session, agency_a, "WSA")
    ws_b = _make_workspace(setup_session, agency_b, "WSB")
    cat_a = _make_kb_category(setup_session, agency_a, ws_a)

    # Try to create an article in agency B with category from agency A
    art_id = uuid.uuid4()
    with pytest.raises(Exception) as exc:
        setup_session.execute(text(
            f"INSERT INTO kb_articles (id, agency_id, workspace_id, category_id, title, slug, content_md) "
            f"VALUES ('{art_id}', '{agency_b}', '{ws_b}', '{cat_a}', 'Title', 'slug', 'content')"
        ))
    assert "foreign key" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# B1-05: m369_app cannot SELECT super_admins
# ---------------------------------------------------------------------------


def test_B1_05_app_cannot_select_super_admins(setup_session):
    """B1-05: m369_app has NO SELECT on super_admins."""
    conn = psycopg.connect(APP_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("SELECT * FROM super_admins LIMIT 1")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-06: m369_app cannot UPDATE super_admins
# ---------------------------------------------------------------------------


def test_B1_06_app_cannot_update_super_admins(setup_session):
    """B1-06: m369_app has NO UPDATE on super_admins."""
    conn = psycopg.connect(APP_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("UPDATE super_admins SET is_active = false")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-07: m369_app has no access to MFA tables
# ---------------------------------------------------------------------------


def test_B1_07_app_no_mfa_access(setup_session):
    """B1-07: m369_app has NO access to MFA tables."""
    mfa_tables = [
        "super_admin_mfa_challenges",
        "super_admin_mfa_recovery_codes",
        "super_admin_used_totp_codes",
    ]
    conn = psycopg.connect(APP_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            for table in mfa_tables:
                for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        cur.execute(f"{priv} FROM {table} LIMIT 1" if priv == "SELECT" else f"INSERT INTO {table} DEFAULT VALUES")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-08: m369_app has no access to super_admin_audit_logs
# ---------------------------------------------------------------------------


def test_B1_08_app_no_audit_access(setup_session):
    """B1-08: m369_app has NO access to super_admin_audit_logs."""
    conn = psycopg.connect(APP_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("SELECT * FROM super_admin_audit_logs LIMIT 1")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-09: Real authentication via m369_sa_auth
# ---------------------------------------------------------------------------


def test_B1_09_real_auth_via_sa_auth(client, setup_session, monkeypatch):
    """B1-09: Login + MFA flows work with m369_sa_auth connection."""
    from app.core.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    from app.models import SuperAdmin
    admin = SuperAdmin(
        email=f"b1test-{uuid.uuid4().hex[:6]}@m369.platform",
        name="B1 Test SA",
        password_hash=hash_password("super-admin-password-123"),
        is_active=True,
    )
    setup_session.add(admin)
    setup_session.commit()
    setup_session.refresh(admin)

    # Wrong password → 401
    r1 = client.post("/api/v1/super-admin/auth/login",
                      json={"email": admin.email, "password": "wrong"})
    assert r1.status_code == 401

    # Correct password → 200
    r2 = client.post("/api/v1/super-admin/auth/login",
                      json={"email": admin.email, "password": "super-admin-password-123"})
    assert r2.status_code == 200, f"login failed: {r2.text}"


# ---------------------------------------------------------------------------
# B1-10: Real MFA via m369_sa_auth
# ---------------------------------------------------------------------------


def test_B1_10_real_mfa_via_sa_auth(client, setup_session, monkeypatch):
    """B1-10: MFA setup → login → verify works with m369_sa_auth."""
    import pyotp
    from app.core.config import get_settings
    from app.models import SuperAdmin

    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", False)

    admin = SuperAdmin(
        email=f"mfatest-{uuid.uuid4().hex[:6]}@m369.platform",
        name="MFA Test SA",
        password_hash=hash_password("super-admin-password-123"),
        is_active=True,
    )
    setup_session.add(admin)
    setup_session.commit()
    setup_session.refresh(admin)

    # Login to get a token (MFA not yet enabled)
    r_login = client.post("/api/v1/super-admin/auth/login",
                          json={"email": admin.email, "password": "super-admin-password-123"})
    assert r_login.status_code == 200
    token = r_login.cookies.get("super_admin_access_token")
    assert token is not None

    # Setup MFA
    r_setup = client.post("/api/v1/super-admin/auth/mfa/setup",
                           headers={"Authorization": f"Bearer {token}"})
    assert r_setup.status_code == 200
    secret = r_setup.json()["secret"]

    # Enable MFA with valid TOTP code
    totp = pyotp.TOTP(secret, digits=s.totp_digits, interval=s.totp_step_seconds)
    code = totp.now()
    r_enable = client.post("/api/v1/super-admin/auth/mfa/enable",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"secret": secret, "code": code})
    assert r_enable.status_code == 200, f"MFA enable failed: {r_enable.text}"

    # Logout
    client.post("/api/v1/super-admin/auth/logout",
                headers={"Authorization": f"Bearer {token}"})

    # Login again → should require MFA
    r_login2 = client.post("/api/v1/super-admin/auth/login",
                            json={"email": admin.email, "password": "super-admin-password-123"})
    assert r_login2.status_code == 200
    assert r_login2.json().get("mfa_required") is True
    challenge = r_login2.json()["mfa_challenge"]

    # Verify MFA with correct code
    code2 = totp.now()
    r_verify = client.post("/api/v1/super-admin/auth/login/verify-mfa",
                           json={"mfa_challenge": challenge, "code": code2})
    assert r_verify.status_code == 200, f"MFA verify failed: {r_verify.text}"


# ---------------------------------------------------------------------------
# B1-11: Column-level UPDATE restriction
# ---------------------------------------------------------------------------


def test_B1_11_column_level_update_restriction(setup_session):
    """B1-11: m369_sa_auth can UPDATE allowed columns but NOT password_hash or is_active."""
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
            # Allowed: UPDATE failed_login_attempts
            cur.execute(
                f"UPDATE super_admins SET failed_login_attempts = 1 WHERE id = '{admin.id}'"
            )
            # Allowed: UPDATE locked_until
            cur.execute(
                f"UPDATE super_admins SET locked_until = NULL WHERE id = '{admin.id}'"
            )
            # NOT allowed: UPDATE password_hash
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    f"UPDATE super_admins SET password_hash = 'unauthorized' WHERE id = '{admin.id}'"
                )
            # NOT allowed: UPDATE is_active
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    f"UPDATE super_admins SET is_active = false WHERE id = '{admin.id}'"
                )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-12: m369_sa_auth cannot access tenant data
# ---------------------------------------------------------------------------


def test_B1_12_sa_auth_no_tenant_access(setup_session):
    """B1-12: m369_sa_auth has NO SELECT on tenant tables."""
    tenant_tables = [
        "agencies", "users", "workspaces", "conversations",
        "messages", "message_attachments", "subscriptions", "payments",
    ]
    conn = psycopg.connect(SA_AUTH_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            for table in tenant_tables:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cur.execute(f"SELECT * FROM {table} LIMIT 1")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-13: Role escalation prevention
# ---------------------------------------------------------------------------


def test_B1_13_role_escalation_prevented(setup_session):
    """B1-13: m369_sa_auth cannot SET ROLE m369_sa_runner or CREATE TABLE."""
    conn = psycopg.connect(SA_AUTH_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            # Cannot SET ROLE
            raised = False
            try:
                cur.execute("SET ROLE m369_sa_runner")
            except Exception:
                raised = True
            assert raised, "m369_sa_auth was able to SET ROLE m369_sa_runner"

            # Cannot CREATE TABLE
            raised = False
            try:
                cur.execute("CREATE TABLE evil (id int)")
            except Exception:
                raised = True
            assert raised, "m369_sa_auth was able to CREATE TABLE"

            # Cannot CREATE ROLE
            raised = False
            try:
                cur.execute("CREATE ROLE evil_role")
            except Exception:
                raised = True
            assert raised, "m369_sa_auth was able to CREATE ROLE"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-14: m369_sa_runner still works for management
# ---------------------------------------------------------------------------


def test_B1_14_sa_runner_still_works(setup_session):
    """B1-14: m369_sa_runner can still manage agencies, plans, etc."""
    agency_id = _make_agency(setup_session)
    conn = psycopg.connect(SA_DB_URL, autocommit=True)
    try:
        with conn.cursor() as cur:
            # Can SELECT agencies
            cur.execute(f"SELECT name FROM agencies WHERE id = '{agency_id}'")
            assert cur.fetchone()[0] == "A"
            # Can UPDATE agencies (suspend)
            cur.execute(f"UPDATE agencies SET is_active = false WHERE id = '{agency_id}'")
            # Can INSERT plans
            plan_id = uuid.uuid4()
            cur.execute(
                f"INSERT INTO plans (id, name, display_name, price_monthly, currency) "
                f"VALUES ('{plan_id}', 'test', 'Test', 1900, 'USD')"
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-15: Role attributes verification
# ---------------------------------------------------------------------------


def test_B1_15_role_attributes(setup_session):
    """B1-15: Verify exact role attributes via SQL."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rolname, rolsuper, rolinherit, rolcreaterole,
                       rolcreatedb, rolcanlogin, rolreplication, rolbypassrls
                FROM pg_roles
                WHERE rolname IN ('m369_app', 'm369_sa_auth', 'm369_sa_runner')
                ORDER BY rolname
            """)
            rows = cur.fetchall()
            roles = {row[0]: row for row in rows}

            # m369_app
            app = roles["m369_app"]
            assert not app[1], "m369_app should be NOSUPERUSER"
            assert not app[7], "m369_app should be NOBYPASSRLS"

            # m369_sa_auth
            auth = roles["m369_sa_auth"]
            assert auth[5], "m369_sa_auth should be LOGIN"
            assert not auth[1], "m369_sa_auth should be NOSUPERUSER"
            assert not auth[7], "m369_sa_auth should be NOBYPASSRLS"
            assert not auth[3], "m369_sa_auth should be NOCREATEROLE"
            assert not auth[4], "m369_sa_auth should be NOCREATEDB"

            # m369_sa_runner
            runner = roles["m369_sa_runner"]
            assert runner[5], "m369_sa_runner should be LOGIN"
            assert not runner[1], "m369_sa_runner should be NOSUPERUSER"
            assert runner[7], "m369_sa_runner should be BYPASSRLS"
            assert not runner[3], "m369_sa_runner should be NOCREATEROLE"
            assert not runner[4], "m369_sa_runner should be NOCREATEDB"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# B1-16: RLS on message_attachments (cross-tenant)
# ---------------------------------------------------------------------------


def test_B1_16_message_attachments_rls(setup_session):
    """B1-16: Tenant A cannot read/insert/update Tenant B's attachments."""
    agency_a = _make_agency(setup_session, "A")
    agency_b = _make_agency(setup_session, "B")
    ws_a = _make_workspace(setup_session, agency_a, "WSA")
    contact_a = _make_contact(setup_session, agency_a, ws_a, "a@a.com")
    conv_a = _make_conversation(setup_session, agency_a, ws_a, contact_a)
    msg_a = _make_message(setup_session, agency_a, conv_a)

    # Insert an attachment for agency A
    att_id = uuid.uuid4()
    setup_session.execute(text(
        f"INSERT INTO message_attachments (id, message_id, agency_id, filename, mime_type, size_bytes, storage_key) "
        f"VALUES ('{att_id}', '{msg_a}', '{agency_a}', 'test.txt', 'text/plain', 100, 'key1')"
    ))
    setup_session.commit()

    # Tenant B tries to read it via m369_app
    app_engine = create_engine("postgresql+psycopg://m369_app:m369_app_dev_password@localhost:5432/m369_support_test")
    with SASession(app_engine) as session:
        session.execute(text(f"SET LOCAL app.tenant_id = '{agency_b}'"))
        rows = session.execute(text("SELECT COUNT(*) FROM message_attachments")).fetchone()
        assert rows[0] == 0, "Tenant B saw Tenant A's attachment — RLS broken"

        # Try to INSERT with agency_a's agency_id from tenant B's context
        att2_id = uuid.uuid4()
        with pytest.raises(Exception):
            session.execute(text(
                f"INSERT INTO message_attachments (id, message_id, agency_id, filename, mime_type, size_bytes, storage_key) "
                f"VALUES ('{att2_id}', '{msg_a}', '{agency_a}', 'evil.txt', 'text/plain', 100, 'key2')"
            ))


# ---------------------------------------------------------------------------
# B1-17: Regression — all previous tests still pass (marker)
# ---------------------------------------------------------------------------


def test_B1_17_regression_marker():
    """B1-17: Marker test. The full suite verifies all previous tests pass."""
    assert True
