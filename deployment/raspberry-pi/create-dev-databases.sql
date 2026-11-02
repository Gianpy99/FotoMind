-- Development and integration-test databases on the Pi's PostgreSQL 15 (port 5432).
-- A separate role (fotomind_dev) means development can never touch the production DB.
-- Run as the postgres superuser:  sudo -u postgres psql -f create-dev-databases.sql

\prompt 'Password for role fotomind_dev: ' dev_password

SELECT 'CREATE ROLE fotomind_dev LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fotomind_dev')\gexec

ALTER ROLE fotomind_dev WITH LOGIN PASSWORD :'dev_password';

SELECT 'CREATE DATABASE fotomind_dev OWNER fotomind_dev ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'fotomind_dev')\gexec

-- Integration tests downgrade/upgrade migrations here.
SELECT 'CREATE DATABASE fotomind_test OWNER fotomind_dev ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'fotomind_test')\gexec

\connect fotomind_dev
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO fotomind_dev;

\connect fotomind_test
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO fotomind_dev;
