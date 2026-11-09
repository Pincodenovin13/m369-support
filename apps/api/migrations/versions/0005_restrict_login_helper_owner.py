"""Restrict login helper function owner to least-privilege role.

Revision ID: 0005_restrict_login_helper_owner
Revises: 0004_fix_login_helper_acl
Create Date: 2026-11-05

The function ``get_user_memberships_for_login`` was owned by ``postgres``
(a SUPERUSER). SECURITY DEFINER functions run with the owner's privileges,
so this gave the function SUPERUSER-level access — more than needed.

This migration:
1. Creates a dedicated ``m369_login_reader`` role: NOLOGIN, NOSUPERUSER,
   NOCREATEROLE, NOCREATEDB, but WITH BYPASSRLS (needed to read
   agency_memberships and agencies which have RLS).
2. Grants only SELECT on the two tables the function reads.
3. Grants USAGE on schema public (no CREATE).
4. Temporarily grants CREATE to transfer function ownership, then revokes it.
5. Re-secures the function ACL (REVOKE PUBLIC, GRANT EXECUTE to m369_app).

``m369_app`` is NOT a member of ``m369_login_reader`` — the runtime
role cannot SET ROLE to escalate. The only way to exercise the function
is via the narrowly-scoped EXECUTE privilege.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_restrict_login_helper_owner"
down_revision: Union[str, None] = "0004_fix_login_helper_acl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create dedicated least-privilege role
    op.execute("""
        DO $$
        BEGIN
            CREATE ROLE m369_login_reader
                NOLOGIN
                NOSUPERUSER
                NOBYPASSRLS
                NOCREATEDB
                NOCREATEROLE;
        EXCEPTION WHEN duplicate_object THEN
            ALTER ROLE m369_login_reader
                NOLOGIN
                NOSUPERUSER
                NOBYPASSRLS
                NOCREATEDB
                NOCREATEROLE;
        END
        $$;
    """)

    # Grant BYPASSRLS so the function can read RLS-protected tables
    op.execute("ALTER ROLE m369_login_reader BYPASSRLS")

    # 2. Grant minimum table access (SELECT only, on the 2 tables the function reads)
    op.execute("GRANT USAGE ON SCHEMA public TO m369_login_reader")
    op.execute("""
        GRANT SELECT ON TABLE
            public.agency_memberships,
            public.agencies
        TO m369_login_reader
    """)

    # 3. Transfer function ownership (temporarily grant CREATE, then revoke)
    op.execute("GRANT CREATE ON SCHEMA public TO m369_login_reader")
    op.execute("ALTER FUNCTION public.get_user_memberships_for_login(UUID) OWNER TO m369_login_reader")
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_login_reader")

    # 4. Re-secure ACL after ownership change (ownership change resets ACL)
    op.execute("REVOKE ALL ON FUNCTION public.get_user_memberships_for_login(UUID) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_memberships_for_login(UUID) TO m369_app")


def downgrade() -> None:
    # 1. Return function ownership to postgres
    op.execute("ALTER FUNCTION public.get_user_memberships_for_login(UUID) OWNER TO postgres")

    # 2. Re-secure ACL (as it was under migration 0004)
    op.execute("REVOKE ALL ON FUNCTION public.get_user_memberships_for_login(UUID) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_user_memberships_for_login(UUID) TO m369_app")

    # 3. Revoke table privileges from m369_login_reader
    op.execute("""
        REVOKE SELECT ON TABLE
            public.agency_memberships,
            public.agencies
        FROM m369_login_reader
    """)
    op.execute("REVOKE USAGE ON SCHEMA public FROM m369_login_reader")

    # 4. Drop the role — fail if dependencies remain (no CASCADE)
    op.execute("DROP ROLE m369_login_reader")
