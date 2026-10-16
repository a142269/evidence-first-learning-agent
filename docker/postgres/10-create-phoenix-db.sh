#!/usr/bin/env bash
set -euo pipefail

# PostgreSQL's official entrypoint runs this exactly once, when the named
# volume is first initialized.  Keeping Phoenix in its own database avoids
# observability retention policies touching application data.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE USER ${PHOENIX_DB_USER} WITH PASSWORD '${PHOENIX_DB_PASSWORD}';
    CREATE DATABASE ${PHOENIX_DB} OWNER ${PHOENIX_DB_USER};
EOSQL
