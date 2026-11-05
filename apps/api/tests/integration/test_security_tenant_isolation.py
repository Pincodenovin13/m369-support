"""Security tests: tenant isolation, JWT type separation, RLS enforcement.

Architecture:
    - Test data is inserted via ``setup_session`` (postgres superuser, RLS bypassed)
    - Assertions are made via ``db_session`` (m369_app ordinary role, RLS enforced)
    - ``set_tenant_context(db_session, agency_id)`` sets the RLS filter
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
from app.tenancy.context import set_tenant_context


pytestmark = pytest.mark.security


# ---------------------------------------------------------------------------
# Helpers — use setup_session (postgres) for data insertion
# ---------------------------------------------------------------------------


def _make_workspace(setup: Session, agency_id: uuid.UUID, name: str = "WS") -> Workspace:
    ws = Workspace(agency_id=agency_id, name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}")
    setup.add(ws)
    setup.commit()
    setup.refresh(ws)
    return ws


def _make_contact(setup: Session, agency_id: uuid.UUID, workspace_id: uuid.UUID, email: str) -> Contact:
    c = Contact(agency_id=agency_id, workspace_id=workspace_id, email=email)
    setup.add(c)
    setup.commit()
    setup.refresh(c)
    return c


def _make_team(setup: Session, agency_id: uuid.UUID, workspace_id: uuid.UUID, name: str) -> Team:
    t = Team(workspace_id=workspace_id, agency_id=agency_id, name=name)
    setup.add(t)
    setup.commit()
    setup.refresh(t)
    return t


# ---------------------------------------------------------------------------
# 1-3: Cross-tenant read / modify / delete denial (via db_session = m369_app)
# ---------------------------------------------------------------------------


def test_agency_a_cannot_read_agency_b_data(setup_session: Session, db_session: Session, agency_a, agency_b):
    """Agency A queries contacts; only sees its own, not Agency B's."""
    ws_a = _make_workspace(setup_session, agency_a[0].id, "WS A")
    ws_b = _make_workspace(setup_session, agency_b[0].id, "WS B")
    _make_contact(setup_session, agency_a[0].id, ws_a.id, "a@a.test")
    _make_contact(setup_session, agency_b[0].id, ws_b.id, "b@b.test")

    # Use db_session (m369_app) with tenant context set to A
    set_tenant_context(db_session, agency_a[0].id)
    visible = db_session.scalars(select(Contact)).all()
    visible_emails = {c.email for c in visible}
    assert "a@a.test" in visible_emails
    assert "b@b.test" not in visible_emails, "Cross-tenant data leak detected"


def test_agency_a_cannot_modify_agency_b_record(setup_session: Session, db_session: Session, agency_a, agency_b):
    """Agency A cannot update a contact owned by Agency B."""
    ws_b = _make_workspace(setup_session, agency_b[0].id, "WS B")
    _make_contact(setup_session, agency_b[0].id, ws_b.id, "b@b.test")

    db_session.commit()
    set_tenant_context(db_session, agency_a[0].id)
    fetched = db_session.scalars(select(Contact).where(Contact.email == "b@b.test")).all()
    assert fetched == [], "Cross-tenant read leak"

    result = db_session.execute(text("UPDATE contacts SET name='Hacked' WHERE email='b@b.test'"))
    db_session.commit()
    assert result.rowcount == 0, "Cross-tenant write occurred"

    db_session.rollback()
    # Verify via setup_session (postgres) that the row was not modified
    still_b = setup_session.scalars(select(Contact).where(Contact.email == "b@b.test")).first()
    assert still_b is not None and still_b.name != "Hacked", "Cross-tenant write leak"


def test_agency_a_cannot_delete_agency_b_record(setup_session: Session, db_session: Session, agency_a, agency_b):
    """Agency A cannot delete a contact owned by Agency B."""
    ws_b = _make_workspace(setup_session, agency_b[0].id, "WS B")
    _make_contact(setup_session, agency_b[0].id, ws_b.id, "b@b.test")

    db_session.commit()
    set_tenant_context(db_session, agency_a[0].id)
    result = db_session.execute(text("DELETE FROM contacts WHERE email='b@b.test'"))
    db_session.commit()
    assert result.rowcount == 0, "Cross-tenant delete occurred"

    db_session.rollback()
    still_exists = setup_session.scalars(select(Contact).where(Contact.email == "b@b.test")).first()
    assert still_exists is not None, "Cross-tenant delete leak"


# ---------------------------------------------------------------------------
# 4: Workspace access without membership is empty
# ---------------------------------------------------------------------------


def test_workspace_access_without_membership_is_empty(setup_session: Session, db_session: Session, agency_a):
    """Without tenant context set, no tenant data is visible (via m369_app)."""
    ws = _make_workspace(setup_session, agency_a[0].id, "WS A")
    _make_contact(setup_session, agency_a[0].id, ws.id, "a@a.test")

    db_session.commit()
    visible = db_session.scalars(select(Contact)).all()
    assert visible == [], "Data leaked without tenant context"


# ---------------------------------------------------------------------------
# 5: Cross-agency assignment rejected by composite FK
# ---------------------------------------------------------------------------


def test_conversation_cannot_assign_foreign_agency_user(setup_session: Session, db_session: Session, agency_a, agency_b):
    """Composite FK on (assigned_user_id, agency_id) prevents cross-tenant assignment."""
    ws_a = _make_workspace(setup_session, agency_a[0].id, "WS A")
    contact_a = _make_contact(setup_session, agency_a[0].id, ws_a.id, "a@a.test")

    user_b = User(email=f"b-user-{uuid.uuid4().hex[:6]}@agency-b.test", password_hash="x", name="B User")
    setup_session.add(user_b)
    setup_session.commit()
    setup_session.refresh(user_b)
    membership_b = AgencyMembership(user_id=user_b.id, agency_id=agency_b[0].id, role="owner")
    setup_session.add(membership_b)
    setup_session.commit()

    conv = Conversation(
        workspace_id=ws_a.id,
        agency_id=agency_a[0].id,
        contact_id=contact_a.id,
        assigned_user_id=user_b.id,
        subject="Cross-tenant test",
    )
    setup_session.add(conv)
    with pytest.raises(Exception) as exc:
        setup_session.commit()
    assert "fk_conversations_assignee_agency" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    setup_session.rollback()


# ---------------------------------------------------------------------------
# 6: Conversation cannot reference foreign-workspace contact
# ---------------------------------------------------------------------------


def test_conversation_cannot_reference_foreign_workspace_contact(setup_session: Session, db_session: Session, agency_a):
    """Composite FK blocks cross-workspace contact references."""
    ws1 = _make_workspace(setup_session, agency_a[0].id, "WS1")
    ws2 = _make_workspace(setup_session, agency_a[0].id, "WS2")
    contact_w2 = _make_contact(setup_session, agency_a[0].id, ws2.id, "w2@a.test")

    conv = Conversation(
        workspace_id=ws1.id,
        agency_id=agency_a[0].id,
        contact_id=contact_w2.id,
        subject="Cross-workspace test",
    )
    setup_session.add(conv)
    with pytest.raises(Exception) as exc:
        setup_session.commit()
    assert "fk_conversations_contact_workspace" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    setup_session.rollback()


# ---------------------------------------------------------------------------
# 7: Missing tenant context → no tenant data exposed
# ---------------------------------------------------------------------------


def test_missing_tenant_context_blocks_all_data(setup_session: Session, db_session: Session, agency_a):
    """When app.tenant_id is unset, RLS returns 0 rows (fail-closed)."""
    ws = _make_workspace(setup_session, agency_a[0].id, "WS A")
    _make_contact(setup_session, agency_a[0].id, ws.id, "x@a.test")

    db_session.execute(text("RESET app.tenant_id"))
    visible = db_session.scalars(select(Contact)).all()
    assert visible == [], "Data leaked when tenant context is missing"


# ---------------------------------------------------------------------------
# 8: Tenant context does not leak across transactions
# ---------------------------------------------------------------------------


def test_tenant_context_does_not_leak_between_transactions(setup_session: Session, db_session: Session, agency_a, agency_b):
    """SET LOCAL scopes tenant_id to the transaction; next transaction sees nothing."""
    ws_a = _make_workspace(setup_session, agency_a[0].id, "WS A")
    ws_b = _make_workspace(setup_session, agency_b[0].id, "WS B")
    _make_contact(setup_session, agency_a[0].id, ws_a.id, "a@a.test")
    _make_contact(setup_session, agency_b[0].id, ws_b.id, "b@b.test")

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


def test_authorization_role_check(client: TestClient, setup_session: Session, agency_a):
    """An ``agent`` role cannot create a workspace (only owner/admin can)."""
    agency, owner, owner_token = agency_a

    agent_user = User(email=f"agent-{uuid.uuid4().hex[:6]}@agency-a.test", password_hash="x", name="Agent")
    setup_session.add(agent_user)
    setup_session.commit()
    setup_session.refresh(agent_user)

    membership = AgencyMembership(user_id=agent_user.id, agency_id=agency.id, role="agent")
    setup_session.add(membership)
    setup_session.commit()

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


def test_team_membership_cannot_reference_foreign_agency_team(setup_session: Session, agency_a, agency_b):
    """Composite FK on (team_id, agency_id) prevents cross-agency team membership."""
    ws_b = _make_workspace(setup_session, agency_b[0].id, "WS B")
    team_b = _make_team(setup_session, agency_b[0].id, ws_b.id, "Team B")

    user_a = User(email=f"a-user-{uuid.uuid4().hex[:6]}@agency-a.test", password_hash="x", name="A User")
    setup_session.add(user_a)
    setup_session.commit()
    setup_session.refresh(user_a)

    tm = TeamMembership(
        team_id=team_b.id,
        user_id=user_a.id,
        agency_id=agency_a[0].id,
    )
    setup_session.add(tm)
    with pytest.raises(Exception) as exc:
        setup_session.commit()
    assert "fk_team_memberships_team_agency" in str(exc.value).lower() or "foreign key" in str(exc.value).lower()
    setup_session.rollback()
