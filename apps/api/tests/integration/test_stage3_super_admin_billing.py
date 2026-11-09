"""Stage 3 — Super Admin endpoints + billing/subscription/payment APIs.

Tests:
  1. Super Admin token separation — agency token cannot call SA endpoints.
  2. Agency management — list/get/update/suspend/activate, RBAC enforced.
  3. Member management — list, role change.
  4. Plans CRUD — create/update/list.
  5. Subscriptions — list/get + lifecycle transitions enforced.
  6. Payments — list/get + idempotent verification + reject terminal state.
  7. Platform settings — upsert/delete.
  8. Agency notes — create/list/delete.
  9. Super Admin audit log — every mutation writes a row.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Numeric, select, text
from sqlalchemy.orm import Session

from app.models import (
    Agency,
    AgencyMembership,
    AgencyNote,
    Payment,
    Plan,
    PlatformSetting,
    Subscription,
    SuperAdmin,
    SuperAdminAuditLog,
    User,
)
from app.security import create_access_token, hash_password


pytestmark = pytest.mark.security


def _sa_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_plan(setup: Session, name: str = "test-plan", price_cents: int = 1900) -> Plan:
    p = Plan(
        name=name,
        display_name=name.title(),
        price_monthly=price_cents,
        currency="USD",
        is_active=True,
        sort_order=0,
        features={"channels": ["widget"]},
        limits={"max_seats": 3},
        trial_days=7,
    )
    setup.add(p)
    setup.commit()
    setup.refresh(p)
    return p


def _make_subscription(setup: Session, agency: Agency, plan: Plan, status: str = "trial") -> Subscription:
    s = Subscription(
        agency_id=agency.id,
        plan_id=plan.id,
        status=status,
        price_monthly_snapshot=plan.price_monthly,
        currency_snapshot=plan.currency,
        plan_name_snapshot=plan.display_name,
        plan_features_snapshot=plan.features,
        plan_limits_snapshot=plan.limits,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    setup.add(s)
    setup.commit()
    setup.refresh(s)
    return s


def _make_payment(setup: Session, sub: Subscription, agency: Agency, txid: str, amount_cents: int = 1900) -> Payment:
    p = Payment(
        subscription_id=sub.id,
        agency_id=agency.id,
        txid=txid,
        idempotency_key=f"idem-{txid}",
        amount_expected=amount_cents,
        amount_paid=0,
        currency="USD",
        status="pending",
        payment_method="crypto_usdt_trc20",
    )
    setup.add(p)
    setup.commit()
    setup.refresh(p)
    return p


# ---------------------------------------------------------------------------
# 1. Token separation — agency token cannot call Super Admin endpoints
# ---------------------------------------------------------------------------


def test_agency_token_cannot_call_super_admin(client: TestClient, agency_a, sa_token):
    """An agency-scoped JWT must be rejected by every Super Admin endpoint."""
    a, _, tok_a = agency_a
    # Agency token tries to list all agencies via Super Admin
    r = client.get("/api/v1/super-admin/agencies", headers=_sa_headers(tok_a))
    assert r.status_code == 401, f"agency token accepted by SA: {r.status_code}: {r.text}"


def test_super_admin_token_cannot_call_agency_endpoints(client: TestClient, agency_a, sa_token):
    """A Super Admin JWT must be rejected by agency-scoped endpoints."""
    r = client.get("/api/v1/contacts", headers=_sa_headers(sa_token))
    # 403 because the super_admin token is decoded by both decoders, but
    # get_current_user rejects it explicitly.
    assert r.status_code == 403, f"SA token accepted by agency endpoint: {r.status_code}"


def test_unauthenticated_super_admin_rejected(client: TestClient):
    r = client.get("/api/v1/super-admin/agencies")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 2. Agency management
# ---------------------------------------------------------------------------


def test_sa_list_agencies_returns_all(client: TestClient, setup_session: Session, agency_a, agency_b, sa_token):
    """Super Admin sees ALL agencies (BYPASSRLS via m369_sa_runner)."""
    r = client.get("/api/v1/super-admin/agencies", headers=_sa_headers(sa_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 2
    names = {a["name"] for a in body["items"]}
    assert {"Agency A", "Agency B"}.issubset(names)


def test_sa_get_agency_detail(client: TestClient, agency_a, sa_token):
    a, _, _ = agency_a
    r = client.get(f"/api/v1/super-admin/agencies/{a.id}", headers=_sa_headers(sa_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(a.id)
    assert body["name"] == "Agency A"


def test_sa_update_agency_name(client: TestClient, agency_a, sa_token):
    a, _, _ = agency_a
    r = client.patch(
        f"/api/v1/super-admin/agencies/{a.id}",
        headers=_sa_headers(sa_token),
        json={"name": "Renamed Agency"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Renamed Agency"


def test_sa_suspend_agency_idempotent(client: TestClient, setup_session: Session, agency_a, sa_token):
    a, _, _ = agency_a
    r1 = client.post(f"/api/v1/super-admin/agencies/{a.id}/suspend", headers=_sa_headers(sa_token))
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_active"] is False
    # Second suspend is idempotent
    r2 = client.post(f"/api/v1/super-admin/agencies/{a.id}/suspend", headers=_sa_headers(sa_token))
    assert r2.status_code == 200
    assert r2.json()["is_active"] is False
    # Audit log records the suspend
    rows = setup_session.execute(
        text("SELECT action FROM super_admin_audit_logs WHERE action = 'agency.suspend'")
    ).all()
    assert len(rows) >= 1


def test_sa_activate_agency(client: TestClient, agency_a, sa_token):
    a, _, _ = agency_a
    # Suspend first
    client.post(f"/api/v1/super-admin/agencies/{a.id}/suspend", headers=_sa_headers(sa_token))
    # Then activate
    r = client.post(f"/api/v1/super-admin/agencies/{a.id}/activate", headers=_sa_headers(sa_token))
    assert r.status_code == 200
    assert r.json()["is_active"] is True


def test_sa_agency_404_for_unknown_id(client: TestClient, sa_token):
    fake = uuid.uuid4()
    r = client.get(f"/api/v1/super-admin/agencies/{fake}", headers=_sa_headers(sa_token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 3. Member management
# ---------------------------------------------------------------------------


def test_sa_list_agency_members(client: TestClient, setup_session: Session, agency_a, sa_token):
    a, _, _ = agency_a
    # Add another member with 'agent' role
    u = User(email="agent@agency-a.com", password_hash=hash_password("x"), name="Agent")
    m = AgencyMembership(user=u, agency=a, role="agent")
    setup_session.add_all([u, m])
    setup_session.commit()

    r = client.get(f"/api/v1/super-admin/agencies/{a.id}/members", headers=_sa_headers(sa_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 2
    roles = {m["role"] for m in body}
    assert roles == {"owner", "agent"}


def test_sa_change_member_role(client: TestClient, setup_session: Session, agency_a, sa_token):
    a, owner, _ = agency_a
    r = client.patch(
        f"/api/v1/super-admin/agencies/{a.id}/members/{owner.id}",
        headers=_sa_headers(sa_token),
        json={"role": "admin"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"


# ---------------------------------------------------------------------------
# 4. Plans CRUD
# ---------------------------------------------------------------------------


def test_sa_create_plan(client: TestClient, sa_token):
    r = client.post(
        "/api/v1/super-admin/plans",
        headers=_sa_headers(sa_token),
        json={
            "name": "test-plan-create",
            "display_name": "Test Plan",
            "price_monthly": 2999,
            "currency": "USD",
            "is_active": True,
            "sort_order": 10,
            "features": {"channels": ["widget"]},
            "limits": {"max_seats": 5},
            "trial_days": 14,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "test-plan-create"
    assert body["price_monthly"] == 2999
    assert body["trial_days"] == 14


def test_sa_create_plan_duplicate_409(client: TestClient, sa_token):
    body = {"name": "test-dup-plan", "display_name": "Dup", "price_monthly": 100}
    r1 = client.post("/api/v1/super-admin/plans", headers=_sa_headers(sa_token), json=body)
    assert r1.status_code == 201
    r2 = client.post("/api/v1/super-admin/plans", headers=_sa_headers(sa_token), json=body)
    assert r2.status_code == 409


def test_sa_list_plans_includes_seeded(client: TestClient, sa_token):
    """Migration 0006 seeded 4 plans: starter, growth, pro, vip."""
    r = client.get("/api/v1/super-admin/plans", headers=_sa_headers(sa_token))
    assert r.status_code == 200, r.text
    names = {p["name"] for p in r.json()["items"]}
    assert {"starter", "growth", "pro", "vip"}.issubset(names)


def test_sa_update_plan_price(client: TestClient, setup_session: Session, sa_token):
    plan = _make_plan(setup_session, name="update-test-plan", price_cents=1000)
    r = client.patch(
        f"/api/v1/super-admin/plans/{plan.id}",
        headers=_sa_headers(sa_token),
        json={"price_monthly": 1500, "display_name": "Updated"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["price_monthly"] == 1500
    assert r.json()["display_name"] == "Updated"


# ---------------------------------------------------------------------------
# 5. Subscriptions + lifecycle transitions
# ---------------------------------------------------------------------------


def test_sa_list_subscriptions(client: TestClient, setup_session: Session, agency_a, sa_token):
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="sub-test-plan")
    _make_subscription(setup_session, a, plan, status="trial")

    r = client.get("/api/v1/super-admin/subscriptions", headers=_sa_headers(sa_token))
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1


def test_sa_subscription_transition_trial_to_active(client: TestClient, setup_session: Session, agency_a, sa_token):
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="trans-test-plan")
    sub = _make_subscription(setup_session, a, plan, status="trial")

    r = client.patch(
        f"/api/v1/super-admin/subscriptions/{sub.id}",
        headers=_sa_headers(sa_token),
        json={"status": "active", "current_period_ends_at": "2026-12-31T23:59:59Z"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"


def test_sa_subscription_rejects_invalid_transition(client: TestClient, setup_session: Session, agency_a, sa_token):
    """cancelled → active is NOT allowed (cancelled is terminal)."""
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="invalid-trans-plan")
    sub = _make_subscription(setup_session, a, plan, status="cancelled")

    r = client.patch(
        f"/api/v1/super-admin/subscriptions/{sub.id}",
        headers=_sa_headers(sa_token),
        json={"status": "active"},
    )
    assert r.status_code == 400, f"expected 400 for invalid transition, got {r.status_code}: {r.text}"


def test_sa_subscription_price_snapshot_preserved(client: TestClient, setup_session: Session, agency_a, sa_token):
    """If the plan's price changes after subscription creation, the
    subscription's price_monthly_snapshot must NOT change."""
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="snapshot-test-plan", price_cents=1900)
    sub = _make_subscription(setup_session, a, plan, status="trial")
    # Now change the plan price
    plan.price_monthly = 9999
    setup_session.commit()

    r = client.get(f"/api/v1/super-admin/subscriptions/{sub.id}", headers=_sa_headers(sa_token))
    body = r.json()
    assert body["price_monthly_snapshot"] == 1900, "snapshot leaked plan's new price"


# ---------------------------------------------------------------------------
# 6. Payments — idempotent verify, terminal state, financial precision
# ---------------------------------------------------------------------------


def test_sa_payment_verify_idempotent(client: TestClient, setup_session: Session, agency_a, sa_token, super_admin):
    """Re-verifying an already-verified payment is a no-op."""
    a, _, _ = agency_a
    sa, _ = super_admin
    plan = _make_plan(setup_session, name="pay-test-plan")
    sub = _make_subscription(setup_session, a, plan, status="active")
    pay = _make_payment(setup_session, sub, a, txid="tx-verify-1", amount_cents=1900)

    r1 = client.post(
        f"/api/v1/super-admin/payments/{pay.id}/verify",
        headers=_sa_headers(sa_token),
        json={
            "amount_paid": 1900,
            "paid_currency": "USDT",
            "paid_amount_raw": 1900000000,
            "paid_amount_decimals": 6,
            "exchange_rate": 1.0,
            "network": "tron",
        },
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "verified"
    assert r1.json()["amount_paid"] == 1900
    assert r1.json()["verified_by_super_admin_id"] == str(sa.id)

    # Verify again — should be idempotent
    r2 = client.post(
        f"/api/v1/super-admin/payments/{pay.id}/verify",
        headers=_sa_headers(sa_token),
        json={"amount_paid": 9999},  # different value, but should be ignored
    )
    assert r2.status_code == 200
    assert r2.json()["amount_paid"] == 1900, "idempotent re-verify mutated amount_paid"


def test_sa_payment_verify_rejects_rejected_state(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Cannot verify a payment that is already in 'rejected' state."""
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="reject-test-plan")
    sub = _make_subscription(setup_session, a, plan, status="active")
    pay = _make_payment(setup_session, sub, a, txid="tx-reject-1")
    pay.status = "rejected"
    pay.failure_reason = "insufficient funds"
    setup_session.commit()

    r = client.post(
        f"/api/v1/super-admin/payments/{pay.id}/verify",
        headers=_sa_headers(sa_token),
        json={"amount_paid": 1900},
    )
    assert r.status_code == 409


def test_sa_payment_reject_after_verify_blocked(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Cannot reject a payment that is already verified."""
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="block-reject-plan")
    sub = _make_subscription(setup_session, a, plan, status="active")
    pay = _make_payment(setup_session, sub, a, txid="tx-block-1")
    pay.status = "verified"
    pay.amount_paid = 1900
    setup_session.commit()

    r = client.post(
        f"/api/v1/super-admin/payments/{pay.id}/reject",
        headers=_sa_headers(sa_token),
        json={"failure_reason": "changed my mind"},
    )
    assert r.status_code == 409


def test_sa_payment_txid_unique(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Two payments cannot share the same txid (UNIQUE constraint)."""
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="txid-unique-plan")
    sub = _make_subscription(setup_session, a, plan, status="active")
    _make_payment(setup_session, sub, a, txid="duplicate-txid")

    # Insert second payment with same txid — should fail at DB level
    pay2 = Payment(
        subscription_id=sub.id,
        agency_id=a.id,
        txid="duplicate-txid",
        amount_expected=1900,
        amount_paid=0,
        currency="USD",
        status="pending",
    )
    setup_session.add(pay2)
    with pytest.raises(Exception) as exc:
        setup_session.commit()
    assert "unique" in str(exc.value).lower() or "duplicate" in str(exc.value).lower()
    setup_session.rollback()


def test_sa_payment_financial_precision_integer_cents(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Base-currency amounts are INTEGER cents; raw token units are exact integers.

    Verify that $19.99 is stored as 1999, not 19.99.
    """
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="precision-plan", price_cents=1999)
    sub = _make_subscription(setup_session, a, plan, status="active")
    pay = _make_payment(setup_session, sub, a, txid="tx-precision", amount_cents=1999)

    # Verify with USDT TRC20 (6 decimals): 19.99 USDT = 19990000 raw
    r = client.post(
        f"/api/v1/super-admin/payments/{pay.id}/verify",
        headers=_sa_headers(sa_token),
        json={
            "amount_paid": 1999,
            "paid_currency": "USDT",
            "paid_amount_raw": 19990000,
            "paid_amount_decimals": 6,
            "exchange_rate": 1.0,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["amount_paid"] == 1999  # integer cents
    assert body["paid_amount_raw"] == "19990000"  # exact raw integer serialized as a string
    assert body["paid_amount_decimals"] == 6
    # exchange_rate comes back as float (Numeric) — verify it's stored correctly
    assert body["exchange_rate"] == 1.0



def test_sa_payment_raw_token_amount_preserves_uint256_precision(
    client: TestClient,
    setup_session: Session,
    agency_a,
    sa_token,
):
    """Raw token units must survive values beyond INTEGER and JS safe-number limits."""
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="raw-precision-plan")
    sub = _make_subscription(setup_session, a, plan, status="active")
    pay = _make_payment(setup_session, sub, a, txid="tx-raw-precision")

    raw_amount = (1 << 256) - 1  # maximum uint256 value: 78 decimal digits
    raw_column = Payment.__table__.c.paid_amount_raw.type
    assert isinstance(raw_column, Numeric)
    assert raw_column.precision == 78
    assert raw_column.scale == 0

    response = client.post(
        f"/api/v1/super-admin/payments/{pay.id}/verify",
        headers=_sa_headers(sa_token),
        json={
            "amount_paid": 1900,
            "paid_currency": "USDT",
            "paid_amount_raw": raw_amount,
            "paid_amount_decimals": 18,
            "exchange_rate": 1.0,
            "network": "bsc",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["paid_amount_raw"] == str(raw_amount)

    setup_session.expire_all()
    stored = setup_session.get(Payment, pay.id)
    assert stored is not None
    assert int(stored.paid_amount_raw) == raw_amount



# ---------------------------------------------------------------------------
# 7. Platform settings
# ---------------------------------------------------------------------------


def test_sa_platform_settings_crud(client: TestClient, sa_token):
    # Upsert
    r1 = client.put(
        "/api/v1/super-admin/platform-settings/test_key",
        headers=_sa_headers(sa_token),
        json={"value": "test_value", "value_type": "string", "description": "a test"},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["value"] == "test_value"

    # List
    r2 = client.get("/api/v1/super-admin/platform-settings", headers=_sa_headers(sa_token))
    assert r2.status_code == 200
    keys = {s["key"] for s in r2.json()}
    assert "test_key" in keys

    # Update
    r3 = client.put(
        "/api/v1/super-admin/platform-settings/test_key",
        headers=_sa_headers(sa_token),
        json={"value": "updated_value", "value_type": "string", "description": "updated"},
    )
    assert r3.status_code == 200
    assert r3.json()["value"] == "updated_value"

    # Delete
    r4 = client.delete(
        "/api/v1/super-admin/platform-settings/test_key",
        headers=_sa_headers(sa_token),
    )
    assert r4.status_code == 204


# ---------------------------------------------------------------------------
# 8. Agency notes
# ---------------------------------------------------------------------------


def test_sa_agency_notes_crud(client: TestClient, setup_session: Session, agency_a, sa_token, super_admin):
    a, _, _ = agency_a
    sa, _ = super_admin

    # Create
    r1 = client.post(
        f"/api/v1/super-admin/agencies/{a.id}/notes",
        headers=_sa_headers(sa_token),
        json={"note": "VIP customer — handle with care", "is_pinned": True},
    )
    assert r1.status_code == 201, r1.text
    note_id = r1.json()["id"]
    assert r1.json()["is_pinned"] is True
    assert r1.json()["super_admin_id"] == str(sa.id)

    # List (pinned first)
    r2 = client.get(f"/api/v1/super-admin/agencies/{a.id}/notes", headers=_sa_headers(sa_token))
    assert r2.status_code == 200
    assert len(r2.json()) == 1

    # Delete
    r3 = client.delete(
        f"/api/v1/super-admin/agencies/{a.id}/notes/{note_id}",
        headers=_sa_headers(sa_token),
    )
    assert r3.status_code == 204


def test_sa_agency_notes_invisible_to_agency_users(client: TestClient, setup_session: Session, agency_a, sa_token):
    """Agency notes are stored in agency_notes table — only Super Admin APIs
    can read/write. Agency users have no endpoint to access them.

    Defense-in-depth: even if an agency user got the SA endpoint URL, the
    SA auth dependency would reject their token (test_agency_token_cannot_call_super_admin).
    """
    a, _, tok_a = agency_a
    # Create a note as Super Admin
    client.post(
        f"/api/v1/super-admin/agencies/{a.id}/notes",
        headers=_sa_headers(sa_token),
        json={"note": "internal note"},
    )
    # Agency token cannot list notes via SA endpoint
    r = client.get(f"/api/v1/super-admin/agencies/{a.id}/notes", headers=_sa_headers(tok_a))
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 9. Super Admin audit log
# ---------------------------------------------------------------------------


def test_sa_audit_log_records_agency_suspend(client: TestClient, setup_session: Session, agency_a, sa_token):
    a, _, _ = agency_a
    client.post(f"/api/v1/super-admin/agencies/{a.id}/suspend", headers=_sa_headers(sa_token))

    r = client.get(
        "/api/v1/super-admin/audit-logs?action=agency.suspend",
        headers=_sa_headers(sa_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert all(item["action"] == "agency.suspend" for item in body["items"])


def test_sa_audit_log_records_payment_verify(client: TestClient, setup_session: Session, agency_a, sa_token):
    a, _, _ = agency_a
    plan = _make_plan(setup_session, name="audit-pay-plan")
    sub = _make_subscription(setup_session, a, plan, status="active")
    pay = _make_payment(setup_session, sub, a, txid="tx-audit-1")

    client.post(
        f"/api/v1/super-admin/payments/{pay.id}/verify",
        headers=_sa_headers(sa_token),
        json={"amount_paid": 1900, "exchange_rate": 1.0},
    )

    r = client.get(
        "/api/v1/super-admin/audit-logs?action=payment.verify",
        headers=_sa_headers(sa_token),
    )
    body = r.json()
    assert body["total"] >= 1


# ---------------------------------------------------------------------------
# 10. m369_sa_runner role sanity (catches migration 0008 regression)
# ---------------------------------------------------------------------------


def test_sa_runner_role_attributes(db_engine):
    """m369_sa_runner must be LOGIN + BYPASSRLS + NOSUPERUSER."""
    import psycopg

    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
                "FROM pg_roles WHERE rolname = 'm369_sa_runner'"
            )
            row = cur.fetchone()
            assert row is not None, "m369_sa_runner role missing — migration 0008 not applied"
            canlogin, super_, bypass, createrole, createdb = row
            assert canlogin, "m369_sa_runner must be LOGIN"
            assert not super_, "m369_sa_runner must be NOSUPERUSER"
            assert bypass, "m369_sa_runner must have BYPASSRLS"
            assert not createrole, "m369_sa_runner must be NOCREATEROLE"
            assert not createdb, "m369_sa_runner must be NOCREATEDB"
    finally:
        conn.close()


def test_sa_runner_has_crud_on_all_tables(db_engine):
    """m369_sa_runner must have the specific privileges it needs on each table.

    After migration 0011 (Package B), m369_sa_runner is least-privilege:
    it has SELECT/UPDATE on super_admins (not INSERT/DELETE — Super Admins
    are created via CLI, not via API), SELECT/INSERT on audit logs (no
    UPDATE/DELETE — audit logs are append-only), etc.

    This test verifies the SPECIFIC grants from migration 0011 rather than
    blanket CRUD on all tables.
    """
    import psycopg

    # Expected privileges per table after migration 0011
    # (table, set_of_privileges) — derived from the GRANT statements in 0011
    EXPECTED = {
        "super_admins": {"SELECT", "UPDATE"},
        "super_admin_audit_logs": {"SELECT", "INSERT"},
        "super_admin_mfa_challenges": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "super_admin_mfa_recovery_codes": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "super_admin_used_totp_codes": {"SELECT", "INSERT", "DELETE"},
        "agencies": {"SELECT", "UPDATE"},
        "agency_memberships": {"SELECT", "UPDATE"},
        "users": {"SELECT"},
        "plans": {"SELECT", "INSERT", "UPDATE"},
        "subscriptions": {"SELECT", "UPDATE"},
        "payments": {"SELECT", "UPDATE"},
        "platform_settings": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "agency_notes": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    }

    conn = psycopg.connect("postgresql://postgres@localhost:5432/m369_support_test")
    try:
        with conn.cursor() as cur:
            for table, expected_privs in EXPECTED.items():
                for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    cur.execute(
                        "SELECT has_table_privilege('m369_sa_runner', %s, %s)",
                        (table, priv),
                    )
                    has_priv = cur.fetchone()[0]
                    if priv in expected_privs:
                        assert has_priv, (
                            f"m369_sa_runner missing {priv} on {table} — expected per 0011 grants"
                        )
                    else:
                        assert not has_priv, (
                            f"m369_sa_runner has {priv} on {table} — should NOT have it (least privilege)"
                        )
    finally:
        conn.close()
