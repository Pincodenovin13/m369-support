"""RLS signed tenant context adversarial regression tests."""
from __future__ import annotations
import uuid
import psycopg
import pytest
from app.tenancy.context import tenant_context_signature
APP_DB_URL = "postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test"
pytestmark = [pytest.mark.security, pytest.mark.integration]

def test_unsigned_and_forged_context_fail_closed():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(APP_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (a,))
            cur.execute("SELECT public.m369_current_tenant_id()")
            assert cur.fetchone()[0] is None
            cur.execute("SELECT set_config('app.tenant_sig', %s, true)", (tenant_context_signature(a),))
            cur.execute("SELECT public.m369_current_tenant_id()")
            assert cur.fetchone()[0] == uuid.UUID(a)
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (b,))
            cur.execute("SELECT public.m369_current_tenant_id()")
            assert cur.fetchone()[0] is None

def test_all_tenant_tables_have_force_rls_and_signed_policy():
    tables = ["agencies","workspaces","agency_memberships","teams","team_memberships","contacts","conversations","audit_logs","subscriptions","message_attachments","channels","kb_categories","kb_articles","canned_responses","payments","messages"]
    with psycopg.connect(APP_DB_URL) as conn:
        with conn.cursor() as cur:
            for table in tables:
                cur.execute("SELECT c.relrowsecurity,c.relforcerowsecurity,pg_get_expr(p.polqual,p.polrelid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_policy p ON p.polrelid=c.oid AND p.polname=%s WHERE n.nspname='public' AND c.relname=%s", (f"tenant_isolation_{table}",table))
                row = cur.fetchone()
                assert row and row[0] and row[1], f"{table} missing ENABLE/FORCE RLS"
                assert row[2] and "m369_current_tenant_id" in row[2], f"{table} not protected by verifier"
