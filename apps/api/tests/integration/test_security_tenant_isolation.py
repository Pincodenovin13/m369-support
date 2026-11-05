"""Security tests: tenant isolation, JWT type separation, RLS enforcement.

Each test creates two independent agencies (A and B) and verifies:
    - Agency A cannot read Agency B's data
    - Cross-tenant FK references are rejected by the database
    - Missing tenant context blocks all data access
    - Tenant context does not leak across pooled connections
    - JWT type confusion is rejected
    - Expired/invalid tokens are rejected
    - Unauthenticated requests are rejected
    - Authorization is enforced per role
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    Agency,
    AgencyMembership,
    Contact,
    Conversation,
    Team,
    TeamMembership,
    User,
    Workspace,
)
from app.security import (
    create_access_token,
    decode_access_token,
    decode_super_admin_token,
)
from app.tenancy.context import (
    bypass_rls_for_super_admin,
    set_tenant_context,
)


pytestmark = pytest.mark.security


def _make_workspace(db: Session, agency_id: uuid.UUID, name: str = "WS") -> Workspace:
    bypass_rls_for_super_admin(db)
    ws = Workspace(agency_id=agency_id, name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}")
    db.add(ws)
    db.commit()
    bypass_rls_for_super_admin(db)
    db.refresh(ws)
    return ws


def _make_contact(db: Session, agency_id: uuid.UUID, workspace_id: uuid.UUID, email: str) -> Contact:
    bypass_rls_for_super_admin(db)
    c = Contact(agency_id=agency_id, workspace_id=workspace_id, email=email)
    db.add(c)
    db.commit()
    bypass_rls_for_super_admin(db)
    db.refresh(c)
    return c


def _make_team(db: Session, agency_id: uuid.UUID, workspace_id: uuid.UUID, name: str) -> Team:
    bypass_rls_for_super_admin(db)
    t = Team(workspace_id=workspace_id, agency_id=agency_id, name=name)
    db.add(t)
    db.commit()
    bypass_rls_for_super_admin(db)
    db.refresh(t)
    return t


# ---------------------------------------------------------------------------
# 1-3: Cross-tenant read / modify / delete denial
# ---------------------------------------------------------------------------


def test_agency_a_cannot_read_agency_b_data(db_session: Session, agency_a, agency_b):
    bypass_rls_for_super_admin(db_session)
    ws_a = _make_workspace(db_session, agency_a[0].id, "WS A")
    ws_b = _make_workspace(db_session, agency_b[0].id, "WS B")
    _make_contact(db_session, agency_a[0].id, ws_a.id, "a@a.test")
    _make_contact(db_session, agency_b[0].id, ws_b.id, "b@b.test")

    db_session.commit()
    set_tenant_context(db_session, agency_a[0].id)
    visible = db_session.scalars(select(Contact)).all()
    visible_emails = {c.email for c in visible}
    assert "a@a.test" in visible_emails
    assert "b@b.test" not in visible_emails, "Cross-tenant data leak detected"


def test_agency_a_cannot_modify_agency_b_record(db_session: Session, agency_a, agency_b):
    bypass_rls_for_super_admin(db_session)
    ws_b = _make_workspace(db_session, agency_b[0].id, "WS B")
    _make_contact(db_session, agency_b[0].id, ws_b.id, "b@b.test")

    db_session.commit()
    set_tenant_context(db_session, agency_a[0].id)
    fetched = db_session.scalars(select(Contact).where(Contact.email == "b@b.test")).all()
    assert fetched == [], "Cross-tenant read leak"

    result = db_session.execute(text("UPDATE contacts SET name='Hacked' WHERE email='b@b.test'"))
    db_session.commit()
    assert result.rowcount == 0, "Cross-tenant write occurred"

    db_session.rollback()
    bypass_rls_for_super_admin(db_session)
    still_b = db_session.scalars(select(Contact).where(Contact.email == "b@b.test")).first()
    assert still_b is not None and still_b.name != "Hacked", "Cross-tenant write leak"


def test_agency_a_cannot_delete_agency_b_record(db_session: Session, agency_a, agency_b):
    bypass_rls_for_super_admin(db_session)
    ws_b = _make_workspace(db_session, agency_b[0].id, "WS B")
    _make_contact(db_session, agency_b[0].id, ws_b.id, "b@b.test")

    db_session.commit()
    set_tenant_context(db_session, agency_a[0].id)
    result = db_session.execute(text("DELETE FROM contacts WHERE email='b@b.test'"))
    db_session.commit()
    assert result.rowcount == 0, "Cross-tenant delete occurred"

    db_session.rollback()
    bypass_rls_for_super_admin(db_session)
    still_exists = db_session.scalars(select(Contact).where(Contact.email == "b@b.test")).first()
    assert still_exists is not None, "Cross-tenant delete leak"


# ---------------------------------------------------------------------------
# 4: Workspace access without membership is empty
# ---------------------------------------------------------------------------


def test_workspace_access_without_membership_is_empty(db_session: Session, agency_a):
    bypass_rls_for_super_admin(db_session)
    ws = _make_workspace(db_session, agency_a[0].id, "WS A")
    _make_contact(db_session, agency_a[0].id, ws.id, "a@a.test")

    db_session.commit()
    visible = db_session.scalars(select(Contact)).all()
    assert visible == [], "Data leaked without tenant context"


# ---------------------------------------------------------------------------
# 5: Cross-agency assignment rejected by composite FK
# ---------------------------------------------------------------------------


def test_conversation_cannot_assign_foreign_agency_user(db_session: Session, agency_a, agency_b):
    bypass_rls_for_super_admin(db_session)
    ws_a = _make_workspace(db_session, agency_a[0].id, "WS A")
    contact_a = _make_contact(db_session, agency_a[0].id, ws_a.id, "a@a.test")

    bypass_rls_for_super_admin(db_session)
    user_b = User(email=f"b-user-{uuid.uuid4().hex[:6]}@agency-b.test", password_hash="x", name="B User")
    db_session.add(user_b)
    db_session.commit()
    bypass_rls_for_super_admin(db_session)
    db_session.refresh(user_b)
    bypass_rls_for_super_admin(db_session)
    membership_b = AgencyMembership(user_id=user_b.id, agency_id=agency_b[0].id, role="owner")
    db_session.add(membership_b)
    db_session.commit()

    bypass_rls_for_super_admin(db_session)
    conv = Conversation(
        workspace_id=ws_a.id,
        agency_id=agency_a[0].id,
        contact_id=contact_a.id,
        assigned_user_id=user_b.id,
        subject="Cross-tenant test",
    )
    db_session.add(conv)
    with pytest.raises(Exception) as exc:
        db_session.commit()
    assert "fk_conversations_assignee_agency" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    db_session.rollback()


# ---------------------------------------------------------------------------
# 6: Conversation cannot reference foreign-workspace contact
# ---------------------------------------------------------------------------


def test_conversation_cannot_reference_foreign_workspace_contact(db_session: Session, agency_a):
    bypass_rls_for_super_admin(db_session)
    ws1 = _make_workspace(db_session, agency_a[0].id, "WS1")
    ws2 = _make_workspace(db_session, agency_a[0].id, "WS2")
    contact_w2 = _make_contact(db_session, agency_a[0].id, ws2.id, "w2@a.test")

    bypass_rls_for_super_admin(db_session)
    conv = Conversation(
        workspace_id=ws1.id,
        agency_id=agency_a[0].id,
        contact_id=contact_w2.id,
        subject="Cross-workspace test",
    )
    db_session.add(conv)
    with pytest.raises(Exception) as exc:
        db_session.commit()
    assert "fk_conversations_contact_workspace" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    db_session.rollback()


# ---------------------------------------------------------------------------
# 7: Missing tenant context → no tenant data exposed
# ---------------------------------------------------------------------------


def test_missing_tenant_context_blocks_all_data(db_session: Session, agency_a):
    bypass_rls_for_super_admin(db_session)
    ws = _make_workspace(db_session, agency_a[0].id, "WS A")
    _make_contact(db_session, agency_a[0].id, ws.id, "x@a.test")

    db_session.commit()
    db_session.execute(text("RESET app.tenant_id"))
    db_session.execute(text("RESET app.bypass_rls"))

    visible = db_session.scalars(select(Contact)).all()
    assert visible == [], "Data leaked when tenant context is missing"


# ---------------------------------------------------------------------------
# 8: Tenant context does not leak across transactions
# ---------------------------------------------------------------------------


def test_tenant_context_does_not_leak_between_transactions(db_session: Session, agency_a, agency_b):
    bypass_rls_for_super_admin(db_session)
    ws_a = _make_workspace(db_session, agency_a[0].id, "WS A")
    ws_b = _make_workspace(db_session, agency_b[0].id, "WS B")
    _make_contact(db_session, agency_a[0].id, ws_a.id, "a@a.test")
    _make_contact(db_session, agency_b[0].id, ws_b.id, "b@b.test")

    db_session.commit()
    set_tenant_context(db_session, agency_a[0].id)
    visible_tx1 = {c.email for c in db_session.scalars(select(Contact)).all()}
    db_session.commit()

    assert visible_tx1 == {"a@a.test"}

    visible_tx2 = db_session.scalars(select(Contact)).all()
    assert visible_tx2 == [], "Tenant context leaked across transactions"


# ---------------------------------------------------------------------------
# 9-11: JWT lifecycle
# ---------------------------------------------------------------------------


def test_expired_token_rejected():
    import jwt as pyjwt
    from app.core.config import get_settings

    s = get_settings()
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "agency",
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "agency_id": str(uuid.uuid4()),
    }
    expired = pyjwt.encode(payload, s.jwt_secret_key, algorithm=s.jwt_algorithm)
    assert decode_access_token(expired) is None


def test_invalid_signature_rejected():
    import jwt as pyjwt
    from app.core.config import get_settings

    s = get_settings()
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "agency",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "jti": uuid.uuid4().hex,
        "agency_id": str(uuid.uuid4()),
    }
    bad_token = pyjwt.encode(payload, "wrong-secret", algorithm=s.jwt_algorithm)
    assert decode_access_token(bad_token) is None


def test_wrong_token_type_rejected():
    sa_token = create_access_token(subject=str(uuid.uuid4()), token_type="super_admin")
    assert decode_access_token(sa_token) is None, "Super admin token leaked through agency decoder"

    agency_token = create_access_token(
        subject=str(uuid.uuid4()),
        token_type="agency",
        agency_id=str(uuid.uuid4()),
    )
    assert decode_super_admin_token(agency_token) is None, "Agency token leaked through super admin decoder"


# ---------------------------------------------------------------------------
# 12: Unauthenticated requests rejected
# ---------------------------------------------------------------------------


def test_unauthenticated_request_rejected(client: TestClient):
    r = client.get("/api/v1/agencies/current")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


def test_unauthenticated_workspace_list_rejected(client: TestClient):
    r = client.get("/api/v1/workspaces")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 13: Authorization (role check)
# ---------------------------------------------------------------------------


def test_authorization_role_check(client: TestClient, db_session: Session, agency_a):
    agency, owner, owner_token = agency_a

    bypass_rls_for_super_admin(db_session)
    agent_user = User(email=f"agent-{uuid.uuid4().hex[:6]}@agency-a.test", password_hash="x", name="Agent")
    db_session.add(agent_user)
    db_session.commit()
    bypass_rls_for_super_admin(db_session)
    db_session.refresh(agent_user)

    bypass_rls_for_super_admin(db_session)
    membership = AgencyMembership(user_id=agent_user.id, agency_id=agency.id, role="agent")
    db_session.add(membership)
    db_session.commit()

    agent_token = create_access_token(
        subject=str(agent_user.id),
        token_type="agency",
        agency_id=str(agency.id),
    )

    r = client.post(
        "/api/v1/workspaces",
        json={"name": "Test WS", "slug": f"test-ws-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert r.status_code == 403, f"Expected 403 (insufficient role), got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 14: Cross-tenant team membership rejected by composite FK
# ---------------------------------------------------------------------------


def test_team_membership_cannot_reference_foreign_agency_team(db_session: Session, agency_a, agency_b):
    bypass_rls_for_super_admin(db_session)
    ws_b = _make_workspace(db_session, agency_b[0].id, "WS B")
    team_b = _make_team(db_session, agency_b[0].id, ws_b.id, "Team B")

    bypass_rls_for_super_admin(db_session)
    user_a = User(email=f"a-user-{uuid.uuid4().hex[:6]}@agency-a.test", password_hash="x", name="A User")
    db_session.add(user_a)
    db_session.commit()
    bypass_rls_for_super_admin(db_session)
    db_session.refresh(user_a)

    bypass_rls_for_super_admin(db_session)
    tm = TeamMembership(
        team_id=team_b.id,
        user_id=user_a.id,
        agency_id=agency_a[0].id,
    )
    db_session.add(tm)
    with pytest.raises(Exception) as exc:
        db_session.commit()
    assert "fk_team_memberships_team_agency" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    db_session.rollback()
