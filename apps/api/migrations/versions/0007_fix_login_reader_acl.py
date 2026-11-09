"""Migration 0007: Revoke excess privileges from m369_login_reader.

Stage 1 (migration 0006) ended with::

    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
        TO m369_login_reader;

This was wrong — ``m369_login_reader`` is the dedicated least-privilege role
that owns the ``get_user_memberships_for_login(UUID)`` SECURITY DEFINER
function used at login. Its only job is to let that function read the
memberships + agencies needed to authenticate a user. Granting it INSERT /
UPDATE / DELETE on every tenant-owned table was a privilege-escalation
regression caught by ``test_login_reader_has_only_select_on_required_tables``.

This migration restores the intended ACL:

* ``m369_login_reader`` keeps USAGE on schema ``public`` (so it can resolve
  table names) but loses every table-level privilege.
* It then gets SELECT — and only SELECT — on ``agencies`` and
  ``agency_memberships`` (the two tables the login function reads).
* ``m369_app`` keeps its CRUD grant on every table — that role is the
  ordinary application role and needs full CRUD; it has NO BYPASSRLS, so
  RLS still filters everything it touches.

Idempotent: REVOKE is safe to re-run; the GRANT SELECTs use ``ON TABLE``
explicitly so they replace nothing and are also idempotent.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0007_fix_login_reader_acl"
down_revision: Union[str, None] = "0006_phase1_extended"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Strip ALL table-level privileges from m369_login_reader.
    #    This removes the over-broad grant that 0006 ended with.
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM m369_login_reader")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM m369_login_reader")

    # 2. Re-grant the only two SELECTs the login helper actually needs.
    op.execute("GRANT SELECT ON TABLE agencies TO m369_login_reader")
    op.execute("GRANT SELECT ON TABLE agency_memberships TO m369_login_reader")

    # 3. m369_app retains full CRUD on every table (RLS still filters it).
    #    This is a defensive re-grant in case a future migration adds a table
    #    but forgets to grant on it — the test suite asserts m369_app can CRUD
    #    every tenant-owned table.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO m369_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO m369_app")

    # 4. Default privileges for future tables created by postgres — so a
    #    later migration that does CREATE TABLE doesn't accidentally leave
    #    m369_app without access (which would surface as 500s in prod).
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO m369_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO m369_app"
    )


def downgrade() -> None:
    # Restoring the wrong-but-historical state would re-introduce the bug,
    # so downgrade is a no-op (privileges are not "rolled back" — the fix
    # is forward-only by design).
    pass
