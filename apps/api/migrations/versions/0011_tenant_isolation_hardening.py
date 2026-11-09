"""Migration 0011: Database tenant isolation & least-privilege hardening.

Package B — completes the database security layer:

  1. message_attachments: add agency_id column + backfill from messages +
     NOT NULL + composite FK (message_id, agency_id) → messages(id, agency_id)
  2. Composite FKs for workspace/agency relationships on:
     channels, kb_categories, kb_articles, canned_responses, conversations,
     payments, messages (reply_to), message_attachments
  3. RLS enabled + forced on:
     subscriptions, message_attachments, agency_notes
  4. agency_notes: platform-private — RLS policy USING (false) so m369_app
     (which does NOT have BYPASSRLS) can never see rows. m369_sa_runner
     (BYPASSRLS) can still access them via the Super Admin engine.
  5. Restrict m369_sa_runner from ALL TABLES → grant only the specific
     tables + privileges each Super Admin endpoint actually needs.
  6. Restrict m369_app:
     - REVOKE ALL on agency_notes (platform-private, never visible to agency users)
     - REVOKE INSERT/UPDATE/DELETE on plans (agency portal only reads plans)
     - REVOKE ALL on super_admins, super_admin_audit_logs, platform_settings
       EXCEPT what the login flow genuinely needs (super_admins SELECT/UPDATE
       for password verify + counter updates; super_admin_audit_logs INSERT
       for audit; MFA tables for login/verify flow; platform_settings is
       Super-Admin-only so fully revoked)

  This migration does NOT drop or recreate any existing table. Existing
  data is preserved. All constraint additions are preceded by data
  validation — if orphan/mismatched rows exist, the migration raises
  an exception and aborts rather than silently corrupting data.

  down_revision = 0010_sa_auth_hardening
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0011_tenant_isolation_hardening"
down_revision: Union[str, None] = "0010_sa_auth_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===================================================================
    # 1. message_attachments: add agency_id + backfill + NOT NULL + FK
    # ===================================================================

    # 1a. Add agency_id as nullable first (so backfill can populate it)
    op.add_column(
        "message_attachments",
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 1b. Backfill from messages
    op.execute("""
        UPDATE message_attachments AS a
        SET agency_id = m.agency_id
        FROM messages AS m
        WHERE m.id = a.message_id
          AND a.agency_id IS NULL
    """)

    # 1c. Validate: no orphan rows remaining
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM message_attachments WHERE agency_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: message_attachments contains orphan rows '
                    'with no matching message_id in messages';
            END IF;
        END $$;
    """)

    # 1d. Set NOT NULL
    op.alter_column(
        "message_attachments",
        "agency_id",
        nullable=False,
    )

    # 1e. Add FK agency_id → agencies(id) ON DELETE RESTRICT
    op.create_foreign_key(
        "fk_message_attachments_agency",
        "message_attachments",
        "agencies",
        ["agency_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 1f. Add index on agency_id for RLS performance
    op.create_index(
        "ix_message_attachments_agency_id",
        "message_attachments",
        ["agency_id"],
    )

    # ===================================================================
    # 2. Composite FKs — unique indexes on parent tables first
    # ===================================================================

    # 2a. Unique indexes needed as FK targets
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_workspaces_id_agency
        ON workspaces(id, agency_id)
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_categories_id_workspace_agency
        ON kb_categories(id, workspace_id, agency_id)
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_id_agency
        ON subscriptions(id, agency_id)
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_id_agency
        ON messages(id, agency_id)
    """)

    # ===================================================================
    # 2b. Composite FKs — validate data before adding
    # ===================================================================

    # Validate channels: every (workspace_id, agency_id) must match a workspace
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM channels c
                LEFT JOIN workspaces w ON w.id = c.workspace_id AND w.agency_id = c.agency_id
                WHERE w.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: channels contains rows where (workspace_id, agency_id) does not match any workspace';
            END IF;
        END $$;
    """)

    # Validate kb_categories: (workspace_id, agency_id) must match workspace
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM kb_categories k
                LEFT JOIN workspaces w ON w.id = k.workspace_id AND w.agency_id = k.agency_id
                WHERE w.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: kb_categories contains rows where (workspace_id, agency_id) does not match any workspace';
            END IF;
        END $$;
    """)

    # Validate kb_categories parent: if parent_id is set, (parent_id, workspace_id, agency_id) must match another kb_category
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM kb_categories k
                WHERE k.parent_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM kb_categories p
                      WHERE p.id = k.parent_id
                        AND p.workspace_id = k.workspace_id
                        AND p.agency_id = k.agency_id
                  )
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: kb_categories contains parent_id references that cross workspace/agency boundaries';
            END IF;
        END $$;
    """)

    # Validate kb_articles: (workspace_id, agency_id) must match workspace
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM kb_articles a
                LEFT JOIN workspaces w ON w.id = a.workspace_id AND w.agency_id = a.agency_id
                WHERE w.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: kb_articles contains rows where (workspace_id, agency_id) does not match any workspace';
            END IF;
        END $$;
    """)

    # Validate kb_articles category: if category_id is set, (category_id, workspace_id, agency_id) must match
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM kb_articles a
                WHERE a.category_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM kb_categories c
                      WHERE c.id = a.category_id
                        AND c.workspace_id = a.workspace_id
                        AND c.agency_id = a.agency_id
                  )
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: kb_articles contains category_id references that cross workspace/agency boundaries';
            END IF;
        END $$;
    """)

    # Validate canned_responses: (workspace_id, agency_id) must match workspace
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM canned_responses cr
                LEFT JOIN workspaces w ON w.id = cr.workspace_id AND w.agency_id = cr.agency_id
                WHERE w.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: canned_responses contains rows where (workspace_id, agency_id) does not match any workspace';
            END IF;
        END $$;
    """)

    # Validate conversations: (workspace_id, agency_id) must match workspace
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM conversations cv
                LEFT JOIN workspaces w ON w.id = cv.workspace_id AND w.agency_id = cv.agency_id
                WHERE w.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: conversations contains rows where (workspace_id, agency_id) does not match any workspace';
            END IF;
        END $$;
    """)

    # Validate payments: (subscription_id, agency_id) must match subscription
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM payments p
                LEFT JOIN subscriptions s ON s.id = p.subscription_id AND s.agency_id = p.agency_id
                WHERE s.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: payments contains rows where (subscription_id, agency_id) does not match any subscription';
            END IF;
        END $$;
    """)

    # Validate messages reply_to: if reply_to_message_id is set, (reply_to_message_id, agency_id) must match
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM messages m
                WHERE m.reply_to_message_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM messages p
                      WHERE p.id = m.reply_to_message_id
                        AND p.agency_id = m.agency_id
                  )
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: messages contains reply_to_message_id references that cross agency boundaries';
            END IF;
        END $$;
    """)

    # Validate message_attachments: (message_id, agency_id) must match message
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM message_attachments a
                LEFT JOIN messages m ON m.id = a.message_id AND m.agency_id = a.agency_id
                WHERE m.id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Migration 0011 blocked: message_attachments contains rows where (message_id, agency_id) does not match any message';
            END IF;
        END $$;
    """)

    # ===================================================================
    # 2c. Add composite FKs
    # ===================================================================

    # channels → workspaces(id, agency_id)
    op.create_foreign_key(
        "fk_channels_workspace_agency",
        "channels",
        "workspaces",
        ["workspace_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )

    # kb_categories → workspaces(id, agency_id)
    op.create_foreign_key(
        "fk_kb_categories_workspace_agency",
        "kb_categories",
        "workspaces",
        ["workspace_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )

    # kb_categories self-reference: (parent_id, workspace_id, agency_id) → kb_categories(id, workspace_id, agency_id)
    op.create_foreign_key(
        "fk_kb_categories_parent_ws_agency",
        "kb_categories",
        "kb_categories",
        ["parent_id", "workspace_id", "agency_id"],
        ["id", "workspace_id", "agency_id"],
        ondelete="CASCADE",
    )

    # kb_articles → workspaces(id, agency_id)
    op.create_foreign_key(
        "fk_kb_articles_workspace_agency",
        "kb_articles",
        "workspaces",
        ["workspace_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )

    # kb_articles → kb_categories(id, workspace_id, agency_id)
    op.create_foreign_key(
        "fk_kb_articles_category_ws_agency",
        "kb_articles",
        "kb_categories",
        ["category_id", "workspace_id", "agency_id"],
        ["id", "workspace_id", "agency_id"],
        ondelete="SET NULL",
    )

    # canned_responses → workspaces(id, agency_id)
    op.create_foreign_key(
        "fk_canned_responses_workspace_agency",
        "canned_responses",
        "workspaces",
        ["workspace_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )

    # conversations → workspaces(id, agency_id)
    op.create_foreign_key(
        "fk_conversations_workspace_agency",
        "conversations",
        "workspaces",
        ["workspace_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )

    # payments → subscriptions(id, agency_id)
    op.create_foreign_key(
        "fk_payments_subscription_agency",
        "payments",
        "subscriptions",
        ["subscription_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="RESTRICT",
    )

    # messages self-reference: (reply_to_message_id, agency_id) → messages(id, agency_id)
    op.create_foreign_key(
        "fk_messages_reply_to_agency",
        "messages",
        "messages",
        ["reply_to_message_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="SET NULL",
    )

    # message_attachments → messages(id, agency_id) — composite
    # The old simple FK on message_id → messages(id) still exists and is
    # fine to keep (it's a subset of the composite). The composite adds
    # the cross-tenant protection.
    op.create_foreign_key(
        "fk_message_attachments_message_agency",
        "message_attachments",
        "messages",
        ["message_id", "agency_id"],
        ["id", "agency_id"],
        ondelete="CASCADE",
    )

    # ===================================================================
    # 3. RLS on subscriptions, message_attachments, agency_notes
    # ===================================================================

    # 3a. subscriptions — tenant-owned
    op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_subscriptions
        ON subscriptions
        USING (
            agency_id::text = current_setting('app.tenant_id', true)
        )
        WITH CHECK (
            agency_id::text = current_setting('app.tenant_id', true)
        )
    """)

    # 3b. message_attachments — tenant-owned (now that agency_id exists)
    op.execute("ALTER TABLE message_attachments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE message_attachments FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_message_attachments
        ON message_attachments
        USING (
            agency_id::text = current_setting('app.tenant_id', true)
        )
        WITH CHECK (
            agency_id::text = current_setting('app.tenant_id', true)
        )
    """)

    # 3c. agency_notes — platform-private
    # USING (false) means NO row is ever visible to roles subject to RLS
    # (i.e., m369_app). m369_sa_runner has BYPASSRLS so it can still
    # access rows via the Super Admin engine. This is defense-in-depth:
    # even if m369_app somehow gets a table-level GRANT, RLS blocks it.
    op.execute("ALTER TABLE agency_notes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agency_notes FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY agency_notes_platform_private
        ON agency_notes
        USING (false)
        WITH CHECK (false)
    """)

    # ===================================================================
    # 4. Restrict m369_sa_runner — least privilege
    # ===================================================================

    # 4a. Revoke ALL previous grants
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM m369_sa_runner")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM m369_sa_runner")
    # Also revoke CREATE on the schema itself — m369_sa_runner should NOT
    # be able to CREATE TABLE, CREATE INDEX, etc. It only needs CRUD on
    # existing tables, never DDL.
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_sa_runner")
    # Keep USAGE so it can resolve table names
    op.execute("GRANT USAGE ON SCHEMA public TO m369_sa_runner")

    # 4b. Revoke default privileges (set by migration 0008)
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        REVOKE ALL ON TABLES FROM m369_sa_runner
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        REVOKE ALL ON SEQUENCES FROM m369_sa_runner
    """)

    # 4c. Grant only what Super Admin endpoints actually need.
    #
    # Endpoint analysis (verified by reading every router in super_admin/):
    #
    #   auth.py (login, verify-mfa, logout, /me, mfa setup/enable/disable):
    #     - super_admins: SELECT (lookup), UPDATE (counters, token_version, mfa)
    #     - super_admin_audit_logs: SELECT (none), INSERT (audit writes)
    #     - super_admin_mfa_challenges: SELECT, INSERT, UPDATE, DELETE
    #     - super_admin_mfa_recovery_codes: SELECT, INSERT, UPDATE, DELETE
    #     - super_admin_used_totp_codes: SELECT, INSERT, DELETE
    #
    #   agencies.py (list, get, update, suspend, activate, members):
    #     - agencies: SELECT, UPDATE (suspend/activate/name)
    #     - agency_memberships: SELECT (list members), UPDATE (role change)
    #     - users: SELECT (member email/name lookup)
    #
    #   plans.py (list, create, update):
    #     - plans: SELECT, INSERT, UPDATE
    #
    #   subscriptions.py (list, get, update status):
    #     - subscriptions: SELECT, UPDATE
    #
    #   payments.py (list, get, verify, reject):
    #     - payments: SELECT, UPDATE
    #     - subscriptions: SELECT (verify reads subscription)
    #
    #   settings_notes_audit.py (settings CRUD, notes CRUD, audit log read):
    #     - platform_settings: SELECT, INSERT, UPDATE, DELETE
    #     - agency_notes: SELECT, INSERT, UPDATE, DELETE
    #     - super_admin_audit_logs: SELECT (read SA audit log), INSERT (write)
    #
    # NOTE: login + verify-mfa use get_db (m369_app), NOT get_super_admin_db.
    # So the MFA tables are accessed by BOTH m369_app AND m369_sa_runner.
    # m369_sa_runner needs them for mfa/disable (which reads recovery codes
    # + TOTP verify + deletes challenges).

    # Super Admin identity + auth tables
    op.execute("GRANT SELECT, UPDATE ON super_admins TO m369_sa_runner")
    op.execute("GRANT SELECT, INSERT ON super_admin_audit_logs TO m369_sa_runner")
    # USAGE on the sequence needed for INSERT into super_admin_audit_logs (serial id)
    op.execute("GRANT USAGE, SELECT ON SEQUENCE super_admin_audit_logs_id_seq TO m369_sa_runner")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_mfa_challenges TO m369_sa_runner")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON super_admin_mfa_recovery_codes TO m369_sa_runner")
    op.execute("GRANT SELECT, INSERT, DELETE ON super_admin_used_totp_codes TO m369_sa_runner")

    # Agency management
    op.execute("GRANT SELECT, UPDATE ON agencies TO m369_sa_runner")
    op.execute("GRANT SELECT, UPDATE ON agency_memberships TO m369_sa_runner")
    op.execute("GRANT SELECT ON users TO m369_sa_runner")

    # Billing
    op.execute("GRANT SELECT, INSERT, UPDATE ON plans TO m369_sa_runner")
    op.execute("GRANT SELECT, UPDATE ON subscriptions TO m369_sa_runner")
    op.execute("GRANT SELECT, UPDATE ON payments TO m369_sa_runner")

    # Platform settings + agency notes
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON platform_settings TO m369_sa_runner")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON agency_notes TO m369_sa_runner")

    # ===================================================================
    # 5. Restrict m369_app — platform tables
    # ===================================================================

    # 5a. agency_notes — m369_app must NEVER access (platform-private)
    op.execute("REVOKE ALL PRIVILEGES ON agency_notes FROM m369_app")

    # 5b. platform_settings — Super Admin only; m369_app has no endpoint for it
    op.execute("REVOKE ALL PRIVILEGES ON platform_settings FROM m369_app")

    # 5c. plans — agency portal only reads (for subscription display)
    #    Revoke INSERT, UPDATE, DELETE; keep SELECT
    op.execute("REVOKE INSERT, UPDATE, DELETE ON plans FROM m369_app")
    # SELECT on plans remains (granted by the ALL TABLES grant in 0006)

    # 5d. super_admins + super_admin_audit_logs — the login flow (running
    #    on m369_app) needs SELECT + UPDATE on super_admins (password verify,
    #    counter increments, token_version). super_admin_audit_logs needs
    #    INSERT (audit writes from login). These are ALREADY granted by
    #    the ALL TABLES grant in 0006. We do NOT revoke them — doing so
    #    would break login. The RLS on super_admins is NOT enabled (it's a
    #    global table, not tenant-scoped), so m369_app can read all rows.
    #    This is acceptable because super_admins contains only hashed
    #    passwords (Argon2id) — no plaintext, no MFA secrets (those are
    #    in encrypted columns).

    # 5e. MFA tables — login flow (m369_app) needs access:
    #    - super_admin_mfa_challenges: INSERT (issue), SELECT+UPDATE (consume)
    #    - super_admin_mfa_recovery_codes: SELECT (verify), UPDATE (consume)
    #    - super_admin_used_totp_codes: INSERT (replay protection)
    #    These are ALREADY granted by ALL TABLES in 0006. Keep them —
    #    revoking would break login + MFA verify flow.

    # 5f. Ensure m369_app is NOT a member of m369_sa_runner (defense)
    #    (This was verified in Stage 4 tests; we don't need to do anything
    #    here — the membership was never granted.)


def downgrade() -> None:
    # 1. Drop RLS on agency_notes, message_attachments, subscriptions
    op.execute("DROP POLICY IF EXISTS agency_notes_platform_private ON agency_notes")
    op.execute("ALTER TABLE agency_notes NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agency_notes DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_message_attachments ON message_attachments")
    op.execute("ALTER TABLE message_attachments NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE message_attachments DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_subscriptions ON subscriptions")
    op.execute("ALTER TABLE subscriptions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY")

    # 2. Drop composite FKs
    op.drop_constraint("fk_message_attachments_message_agency", "message_attachments", type_="foreignkey")
    op.drop_constraint("fk_messages_reply_to_agency", "messages", type_="foreignkey")
    op.drop_constraint("fk_payments_subscription_agency", "payments", type_="foreignkey")
    op.drop_constraint("fk_conversations_workspace_agency", "conversations", type_="foreignkey")
    op.drop_constraint("fk_canned_responses_workspace_agency", "canned_responses", type_="foreignkey")
    op.drop_constraint("fk_kb_articles_category_ws_agency", "kb_articles", type_="foreignkey")
    op.drop_constraint("fk_kb_articles_workspace_agency", "kb_articles", type_="foreignkey")
    op.drop_constraint("fk_kb_categories_parent_ws_agency", "kb_categories", type_="foreignkey")
    op.drop_constraint("fk_kb_categories_workspace_agency", "kb_categories", type_="foreignkey")
    op.drop_constraint("fk_channels_workspace_agency", "channels", type_="foreignkey")

    # 3. Drop unique indexes created for FK targets
    op.execute("DROP INDEX IF EXISTS uq_messages_id_agency")
    op.execute("DROP INDEX IF EXISTS uq_subscriptions_id_agency")
    op.execute("DROP INDEX IF EXISTS uq_kb_categories_id_workspace_agency")
    op.execute("DROP INDEX IF EXISTS uq_workspaces_id_agency")

    # 4. Drop message_attachments FK to agencies + index + column
    op.drop_constraint("fk_message_attachments_agency", "message_attachments", type_="foreignkey")
    op.drop_index("ix_message_attachments_agency_id", table_name="message_attachments")
    op.drop_column("message_attachments", "agency_id")

    # 5. Restore m369_sa_runner CRUD on all tables (revert to 0008 state)
    op.execute("GRANT ALL ON SCHEMA public TO m369_sa_runner")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO m369_sa_runner")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO m369_sa_runner")
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO m369_sa_runner
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO m369_sa_runner
    """)

    # 6. Restore m369_app full CRUD on all tables (revert plans revocation)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON plans TO m369_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON agency_notes TO m369_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON platform_settings TO m369_app")
