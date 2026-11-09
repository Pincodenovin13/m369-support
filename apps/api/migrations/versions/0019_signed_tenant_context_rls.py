"""Replace forgeable tenant GUC policies with database-verified HMAC context."""
from __future__ import annotations
import os
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0019_signed_tenant_context_rls"
down_revision: Union[str, None] = "0018_workspace_agency_fks_contacts_teams"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = (
    "agencies", "workspaces", "agency_memberships", "teams", "team_memberships",
    "contacts", "conversations", "audit_logs", "subscriptions", "message_attachments",
    "channels", "kb_categories", "kb_articles", "canned_responses", "payments", "messages",
)

def upgrade() -> None:
    secret = os.environ.get("M369_TENANT_CONTEXT_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("M369_TENANT_CONTEXT_SECRET must be at least 32 UTF-8 bytes")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
    extension_schema = op.get_bind().execute(sa.text(
        "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='pgcrypto'"
    )).scalar_one()
    if extension_schema != "public":
        op.execute("ALTER EXTENSION pgcrypto SET SCHEMA public")
    op.execute("""
      DO $ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='m369_tenant_context') THEN
          CREATE ROLE m369_tenant_context NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
        END IF;
      END $;
    """)
    # Enforce the verifier owner role's attributes even if it pre-existed.
    op.execute("ALTER ROLE m369_tenant_context NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT")
    # A stale membership in either direction could make SET ROLE or inherited
    # privileges possible. Remove every membership involving this role.
    op.execute("""
      DO $
      DECLARE m record;
      BEGIN
        FOR m IN
          SELECT parent.rolname AS granted_role, member.rolname AS member_role
          FROM pg_auth_members am
          JOIN pg_roles parent ON parent.oid = am.roleid
          JOIN pg_roles member ON member.oid = am.member
          WHERE parent.rolname = 'm369_tenant_context'
             OR member.rolname = 'm369_tenant_context'
        LOOP
          EXECUTE format('REVOKE %I FROM %I', m.granted_role, m.member_role);
        END LOOP;
      END $;
    """)
    op.execute("CREATE SCHEMA m369_private AUTHORIZATION postgres")
    op.execute("REVOKE ALL ON SCHEMA m369_private FROM PUBLIC, m369_app")
    op.execute("GRANT USAGE ON SCHEMA public TO m369_tenant_context")
    op.execute("GRANT USAGE ON SCHEMA m369_private TO m369_tenant_context")
    op.execute("""
      CREATE TABLE m369_private.tenant_context_secret (
        singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
        secret bytea NOT NULL CHECK (octet_length(secret) >= 32),
        created_at timestamptz NOT NULL DEFAULT now()
      )
    """)
    op.execute("REVOKE ALL ON m369_private.tenant_context_secret FROM PUBLIC, m369_app")
    op.execute("GRANT SELECT ON m369_private.tenant_context_secret TO m369_tenant_context")
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO m369_private.tenant_context_secret(singleton,secret) VALUES(true,convert_to(:s,'UTF8')) ON CONFLICT(singleton) DO NOTHING"), {"s": secret})
    match = bind.execute(sa.text("SELECT secret=convert_to(:s,'UTF8') FROM m369_private.tenant_context_secret WHERE singleton=true"), {"s": secret}).scalar_one()
    if not match:
        raise RuntimeError("M369_TENANT_CONTEXT_SECRET mismatch with database-provisioned key")
    op.execute("""
      CREATE FUNCTION public.m369_current_tenant_id() RETURNS uuid
      LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog
      AS $$
      DECLARE v_id text; v_sig text; v_secret bytea; v_expected bytea;
      BEGIN
        v_id := pg_catalog.current_setting('app.tenant_id',true);
        v_sig := pg_catalog.current_setting('app.tenant_sig',true);
        IF v_id IS NULL OR v_id='' OR v_sig IS NULL OR v_sig !~ '^[0-9a-f]{64}$'
           OR v_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           OR v_id <> lower(v_id) THEN RETURN NULL; END IF;
        SELECT secret INTO v_secret FROM m369_private.tenant_context_secret WHERE singleton=true;
        IF v_secret IS NULL THEN RETURN NULL; END IF;
        v_expected := public.hmac(pg_catalog.convert_to('m369:tenant:v1:'||v_id,'UTF8'),v_secret,'sha256');
        IF v_expected IS DISTINCT FROM pg_catalog.decode(v_sig,'hex') THEN RETURN NULL; END IF;
        RETURN v_id::uuid;
      EXCEPTION WHEN OTHERS THEN RETURN NULL;
      END $$;
    """)
    op.execute("ALTER FUNCTION public.m369_current_tenant_id() OWNER TO m369_tenant_context")
    op.execute("REVOKE ALL ON FUNCTION public.m369_current_tenant_id() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.m369_current_tenant_id() TO m369_app")
    for table in TENANT_TABLES:
        op.execute(sa.text(f'DROP POLICY IF EXISTS tenant_isolation_{table} ON public.{table}'))
        col = "id" if table == "agencies" else "agency_id"
        op.execute(sa.text(f'CREATE POLICY tenant_isolation_{table} ON public.{table} USING ({col}=public.m369_current_tenant_id()) WITH CHECK ({col}=public.m369_current_tenant_id())'))
        op.execute(sa.text(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY'))
    # Keep platform-private notes policy deny-all, explicitly confirm it remains.
    op.execute("DROP POLICY IF EXISTS agency_notes_platform_private ON public.agency_notes")
    op.execute("CREATE POLICY agency_notes_platform_private ON public.agency_notes USING(false) WITH CHECK(false)")
    # Fail migration if an unexpected permissive policy could OR-bypass RLS.
    op.execute("""
      DO $
      DECLARE t text; policy_count integer;
      BEGIN
        FOREACH t IN ARRAY ARRAY[
          'agencies','workspaces','agency_memberships','teams','team_memberships',
          'contacts','conversations','audit_logs','subscriptions','message_attachments',
          'channels','kb_categories','kb_articles','canned_responses','payments','messages',
          'agency_notes'
        ] LOOP
          SELECT count(*) INTO policy_count
          FROM pg_policy p
          JOIN pg_class c ON c.oid=p.polrelid
          JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='public' AND c.relname=t;
          IF policy_count <> 1 THEN
            RAISE EXCEPTION 'RLS policy invariant failed for %. Expected exactly one policy, found %', t, policy_count;
          END IF;
        END LOOP;
      END $;
    """)
    op.execute("REVOKE CREATE ON SCHEMA public FROM m369_app")

def downgrade() -> None:
    raise RuntimeError("Unsafe downgrade refused: unsigned tenant GUC policies must never be restored")
