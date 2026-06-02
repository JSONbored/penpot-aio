#!/command/with-contenv bash
# shellcheck shell=bash
# shellcheck disable=SC2310,SC2312
set -euo pipefail

ENV_FILE="${PENPOT_AIO_GENERATED_ENV_FILE:-/appdata/config/generated.env}"
EXTRA_ENV_FILE="${PENPOT_AIO_EXTRA_ENV_FILE:-/appdata/config/extra.env}"
RUNTIME_ENV_FILE="/run/penpot-aio/runtime.env"
SAFE_EXTRA_ENV_FILE="/run/penpot-aio/extra.env"
MAILPIT_DIR="/appdata/config/mailpit"
MAILPIT_UI_AUTH_FILE="${MAILPIT_DIR}/ui-auth.txt"

log() {
	printf '[penpot-aio] %s\n' "$*"
}

ensure_env_file() {
	mkdir -p "$(dirname "${ENV_FILE}")"
	touch "${ENV_FILE}"
	chmod 600 "${ENV_FILE}"
}

set_env_value() {
	local key="$1"
	local value="$2"
	ensure_env_file
	node - "${ENV_FILE}" "${key}" "${value}" <<'NODE'
const fs = require("fs");
const [file, key, value] = process.argv.slice(2);
const line = `${key}=${JSON.stringify(value)}\n`;
let contents = "";
try {
  contents = fs.readFileSync(file, "utf8");
} catch {}
const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const pattern = new RegExp(`^${escapedKey}=.*$`, "m");
if (pattern.test(contents)) {
  contents = contents.replace(pattern, line.trimEnd());
  if (!contents.endsWith("\n")) contents += "\n";
} else {
  contents += line;
}
fs.writeFileSync(file, contents, { mode: 0o600 });
NODE
}

persist_if_missing() {
	local key="$1"
	local value="$2"
	ensure_env_file
	if ! grep -q "^${key}=" "${ENV_FILE}"; then
		set_env_value "${key}" "${value}"
	fi
}

generated_value() {
	local key="$1"
	node - "${ENV_FILE}" "${key}" <<'NODE'
const fs = require("fs");
const [file, key] = process.argv.slice(2);
let contents = "";
try {
  contents = fs.readFileSync(file, "utf8");
} catch {
  process.exit(1);
}
for (const line of contents.split(/\r?\n/)) {
  if (!line.startsWith(`${key}=`)) continue;
  const raw = line.slice(key.length + 1);
  try {
    process.stdout.write(JSON.parse(raw));
  } catch {
    process.stdout.write(raw);
  }
  process.exit(0);
}
process.exit(1);
NODE
}

load_generated_env() {
	ensure_env_file
	while IFS='=' read -r key raw_value; do
		[[ -z ${key} ]] && continue
		[[ ${key} =~ ^[A-Z0-9_]+$ ]] || continue
		if [[ -n ${!key-} ]]; then
			continue
		fi
		local decoded_value
		decoded_value="$(
			node - "${raw_value}" <<'NODE'
const raw = process.argv[2];
try {
  process.stdout.write(JSON.parse(raw));
} catch {
  process.stdout.write(raw);
}
NODE
		)"
		export "${key}=${decoded_value}"
	done <"${ENV_FILE}"
}

load_extra_env() {
	if [[ -f ${EXTRA_ENV_FILE} ]]; then
		mkdir -p "$(dirname "${SAFE_EXTRA_ENV_FILE}")"
		python3 - "${EXTRA_ENV_FILE}" "${SAFE_EXTRA_ENV_FILE}" <<'PY'
import ast
import re
import shlex
import sys

source_path, target_path = sys.argv[1:3]
name_pattern = re.compile(r"^[A-Z_][A-Z0-9_]*$")
exact = {"LANG", "LC_ALL", "JAVA_HOME", "JVM_OPTS", "JAVA_OPTS", "PLAYWRIGHT_BROWSERS_PATH", "TZ"}


def allowed_name(name: str) -> bool:
    return name.startswith(("PENPOT_", "AWS_")) or name in exact


with open(source_path, encoding="utf-8") as source, open(
    target_path, "w", encoding="utf-8"
) as target:
    for lineno, line in enumerate(source, start=1):
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("export "):
            raw = raw.removeprefix("export ").lstrip()
        if "=" not in raw:
            raise SystemExit(f"{source_path}:{lineno}: expected KEY=VALUE")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not name_pattern.fullmatch(key):
            raise SystemExit(f"{source_path}:{lineno}: invalid environment key {key!r}")
        if not allowed_name(key):
            raise SystemExit(f"{source_path}:{lineno}: unsupported environment key {key!r}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            try:
                value = ast.literal_eval(value)
            except (SyntaxError, ValueError) as exc:
                raise SystemExit(f"{source_path}:{lineno}: invalid quoted value") from exc
        target.write(f"export {key}={shlex.quote(value)}\n")
PY
		chmod 600 "${SAFE_EXTRA_ENV_FILE}"
		# shellcheck disable=SC1090
		source "${SAFE_EXTRA_ENV_FILE}"
	fi
}

env_flag_is_false() {
	case "${1-}" in
	0 | false | FALSE | no | NO | off | OFF)
		return 0
		;;
	*)
		return 1
		;;
	esac
}

env_flag_is_true() {
	case "${1-}" in
	1 | true | TRUE | yes | YES | on | ON)
		return 0
		;;
	*)
		return 1
		;;
	esac
}

uri_host_is_loopback() {
	local uri="$1"
	node - "${uri}" <<'NODE'
const value = process.argv[2];
try {
  const parsed = new URL(value);
  const host = (parsed.hostname || "").toLowerCase();
  process.exit(["127.0.0.1", "localhost", "::1"].includes(host) ? 0 : 1);
} catch {
  process.exit(1);
}
NODE
}

postgres_is_external() {
	if env_flag_is_false "${PENPOT_AIO_ENABLE_INTERNAL_POSTGRES:-true}"; then
		return 0
	fi
	[[ -n ${PENPOT_DATABASE_URI-} ]] && ! uri_host_is_loopback "${PENPOT_DATABASE_URI}"
}

redis_is_external() {
	if env_flag_is_false "${PENPOT_AIO_ENABLE_INTERNAL_REDIS:-true}"; then
		return 0
	fi
	[[ -n ${PENPOT_REDIS_URI-} ]] && ! uri_host_is_loopback "${PENPOT_REDIS_URI}"
}

mailpit_enabled() {
	if env_flag_is_false "${PENPOT_AIO_ENABLE_MAILPIT:-true}"; then
		return 1
	fi
	if [[ -z ${PENPOT_SMTP_HOST-} ]]; then
		return 0
	fi
	[[ ${PENPOT_SMTP_HOST} == "127.0.0.1" || ${PENPOT_SMTP_HOST} == "localhost" ]] && [[ ${PENPOT_SMTP_PORT:-1025} == "1025" ]]
}

random_token() {
	openssl rand -base64 "${1:-48}" | tr -d '\n'
}

compose_penpot_flags() {
	local flags="${PENPOT_AIO_DEFAULT_FLAGS:-disable-email-verification enable-smtp disable-secure-session-cookies enable-mcp}"
	local key value flag
	while IFS='=' read -r key value; do
		[[ ${key} == PENPOT_AIO_FLAG_* ]] || continue
		[[ ${value} == "enable" || ${value} == "disable" ]] || continue
		flag="${key#PENPOT_AIO_FLAG_}"
		flag="${flag,,}"
		flag="${flag//_/-}"
		flags="${flags} ${value}-${flag}"
	done < <(env | sort)
	printf '%s\n' "${flags}" | xargs
}

write_mailpit_ui_auth_file() {
	local username="$1"
	local password="$2"
	local salt
	local hashed_password

	mkdir -p "${MAILPIT_DIR}"
	chmod 711 "$(dirname "${MAILPIT_DIR}")"
	salt="$(openssl rand -hex 8)"
	hashed_password="$(openssl passwd -6 -salt "${salt}" "${password}")"
	printf '%s:%s\n' "${username}" "${hashed_password}" >"${MAILPIT_UI_AUTH_FILE}"
	chown mailpit:mailpit "${MAILPIT_UI_AUTH_FILE}"
	chmod 600 "${MAILPIT_UI_AUTH_FILE}"
}

configure_runtime_env() {
	ensure_env_file
	load_generated_env

	export PENPOT_AIO_ENABLE_INTERNAL_POSTGRES="${PENPOT_AIO_ENABLE_INTERNAL_POSTGRES:-true}"
	export PENPOT_AIO_ENABLE_INTERNAL_REDIS="${PENPOT_AIO_ENABLE_INTERNAL_REDIS:-true}"
	export PENPOT_AIO_ENABLE_MAILPIT="${PENPOT_AIO_ENABLE_MAILPIT:-true}"
	export PENPOT_AIO_ENABLE_MCP="${PENPOT_AIO_ENABLE_MCP:-true}"
	export PENPOT_AIO_WAIT_TIMEOUT_SECONDS="${PENPOT_AIO_WAIT_TIMEOUT_SECONDS:-360}"
	export PENPOT_AIO_DATABASE_NAME="${PENPOT_AIO_DATABASE_NAME:-penpot}"
	export PENPOT_PUBLIC_URI="${PENPOT_PUBLIC_URI:-http://localhost:9001}"
	export PENPOT_HTTP_SERVER_HOST="${PENPOT_HTTP_SERVER_HOST:-127.0.0.1}"
	export PENPOT_HTTP_SERVER_PORT="${PENPOT_HTTP_SERVER_PORT:-6060}"
	export PENPOT_HTTP_SERVER_MAX_BODY_SIZE="${PENPOT_HTTP_SERVER_MAX_BODY_SIZE:-367001600}"
	export PENPOT_HTTP_SERVER_MAX_MULTIPART_BODY_SIZE="${PENPOT_HTTP_SERVER_MAX_MULTIPART_BODY_SIZE:-367001600}"
	export PENPOT_IPV6_LISTEN_DIRECTIVE="${PENPOT_IPV6_LISTEN_DIRECTIVE-}"
	export PENPOT_BACKEND_URI="${PENPOT_BACKEND_URI:-http://127.0.0.1:6060}"
	export PENPOT_EXPORTER_URI="${PENPOT_EXPORTER_URI:-http://127.0.0.1:6061}"
	export PENPOT_NITRATE_URI="${PENPOT_NITRATE_URI:-http://127.0.0.1:3000}"
	export PENPOT_MCP_URI="${PENPOT_MCP_URI:-http://127.0.0.1:4401}"
	export PENPOT_MCP_URI_WS="${PENPOT_MCP_URI_WS:-http://127.0.0.1:4402}"
	export PENPOT_OBJECTS_STORAGE_BACKEND="${PENPOT_OBJECTS_STORAGE_BACKEND:-fs}"
	export PENPOT_OBJECTS_STORAGE_FS_DIRECTORY="${PENPOT_OBJECTS_STORAGE_FS_DIRECTORY:-/appdata/assets}"
	export PENPOT_FILE_DATA_BACKEND="${PENPOT_FILE_DATA_BACKEND:-storage}"
	export PENPOT_TELEMETRY_ENABLED="${PENPOT_TELEMETRY_ENABLED:-false}"
	export PENPOT_TELEMETRY_REFERER="${PENPOT_TELEMETRY_REFERER:-unraid-aio}"
	export PENPOT_MCP_SERVER_HOST="${PENPOT_MCP_SERVER_HOST:-127.0.0.1}"
	export PENPOT_MCP_SERVER_PORT="${PENPOT_MCP_SERVER_PORT:-4401}"
	export PENPOT_MCP_WEBSOCKET_PORT="${PENPOT_MCP_WEBSOCKET_PORT:-4402}"
	export PENPOT_MCP_REMOTE_MODE="${PENPOT_MCP_REMOTE_MODE:-true}"
	export PENPOT_MCP_LOG_LEVEL="${PENPOT_MCP_LOG_LEVEL:-info}"
	export PENPOT_MCP_LOG_DIR="${PENPOT_MCP_LOG_DIR:-/appdata/logs/mcp}"

	if [[ -z ${PENPOT_SECRET_KEY-} ]]; then
		persist_if_missing "PENPOT_SECRET_KEY" "$(random_token 64)"
		local generated_secret_key
		generated_secret_key="$(generated_value PENPOT_SECRET_KEY)"
		export PENPOT_SECRET_KEY="${generated_secret_key}"
	fi

	if ! postgres_is_external; then
		if [[ -z ${PENPOT_DATABASE_PASSWORD-} ]]; then
			persist_if_missing "PENPOT_DATABASE_PASSWORD" "$(openssl rand -hex 24)"
			local generated_database_password
			generated_database_password="$(generated_value PENPOT_DATABASE_PASSWORD)"
			export PENPOT_DATABASE_PASSWORD="${generated_database_password}"
		fi
		export PENPOT_DATABASE_USERNAME="${PENPOT_DATABASE_USERNAME:-penpot}"
		if [[ -z ${PENPOT_DATABASE_URI-} ]]; then
			export PENPOT_DATABASE_URI="postgresql://127.0.0.1:5432/${PENPOT_AIO_DATABASE_NAME}"
		fi
	fi

	if ! redis_is_external; then
		if [[ -z ${PENPOT_AIO_REDIS_PASSWORD-} ]]; then
			persist_if_missing "PENPOT_AIO_REDIS_PASSWORD" "$(openssl rand -hex 24)"
			local generated_redis_password
			generated_redis_password="$(generated_value PENPOT_AIO_REDIS_PASSWORD)"
			export PENPOT_AIO_REDIS_PASSWORD="${generated_redis_password}"
		fi
		if [[ -z ${PENPOT_REDIS_URI-} ]]; then
			export PENPOT_REDIS_URI="redis://default:${PENPOT_AIO_REDIS_PASSWORD}@127.0.0.1:6379/0"
		fi
	fi

	if mailpit_enabled; then
		export PENPOT_SMTP_HOST="${PENPOT_SMTP_HOST:-127.0.0.1}"
		export PENPOT_SMTP_PORT="${PENPOT_SMTP_PORT:-1025}"
		export PENPOT_SMTP_TLS="${PENPOT_SMTP_TLS:-false}"
		export PENPOT_SMTP_SSL="${PENPOT_SMTP_SSL:-false}"
		export PENPOT_SMTP_DEFAULT_FROM="${PENPOT_SMTP_DEFAULT_FROM:-Penpot <no-reply@penpot.local>}"
		export PENPOT_SMTP_DEFAULT_REPLY_TO="${PENPOT_SMTP_DEFAULT_REPLY_TO:-Penpot <no-reply@penpot.local>}"

		if [[ -z ${PENPOT_AIO_MAILPIT_UI_USERNAME-} ]]; then
			persist_if_missing "PENPOT_AIO_MAILPIT_UI_USERNAME" "penpot"
			local generated_mailpit_username
			generated_mailpit_username="$(generated_value PENPOT_AIO_MAILPIT_UI_USERNAME)"
			export PENPOT_AIO_MAILPIT_UI_USERNAME="${generated_mailpit_username}"
		fi
		if [[ -z ${PENPOT_AIO_MAILPIT_UI_PASSWORD-} ]]; then
			persist_if_missing "PENPOT_AIO_MAILPIT_UI_PASSWORD" "$(random_token 24)"
			local generated_mailpit_password
			generated_mailpit_password="$(generated_value PENPOT_AIO_MAILPIT_UI_PASSWORD)"
			export PENPOT_AIO_MAILPIT_UI_PASSWORD="${generated_mailpit_password}"
		fi
		write_mailpit_ui_auth_file "${PENPOT_AIO_MAILPIT_UI_USERNAME}" "${PENPOT_AIO_MAILPIT_UI_PASSWORD}"
	fi

	if [[ -z ${PENPOT_FLAGS-} ]]; then
		local composed_flags
		composed_flags="$(compose_penpot_flags)"
		export PENPOT_FLAGS="${composed_flags}"
	fi

	load_extra_env
	write_runtime_env
}

write_runtime_env() {
	mkdir -p "$(dirname "${RUNTIME_ENV_FILE}")"
	python3 - "${RUNTIME_ENV_FILE}" <<'PY'
import os
import shlex
import sys

path = sys.argv[1]
prefixes = ("PENPOT_", "AWS_")
exact = {"LANG", "LC_ALL", "JAVA_HOME", "JVM_OPTS", "JAVA_OPTS", "PLAYWRIGHT_BROWSERS_PATH", "TZ"}
keys = sorted(k for k in os.environ if k.startswith(prefixes) or k in exact)
with open(path, "w", encoding="utf-8") as handle:
    for key in keys:
        handle.write(f"export {key}={shlex.quote(os.environ[key])}\n")
PY
	chmod 600 "${RUNTIME_ENV_FILE}"
}

load_runtime_env() {
	if [[ -f ${RUNTIME_ENV_FILE} ]]; then
		# shellcheck disable=SC1090
		source "${RUNTIME_ENV_FILE}"
		return 0
	fi
	load_generated_env
	load_extra_env
}

wait_for_tcp_endpoint() {
	local host="$1"
	local port="$2"
	local label="$3"
	local timeout="${PENPOT_AIO_WAIT_TIMEOUT_SECONDS:-360}"
	local deadline=$((SECONDS + timeout))

	until (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1; do
		if ((SECONDS >= deadline)); then
			printf 'Timed out waiting for %s on %s:%s.\n' "${label}" "${host}" "${port}" >&2
			return 1
		fi
		log "Waiting for ${label} on ${host}:${port}..."
		sleep 2
	done
}

wait_for_postgres_ready() {
	postgres_is_external && return 0
	local timeout="${PENPOT_AIO_WAIT_TIMEOUT_SECONDS:-360}"
	local deadline=$((SECONDS + timeout))
	until pg_isready -h 127.0.0.1 -p 5432 -U "${PENPOT_DATABASE_USERNAME:-penpot}" >/dev/null 2>&1; do
		if ((SECONDS >= deadline)); then
			printf 'Timed out waiting for PostgreSQL.\n' >&2
			return 1
		fi
		log "Waiting for PostgreSQL..."
		sleep 2
	done
}

wait_for_redis_ready() {
	redis_is_external && return 0
	local timeout="${PENPOT_AIO_WAIT_TIMEOUT_SECONDS:-360}"
	local deadline=$((SECONDS + timeout))
	until REDISCLI_AUTH="${PENPOT_AIO_REDIS_PASSWORD-}" redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -qx "PONG"; do
		if ((SECONDS >= deadline)); then
			printf 'Timed out waiting for Redis-compatible cache.\n' >&2
			return 1
		fi
		log "Waiting for Redis-compatible cache..."
		sleep 2
	done
}

wait_for_mailpit_ready() {
	mailpit_enabled || return 0
	wait_for_tcp_endpoint "127.0.0.1" "1025" "Mailpit SMTP"
}
