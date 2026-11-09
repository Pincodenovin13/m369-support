"""Package B.1 critical FK deletion corrections and SA auth role.

Migration 0012 fixes two FK deletion-behavior issues from migration 0011
and introduces the dedicated ``m369_sa_auth`` role for Super Admin
authentication (login + MFA verify), separating it from both the ordinary
application role (``m369_app``) and the management role (``m369_sa_runner``).

FK corrections:
  1. kb_articles composite FK (category_id, workspace_id, agency_id):
     - Was ON DELETE SET NULL (which would NULL workspace_id + agency_id
       — both NOT NULL → would fail)
     - Now ON DELETE NO ACTION (composite only enforces tenant boundary)
     - Simple FK category_id → kb_categories.id stays ON DELETE SET NULL
  2. messages reply_to composite FK (reply_to_message_id, agency_id):
     - Was ON DELETE SET NULL (same NOT NULL problem on agency_id)
     - Now: simple FK reply_to_message_id → messages.id ON DELETE SET NULL
       + composite FK (reply_to_message_id, agency_id) ON DELETE NO ACTION

Role separation:
  - m369_sa_auth: LOGIN, NOSUPERUSER, NOBYPASSRLS, NOCREATEROLE, NOCREATEDB
    Used ONLY by /super-admin/auth/login and /super-admin/auth/login/verify-mfa
    via get_super_admin_auth_db(). Has:
    - SELECT on super_admins (read identity for password verify)
    - UPDATE on (failed_login_attempts, last_failed_login_at,
                 failed_mfa_attempts, locked_until, last_login_at) only
    - INSERT + SELECT(id) on super_admin_audit_logs + sequence USAGE
    - Full CRUD on MFA tables (challenges, recovery codes, used TOTP codes)
  - m369_app: REVOKE ALL on super_admins + audit_logs + MFA tables
    (login flow no longer runs on m369_app)
  - m369_sa_runner: unchanged (still BYPASSRLS for management endpoints)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012_package_b1_critical_corrections"
down_revision: Union[str, None] = "0011_tenant_isolation_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen alembic_version.version_num to accommodate longer revision IDs
    # (0012_package_b1_critical_corrections = 35 chars, VARCHAR(32) too short)
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(32),
        type_=sa.String(128),
        nullable=False,
    )

    # ---------------------------------------------------------
    # 1. KB article category FK — fix ON DELETE behavior
    # ---------------------------------------------------------

    # Drop the composite FK that had ON DELETE SET NULL
    # (which would try to NULL workspace_id + agency_id — both NOT NULL)
    op.drop_constraint(
        "fk_kb_articles_category_ws_agency",
        "kb_articles",
        type_="foreignkey",
    )

    # Re-create with ON DELETE NO ACTION — the composite FK only enforces
    # the tenant boundary. The simple FK on category_id (already exists
    # from migration 0006 with ON DELETE SET NULL) handles the NULL-on-delete.
    op.create_foreign_key(
        "fk_kb_articles_category_ws_agency",
        "kb_articles",
        "kb_categories",
        ["category_id", "workspace_id", "agency_id"],
        ["id", "workspace_id", "agency_id"],
        ondelete="NO ACTION",
    )

    # ---------------------------------------------------------
    # 2. Message reply FK — fix ON DELETE behavior
    # ---------------------------------------------------------

    # Drop the composite FK that had ON DELETE SET NULL
    op.drop_constraint(
        "fk_messages_reply_to_agency",
        "messages",
        type_="foreignkey",
    )

    # Simple FK: only reply_to_message_id becomes NULL on delete.
    # This is the FK that actually handles the "set null on parent delete"
    # behavior correctly (only NULLs the nullable column).
    op.create_foreign_key(
        "fk_messages_reply_to_message",
        "messages",
        "messages",
        ["reply_to_message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Composite FK: tenant boundary protection only — NO ACTION on delete.
    # The simple FK above handles the NULL; this one just prevents
    # cross-agency reply references.
    op.create_foreign_key(
        "fk_messages_reply_to_agency",
        "messages",
        "messages",
        ["reply_to_message_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="NO ACTION",
    )

    # ---------------------------------------------------------
    # 3. Dedicated Super Admin authentication role
    # ---------------------------------------------------------

    op.execute("""
        DO $$
        BEGIN
            CREATE ROLE m369_sa_auth
                LOGIN
                NOSUPERUSER
                NOBYPASSRLS
                NOCREATEDB
                NOCREATEROLE
                NOREPLICATION
                NOINHERIT;
        EXCEPTION
            WHEN duplicate_object THEN
                ALTER ROLE m369_sa_auth
                    LOGIN
                    NOSUPERUSER
                    NOBYPASSRLS
                    NOCREATEDB
                    NOCREATEROLE
                    NOREPLICATION
                    NOINHERIT;
        END
        $$;
    """)

    op.execute("GRANT USAGE ON SCHEMA public TO m369_sa_auth")
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_sa_auth")

    # Explicitly prevent role escalation
    op.execute("REVOKE m369_sa_runner FROM m369_sa_auth")
    op.execute("REVOKE m369_sa_auth FROM m369_app")
    op.execute("REVOKE m369_sa_runner FROM m369_app")

    # ---------------------------------------------------------
    # 4. Remove Super Admin access from ordinary application
    # ---------------------------------------------------------

    sa_tables = (
        "super_admins",
        "super_admin_audit_logs",
        "super_admin_mfa_challenges",
        "super_admin_mfa_recovery_codes",
        "super_admin_used_totp_codes",
    )

    for table in sa_tables:
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM m369_app, PUBLIC"
        )

    op.execute(
        "REVOKE ALL PRIVILEGES ON SEQUENCE super_admin_audit_logs_id_seq "
        "FROM m369_app, PUBLIC"
    )

    # ---------------------------------------------------------
    # 5. Minimum required privileges for m369_sa_auth
    # ---------------------------------------------------------

    # Authentication needs to read the SuperAdmin identity (full row SELECT)
    op.execute("GRANT SELECT ON TABLE super_admins TO m369_sa_auth")

    # UPDATE restricted to columns actually changed by login/MFA services
    op.execute("""
        GRANT UPDATE (
            failed_login_attempts,
            last_failed_login_at,
            failed_mfa_attempts,
            locked_until,
            last_login_at
        )
        ON TABLE super_admins
        TO m369_sa_auth
    """)

    # Audit writes — INSERT + SELECT(id) for RETURNING
    op.execute("GRANT INSERT ON TABLE super_admin_audit_logs TO m369_sa_auth")
    op.execute("GRANT SELECT (id) ON TABLE super_admin_audit_logs TO m369_sa_auth")
    op.execute("GRANT USAGE ON SEQUENCE super_admin_audit_logs_id_seq TO m369_sa_auth")

    # MFA tables — full CRUD (challenge issue/consume, recovery, TOTP replay)
    for table in (
        "super_admin_mfa_challenges",
        "super_admin_mfa_recovery_codes",
        "super_admin_used_totp_codes",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO m369_sa_auth")

    # IMPORTANT: m369_sa_auth has NO privileges on:
    # agencies, users, workspaces, conversations, messages, attachments,
    # payments, subscriptions, plans, platform_settings, agency_notes, etc.
    # It is NOT BYPASSRLS — RLS applies (but super_admins has no RLS policy,
    # so all rows are visible, which is correct for a global identity table).


def downgrade() -> None:
    # Revoke ALL privileges before dropping the role
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM m369_sa_auth")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM m369_sa_auth")
    op.execute("REVOKE ALL PRIVILEGES ON SCHEMA public FROM m369_sa_auth")
    op.execute("DROP ROLE IF EXISTS m369_sa_auth")

    # Restore m369_app privileges on SA tables (pre-0012 state)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE super_admins TO m369_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE super_admin_audit_logs TO m369_app")
    for table in (
        "super_admin_mfa_challenges",
        "super_admin_mfa_recovery_codes",
        "super_admin_used_totp_codes",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO m369_app")
    op.execute("GRANT USAGE ON SEQUENCE super_admin_audit_logs_id_seq TO m369_app")

    # Restore original composite FK behavior (ON DELETE SET NULL)
    op.drop_constraint("fk_messages_reply_to_agency", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_reply_to_message", "messages", type_="foreignkey")
    op.create_foreign_key(
        "fk_messages_reply_to_agency",
        "messages",
        "messages",
        ["reply_to_message_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("fk_kb_articles_category_ws_agency", "kb_articles", type_="foreignkey")
    op.create_foreign_key(
        "fk_kb_articles_category_ws_agency",
        "kb_articles",
        "kb_categories",
        ["category_id", "workspace_id", "agency_id"],
        ["id", "workspace_id", "agency_id"],
        ondelete="SET NULL",
    )

    # NOTE: We do NOT narrow alembic_version back to VARCHAR(32) — keeping
    # it at VARCHAR(128) is harmless and avoids a "value too long" error
    # during the intermediate state of the downgrade chain.
