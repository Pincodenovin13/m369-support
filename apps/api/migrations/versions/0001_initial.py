"""Initial schema: super admins, agencies, workspaces, users, memberships, teams, contacts, conversations, audit logs + RLS policies.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-05

Design notes
------------
- All tenant-owned tables carry ``agency_id`` so RLS can filter on it.
- ``users`` is global (no agency_id) — identity is global, membership is per-agency.
- ``super_admins`` is fully separate from ``users``: separate table, separate
  JWT signing key, separate audit log.
- Composite foreign keys enforce cross-tenant integrity.
- RLS is enabled on all tenant-owned tables. Policies read ``app.tenant_id``
  (a session-local GUC set by the application per request). Super Admin can
  bypass RLS only via ``SET LOCAL app.bypass_rls = 'on'``, which requires the
  role ``m369_super_admin``.
- Audit logs use ``ON DELETE RESTRICT`` on agency_id: deleting an agency with
  audit history is blocked (regulatory requirement).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ---
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    # --- Roles (idempotent) ---
    op.execute("DO $$ BEGIN CREATE ROLE m369_super_admin NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # --- super_admins ---
    op.create_table(
        "super_admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("mfa_secret_encrypted", sa.Text, nullable=True),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("failed_mfa_attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- agencies ---
    op.create_table(
        "agencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True, index=True),
        sa.Column("brand_color", sa.String(20), nullable=False, server_default=sa.text("'#FF6B35'")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- workspaces ---
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("agency_id", "slug", name="uq_workspaces_agency_slug"),
    )

    # --- users (global identity) ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- agency_memberships ---
    op.create_table(
        "agency_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(30), nullable=False, server_default=sa.text("'agent'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "agency_id", name="uq_memberships_user_agency"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'manager', 'agent', 'viewer')",
            name="ck_memberships_role",
        ),
    )

    # --- teams ---
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "name", name="uq_teams_workspace_name"),
        sa.UniqueConstraint("id", "agency_id", name="uq_teams_id_agency"),
    )

    # --- team_memberships (composite FK to teams.id+agency_id) ---
    op.create_table(
        "team_memberships",
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["team_id", "agency_id"],
            ["teams.id", "teams.agency_id"],
            name="fk_team_memberships_team_agency",
            ondelete="CASCADE",
        ),
    )

    # --- contacts ---
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(320), nullable=True, index=True),
        sa.Column("phone", sa.String(40), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "email", name="uq_contacts_workspace_email"),
        sa.UniqueConstraint("id", "workspace_id", "agency_id", name="uq_contacts_id_ws_agency"),
    )

    # --- conversations (composite FK to contacts + agency_memberships) ---
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(255), nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('open', 'pending', 'resolved', 'closed')",
            name="ck_conversations_status",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id", "workspace_id", "agency_id"],
            ["contacts.id", "contacts.workspace_id", "contacts.agency_id"],
            name="fk_conversations_contact_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_user_id", "agency_id"],
            ["agency_memberships.user_id", "agency_memberships.agency_id"],
            name="fk_conversations_assignee_agency",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_team_id", "agency_id"],
            ["teams.id", "teams.agency_id"],
            name="fk_conversations_team_agency",
            ondelete="SET NULL",
        ),
    )

    # --- audit_logs (RESTRICT on agency delete) ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_agency_created", "audit_logs", ["agency_id", "created_at"])

    # --- super_admin_audit_logs (separate) ---
    op.create_table(
        "super_admin_audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("super_admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- RLS: enable + FORCE on all tenant-owned tables ---
    tenant_tables = [
        "agencies",
        "workspaces",
        "agency_memberships",
        "teams",
        "team_memberships",
        "contacts",
        "conversations",
        "audit_logs",
    ]
    for table in tenant_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # --- RLS policies ---
    op.execute("""
        CREATE POLICY tenant_isolation_agencies ON agencies
        USING (
            current_setting('app.bypass_rls', true) = 'on'
            OR id::text = current_setting('app.tenant_id', true)
        )
        WITH CHECK (
            current_setting('app.bypass_rls', true) = 'on'
            OR id::text = current_setting('app.tenant_id', true)
        )
    """)
    for table in ["workspaces", "agency_memberships", "teams", "team_memberships", "contacts", "conversations", "audit_logs"]:
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (
                current_setting('app.bypass_rls', true) = 'on'
                OR agency_id::text = current_setting('app.tenant_id', true)
            )
            WITH CHECK (
                current_setting('app.bypass_rls', true) = 'on'
                OR agency_id::text = current_setting('app.tenant_id', true)
            )
        """)


def downgrade() -> None:
    tenant_tables = ["agencies", "workspaces", "agency_memberships", "teams", "team_memberships", "contacts", "conversations", "audit_logs"]
    for table in tenant_tables:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in [
        "super_admin_audit_logs",
        "audit_logs",
        "conversations",
        "contacts",
        "team_memberships",
        "teams",
        "agency_memberships",
        "users",
        "workspaces",
        "agencies",
        "super_admins",
    ]:
        op.drop_table(table)

    op.execute("DROP ROLE IF EXISTS m369_super_admin")
