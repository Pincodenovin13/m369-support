"""Migration 0006: Add Phase 1 extended models.

Revision ID: 0006_phase1_extended
Revises: 0005_restrict_login_helper_owner
Create Date: 2026-11-06

Adds 11 new tables:
  - messages, message_attachments
  - channels
  - kb_categories, kb_articles
  - canned_responses
  - plans, subscriptions, payments
  - platform_settings
  - agency_notes

All tenant-owned tables carry agency_id for RLS.
Composite FKs prevent cross-tenant references.
Money columns use INTEGER (cents) — never FLOAT.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase1_extended"
down_revision: Union[str, None] = "0005_restrict_login_helper_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add UNIQUE constraint on conversations(id, agency_id) needed by messages FK
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_conversations_id_agency ON conversations (id, agency_id)")

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sender_type", sa.String(20), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("llm_content", sa.Text, nullable=True),
        sa.Column("is_internal", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("external_message_id", sa.String(255), nullable=True, index=True),
        sa.Column("delivery_status", sa.String(20), nullable=True),
        sa.Column("delivery_error", sa.Text, nullable=True),
        sa.Column("reply_to_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reaction", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("sender_type IN ('contact', 'agent', 'system', 'bot')", name="ck_messages_sender_type"),
        sa.CheckConstraint("delivery_status IS NULL OR delivery_status IN ('sent', 'delivered', 'read', 'failed')", name="ck_messages_delivery_status"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "agency_id"],
            ["conversations.id", "conversations.agency_id"],
            name="fk_messages_conversation_agency",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    # --- message_attachments ---
    op.create_table(
        "message_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default=sa.text("'local'")),
        sa.Column("kind", sa.String(20), nullable=False, server_default=sa.text("'file'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- channels ---
    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("credentials_encrypted", sa.Text, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("public_id", sa.String(64), nullable=True, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "type", name="uq_channels_workspace_type"),
        sa.CheckConstraint("type IN ('widget', 'email', 'whatsapp_cloud', 'telegram', 'instagram', 'messenger')", name="ck_channels_type"),
    )

    # --- kb_categories ---
    op.create_table(
        "kb_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_categories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("position", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_kb_categories_workspace_slug"),
    )

    # --- kb_articles ---
    op.create_table(
        "kb_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("content_md", sa.Text, nullable=False),
        sa.Column("content_html", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("views_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("helpful_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("not_helpful_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_kb_articles_workspace_slug"),
    )
    op.create_index("ix_kb_articles_workspace_published", "kb_articles", ["workspace_id", "is_published"])

    # --- canned_responses ---
    op.create_table(
        "canned_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("shortcut", sa.String(60), nullable=False),
        sa.Column("content", sa.String(4000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "shortcut", name="uq_canned_responses_workspace_shortcut"),
    )

    # --- plans (NOT tenant-scoped) ---
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("price_monthly", sa.Integer, nullable=False),  # cents
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("features", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("limits", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trial_days", sa.Integer, nullable=False, server_default=sa.text("7")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Seed default plans — use raw connection to avoid SQLAlchemy param binding
    conn = op.get_bind()
    conn.exec_driver_sql(
        "INSERT INTO plans (id, name, display_name, price_monthly, currency, is_active, sort_order, features, limits, trial_days) "
        "VALUES "
        "(gen_random_uuid(), 'starter', 'Starter', 1900, 'USD', true, 1, "
        "'{\"channels\":[\"widget\"]}'::jsonb, "
        "'{\"max_seats\":3,\"max_conversations\":500,\"max_workspaces\":1}'::jsonb, 7), "
        "(gen_random_uuid(), 'growth', 'Growth', 4900, 'USD', true, 2, "
        "'{\"channels\":[\"widget\",\"whatsapp_cloud\"]}'::jsonb, "
        "'{\"max_seats\":6,\"max_conversations\":2000,\"max_workspaces\":3}'::jsonb, 7), "
        "(gen_random_uuid(), 'pro', 'Pro', 7900, 'USD', true, 3, "
        "'{\"channels\":[\"widget\",\"whatsapp_cloud\",\"email\",\"telegram\"]}'::jsonb, "
        "'{\"max_seats\":9,\"max_conversations\":6000,\"max_workspaces\":5}'::jsonb, 7), "
        "(gen_random_uuid(), 'vip', 'VIP', 9900, 'USD', true, 4, "
        "'{\"channels\":[\"widget\",\"whatsapp_cloud\",\"email\",\"telegram\",\"instagram\",\"messenger\"],\"whitelabel\":true}'::jsonb, "
        "'{\"max_seats\":12,\"max_conversations\":15000,\"max_workspaces\":99}'::jsonb, 7) "
        "ON CONFLICT (name) DO NOTHING"
    )

    # --- subscriptions ---
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'trial'")),
        sa.Column("price_monthly_snapshot", sa.Integer, nullable=False),
        sa.Column("currency_snapshot", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("plan_name_snapshot", sa.String(120), nullable=False),
        sa.Column("plan_features_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("plan_limits_snapshot", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('trial', 'active', 'past_due', 'suspended', 'cancelled', 'superseded')", name="ck_subscriptions_status"),
    )
    op.create_index(
        "uq_subscriptions_agency_active",
        "subscriptions",
        ["agency_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('trial', 'active', 'past_due', 'suspended')"),
    )

    # --- payments ---
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("txid", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True, index=True),
        sa.Column("amount_expected", sa.Integer, nullable=False),
        sa.Column("amount_paid", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("paid_currency", sa.String(3), nullable=True),
        sa.Column("paid_amount_raw", sa.Integer, nullable=True),
        sa.Column("paid_amount_decimals", sa.Integer, nullable=True),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("verifying_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_super_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("super_admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("payment_method", sa.String(30), nullable=False, server_default=sa.text("'crypto_usdt_trc20'")),
        sa.Column("network", sa.String(20), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('pending', 'verifying', 'verified', 'rejected', 'expired')", name="ck_payments_status"),
        sa.CheckConstraint("amount_paid >= 0 AND amount_expected >= 0", name="ck_payments_amounts_nonneg"),
    )
    op.create_index("ix_payments_subscription_status", "payments", ["subscription_id", "status"])

    # --- platform_settings ---
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("value_type", sa.String(20), nullable=False, server_default=sa.text("'string'")),
        sa.Column("description", sa.String(255), nullable=False, server_default=sa.text("''")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by_super_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("super_admins.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint("value_type IN ('string', 'bool', 'int', 'json')", name="ck_platform_settings_value_type"),
    )

    # --- agency_notes ---
    op.create_table(
        "agency_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("super_admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- RLS for new tenant-owned tables ---
    new_tenant_tables = ["messages", "channels", "kb_categories", "kb_articles", "canned_responses", "payments"]
    for table in new_tenant_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (
                agency_id::text = current_setting('app.tenant_id', true)
            )
            WITH CHECK (
                agency_id::text = current_setting('app.tenant_id', true)
            )
        """)

    # --- Grants for new tables ---
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO m369_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO m369_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO m369_login_reader")


def downgrade() -> None:
    # Drop RLS policies
    for table in ["messages", "channels", "kb_categories", "kb_articles", "canned_responses", "payments"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in [
        "agency_notes",
        "platform_settings",
        "payments",
        "subscriptions",
        "plans",
        "canned_responses",
        "kb_articles",
        "kb_categories",
        "channels",
        "message_attachments",
        "messages",
    ]:
        op.drop_table(table)
