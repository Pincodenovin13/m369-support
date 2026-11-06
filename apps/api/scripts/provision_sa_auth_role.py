"""Provision the m369_sa_auth role password from the environment.

This script runs AFTER ``alembic upgrade head`` to set the password of
the ``m369_sa_auth`` role from the ``M369_SA_AUTH_PASSWORD`` environment
variable. It is idempotent — running it multiple times is safe.

Usage:
    DATABASE_URL=postgresql+psycopg://postgres:...@db:5432/m369_support \
    M369_SA_AUTH_PASSWORD=... \
    python scripts/provision_sa_auth_role.py

The script connects with the migration credential (DATABASE_URL), NOT
with m369_app or m369_sa_auth. It verifies the role's security attributes
after setting the password and exits non-zero on any failure.

Security:
  - The password is NEVER printed, logged, or stored in a file.
  - The connection string is NEVER printed.
  - Raw exception details are suppressed to avoid leaking information.
"""
from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql


def main() -> int:
    password = os.environ.get("M369_SA_AUTH_PASSWORD")
    database_url = os.environ.get("DATABASE_URL")

    if not password:
        print("ERROR: M369_SA_AUTH_PASSWORD is required.")
        return 1

    if not database_url:
        print("ERROR: DATABASE_URL is required.")
        return 1

    # psycopg.connect expects a standard PostgreSQL URL.
    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1,
        )

    # Use sql.Literal so the password is properly escaped — never use
    # string interpolation for SQL.
    statement = sql.SQL(
        """
        ALTER ROLE m369_sa_auth
        WITH LOGIN
        PASSWORD {}
        NOSUPERUSER
        NOBYPASSRLS
        NOCREATEDB
        NOCREATEROLE
        NOREPLICATION
        NOINHERIT
        """
    ).format(sql.Literal(password))

    try:
        with psycopg.connect(database_url, connect_timeout=10) as conn:
            conn.execute(statement)

            # Verify role attributes without retrieving its password.
            row = conn.execute(
                """
                SELECT
                    rolcanlogin,
                    rolsuper,
                    rolbypassrls,
                    rolcreatedb,
                    rolcreaterole,
                    rolreplication,
                    rolinherit
                FROM pg_roles
                WHERE rolname = 'm369_sa_auth'
                """
            ).fetchone()

            expected = (True, False, False, False, False, False, False)

            if row != expected:
                raise RuntimeError(
                    "m369_sa_auth role attributes do not match policy."
                )

        print("m369_sa_auth provisioning completed.")
        return 0

    except Exception:
        # Do not print connection strings, password, or raw exception details.
        print("ERROR: m369_sa_auth provisioning failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
