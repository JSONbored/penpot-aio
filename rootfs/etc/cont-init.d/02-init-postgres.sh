#!/command/with-contenv bash
# shellcheck shell=bash
# shellcheck disable=SC1091,SC2154
set -euo pipefail

source /usr/local/bin/env-helpers.sh
load_runtime_env

if postgres_is_external; then
	log "External PostgreSQL configured. Skipping bundled PostgreSQL bootstrap."
	exit 0
fi

mkdir -p /appdata/postgres /run/postgresql
chown -R postgres:postgres /appdata/postgres /run/postgresql
chmod 700 /appdata/postgres

PG_BIN_DIR="$(find /usr/lib/postgresql -mindepth 2 -maxdepth 2 -type d -name bin | sort | head -n 1)"
if [[ -z ${PG_BIN_DIR} ]]; then
	echo "Unable to locate PostgreSQL binaries under /usr/lib/postgresql." >&2
	exit 1
fi

if [[ ! -f /appdata/postgres/PG_VERSION ]]; then
	log "Initializing bundled PostgreSQL cluster..."
	su -s /bin/bash postgres -c "${PG_BIN_DIR}/initdb -D /appdata/postgres --locale=C.UTF-8 --encoding=UTF8 --auth-local=peer --auth-host=scram-sha-256"
fi

su -s /bin/bash postgres -c "${PG_BIN_DIR}/pg_ctl -D /appdata/postgres -o \"-c listen_addresses='127.0.0.1'\" -w start"

PENPOT_INIT_DATABASE_USERNAME="${PENPOT_DATABASE_USERNAME}" \
	PENPOT_INIT_DATABASE_PASSWORD="${PENPOT_DATABASE_PASSWORD}" \
	PENPOT_INIT_DATABASE_NAME="${PENPOT_AIO_DATABASE_NAME}" \
	python3 <<'PY' | su -s /bin/bash postgres -c "psql postgres"
import os

user = os.environ["PENPOT_INIT_DATABASE_USERNAME"]
password = os.environ["PENPOT_INIT_DATABASE_PASSWORD"]
dbname = os.environ["PENPOT_INIT_DATABASE_NAME"]

def ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'

def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

print(
    f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {literal(user)}) THEN
        CREATE ROLE {ident(user)} LOGIN PASSWORD {literal(password)};
    ELSE
        ALTER ROLE {ident(user)} WITH PASSWORD {literal(password)};
    END IF;
END
$$;
SELECT 'CREATE DATABASE {ident(dbname)} OWNER {ident(user)}'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = {literal(dbname)})\\gexec
"""
)
PY
su -s /bin/bash postgres -c "${PG_BIN_DIR}/pg_ctl -D /appdata/postgres -m fast -w stop"

log "Bundled PostgreSQL bootstrap is complete."
