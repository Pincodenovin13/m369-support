"""Migration 0018: enforce workspace/agency consistency for contacts and teams.

Contacts and teams already stored both workspace_id and agency_id, but the
original schema only had independent foreign keys. That allowed a row to
reference a workspace owned by one agency while claiming another agency_id.
Add composite foreign keys after validating existing data.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0018_workspace_agency_fks_contacts_teams"
down_revision: Union[str, None] = "0017_revoke_runtime_schema_create"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fail closed if historical data already contains cross-agency references.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM contacts AS c
                LEFT JOIN workspaces AS w
                  ON w.id = c.workspace_id
                 AND w.agency_id = c.agency_id
                WHERE w.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0018 blocked: contacts contains workspace/agency mismatches';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM teams AS t
                LEFT JOIN workspaces AS w
                  ON w.id = t.workspace_id
                 AND w.agency_id = t.agency_id
                WHERE w.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0018 blocked: teams contains workspace/agency mismatches';
            END IF;
        END $$;
        """
    )

    # uq_workspaces_id_agency is created by migration 0011 and is the
    # referenced unique key for both composite foreign keys.
    op.create_foreign_key(
        "fk_contacts_workspace_agency",
        "contacts",
        "workspaces",
        ["workspace_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_teams_workspace_agency",
        "teams",
        "workspaces",
        ["workspace_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Removing these constraints would reopen cross-agency reference bugs.
    # Keep them in place even when rolling back later application features.
    pass
