-- FotoMind database on the Raspberry Pi's native PostgreSQL 15 (port 5432).
-- Run as the postgres superuser:  sudo -u postgres psql -f create-database.sql
-- The password is prompted for interactively and never stored in this file.

\prompt 'Password for role fotomind: ' fotomind_password

SELECT 'CREATE ROLE fotomind LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fotomind')\gexec

ALTER ROLE fotomind WITH LOGIN PASSWORD :'fotomind_password';

SELECT 'CREATE DATABASE fotomind OWNER fotomind ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'fotomind')\gexec

\connect fotomind
-- The role owns the database. Migrations create the trusted extension pg_trgm themselves.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO fotomind;
