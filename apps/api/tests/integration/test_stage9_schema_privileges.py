"""Database schema privilege regression tests."""
from __future__ import annotations

from sqlalchemy import text


def test_runtime_role_has_schema_usage_but_not_create(db_engine):
    """The ordinary API credential must never create objects in public."""
    with db_engine.connect() as conn:
        privileges = conn.execute(
            text(
                """
                SELECT
                    has_schema_privilege('m369_app', 'public', 'USAGE'),
                    has_schema_privilege('m369_app', 'public', 'CREATE')
                """
            )
        ).one()

    assert privileges[0] is True, "m369_app must retain USAGE on public schema"
    assert privileges[1] is False, "m369_app must not have CREATE on public schema"


def test_privileged_runtime_roles_do_not_have_schema_create(db_engine):
    """Super Admin runtime/auth roles also must not perform schema DDL."""
    with db_engine.connect() as conn:
        privileges = conn.execute(
            text(
                """
                SELECT
                    has_schema_privilege('m369_sa_runner', 'public', 'CREATE'),
                    has_schema_privilege('m369_sa_auth', 'public', 'CREATE')
                """
            )
        ).one()

    assert privileges[0] is False
    assert privileges[1] is False
