"""Migration 0015: Revoke m369_super_admin memberships in both directions.

Migration 0013 removed memberships where ``m369_super_admin`` was the
**member** (i.e., ``member = m369_super_admin``), but did NOT remove
memberships where ``m369_super_admin`` was the **granted role** (i.e.,
``roleid = m369_super_admin``). This leaves dormant membership grants
that could be exploited if:

1. Migration 0013's downgrade is run (restoring BYPASSRLS + DML)
2. A future migration re-grants privileges to m369_super_admin
3. A login-capable role with a dormant membership does SET ROLE

This migration closes the gap by removing memberships in both directions.

down_revision = 0014_agency_user_token_version
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0015_revoke_super_admin_memberships_both_directions"
down_revision: Union[str, None] = "0014_agency_user_token_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove memberships where m369_super_admin is the MEMBER
    # (i.e., m369_super_admin was granted membership in another role)
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN
                SELECT roleid::regrole::text AS role_name
                FROM pg_auth_members
                WHERE member = 'm369_super_admin'::regrole
            LOOP
                EXECUTE format('REVOKE %I FROM m369_super_admin', r.role_name);
            END LOOP;
        END $$;
    """)

    # Remove memberships where m369_super_admin is the GRANTED ROLE
    # (i.e., another role was granted membership IN m369_super_admin)
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN
                SELECT member::regrole::text AS member_name
                FROM pg_auth_members
                WHERE roleid = 'm369_super_admin'::regrole
            LOOP
                EXECUTE format('REVOKE m369_super_admin FROM %I', r.member_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    # Intentionally non-restorative: we do NOT recreate the insecure
    # membership grants. The pre-0015 state was a security defect.
    # Downgrade is a no-op — the role remains neutralized (NOLOGIN,
    # NOBYPASSRLS, zero privileges) from migration 0013.
    pass
