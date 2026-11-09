"""Regression tests for workspace/agency composite foreign keys."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def _seed_agencies_and_workspaces(setup_session):
    agency_a = uuid.uuid4()
    agency_b = uuid.uuid4()
    workspace_a = uuid.uuid4()
    workspace_b = uuid.uuid4()

    setup_session.execute(
        text(
            "INSERT INTO agencies (id, name, slug, brand_color, is_active) "
            "VALUES (:id, 'Tenant A', :slug, '#123456', true)"
        ),
        {"id": agency_a, "slug": f"tenant-a-{uuid.uuid4().hex[:10]}"},
    )
    setup_session.execute(
        text(
            "INSERT INTO agencies (id, name, slug, brand_color, is_active) "
            "VALUES (:id, 'Tenant B', :slug, '#654321', true)"
        ),
        {"id": agency_b, "slug": f"tenant-b-{uuid.uuid4().hex[:10]}"},
    )
    setup_session.execute(
        text(
            "INSERT INTO workspaces (id, agency_id, name, slug, timezone, is_active) "
            "VALUES (:id, :agency_id, 'Workspace A', :slug, 'UTC', true)"
        ),
        {"id": workspace_a, "agency_id": agency_a, "slug": f"ws-a-{uuid.uuid4().hex[:10]}"},
    )
    setup_session.execute(
        text(
            "INSERT INTO workspaces (id, agency_id, name, slug, timezone, is_active) "
            "VALUES (:id, :agency_id, 'Workspace B', :slug, 'UTC', true)"
        ),
        {"id": workspace_b, "agency_id": agency_b, "slug": f"ws-b-{uuid.uuid4().hex[:10]}"},
    )
    setup_session.commit()
    return agency_a, agency_b, workspace_a, workspace_b


def test_contacts_cannot_reference_another_agency_workspace(db_engine, setup_session):
    """A contact claiming tenant B cannot point at tenant A's workspace."""
    _, agency_b, workspace_a, _ = _seed_agencies_and_workspaces(setup_session)

    with pytest.raises(IntegrityError):
        with setup_session.begin_nested():
            setup_session.execute(
                text(
                    "INSERT INTO contacts (id, workspace_id, agency_id, email, name) "
                    "VALUES (:id, :workspace_id, :agency_id, :email, 'Cross tenant')"
                ),
                {
                    "id": uuid.uuid4(),
                    "workspace_id": workspace_a,
                    "agency_id": agency_b,
                    "email": f"{uuid.uuid4().hex}@invalid.test",
                },
            )


def test_teams_cannot_reference_another_agency_workspace(db_engine, setup_session):
    """A team claiming tenant B cannot point at tenant A's workspace."""
    _, agency_b, workspace_a, _ = _seed_agencies_and_workspaces(setup_session)

    with pytest.raises(IntegrityError):
        with setup_session.begin_nested():
            setup_session.execute(
                text(
                    "INSERT INTO teams (id, workspace_id, agency_id, name, is_default) "
                    "VALUES (:id, :workspace_id, :agency_id, 'Cross tenant', false)"
                ),
                {
                    "id": uuid.uuid4(),
                    "workspace_id": workspace_a,
                    "agency_id": agency_b,
                },
            )
