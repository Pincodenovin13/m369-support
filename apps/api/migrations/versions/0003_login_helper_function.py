"""Add SECURITY DEFINER function for login flow.

Revision ID: 0003_login_helper
Revises: 0002_remove_admin_login
Create Date: 2026-11-05

The login/refresh endpoints need to read agency and membership data
before the tenant context is established. RLS blocks these reads
because app.tenant_id is not yet set.

This migration creates a SECURITY DEFINER function that runs as the
table owner (postgres) and returns agency + membership data for a
specific user_id. The function is narrowly scoped — it only returns
the columns needed for login verification.

This is the standard PostgreSQL pattern for multi-tenant auth flows.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_login_helper"
down_revision: Union[str, None] = "0002_remove_admin_login"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SECURITY DEFINER function: runs as the table owner (postgres),
    # bypasses RLS. Only used by the login/refresh flow.
    # Returns: (agency_id, is_active, role) for all memberships of a user.
    op.execute("""
        CREATE OR REPLACE FUNCTION get_user_memberships_for_login(p_user_id UUID)
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
    # Grant execute to m369_app
    op.execute("GRANT EXECUTE ON FUNCTION get_user_memberships_for_login(UUID) TO m369_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS get_user_memberships_for_login(UUID)")
