"""Fix SECURITY DEFINER function: revoke PUBLIC, schema-qualify, restrict search_path.

Revision ID: 0004_fix_login_helper_acl
Revises: 0003_login_helper
Create Date: 2026-11-05

Security fix for migration 0003:
  1. Revoke EXECUTE from PUBLIC (PostgreSQL grants EXECUTE to PUBLIC by default)
  2. Revoke EXECUTE from anon if the role exists
  3. Grant EXECUTE only to m369_app
  4. Recreate the function with:
     - search_path = 'pg_catalog, public' (prevents search_path injection)
     - Schema-qualified table names (public.agency_memberships, public.agencies)
  5. No dynamic SQL — function body is static SQL only
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004_fix_login_helper_acl"
down_revision: Union[str, None] = "0003_login_helper"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recreate the function with hardened settings:
    # - search_path = pg_catalog, public (prevents search_path hijacking)
    # - Schema-qualified table names
    # - SECURITY DEFINER (runs as table owner = postgres)
    op.execute("""
        CREATE OR REPLACE FUNCTION public.get_user_memberships_for_login(p_user_id UUID)
        RETURNS TABLE(agency_id UUID, is_active BOOLEAN, role TEXT)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT m.agency_id, a.is_active, m.role
            FROM public.agency_memberships AS m
            JOIN public.agencies AS a ON a.id = m.agency_id
            WHERE m.user_id = p_user_id
        $$;
    """)

    # Revoke EXECUTE from PUBLIC (PostgreSQL grants it by default)
    op.execute("REVOKE ALL ON FUNCTION public.get_user_memberships_for_login(UUID) FROM PUBLIC")

    # Revoke from anon if the role exists (do NOT fail if it doesn't)
    op.execute("""
        DO $$
        BEGIN
            EXECUTE 'REVOKE ALL ON FUNCTION public.get_user_memberships_for_login(UUID) FROM anon';
        EXCEPTION WHEN undefined_object THEN
            -- Role 'anon' does not exist — nothing to revoke
        END
        $$;
    """)

    # Grant EXECUTE only to m369_app (the runtime application role)
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_memberships_for_login(UUID) TO m369_app")


def downgrade() -> None:
    # Restore the original (less secure) version for downgrade
    op.execute("""
        CREATE OR REPLACE FUNCTION public.get_user_memberships_for_login(p_user_id UUID)
        RETURNS TABLE(agency_id UUID, is_active BOOLEAN, role TEXT)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public
        AS $$
            SELECT m.agency_id, a.is_active, m.role
            FROM agency_memberships m
            JOIN agencies a ON a.id = m.agency_id
            WHERE m.user_id = p_user_id
        $$;
    """)
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_memberships_for_login(UUID) TO m369_app")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_memberships_for_login(UUID) TO PUBLIC")
