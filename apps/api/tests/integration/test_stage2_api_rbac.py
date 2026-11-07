"""Stage 2 — API endpoints + RBAC + cross-tenant IDOR + pagination + audit.

Every test exercises the real PostgreSQL + Alembic migration stack via
the conftest dual-connection fixture (setup_session = postgres, db_session
= m369_app with RLS enforced). TestClient uses the m369_app session too,
so all RLS policies are exercised end-to-end.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    Agency,
    AgencyMembership,
    AgencyNote,
    Channel,
    Contact,
    Conversation,
    KBArticle,
    KBCategory,
    Message,
    CannedResponse,
    Team,
    TeamMembership,
    User,
    Workspace,
)
from app.security import create_access_token, hash_password


pytestmark = pytest.mark.security


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_workspace(setup: Session, agency: Agency, name: str = "Main") -> Workspace:
    ws = Workspace(agency_id=agency.id, name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}")
    setup.add(ws)
    setup.commit()
    setup.refresh(ws)
    return ws


def _make_contact(setup: Session, agency: Agency, ws: Workspace, email: str, name: str = "C") -> Contact:
    c = Contact(agency_id=agency.id, workspace_id=ws.id, email=email, name=name)
    setup.add(c)
    setup.commit()
    setup.refresh(c)
    return c


def _make_user_with_role(setup: Session, agency: Agency, email: str, role: str) -> tuple[User, str]:
    u = User(email=email.lower(), name=f"{role}-{email}", password_hash=hash_password("test-password-123"))
    m = AgencyMembership(user=u, agency=agency, role=role)
    setup.add_all([u, m])
    setup.commit()
    setup.refresh(u)
    tok = create_access_token(subject=str(u.id), token_type="agency", agency_id=str(agency.id), token_version=0)
    return u, tok


# ---------------------------------------------------------------------------
# 1. Cross-tenant IDOR — Agency A cannot see Agency B's resources via API
# ---------------------------------------------------------------------------


def test_idor_contact_list_isolated(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A's contacts must not appear in Agency B's GET /contacts."""
    a, _, tok_a = agency_a
    b, _, tok_b = agency_b
    ws_a = _make_workspace(setup_session, a, "WS A")
    ws_b = _make_workspace(setup_session, b, "WS B")
    _make_contact(setup_session, a, ws_a, "a@a.com", "AAA")
    _make_contact(setup_session, b, ws_b, "b@b.com", "BBB")

    r = client.get("/api/v1/contacts", headers=_auth_headers(tok_a))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    emails = {c["email"] for c in body["items"]}
    assert emails == {"a@a.com"}, f"Agency A saw Agency B's contact: {emails}"


def test_idor_contact_get_returns_404_for_foreign(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A cannot GET Agency B's contact by id."""
    a, _, tok_a = agency_a
    b, _, _ = agency_b
    ws_b = _make_workspace(setup_session, b, "WS B")
    c_b = _make_contact(setup_session, b, ws_b, "b@b.com", "BBB")

    r = client.get(f"/api/v1/contacts/{c_b.id}", headers=_auth_headers(tok_a))
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


def test_idor_conversation_get_returns_404_for_foreign(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A cannot read Agency B's conversation."""
    a, _, tok_a = agency_a
    b, _, _ = agency_b
    ws_b = _make_workspace(setup_session, b, "WS B")
    contact_b = _make_contact(setup_session, b, ws_b, "b@b.com")
    conv_b = Conversation(workspace_id=ws_b.id, agency_id=b.id, contact_id=contact_b.id, subject="secret", status="open")
    setup_session.add(conv_b)
    setup_session.commit()
    setup_session.refresh(conv_b)

    r = client.get(f"/api/v1/conversations/{conv_b.id}", headers=_auth_headers(tok_a))
    assert r.status_code == 404


def test_idor_message_send_to_foreign_conversation_blocked(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A cannot send a message to Agency B's conversation.

    Even if Agency A somehow learns the foreign conversation_id, the composite
    FK ``(conversation_id, agency_id)`` rejects the insert — RLS on messages
    also filters the agency_id.
    """
    a, user_a, tok_a = agency_a
    b, _, _ = agency_b
    ws_b = _make_workspace(setup_session, b, "WS B")
    contact_b = _make_contact(setup_session, b, ws_b, "b@b.com")
    conv_b = Conversation(workspace_id=ws_b.id, agency_id=b.id, contact_id=contact_b.id, subject="secret", status="open")
    setup_session.add(conv_b)
    setup_session.commit()
    setup_session.refresh(conv_b)

    r = client.post(
        "/api/v1/messages",
        headers=_auth_headers(tok_a),
        json={"conversation_id": str(conv_b.id), "content": "pwned"},
    )
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


def test_idor_kb_article_cross_agency_invisible(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A cannot read Agency B's KB article."""
    a, _, tok_a = agency_a
    b, _, _ = agency_b
    ws_b = _make_workspace(setup_session, b, "WS B")
    art = KBArticle(
        agency_id=b.id,
        workspace_id=ws_b.id,
        title="Secret KB",
        slug="secret-kb",
        content_md="# secret",
        content_html="",
        is_published=True,
    )
    setup_session.add(art)
    setup_session.commit()
    setup_session.refresh(art)

    r = client.get(f"/api/v1/kb/articles/{art.id}", headers=_auth_headers(tok_a))
    assert r.status_code == 404


def test_idor_channel_cross_agency_invisible(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A cannot see Agency B's channels."""
    a, _, tok_a = agency_a
    b, _, _ = agency_b
    ws_b = _make_workspace(setup_session, b, "WS B")
    ch = Channel(agency_id=b.id, workspace_id=ws_b.id, type="widget", name="widget-b", public_id="pub-b")
    setup_session.add(ch)
    setup_session.commit()

    r = client.get("/api/v1/channels", headers=_auth_headers(tok_a))
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_idor_team_add_foreign_user_blocked(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A cannot add Agency B's user to its team (membership check rejects)."""
    a, _, tok_a = agency_a
    b, user_b, _ = agency_b
    ws_a = _make_workspace(setup_session, a, "WS A")
    team_a = Team(workspace_id=ws_a.id, agency_id=a.id, name="Team A")
    setup_session.add(team_a)
    setup_session.commit()
    setup_session.refresh(team_a)

    r = client.post(
        f"/api/v1/teams/{team_a.id}/members",
        headers=_auth_headers(tok_a),
        json={"user_id": str(user_b.id)},
    )
    assert r.status_code == 400, f"expected 400 (foreign user), got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 2. RBAC — role gating on mutating endpoints
# ---------------------------------------------------------------------------


def test_rbac_viewer_cannot_create_contact(client: TestClient, setup_session: Session, agency_a):
    """A 'viewer' role cannot POST /contacts (requires agent+)."""
    a, _, _ = agency_a
    ws = _make_workspace(setup_session, a)
    _, tok_viewer = _make_user_with_role(setup_session, a, "viewer1@a.com", "viewer")

    r = client.post(
        "/api/v1/contacts",
        headers=_auth_headers(tok_viewer),
        json={"workspace_id": str(ws.id), "email": "new@test.com", "name": "New"},
    )
    assert r.status_code == 403, f"expected 403 for viewer, got {r.status_code}"


def test_rbac_agent_can_create_contact(client: TestClient, setup_session: Session, agency_a):
    """An 'agent' role CAN POST /contacts."""
    a, _, _ = agency_a
    ws = _make_workspace(setup_session, a)
    _, tok_agent = _make_user_with_role(setup_session, a, "agent1@a.com", "agent")

    r = client.post(
        "/api/v1/contacts",
        headers=_auth_headers(tok_agent),
        json={"workspace_id": str(ws.id), "email": "new@test.com", "name": "New"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "new@test.com"


def test_rbac_viewer_can_list_contacts(client: TestClient, setup_session: Session, agency_a):
    """A 'viewer' role CAN GET /contacts (read is allowed for all roles)."""
    a, _, _ = agency_a
    _, tok_viewer = _make_user_with_role(setup_session, a, "viewer2@a.com", "viewer")

    r = client.get("/api/v1/contacts", headers=_auth_headers(tok_viewer))
    assert r.status_code == 200


def test_rbac_manager_cannot_create_channel(client: TestClient, setup_session: Session, agency_a):
    """Channel create requires owner/admin — manager is rejected."""
    a, _, _ = agency_a
    ws = _make_workspace(setup_session, a)
    _, tok_mgr = _make_user_with_role(setup_session, a, "mgr1@a.com", "manager")

    r = client.post(
        "/api/v1/channels",
        headers=_auth_headers(tok_mgr),
        json={"workspace_id": str(ws.id), "type": "widget", "name": "w1"},
    )
    assert r.status_code == 403


def test_rbac_admin_can_create_channel(client: TestClient, setup_session: Session, agency_a):
    """Channel create with admin role succeeds."""
    a, _, _ = agency_a
    ws = _make_workspace(setup_session, a)
    _, tok_admin = _make_user_with_role(setup_session, a, "admin1@a.com", "admin")

    r = client.post(
        "/api/v1/channels",
        headers=_auth_headers(tok_admin),
        json={"workspace_id": str(ws.id), "type": "widget", "name": "w1"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["public_id"]  # widget channels get a public_id


# ---------------------------------------------------------------------------
# 3. Pagination + filtering — limits, offsets, totals match
# ---------------------------------------------------------------------------


def test_pagination_returns_total_and_respects_limit(client: TestClient, setup_session: Session, agency_a):
    """GET /contacts paginates correctly: total reflects all rows, items reflect page."""
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    for i in range(5):
        _make_contact(setup_session, a, ws, f"u{i}@test.com", f"U{i}")

    r = client.get("/api/v1/contacts?limit=2&offset=0", headers=_auth_headers(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2

    r2 = client.get("/api/v1/contacts?limit=2&offset=4", headers=_auth_headers(tok))
    body2 = r2.json()
    assert body2["total"] == 5
    assert len(body2["items"]) == 1  # only the last row


def test_pagination_max_limit_enforced(client: TestClient, setup_session: Session, agency_a):
    """limit > 100 is rejected by the Query validator."""
    a, _, tok = agency_a
    r = client.get("/api/v1/contacts?limit=200", headers=_auth_headers(tok))
    assert r.status_code == 422


def test_search_filter_on_contacts(client: TestClient, setup_session: Session, agency_a):
    """?search= filters by name/email/phone ilike."""
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    _make_contact(setup_session, a, ws, "alice@x.com", "Alice")
    _make_contact(setup_session, a, ws, "bob@x.com", "Bob")
    r = client.get("/api/v1/contacts?search=alice", headers=_auth_headers(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "alice@x.com"


# ---------------------------------------------------------------------------
# 4. Audit log — mutations write audit entries
# ---------------------------------------------------------------------------


def test_audit_log_records_contact_create(client: TestClient, setup_session: Session, agency_a):
    """POST /contacts writes an audit log entry with action=contact.create."""
    from app.tenancy.context import set_tenant_context

    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)

    r = client.post(
        "/api/v1/contacts",
        headers=_auth_headers(tok),
        json={"workspace_id": str(ws.id), "email": "audit@test.com", "name": "Audited"},
    )
    assert r.status_code == 201, r.text
    contact_id = r.json()["id"]

    # Use m369_app connection with tenant context set to read the audit log
    db = setup_session  # postgres — bypasses RLS
    rows = db.execute(
        text("SELECT action, target_type, target_id::text FROM audit_logs WHERE agency_id = :aid AND action = 'contact.create'"),
        {"aid": str(a.id)},
    ).all()
    assert len(rows) == 1
    assert rows[0].target_id == contact_id


def test_audit_log_records_message_send(client: TestClient, setup_session: Session, agency_a):
    """POST /messages writes an audit log entry with action=message.send."""
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    contact = _make_contact(setup_session, a, ws, "msg@test.com")
    conv = Conversation(workspace_id=ws.id, agency_id=a.id, contact_id=contact.id, subject="audit-test", status="open")
    setup_session.add(conv)
    setup_session.commit()
    setup_session.refresh(conv)

    r = client.post(
        "/api/v1/messages",
        headers=_auth_headers(tok),
        json={"conversation_id": str(conv.id), "content": "hello"},
    )
    assert r.status_code == 201, r.text
    db = setup_session
    rows = db.execute(
        text("SELECT action FROM audit_logs WHERE agency_id = :aid AND action = 'message.send'"),
        {"aid": str(a.id)},
    ).all()
    assert len(rows) == 1


def test_audit_log_endpoint_filters_by_action(client: TestClient, setup_session: Session, agency_a):
    """GET /audit-logs?action=contact.create returns only matching rows."""
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    # Create 2 contacts → 2 contact.create audit entries
    for i in range(2):
        client.post(
            "/api/v1/contacts",
            headers=_auth_headers(tok),
            json={"workspace_id": str(ws.id), "email": f"al{i}@test.com", "name": f"Al{i}"},
        )

    r = client.get("/api/v1/audit-logs?action=contact.create", headers=_auth_headers(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(item["action"] == "contact.create" for item in body["items"])


# ---------------------------------------------------------------------------
# 5. Conversation + Message round-trip
# ---------------------------------------------------------------------------


def test_conversation_create_then_send_message(client: TestClient, setup_session: Session, agency_a):
    """End-to-end: create conversation, send a message, list messages."""
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    contact = _make_contact(setup_session, a, ws, "e2e@test.com")

    r = client.post(
        "/api/v1/conversations",
        headers=_auth_headers(tok),
        json={"workspace_id": str(ws.id), "contact_id": str(contact.id), "subject": "hi"},
    )
    assert r.status_code == 201, r.text
    conv_id = r.json()["id"]

    r2 = client.post(
        "/api/v1/messages",
        headers=_auth_headers(tok),
        json={"conversation_id": conv_id, "content": "first message"},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["sender_type"] == "agent"

    r3 = client.get(f"/api/v1/messages?conversation_id={conv_id}", headers=_auth_headers(tok))
    assert r3.status_code == 200
    assert r3.json()["total"] == 1


def test_conversation_status_update(client: TestClient, setup_session: Session, agency_a):
    """PATCH /conversations/{id} updates status."""
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    contact = _make_contact(setup_session, a, ws, "su@test.com")
    conv = Conversation(workspace_id=ws.id, agency_id=a.id, contact_id=contact.id, status="open")
    setup_session.add(conv)
    setup_session.commit()
    setup_session.refresh(conv)

    r = client.patch(
        f"/api/v1/conversations/{conv.id}",
        headers=_auth_headers(tok),
        json={"status": "resolved"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"


# ---------------------------------------------------------------------------
# 6. KB round-trip
# ---------------------------------------------------------------------------


def test_kb_category_and_article_round_trip(client: TestClient, setup_session: Session, agency_a):
    """Create category, create article, list, get."""
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    r = client.post(
        "/api/v1/kb/categories",
        headers=_auth_headers(tok),
        json={"workspace_id": str(ws.id), "name": "Getting Started"},
    )
    assert r.status_code == 201, r.text
    cat_id = r.json()["id"]
    assert r.json()["slug"] == "getting-started"

    r2 = client.post(
        "/api/v1/kb/articles",
        headers=_auth_headers(tok),
        json={
            "workspace_id": str(ws.id),
            "category_id": str(cat_id),
            "title": "Welcome",
            "content_md": "# Welcome",
            "is_published": True,
        },
    )
    assert r2.status_code == 201, r2.text

    r3 = client.get("/api/v1/kb/articles?is_published=true", headers=_auth_headers(tok))
    body = r3.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Welcome"


# ---------------------------------------------------------------------------
# 7. Canned responses round-trip + cross-tenant denial
# ---------------------------------------------------------------------------


def test_canned_response_round_trip(client: TestClient, setup_session: Session, agency_a, agency_b):
    a, _, tok_a = agency_a
    b, _, tok_b = agency_b
    ws_a = _make_workspace(setup_session, a, "WS A")
    ws_b = _make_workspace(setup_session, b, "WS B")

    # Create in A
    r = client.post(
        "/api/v1/canned-responses",
        headers=_auth_headers(tok_a),
        json={"workspace_id": str(ws_a.id), "shortcut": "hi", "content": "Hello!"},
    )
    assert r.status_code == 201, r.text
    cr_id = r.json()["id"]

    # B cannot see it
    r2 = client.get("/api/v1/canned-responses", headers=_auth_headers(tok_b))
    assert r2.json()["total"] == 0

    # B cannot fetch by id directly
    r3 = client.get(f"/api/v1/canned-responses/{cr_id}", headers=_auth_headers(tok_b))
    # canned-responses has no GET-by-id endpoint — use list-with-search to verify isolation
    # so use search instead
    r4 = client.get("/api/v1/canned-responses?search=hi", headers=_auth_headers(tok_b))
    assert r4.json()["total"] == 0

    # A can search and find it
    r5 = client.get("/api/v1/canned-responses?search=hi", headers=_auth_headers(tok_a))
    assert r5.json()["total"] == 1


def test_canned_response_duplicate_shortcut_409(client: TestClient, setup_session: Session, agency_a):
    a, _, tok = agency_a
    ws = _make_workspace(setup_session, a)
    body = {"workspace_id": str(ws.id), "shortcut": "hello", "content": "Hi there"}
    r = client.post("/api/v1/canned-responses", headers=_auth_headers(tok), json=body)
    assert r.status_code == 201
    r2 = client.post("/api/v1/canned-responses", headers=_auth_headers(tok), json=body)
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# 8. Login reader ACL regression — confirms migration 0007 fix
# ---------------------------------------------------------------------------


def test_login_reader_acl_after_migration_0007(db_engine):
    """After migration 0007, m369_login_reader must have SELECT only on
    ``agencies`` and ``agency_memberships`` — nothing else."""
    import psycopg

    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            """)
            all_tables = [r[0] for r in cur.fetchall()]
            assert "messages" in all_tables, "messages table missing — migration 0006 not applied"
            assert "channels" in all_tables
            assert "kb_articles" in all_tables

            for t in all_tables:
                cur.execute(
                    "SELECT has_table_privilege('m369_login_reader', %s, 'SELECT')",
                    (t,),
                )
                has_select = cur.fetchone()[0]
                if t in {"agencies", "agency_memberships"}:
                    assert has_select, f"m369_login_reader should have SELECT on {t}"
                else:
                    assert not has_select, (
                        f"m369_login_reader still has SELECT on {t} — migration 0007 not applied or reverted"
                    )
                for priv in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                    cur.execute(
                        "SELECT has_table_privilege('m369_login_reader', %s, %s)",
                        (t, priv),
                    )
                    assert not cur.fetchone()[0], (
                        f"m369_login_reader has {priv} on {t} — privilege escalation regression"
                    )
    finally:
        conn.close()


def test_m369_app_has_crud_on_all_tables(db_engine):
    """m369_app must have SELECT/INSERT/UPDATE/DELETE on every tenant-owned table.

    After migration 0011 (Package B), m369_app NO LONGER has CRUD on
    platform-private tables: agency_notes, platform_settings.
    It also has only SELECT on plans (agency portal reads, doesn't write).
    """
    import psycopg

    # Tables where m369_app should NOT have full CRUD after 0011+0012
    PLATFORM_PRIVATE_TABLES = {"agency_notes", "platform_settings"}
    READ_ONLY_TABLES = {"plans"}  # m369_app has SELECT only
    # After migration 0012, m369_app has NO access to SA tables (login uses m369_sa_auth)
    SA_TABLES = {
        "super_admins",
        "super_admin_audit_logs",
        "super_admin_mfa_challenges",
        "super_admin_mfa_recovery_codes",
        "super_admin_used_totp_codes",
    }

    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            """)
            all_tables = [r[0] for r in cur.fetchall()]
            assert len(all_tables) >= 22, f"only {len(all_tables)} tables — migration incomplete"
            for t in all_tables:
                if t in PLATFORM_PRIVATE_TABLES or t in SA_TABLES:
                    # m369_app must have NO privileges on platform-private + SA tables
                    for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                        cur.execute(
                            "SELECT has_table_privilege('m369_app', %s, %s)",
                            (t, priv),
                        )
                        assert not cur.fetchone()[0], (
                            f"m369_app has {priv} on {t} — should be revoked"
                        )
                elif t in READ_ONLY_TABLES:
                    # m369_app has SELECT only on plans
                    cur.execute(
                        "SELECT has_table_privilege('m369_app', %s, 'SELECT')",
                        (t,),
                    )
                    assert cur.fetchone()[0], f"m369_app missing SELECT on {t}"
                    for priv in ("INSERT", "UPDATE", "DELETE"):
                        cur.execute(
                            "SELECT has_table_privilege('m369_app', %s, %s)",
                            (t, priv),
                        )
                        assert not cur.fetchone()[0], (
                            f"m369_app has {priv} on {t} — should be revoked (read-only)"
                        )
                else:
                    # Full CRUD on all other tenant-owned tables
                    for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                        cur.execute(
                            "SELECT has_table_privilege('m369_app', %s, %s)",
                            (t, priv),
                        )
                        assert cur.fetchone()[0], f"m369_app missing {priv} on {t}"
    finally:
        conn.close()
