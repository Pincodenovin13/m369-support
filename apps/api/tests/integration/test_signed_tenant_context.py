"""Adversarial verification of signed tenant-context RLS on PostgreSQL."""
from __future__ import annotations

import uuid

import psycopg
import pytest
from sqlalchemy import text

from app.tenancy.context import tenant_context_signature

APP_DB_URL = "postgresql://m369_app:m369_app_dev_password@localhost:5432/m369_support_test"
pytestmark = [pytest.mark.security, pytest.mark.integration]

TENANT_TABLES = [
    "agencies", "workspaces", "agency_memberships", "teams", "team_memberships",
    "contacts", "conversations", "audit_logs", "subscriptions", "message_attachments",
    "channels", "kb_categories", "kb_articles", "canned_responses", "payments", "messages",
]


def test_unsigned_and_tampered_tenant_gucs_fail_closed(db_engine, setup_session):
    agency_a, agency_b = uuid.uuid4(), uuid.uuid4()
    setup_session.execute(
        text("INSERT INTO agencies (id,name,slug,brand_color,is_active) "
             "VALUES (:id,:name,:slug,'#123456',true)"),
        [
            {"id": agency_a, "name": "RLS A", "slug": f"rls-a-{agency_a.hex}"},
            {"id": agency_b, "name": "RLS B", "slug": f"rls-b-{agency_b.hex}"},
        ],
    )
    setup_session.commit()

    with psycopg.connect(APP_DB_URL) as conn:
        with conn.cursor() as cur:
            # Raw, unsigned GUC must expose no tenant rows.
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (str(agency_a),))
            cur.execute("SELECT id FROM agencies WHERE id IN (%s,%s)", (agency_a, agency_b))
            assert cur.fetchall() == []

            # Correctly signed tenant A sees A and never B.
            cur.execute("SELECT set_config('app.tenant_sig', %s, true)", (tenant_context_signature(agency_a),))
            cur.execute("SELECT id FROM agencies WHERE id IN (%s,%s)", (agency_a, agency_b))
            assert [row[0] for row in cur.fetchall()] == [agency_a]

            # Changing only the tenant ID while retaining A's signature fails closed.
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (str(agency_b),))
            cur.execute("SELECT id FROM agencies WHERE id IN (%s,%s)", (agency_a, agency_b))
            assert cur.fetchall() == []

            # A syntactically valid but forged signature also fails closed.
            cur.execute("SELECT set_config('app.tenant_sig', %s, true)", ("0" * 64,))
            cur.execute("SELECT public.m369_current_tenant_id()")
            assert cur.fetchone()[0] is None
        conn.rollback()


def test_every_tenant_table_has_one_forced_signed_policy(db_engine):
    with psycopg.connect(APP_DB_URL) as conn:
        with conn.cursor() as cur:
            for table in TENANT_TABLES:
                cur.execute(
                    "SELECT c.relrowsecurity, c.relforcerowsecurity, count(p.oid), "
                    "bool_and(pg_get_expr(p.polqual,p.polrelid) LIKE '%%m369_current_tenant_id%%'), "
                    "bool_and(pg_get_expr(p.polwithcheck,p.polrelid) LIKE '%%m369_current_tenant_id%%'), "
                    "bool_and(p.polcmd='*') "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "LEFT JOIN pg_policy p ON p.polrelid=c.oid "
                    "WHERE n.nspname='public' AND c.relname=%s "
                    "GROUP BY c.oid,c.relrowsecurity,c.relforcerowsecurity",
                    (table,),
                )
                row = cur.fetchone()
                assert row is not None, f"{table} missing"
                assert row[0] and row[1], f"{table} missing ENABLE/FORCE RLS"
                assert row[2] == 1, f"{table} has unexpected additional or missing policies"
                assert row[3] and row[4] and row[5], f"{table} policy is not signed in USING and WITH CHECK"


def test_platform_private_agency_notes_remains_deny_all(db_engine):
    with psycopg.connect(APP_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_get_expr(polqual,polrelid),pg_get_expr(polwithcheck,polrelid) "
                "FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relname='agency_notes'"
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == "false" and rows[0][1] == "false"


def test_runtime_cannot_read_private_hmac_secret(db_engine):
    with psycopg.connect(APP_DB_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("SELECT secret FROM m369_private.tenant_context_secret")
            conn.rollback()


def test_verifier_role_and_function_are_least_privilege(db_engine):
    with psycopg.connect(APP_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication,rolinherit "
                "FROM pg_roles WHERE rolname='m369_tenant_context'"
            )
            assert cur.fetchone() == (False, False, False, False, False, False, False)
            cur.execute(
                "SELECT pg_has_role('m369_app','m369_tenant_context','MEMBER'), "
                "pg_has_role('m369_tenant_context','m369_app','MEMBER'), "
                "has_schema_privilege('m369_app','m369_private','USAGE'), "
                "has_function_privilege('m369_app','public.m369_current_tenant_id()','EXECUTE')"
            )
            assert cur.fetchone() == (False, False, False, True)
            cur.execute(
                "SELECT r.rolname,p.prosecdef,p.proconfig, "
                "EXISTS (SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
                "WHERE a.grantee=0 AND a.privilege_type='EXECUTE') "
                "FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner "
                "WHERE p.oid='public.m369_current_tenant_id()'::regprocedure"
            )
            owner, security_definer, config, public_execute = cur.fetchone()
            assert owner == "m369_tenant_context"
            assert security_definer is True
            assert "search_path=pg_catalog" in config
            assert public_execute is False
