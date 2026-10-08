#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=reader_password="$READER_PASSWORD" --set=app_password="$APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE mc_reader LOGIN PASSWORD %L', :'reader_password') \gexec
SELECT format('CREATE ROLE mc_app LOGIN PASSWORD %L', :'app_password') \gexec
ALTER ROLE mc_reader SET default_transaction_read_only = on;
ALTER ROLE mc_reader SET statement_timeout = '3s';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE TEMP ON DATABASE missioncontrol FROM PUBLIC;
SQL
