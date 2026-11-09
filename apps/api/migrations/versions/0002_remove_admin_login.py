"""Remove m369_admin_login and its membership in m369_super_admin.

Revision ID: 0002_remove_admin_login
Revises: 0001_initial
Create Date: 2026-11-05

Security fix:
    The previous migration (0001) created m369_admin_login — a LOGIN role
    with membership in m369_super_admin (which has BYPASSRLS). This created
    a BYPASSRLS login path that was never used by application code.

    This migration:
    1. Revokes m369_super_admin FROM m369_admin_login
    2. Drops the m369_admin_login role
    3. Removes hardcoded passwords from the codebase

    The m369_super_admin (NOLOGIN, BYPASSRLS) role remains but has NO
    login member — BYPASSRLS is dormant until a reviewed Super Admin
    data-access service is built in a future phase.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0002_remove_admin_login"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Revoke membership (idempotent — use DO block to suppress "role does not exist")
    op.execute("""
        DO $$
        BEGIN
            REVOKE m369_super_admin FROM m369_admin_login;
        EXCEPTION WHEN undefined_object THEN
            -- m369_admin_login already removed — nothing to revoke
        END
        $$
    """)

    # Drop the login role (idempotent)
    op.execute("DROP ROLE IF EXISTS m369_admin_login")


def downgrade() -> None:
    # Do NOT recreate the login role — it was a security issue.
    # If a future phase needs a Super Admin connection, it should
    # provision credentials via a secure bootstrap mechanism.
    pass
