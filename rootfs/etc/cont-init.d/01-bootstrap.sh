#!/command/with-contenv bash
# shellcheck shell=bash
# shellcheck disable=SC1091,SC2154
set -euo pipefail

source /usr/local/bin/env-helpers.sh

mkdir -p \
	/appdata/assets \
	/appdata/config \
	/appdata/logs \
	/appdata/logs/mcp \
	/appdata/mailpit \
	/appdata/postgres \
	/appdata/redis \
	/run/penpot-aio \
	/run/postgresql

chown -R penpot:penpot /appdata/assets /appdata/logs
chown -R postgres:postgres /appdata/postgres /run/postgresql
chown -R redis:redis /appdata/redis
chown -R mailpit:mailpit /appdata/mailpit
chmod 711 /appdata/config
chmod 700 /appdata/postgres /appdata/redis /appdata/mailpit

configure_runtime_env

if [[ "${PENPOT_OBJECTS_STORAGE_BACKEND}" == "fs" ]]; then
	mkdir -p "${PENPOT_OBJECTS_STORAGE_FS_DIRECTORY}"
	chown -R penpot:penpot "${PENPOT_OBJECTS_STORAGE_FS_DIRECTORY}"
fi

log "Generated and runtime environment are ready. Generated values are stored at ${ENV_FILE}."
