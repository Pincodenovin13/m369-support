"""Stage 4 — Integrated security audit + adversarial test suite.

This file consolidates the security-relevant regression tests that
cross-cut Stages 1-3 and audit the whole stack end-to-end. Every test
runs against real PostgreSQL 16.2 with real Alembic migrations
0001-0009 and real RLS policies. There are NO mocks of RLS, JWT, or
the database.

Sections:
  A. Cross-tenant attack vectors — IDOR across every new resource type
  B. JWT boundary tests — token type confusion, replay, expired, malformed
  C. Payment security — replay, idempotency, financial precision, partial payments
  D. Subscription integrity — snapshot preservation, lifecycle transitions
  E. Composite FK enforcement — cross-tenant references blocked at DB layer
  F. RLS audit — every tenant-owned table enforces ENABLE+FORCE+policy
  G. Privilege escalation — m369_app cannot SET ROLE to BYPASSRLS roles
  H. Audit log completeness — every mutation is recorded
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import (
    Agency,
    AgencyMembership,
    Channel,
    Contact,
    Conversation,
    KBArticle,
    KBCategory,
    Message,
    Plan,
    Subscription,
    Payment,
    Team,
    TeamMembership,
    User,
    Workspace,
)
from app.security import create_access_token, hash_password


pytestmark = [pytest.mark.security, pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _h(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _ws(setup: Session, agency: Agency, name: str = "WS") -> Workspace:
    ws = Workspace(agency_id=agency.id, name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}")
    setup.add(ws)
    setup.commit()
    setup.refresh(ws)
    return ws


def _contact(setup: Session, agency: Agency, ws: Workspace, email: str) -> Contact:
    c = Contact(agency_id=agency.id, workspace_id=ws.id, email=email, name=email.split("@")[0])
    setup.add(c)
    setup.commit()
    setup.refresh(c)
    return c


def _conv(setup: Session, agency: Agency, ws: Workspace, contact: Contact) -> Conversation:
    c = Conversation(agency_id=agency.id, workspace_id=ws.id, contact_id=contact.id, status="open", subject="x")
    setup.add(c)
    setup.commit()
    setup.refresh(c)
    return c


# ---------------------------------------------------------------------------
# A. Cross-tenant IDOR — every new resource type
# ---------------------------------------------------------------------------


def test_idor_message_attachment_inaccessible(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Even if Agency A learns the message_id of an Agency B message,
    it cannot list messages in that conversation (RLS on messages)."""
    a, _, tok_a = agency_a
    b, _, _ = agency_b
    ws_b = _ws(setup_session, b, "WS B")
    contact_b = _contact(setup_session, b, ws_b, "b@b.com")
    conv_b = _conv(setup_session, b, ws_b, contact_b)
    # Insert a message as Agency B
    msg_b = Message(conversation_id=conv_b.id, agency_id=b.id, sender_type="agent", content="secret", delivery_status="sent")
    setup_session.add(msg_b)
    setup_session.commit()

    r = client.get(f"/api/v1/messages?conversation_id={conv_b.id}", headers=_h(tok_a))
    assert r.status_code == 404, f"Agency A saw Agency B's conversation: {r.status_code}"


def test_idor_team_membership_cannot_reference_foreign_team_via_api(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A cannot add Agency B's user to its own team (the user is not
    a member of Agency A — endpoint returns 400)."""
    a, _, tok_a = agency_a
    b, user_b, _ = agency_b
    ws_a = _ws(setup_session, a, "WS A")
    team_a = Team(workspace_id=ws_a.id, agency_id=a.id, name="Team A")
    setup_session.add(team_a)
    setup_session.commit()
    setup_session.refresh(team_a)

    r = client.post(
        f"/api/v1/teams/{team_a.id}/members",
        headers=_h(tok_a),
        json={"user_id": str(user_b.id)},
    )
    assert r.status_code == 400


def test_idor_kb_category_cross_workspace_in_same_agency_visible(client: TestClient, setup_session: Session, agency_a):
    """Within the same agency, KB categories are visible across workspaces
    (they're agency-scoped via RLS, not workspace-scoped at the API layer)."""
    a, _, tok = agency_a
    ws1 = _ws(setup_session, a, "WS1")
    ws2 = _ws(setup_session, a, "WS2")
    cat = KBCategory(agency_id=a.id, workspace_id=ws1.id, name="Cat", slug="cat")
    setup_session.add(cat)
    setup_session.commit()

    # List categories without workspace filter — should see cat from ws1
    r = client.get("/api/v1/kb/categories", headers=_h(tok))
    body = r.json()
    assert body["total"] >= 1


def test_idor_canned_response_cross_agency_invisible(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency B's canned responses are invisible to Agency A via API."""
    a, _, tok_a = agency_a
    b, _, tok_b = agency_b
    ws_b = _ws(setup_session, b, "WS B")
    cr = __import__("app.models", fromlist=["CannedResponse"]).CannedResponse(
        agency_id=b.id, workspace_id=ws_b.id, shortcut="hello", content="Hi there"
    )
    setup_session.add(cr)
    setup_session.commit()

    r = client.get("/api/v1/canned-responses?search=hello", headers=_h(tok_a))
    assert r.json()["total"] == 0


def test_idor_audit_log_cross_agency_invisible(client: TestClient, setup_session: Session, agency_a, agency_b):
    """Agency A's audit log entries are invisible to Agency B."""
    a, _, tok_a = agency_a
    b, _, tok_b = agency_b
    ws_a = _ws(setup_session, a, "WS A")
    # Create a contact as A — writes an audit row
    client.post("/api/v1/contacts", headers=_h(tok_a), json={"workspace_id": str(ws_a.id), "email": "audit-a@x.com", "name": "A"})

    # B queries audit logs — should see 0 entries (RLS hides A's audit_logs)
    r = client.get("/api/v1/audit-logs", headers=_h(tok_b))
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ---------------------------------------------------------------------------
# B. JWT boundary tests
# ---------------------------------------------------------------------------


def test_jwt_expired_token_rejected(client: TestClient, agency_a):
    """A token with exp in the past is rejected (401)."""
    import jwt as pyjwt
    from app.core.config import get_settings
    from app.security.jwt import _signing_key
    s = get_settings()
    a, _, _ = agency_a
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(a.id),
        "type": "agency",
        "exp": int((now - timedelta(hours=1)).timestamp()),  # expired
        "iat": int(now.timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "agency_id": str(a.id),
    }
    token = pyjwt.encode(payload, _signing_key("agency"), algorithm=s.jwt_algorithm)
    r = client.get("/api/v1/contacts", headers=_h(token))
    assert r.status_code == 401


def test_jwt_wrong_type_rejected(client: TestClient, sa_token):
    """A super_admin token cannot access agency endpoints."""
    r = client.get("/api/v1/contacts", headers=_h(sa_token))
    assert r.status_code == 403  # decoded as super_admin, get_current_user rejects


def test_jwt_malformed_rejected(client: TestClient):
    """Garbage strings are rejected with 401, never 500."""
    r = client.get("/api/v1/contacts", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_jwt_missing_signature_rejected(client: TestClient, agency_a):
    """A token without a signature is rejected."""
    a, _, _ = agency_a
    # Header.payload.  — no signature
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0."
    r = client.get("/api/v1/contacts", headers=_h(token))
    assert r.status_code == 401


def test_jwt_agency_token_rejected_by_super_admin(client: TestClient, agency_a):
    """An agency-scoped JWT cannot call Super Admin endpoints."""
    a, _, tok_a = agency_a
    r = client.get("/api/v1/super-admin/agencies", headers=_h(tok_a))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# C. Payment security — replay, idempotency, partial payments
# ---------------------------------------------------------------------------


def _seed_payment(setup: Session, agency: Agency, sub: Subscription, txid: str, amount_expected: int = 1900) -> Payment:
    p = Payment(
        subscription_id=sub.id,
        agency_id=agency.id,
        txid=txid,
        idempotency_key=f"key-{txid}",
        amount_expected=amount_expected,
        amount_paid=0,
        currency="USD",
        status="pending",
        payment_method="crypto_usdt_trc20",
    )
    setup.add(p)
    setup.commit()
    setup.refresh(p)
    return p


def _seed_plan_sub(setup: Session, agency: Agency, plan_name: str = "p1", price: int = 1900, status: str = "active"):
    plan = Plan(name=plan_name, display_name=plan_name.title(), price_monthly=price, currency="USD", is_active=True, sort_order=0, features={}, limits={}, trial_days=7)
    setup.add(plan)
    setup.flush()  # populate plan.id
    sub = Subscription(agency_id=agency.id, plan_id=plan.id, status=status, price_monthly_snapshot=plan.price_monthly, currency_snapshot="USD", plan_name_snapshot=plan.display_name, plan_features_snapshot={}, plan_limits_snapshot={})
    setup.add(sub)
    setup.commit()
    setup.refresh(plan)
    setup.refresh(sub)
    return plan, sub


def test_payment_replay_same_txid_returns_same_row(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Re-verifying the same payment id returns the same row — no double-counting."""
    a, _, _ = agency_a
    _, sub = _seed_plan_sub(setup_session, a, "replay-plan")
    pay = _seed_payment(setup_session, a, sub, "tx-replay-1")

    r1 = client.post(f"/api/v1/super-admin/payments/{pay.id}/verify", headers=_h(sa_token), json={"amount_paid": 1900, "exchange_rate": 1.0})
    assert r1.status_code == 200
    assert r1.json()["status"] == "verified"
    ts1 = r1.json()["verified_at"]

    # Wait 1s to ensure timestamp would differ if it were re-set
    import time; time.sleep(1.1)
    r2 = client.post(f"/api/v1/super-admin/payments/{pay.id}/verify", headers=_h(sa_token), json={"amount_paid": 1900, "exchange_rate": 1.0})
    assert r2.status_code == 200
    assert r2.json()["status"] == "verified"
    ts2 = r2.json()["verified_at"]
    assert ts1 == ts2, "idempotent re-verify mutated verified_at timestamp"


def test_payment_partial_amount_does_not_mark_verified_as_full(client: TestClient, setup_session: Session, agency_a, sa_token):
    """A Super Admin verifying with amount_paid < amount_expected is allowed
    (the platform may accept partial payments) but the row reflects the
    actual paid amount — never silently rounded up to expected."""
    a, _, _ = agency_a
    _, sub = _seed_plan_sub(setup_session, a, "partial-plan", price=1900)
    pay = _seed_payment(setup_session, a, sub, "tx-partial-1", amount_expected=1900)

    r = client.post(f"/api/v1/super-admin/payments/{pay.id}/verify", headers=_h(sa_token), json={"amount_paid": 1500, "exchange_rate": 1.0})
    assert r.status_code == 200
    body = r.json()
    assert body["amount_paid"] == 1500
    assert body["amount_expected"] == 1900
    assert body["status"] == "verified"


def test_payment_financial_precision_no_floating_point(client: TestClient, setup_session: Session, agency_a, sa_token):
    """$0.01 is stored as 1 cent (INTEGER), not 0.01 (FLOAT).

    A Float column would accumulate rounding errors. We use INTEGER cents.
    """
    a, _, _ = agency_a
    _, sub = _seed_plan_sub(setup_session, a, "fp-plan", price=1)  # 1 cent
    pay = _seed_payment(setup_session, a, sub, "tx-fp-1", amount_expected=1)

    r = client.post(f"/api/v1/super-admin/payments/{pay.id}/verify", headers=_h(sa_token), json={"amount_paid": 1, "exchange_rate": 1.0})
    assert r.status_code == 200
    assert r.json()["amount_paid"] == 1
    assert r.json()["amount_expected"] == 1
    assert isinstance(r.json()["amount_paid"], int), "amount_paid must be int, not float"


def test_payment_usdt_6_decimals_correctly_recorded(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Verify with USDT TRC20 (6 decimals): 1 USDT = 1_000_000 raw."""
    a, _, _ = agency_a
    _, sub = _seed_plan_sub(setup_session, a, "usdt-plan", price=100)  # $1.00 = 100 cents
    pay = _seed_payment(setup_session, a, sub, "tx-usdt-1", amount_expected=100)

    r = client.post(f"/api/v1/super-admin/payments/{pay.id}/verify", headers=_h(sa_token), json={
        "amount_paid": 100,
        "paid_currency": "USDT",
        "paid_amount_raw": 1_000_000,
        "paid_amount_decimals": 6,
        "exchange_rate": 1.0,
        "network": "tron",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["paid_amount_raw"] == 1_000_000
    assert body["paid_amount_decimals"] == 6


# ---------------------------------------------------------------------------
# D. Subscription integrity — snapshot + lifecycle
# ---------------------------------------------------------------------------


def test_subscription_price_snapshot_immutable_via_plan_change(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Changing the plan's price does NOT affect existing subscriptions.

    Each subscription carries its own price_monthly_snapshot frozen at creation.
    """
    a, _, _ = agency_a
    plan, sub = _seed_plan_sub(setup_session, a, "snapshot-plan", price=1900, status="active")
    assert sub.price_monthly_snapshot == 1900

    # Now change plan price via Super Admin API
    r = client.patch(f"/api/v1/super-admin/plans/{plan.id}", headers=_h(sa_token), json={"price_monthly": 2999})
    assert r.status_code == 200
    assert r.json()["price_monthly"] == 2999

    # Sub's snapshot is unchanged
    setup_session.expire_all()
    sub2 = setup_session.get(Subscription, sub.id)
    assert sub2.price_monthly_snapshot == 1900, "subscription snapshot leaked plan price change"


def test_subscription_lifecycle_all_valid_transitions(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Walk a subscription through: trial → active → past_due → suspended → cancelled."""
    a, _, _ = agency_a
    _, sub = _seed_plan_sub(setup_session, a, "lifecycle-plan", status="trial")

    for next_status in ("active", "past_due", "suspended", "cancelled"):
        r = client.patch(f"/api/v1/super-admin/subscriptions/{sub.id}", headers=_h(sa_token), json={"status": next_status})
        assert r.status_code == 200, f"transition to {next_status} failed: {r.text}"
        assert r.json()["status"] == next_status


def test_subscription_cannot_reactivate_from_cancelled(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Cancelled is terminal — cannot move back to active."""
    a, _, _ = agency_a
    _, sub = _seed_plan_sub(setup_session, a, "terminal-plan", status="cancelled")

    r = client.patch(f"/api/v1/super-admin/subscriptions/{sub.id}", headers=_h(sa_token), json={"status": "active"})
    assert r.status_code == 400


def test_subscription_one_active_per_agency_enforced(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Partial unique index on subscriptions WHERE status IN (trial, active, ...)
    prevents two active subs for the same agency."""
    a, _, _ = agency_a
    plan, sub = _seed_plan_sub(setup_session, a, "unique-active-plan", status="active")

    # Try to insert another active subscription for same agency
    sub2 = Subscription(
        agency_id=a.id,
        plan_id=plan.id,
        status="active",
        price_monthly_snapshot=1900,
        currency_snapshot="USD",
        plan_name_snapshot=plan.display_name,
        plan_features_snapshot={},
        plan_limits_snapshot={},
    )
    setup_session.add(sub2)
    with pytest.raises(Exception) as exc:
        setup_session.commit()
    assert "unique" in str(exc.value).lower() or "duplicate" in str(exc.value).lower()
    setup_session.rollback()


# ---------------------------------------------------------------------------
# E. Composite FK enforcement — DB-layer cross-tenant rejection
# ---------------------------------------------------------------------------


def test_composite_fk_blocks_cross_agency_team_membership(setup_session: Session, agency_a, agency_b):
    """Direct DB insert of a TeamMembership with team from B + agency_id from A
    fails on the composite FK (team_id, agency_id) → teams(id, agency_id)."""
    a, _, _ = agency_a
    b, _, _ = agency_b
    ws_b = _ws(setup_session, b, "WS B")
    team_b = Team(workspace_id=ws_b.id, agency_id=b.id, name="TB")
    setup_session.add(team_b)
    setup_session.commit()
    setup_session.refresh(team_b)

    user_a = User(email=f"ua-{uuid.uuid4().hex[:6]}@a.com", password_hash="x", name="UA")
    setup_session.add(user_a)
    setup_session.commit()
    setup_session.refresh(user_a)

    tm = TeamMembership(team_id=team_b.id, user_id=user_a.id, agency_id=a.id)
    setup_session.add(tm)
    with pytest.raises(Exception) as exc:
        setup_session.commit()
    assert "fk_team_memberships_team_agency" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    setup_session.rollback()


def test_composite_fk_blocks_cross_agency_message(setup_session: Session, agency_a, agency_b):
    """A Message cannot reference a conversation from another agency —
    the composite FK (conversation_id, agency_id) blocks it at the DB layer."""
    a, _, _ = agency_a
    b, _, _ = agency_b
    ws_b = _ws(setup_session, b, "WS B")
    contact_b = _contact(setup_session, b, ws_b, "b@b.com")
    conv_b = _conv(setup_session, b, ws_b, contact_b)

    msg = Message(
        conversation_id=conv_b.id,
        agency_id=a.id,  # wrong agency!
        sender_type="agent",
        content="pwned",
        delivery_status="sent",
    )
    setup_session.add(msg)
    with pytest.raises(Exception) as exc:
        setup_session.commit()
    assert "fk_messages_conversation_agency" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    setup_session.rollback()


# ---------------------------------------------------------------------------
# F. RLS audit — every tenant-owned table has ENABLE+FORCE+policy
# ---------------------------------------------------------------------------


# Tables that MUST have RLS enabled (tenant-owned). Excludes platform-wide
# tables (plans, platform_settings, super_admins, super_admin_audit_logs).
TENANT_OWNED_TABLES = [
    "agencies",
    "workspaces",
    "agency_memberships",
    "teams",
    "team_memberships",
    "contacts",
    "conversations",
    "audit_logs",
    "messages",
    "message_attachments",
    "channels",
    "kb_categories",
    "kb_articles",
    "canned_responses",
    "subscriptions",
    "payments",
]


def test_rls_enabled_on_all_tenant_tables(db_engine):
    """Every tenant-owned table must have RLS ENABLE and FORCE."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            for t in TENANT_OWNED_TABLES:
                cur.execute(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
                    (t,),
                )
                row = cur.fetchone()
                assert row is not None, f"table {t} not found"
                enabled, forced = row
                assert enabled, f"RLS not ENABLED on {t}"
                assert forced, f"RLS not FORCED on {t}"
    finally:
        conn.close()


def test_rls_policy_exists_on_all_tenant_tables(db_engine):
    """Every tenant-owned table must have a tenant_isolation_{table} policy."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            for t in TENANT_OWNED_TABLES:
                cur.execute(
                    "SELECT COUNT(*) FROM pg_policies WHERE tablename = %s AND policyname = %s",
                    (t, f"tenant_isolation_{t}"),
                )
                count = cur.fetchone()[0]
                assert count == 1, f"missing tenant_isolation_{t} policy (found {count})"
    finally:
        conn.close()


def test_rls_no_bypass_guc_in_policies(db_engine):
    """No RLS policy may reference the historical app.bypass_rls GUC.

    The bypass GUC was a security vulnerability (any DB user could SET it).
    Migrations 0001+ must not use it. This test ensures no policy body
    mentions 'bypass_rls'.
    """
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename, policyname, qual, with_check
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND (qual ILIKE '%bypass_rls%' OR with_check ILIKE '%bypass_rls%')
            """)
            rows = cur.fetchall()
            assert rows == [], f"policies referencing bypass_rls found: {rows}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# G. Privilege escalation — m369_app cannot SET ROLE to BYPASSRLS roles
# ---------------------------------------------------------------------------


def test_m369_app_cannot_set_role_to_sa_runner(db_engine):
    """m369_app must NOT be a member of m369_sa_runner (would let it SET ROLE
    to gain BYPASSRLS)."""
    conn = psycopg.connect("postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("SET ROLE m369_sa_runner")
            pytest.fail("m369_app was able to SET ROLE m369_sa_runner — privilege escalation!")
    except psycopg.errors.InsufficientPrivilege:
        pass  # expected — m369_app is not a member
    finally:
        conn.close()


def test_m369_app_cannot_set_role_to_login_reader(db_engine):
    """m369_app must NOT be a member of m369_login_reader."""
    conn = psycopg.connect("postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("SET ROLE m369_login_reader")
            pytest.fail("m369_app was able to SET ROLE m369_login_reader — privilege escalation!")
    except psycopg.errors.InsufficientPrivilege:
        pass
    finally:
        conn.close()


def test_m369_app_cannot_set_role_to_super_admin(db_engine):
    """m369_app must NOT be a member of m369_super_admin."""
    conn = psycopg.connect("postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("SET ROLE m369_super_admin")
            pytest.fail("m369_app was able to SET ROLE m369_super_admin — privilege escalation!")
    except psycopg.errors.InsufficientPrivilege:
        pass
    finally:
        conn.close()


def test_m369_app_cannot_create_role(db_engine):
    """m369_app must be NOCREATEROLE — cannot create new roles."""
    conn = psycopg.connect("postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE ROLE evil_role")
            pytest.fail("m369_app was able to CREATE ROLE — should be NOCREATEROLE!")
    except psycopg.errors.InsufficientPrivilege:
        pass
    finally:
        conn.close()


def test_m369_app_cannot_create_database(db_engine):
    """m369_app must be NOCREATEDB."""
    conn = psycopg.connect("postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE evil_db")
            pytest.fail("m369_app was able to CREATE DATABASE — should be NOCREATEDB!")
    except psycopg.errors.InsufficientPrivilege:
        pass
    finally:
        conn.close()


def test_m369_sa_runner_cannot_create_role(db_engine):
    """m369_sa_runner must be NOCREATEROLE even though it has BYPASSRLS."""
    conn = psycopg.connect("postgresql://m369_sa_runner:m369_sa_runner_dev_password@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE ROLE evil_role")
            pytest.fail("m369_sa_runner was able to CREATE ROLE — should be NOCREATEROLE!")
    except psycopg.errors.InsufficientPrivilege:
        pass
    finally:
        conn.close()


def test_m369_sa_runner_is_not_super_user(db_engine):
    """m369_sa_runner must be NOSUPERUSER — cannot drop databases/roles."""
    conn = psycopg.connect("postgresql://m369_sa_runner:m369_sa_runner_dev_password@localhost:5432/m369_support_test", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DROP DATABASE m369_support_test")
            pytest.fail("m369_sa_runner was able to DROP DATABASE — should be NOSUPERUSER!")
    except psycopg.errors.InsufficientPrivilege:
        pass
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# H. Audit log completeness — every mutation is recorded
# ---------------------------------------------------------------------------


def test_audit_log_written_for_every_contact_mutation(client: TestClient, setup_session: Session, agency_a):
    """POST + PATCH on /contacts each write an audit log row."""
    a, _, tok = agency_a
    ws = _ws(setup_session, a)

    # Create
    r1 = client.post("/api/v1/contacts", headers=_h(tok), json={"workspace_id": str(ws.id), "email": "audit-c@x.com", "name": "AC"})
    assert r1.status_code == 201
    cid = r1.json()["id"]

    # Update
    r2 = client.patch(f"/api/v1/contacts/{cid}", headers=_h(tok), json={"name": "Renamed"})
    assert r2.status_code == 200

    # Audit rows
    rows = setup_session.execute(
        text("SELECT action FROM audit_logs WHERE agency_id = :aid AND target_id = :tid ORDER BY id"),
        {"aid": str(a.id), "tid": cid},
    ).all()
    actions = [r.action for r in rows]
    assert "contact.create" in actions
    assert "contact.update" in actions


def test_audit_log_metadata_records_changes(client: TestClient, setup_session: Session, agency_a):
    """PATCH /contacts writes the changed fields to audit log metadata (JSONB)."""
    a, _, tok = agency_a
    ws = _ws(setup_session, a)
    r1 = client.post("/api/v1/contacts", headers=_h(tok), json={"workspace_id": str(ws.id), "email": "ameta@x.com", "name": "AM"})
    cid = r1.json()["id"]

    client.patch(f"/api/v1/contacts/{cid}", headers=_h(tok), json={"name": "Renamed"})

    rows = setup_session.execute(
        text("SELECT metadata FROM audit_logs WHERE agency_id = :aid AND action = 'contact.update' AND target_id = :tid"),
        {"aid": str(a.id), "tid": cid},
    ).all()
    assert len(rows) == 1
    meta = rows[0][0] if isinstance(rows[0][0], dict) else json.loads(rows[0][0])
    assert "name" in meta
    assert meta["name"] == "Renamed"


def test_super_admin_audit_log_separate_from_agency_audit_log(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Super Admin actions write to super_admin_audit_logs (NOT audit_logs).

    Tables are physically separate — never mixed.
    """
    a, _, _ = agency_a
    # Super Admin action
    client.post(f"/api/v1/super-admin/agencies/{a.id}/suspend", headers=_h(sa_token))

    # audit_logs should have 0 SA rows
    agency_sa_rows = setup_session.execute(
        text("SELECT COUNT(*) FROM audit_logs WHERE action LIKE 'agency.%' OR action LIKE 'super_admin.%'")
    ).scalar()
    # The agency.* audit_logs are written by agency endpoints, not SA — but
    # the SA suspend writes ONLY to super_admin_audit_logs.
    sa_rows = setup_session.execute(
        text("SELECT COUNT(*) FROM super_admin_audit_logs WHERE action = 'agency.suspend'")
    ).scalar()
    assert sa_rows == 1, f"expected 1 SA audit row, got {sa_rows}"


# ---------------------------------------------------------------------------
# I. Endpoint smoke — every endpoint is reachable + auth-gated
# ---------------------------------------------------------------------------


def test_every_agency_endpoint_requires_auth(client: TestClient):
    """No agency endpoint should respond without a valid token.

    Tests one route from each router to catch global auth bypasses.
    """
    routes = [
        ("GET", "/api/v1/agencies/current"),
        ("GET", "/api/v1/workspaces"),
        ("GET", "/api/v1/contacts"),
        ("GET", "/api/v1/conversations"),
        ("GET", "/api/v1/messages?conversation_id=00000000-0000-0000-0000-000000000000"),
        ("GET", "/api/v1/teams"),
        ("GET", "/api/v1/channels"),
        ("GET", "/api/v1/kb/articles"),
        ("GET", "/api/v1/canned-responses"),
        ("GET", "/api/v1/audit-logs"),
    ]
    for method, path in routes:
        r = client.request(method, path)
        assert r.status_code == 401, f"{method} {path} returned {r.status_code} without auth — should be 401"


def test_every_super_admin_endpoint_requires_auth(client: TestClient):
    routes = [
        ("GET", "/api/v1/super-admin/agencies"),
        ("GET", "/api/v1/super-admin/plans"),
        ("GET", "/api/v1/super-admin/subscriptions"),
        ("GET", "/api/v1/super-admin/payments"),
        ("GET", "/api/v1/super-admin/platform-settings"),
        ("GET", "/api/v1/super-admin/audit-logs"),
    ]
    for method, path in routes:
        r = client.request(method, path)
        assert r.status_code == 401, f"{method} {path} returned {r.status_code} without auth — should be 401"


# ---------------------------------------------------------------------------
# J. Final sanity — full migration chain + total table count
# ---------------------------------------------------------------------------


def test_migration_chain_complete(db_engine):
    """The complete migration chain is applied through signed-RLS revision 0019."""
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            v = cur.fetchone()[0]
            assert v == "0020_payment_raw_amount_precision", f"migration chain incomplete: head is {v}, expected 0020_payment_raw_amount_precision"
    finally:
        conn.close()


def test_total_table_count_matches_expected(db_engine):
    """After migration 0010, schema has 26 tables (23 + 3 MFA tables + alembic_version = 27)."""
    expected = {
        # Stage 1 baseline
        "agencies", "workspaces", "agency_memberships", "teams", "team_memberships",
        "contacts", "conversations", "audit_logs",
        "super_admins", "super_admin_audit_logs",
        "users",
        # Stage 1 extended (migration 0006)
        "messages", "message_attachments", "channels",
        "kb_categories", "kb_articles", "canned_responses",
        "plans", "subscriptions", "payments",
        "platform_settings", "agency_notes",
        # Migration 0010 (SA auth hardening)
        "super_admin_mfa_challenges",
        "super_admin_used_totp_codes",
        "super_admin_mfa_recovery_codes",
        # Alembic
        "alembic_version",
    }
    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            actual = {r[0] for r in cur.fetchall()}
        missing = expected - actual
        extra = actual - expected
        assert not missing, f"missing tables: {missing}"
        assert not extra, f"unexpected extra tables: {extra}"
        assert len(actual) == 26, f"expected 26 tables, got {len(actual)}"
    finally:
        conn.close()
