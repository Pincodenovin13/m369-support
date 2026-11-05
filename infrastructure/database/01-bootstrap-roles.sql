-- Bootstrap: provision the m369_app role for local Docker development.
--
-- This script runs ONCE during PostgreSQL container initialization
-- (docker-entrypoint-initdb.d). It creates the m369_app role with the
-- password from the M369_APP_PASSWORD environment variable (passed via
-- psql's \gexec or -v). In production, this role should be provisioned
-- by a DBA or secrets manager — not by this script.
--
-- SECURITY: The password is NOT hardcoded here. It is read from the
-- M369_APP_PASSWORD env var, which Docker Compose injects.
--
-- The role is created with least-privilege attributes:
--   NOSUPERUSER NOBYPASSRLS NOCREATEROLE
-- The migration (0001_initial.py) handles GRANTs and RLS policies.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'm369_app') THEN
        CREATE ROLE m369_app LOGIN PASSWORD :'password' NOSUPERUSER NOBYPASSRLS NOCREATEROLE;
    END IF;
END
$$;

-- Grant schema usage (tables are created by the migration as postgres)
GRANT ALL ON SCHEMA public TO m369_app;

-- Create test database
SELECT 'CREATE DATABASE m369_support_test OWNER postgres'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'm369_support_test')\gexec
