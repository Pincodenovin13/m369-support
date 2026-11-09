"""Migration 0013: Final security hardening — registration guard + role neutralization.

This migration:

1. Creates the ``m369_registration_guard`` role (NOLOGIN, BYPASSRLS, NOCREATEROLE,
   NOCREATEDB, NOREPLICATION, NOINHERIT). BYPASSRLS is needed only because the
   role owns a SECURITY DEFINER function that must inspect whether any agency
   exists (which requires bypassing RLS on the agencies table).

2. Creates ``public.is_initial_agency_registration_open()`` — a SECURITY DEFINER
   SQL function that returns true when no agencies exist. Owned by
   m369_registration_guard. EXECUTE granted only to m369_app.

3. Neutralizes the ``m369_super_admin`` role (created by migration 0001 with
   BYPASSRLS + broad DML). Removes BYPASSRLS, revokes all table/sequence
   privileges, removes default privileges. The role is preserved for
   compatibility but left inert (NOLOGIN, NOBYPASSRLS, no privileges).

4. Cleans up any lingering default privileges for m369_sa_runner that may
   have been set by migration 0008 and not fully cleaned by 0011.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0013_package_b1_2_final_security"
down_revision: Union[str, None] = "0012_package_b1_critical_corrections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===================================================================
    # 1. m369_registration_guard role
    # ===================================================================

    # Create the role if it doesn't exist. BYPASSRLS is required because the
    # SECURITY DEFINER function it owns must read past RLS on agencies.
    op.execute("""
        DO $$
        BEGIN
            CREATE ROLE m369_registration_guard
                NOLOGIN
                NOSUPERUSER
                BYPASSRLS
                NOCREATEDB
                NOCREATEROLE
                NOREPLICATION
                NOINHERIT;
        EXCEPTION
            WHEN duplicate_object THEN
                ALTER ROLE m369_registration_guard
                    NOLOGIN
                    NOSUPERUSER
                    BYPASSRLS
                    NOCREATEDB
                    NOCREATEROLE
                    NOREPLICATION
                    NOINHERIT;
        END
        $$;
    """)

    # Grant SELECT only on agencies — nothing else.
    op.execute("GRANT SELECT ON TABLE public.agencies TO m369_registration_guard")

    # Revoke any other privileges that might have been granted.
    op.execute("""
        REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
        FROM m369_registration_guard
    """)
    op.execute("""
        REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
        FROM m369_registration_guard
    """)
    # Re-grant just the one SELECT we need.
    op.execute("GRANT SELECT ON TABLE public.agencies TO m369_registration_guard")

    # Grant USAGE on schema so the function can resolve names.
    op.execute("GRANT USAGE ON SCHEMA public TO m369_registration_guard")
    # No CREATE — the function is created by postgres (migration runner).
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_registration_guard")

    # ===================================================================
    # 2. is_initial_agency_registration_open() function
    # ===================================================================

    # Temporarily grant CREATE so the guard role can own the function.
    # We'll revoke it immediately after.
    op.execute("GRANT CREATE ON SCHEMA public TO m369_registration_guard")

    # Drop the function if it already exists (idempotent).
    op.execute("DROP FUNCTION IF EXISTS public.is_initial_agency_registration_open()")

    # Create the function as m369_registration_guard.
    # We use SET ROLE to create the function with the correct owner.
    op.execute("""
        SET ROLE m369_registration_guard;
        CREATE FUNCTION public.is_initial_agency_registration_open()
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = pg_catalog
        AS $$
            SELECT NOT EXISTS (
                SELECT 1
                FROM public.agencies
            )
        $$;
        RESET ROLE;
    """)

    # Revoke CREATE — the guard role should never create objects again.
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_registration_guard")

    # REVOKE EXECUTE FROM PUBLIC — only m369_app may call this.
    op.execute("REVOKE EXECUTE ON FUNCTION public.is_initial_agency_registration_open() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.is_initial_agency_registration_open() TO m369_app")

    # ===================================================================
    # 3. Neutralize m369_super_admin role
    # ===================================================================

    # The role was created by migration 0001 with BYPASSRLS + broad DML.
    # We neutralize it: remove BYPASSRLS, revoke all privileges.
    # The role is preserved for compatibility (migration 0001's downgrade
    # expects it to exist).

    # Remove BYPASSRLS and set all attributes to most restrictive.
    op.execute("""
        ALTER ROLE m369_super_admin
            NOLOGIN
            NOSUPERUSER
            NOBYPASSRLS
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOINHERIT
    """)

    # Revoke all table privileges.
    op.execute("""
        REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
        FROM m369_super_admin
    """)
    op.execute("""
        REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
        FROM m369_super_admin
    """)

    # Revoke schema privileges (keep USAGE so catalogs work, remove CREATE).
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_super_admin")

    # Remove any default privileges set for this role.
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE m369_super_admin IN SCHEMA public
        REVOKE ALL ON TABLES FROM m369_super_admin
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE m369_super_admin IN SCHEMA public
        REVOKE ALL ON SEQUENCES FROM m369_super_admin
    """)

    # Remove any role memberships involving m369_super_admin.
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            -- Remove memberships WHERE m369_super_admin is the member
            FOR r IN
                SELECT roleid::regrole::text AS role_name
                FROM pg_auth_members
                WHERE member = 'm369_super_admin'::regrole
            LOOP
                EXECUTE format('REVOKE %I FROM m369_super_admin', r.role_name);
            END LOOP;
        END $$;
    """)

    # ===================================================================
    # 4. Clean up m369_sa_runner default privileges
    # ===================================================================

    # Migration 0008 set default privileges; migration 0011 revoked them.
    # But we verify they're actually gone and revoke any lingering entries.
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        REVOKE ALL ON TABLES FROM m369_sa_runner
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        REVOKE ALL ON SEQUENCES FROM m369_sa_runner
    """)

    # Also check for default privileges set by other roles (m369_super_admin).
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE m369_super_admin IN SCHEMA public
        REVOKE ALL ON TABLES FROM m369_sa_runner
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE m369_super_admin IN SCHEMA public
        REVOKE ALL ON SEQUENCES FROM m369_sa_runner
    """)


def downgrade() -> None:
    # ===================================================================
    # 1. Drop the registration guard function + role
    # ===================================================================
    op.execute("REVOKE EXECUTE ON FUNCTION public.is_initial_agency_registration_open() FROM m369_app")
    op.execute("DROP FUNCTION IF EXISTS public.is_initial_agency_registration_open()")
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM m369_registration_guard")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM m369_registration_guard")
    op.execute("REVOKE USAGE ON SCHEMA public FROM m369_registration_guard")
    op.execute("DROP ROLE IF EXISTS m369_registration_guard")

    # ===================================================================
    # 2. Restore m369_super_admin (back to 0001 state)
    # ===================================================================
    # WARNING: This restores BYPASSRLS + broad DML to m369_super_admin.
    # This is the insecure pre-0013 state. Downgrade is only for development.
    op.execute("""
        ALTER ROLE m369_super_admin
            NOLOGIN
            NOSUPERUSER
            BYPASSRLS
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO m369_super_admin")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO m369_super_admin")

    # ===================================================================
    # 3. Restore m369_sa_runner default privileges (0008 state)
    # ===================================================================
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO m369_sa_runner
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO m369_sa_runner
    """)
