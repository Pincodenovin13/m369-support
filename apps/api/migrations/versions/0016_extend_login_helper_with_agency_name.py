"""Migration 0016: Extend get_user_memberships_for_login to return agency_name.

The login helper function previously returned only (agency_id, is_active, role).
The frontend multi-agency selection dropdown needs a human-readable agency name
to display alongside the UUID. This migration uses CREATE OR REPLACE FUNCTION
to add a ``name`` column to the return type — no data migration needed.

down_revision = 0015_revoke_super_admin_memberships_both_directions
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0016_extend_login_helper_with_agency_name"
down_revision: Union[str, None] = "0015_revoke_super_admin_memberships_both_directions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Must DROP first — PostgreSQL does not allow CREATE OR REPLACE FUNCTION
    # when the return type signature changes (adding agency_name column).
    op.execute("DROP FUNCTION IF EXISTS public.get_user_memberships_for_login(UUID)")

    op.execute("""
        CREATE FUNCTION public.get_user_memberships_for_login(p_user_id UUID)
        RETURNS TABLE(
            agency_id UUID,
            is_active BOOLEAN,
            role TEXT,
            agency_name TEXT
        )
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = pg_catalog
        AS $$
            SELECT a.id AS agency_id,
                   a.is_active AS is_active,
                   m.role AS role,
                   a.name AS agency_name
            FROM public.agency_memberships AS m
            JOIN public.agencies AS a ON a.id = m.agency_id
            WHERE m.user_id = p_user_id
        $$;
    """)

    # Re-apply ACL hardening from migration 0004
    op.execute("REVOKE ALL ON FUNCTION public.get_user_memberships_for_login(UUID) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_memberships_for_login(UUID) TO m369_app")
    # Restore function ownership to m369_login_reader (migration 0005 transferred it)
    op.execute("ALTER FUNCTION public.get_user_memberships_for_login(UUID) OWNER TO m369_login_reader")


def downgrade() -> None:
    # Must DROP first — PostgreSQL does not allow CREATE OR REPLACE FUNCTION
    # when the return type signature changes (removing agency_name column).
    op.execute("DROP FUNCTION IF EXISTS public.get_user_memberships_for_login(UUID)")

    # Restore the original function signature (without agency_name)
    op.execute("""
        CREATE FUNCTION public.get_user_memberships_for_login(p_user_id UUID)
        RETURNS TABLE(
            agency_id UUID,
            is_active BOOLEAN,
            role TEXT
        )
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = pg_catalog
        AS $$
            SELECT a.id AS agency_id,
                   a.is_active AS is_active,
                   m.role AS role
            FROM public.agency_memberships AS m
            JOIN public.agencies AS a ON a.id = m.agency_id
            WHERE m.user_id = p_user_id
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.get_user_memberships_for_login(UUID) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_memberships_for_login(UUID) TO m369_app")
    op.execute("ALTER FUNCTION public.get_user_memberships_for_login(UUID) OWNER TO m369_login_reader")
