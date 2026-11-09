"""Migration 0008: Create m369_sa_runner — LOGIN role with BYPASSRLS.

The Super Admin API endpoints need to read/write across all tenants (e.g.
list all agencies, suspend an agency, verify a payment for a different
agency). The ordinary ``m369_app`` role is subject to RLS — every query is
filtered by ``app.tenant_id``. So Super Admin operations use a separate
database connection with the ``m369_sa_runner`` role.

``m369_sa_runner``:
  - LOGIN (so the API can connect as it)
  - NOSUPERUSER (cannot create databases, roles, or replicate)
  - BYPASSRLS (every SELECT/INSERT/UPDATE/DELETE skips RLS policies)
  - NOCREATEDB, NOCREATEROLE, NOREPLICATION

The role's password is provisioned externally via the bootstrap SQL
(``infrastructure/database/01-bootstrap-roles.sql``) — the migration
only ensures the role exists with the right attribute combination.
This means the migration is safe to run in any environment without
leaking credentials.

Default privileges: grants CRUD on all current + future tables to
``m369_sa_runner``. Same grants as ``m369_app`` plus BYPASSRLS.

The corresponding SQLAlchemy engine is ``super_admin_engine`` in
``app/db/database.py``. The URL comes from ``DATABASE_URL_SUPER_ADMIN``
(a separate env var never shared with the migration service).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0008_create_sa_runner_role"
down_revision: Union[str, None] = "0007_fix_login_reader_acl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the role if missing. NOLOGIN as written in the migration
    #    would not be usable; we explicitly want LOGIN here. The bootstrap
    #    SQL (or environment provisioning) sets the password.
    op.execute(
        "DO $$ BEGIN "
        "CREATE ROLE m369_sa_runner LOGIN NOSUPERUSER BYPASSRLS "
        "  NOCREATEDB NOCREATEROLE NOREPLICATION; "
        "EXCEPTION WHEN duplicate_object THEN "
        "  ALTER ROLE m369_sa_runner NOSUPERUSER BYPASSRLS "
        "  NOCREATEDB NOCREATEROLE NOREPLICATION; "
        "END $$"
    )

    # 2. CRUD on every existing table.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO m369_sa_runner")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO m369_sa_runner")

    # 3. Default privileges for future tables created by postgres — so a
    #    later migration that does CREATE TABLE doesn't accidentally leave
    #    m369_sa_runner without access (which would surface as 500s in prod).
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO m369_sa_runner"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO m369_sa_runner"
    )


def downgrade() -> None:
    # Do NOT drop the role — it may have dependent grants. Just revoke
    # the default privileges; table-level grants are left in place.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM m369_sa_runner"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM m369_sa_runner"
    )
