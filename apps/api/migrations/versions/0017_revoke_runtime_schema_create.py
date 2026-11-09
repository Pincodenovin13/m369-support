"""Migration 0017: remove schema CREATE privilege from runtime roles.

The bootstrap script previously granted ALL on schema public to m369_app.
That includes CREATE and allows the application credential to create objects
in the shared schema. Runtime roles must have USAGE only; schema DDL belongs
exclusively to the migration owner.

This migration also revokes CREATE from PUBLIC to close inherited grants on
older PostgreSQL installations, while preserving schema USAGE.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0017_revoke_runtime_schema_create"
down_revision: Union[str, None] = "0016_extend_login_helper_with_agency_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Runtime application role: resolve objects, but never create schema objects.
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_app")
    op.execute("GRANT USAGE ON SCHEMA public TO m369_app")

    # PUBLIC grants are inherited by every role; remove the dangerous grant
    # globally rather than relying on PostgreSQL-version defaults.
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")


def downgrade() -> None:
    # Deliberately do not restore CREATE. Re-enabling runtime DDL would
    # reintroduce the privilege-escalation surface this migration closes.
    pass
