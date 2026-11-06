-- Bootstrap: provision the m369_app role for local Docker development.
--
-- This script runs ONCE during PostgreSQL container initialization
-- (docker-entrypoint-initdb.d). It creates the m369_app role with the
-- password from the M369_APP_PASSWORD environment variable.
--
-- SECURITY: The password is NOT hardcoded here. It is read from the
-- M369_APP_PASSWORD env var via psql's \getenv command.
--
-- The role is created with least-privilege attributes:
--   NOSUPERUSER NOBYPASSRLS NOCREATEROLE
-- The migration (0001_initial.py) handles GRANTs and RLS policies.

-- Read the password from the container environment.
\getenv m369_app_password M369_APP_PASSWORD

-- Create the role if it does not exist.
SELECT format(
    'CREATE ROLE m369_app LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS NOCREATEROLE',
    :'m369_app_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'm369_app'
)
\gexec

-- Ensure the role has the expected password and restricted attributes.
SELECT format(
    'ALTER ROLE m369_app WITH LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS NOCREATEROLE',
    :'m369_app_password'
)
\gexec

-- Grant schema usage (tables are created by the migration as postgres)
GRANT ALL ON SCHEMA public TO m369_app;

-- Create test database
SELECT 'CREATE DATABASE m369_support_test OWNER postgres'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'm369_support_test')\gexec

-- ---------------------------------------------------------------------------
-- m369_sa_runner: Super Admin operations role (LOGIN, BYPASSRLS, NOSUPERUSER)
-- ---------------------------------------------------------------------------
-- Used by the Super Admin API endpoints via the super_admin_engine.
-- Distinct password from m369_app — NEVER shared with the migration service
-- or the ordinary API runtime.
\getenv m369_sa_runner_password M369_SA_RUNNER_PASSWORD

SELECT format(
    'CREATE ROLE m369_sa_runner LOGIN PASSWORD %L NOSUPERUSER BYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION',
    :'m369_sa_runner_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'm369_sa_runner'
)
\gexec

SELECT format(
    'ALTER ROLE m369_sa_runner WITH LOGIN PASSWORD %L NOSUPERUSER BYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION',
    :'m369_sa_runner_password'
)
\gexec

GRANT ALL ON SCHEMA public TO m369_sa_runner;

-- ---------------------------------------------------------------------------
-- m369_sa_auth: Dedicated Super Admin authentication-only role
-- ---------------------------------------------------------------------------
-- Used ONLY by /super-admin/auth/login and /super-admin/auth/login/verify-mfa.
-- NO BYPASSRLS — least-privilege. Password comes from environment, never source.

\getenv m369_sa_auth_password M369_SA_AUTH_PASSWORD

SELECT format(
    'CREATE ROLE m369_sa_auth LOGIN PASSWORD %L '
    'NOSUPERUSER NOBYPASSRLS NOCREATEDB '
    'NOCREATEROLE NOREPLICATION NOINHERIT',
    :'m369_sa_auth_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'm369_sa_auth'
)
\gexec

SELECT format(
    'ALTER ROLE m369_sa_auth WITH LOGIN PASSWORD %L '
    'NOSUPERUSER NOBYPASSRLS NOCREATEDB '
    'NOCREATEROLE NOREPLICATION NOINHERIT',
    :'m369_sa_auth_password'
)
\gexec

GRANT USAGE ON SCHEMA public TO m369_sa_auth;

REVOKE CREATE ON SCHEMA public FROM m369_sa_auth;
