# Penpot AIO for Unraid

`penpot-aio` is a JSONbored Unraid-first all-in-one wrapper for [Penpot](https://github.com/penpot/penpot).

The image bundles the Penpot frontend served through Nginx, backend, exporter, MCP server, PostgreSQL, Redis-compatible cache, and Mailpit into one container. The Unraid template keeps the beginner path small while still exposing the full discovered upstream configuration surface in Advanced View.

## Quick Start

1. Install the Unraid template.
2. Keep `Web UI Port` and `AppData` at their defaults unless you have a conflict.
3. Set `Public URL` to the URL users will actually visit, for example `http://tower.local:9001` or your reverse-proxy HTTPS URL.
4. Start the container and wait a few minutes for first boot.
5. Open the Web UI and create the first account.

Generated secrets are stored in `/appdata/config/generated.env`. Explicit Unraid template values override generated values.

## Included Services

- Penpot frontend and Nginx gateway on container port `8080`
- Penpot backend on internal port `6060`
- Penpot exporter on internal port `6061`
- Penpot MCP on internal ports `4401` and `4402`
- Bundled PostgreSQL under `/appdata/postgres`
- Bundled Redis-compatible cache under `/appdata/redis`
- Bundled Mailpit inbox under `/appdata/mailpit`
- Filesystem object storage under `/appdata/assets`

## Defaults

The default install is intentionally lab-friendly:

- bundled database/cache/storage/mail
- generated `PENPOT_SECRET_KEY`, database password, Redis password, and Mailpit UI password
- telemetry disabled
- filesystem asset storage
- MCP enabled
- local Mailpit SMTP when external SMTP is blank
- `disable-email-verification`, `enable-smtp`, `disable-secure-session-cookies`, and `enable-mcp` in the AIO default flags

For public HTTPS production, remove `disable-secure-session-cookies` and `disable-email-verification`, configure real SMTP, set the real HTTPS `PENPOT_PUBLIC_URI`, and review the advanced security/SSRF settings.

## Advanced Configuration

`penpot-aio.xml` is generated from `docs/upstream/penpot-config-inventory.json`, which is built from:

- upstream `backend/src/app/config.clj`
- upstream `common/src/app/common/flags.cljc`
- official Docker compose variables
- official configuration docs
- frontend image entrypoint variables
- MCP server environment variables
- AIO wrapper variables

Advanced View exposes external PostgreSQL, external Redis/Valkey, SMTP, S3-compatible object storage, OAuth/OIDC/LDAP, telemetry, MCP, SSRF controls, performance limits, raw `PENPOT_FLAGS`, per-flag dropdown controls, and the final sanitized `PENPOT_AIO_EXTRA_ENV_FILE=/appdata/config/extra.env` key/value escape hatch.

## Local Validation

```sh
python3 scripts/refresh_upstream_inventory.py
python3 scripts/generate_penpot_template.py --check
pytest tests/template
pytest tests/integration -m integration
```

Fleet validation is run from `aio-fleet`:

```sh
python -m aio_fleet export-app-manifest --repo penpot-aio --write
python -m aio_fleet validate-repo --repo penpot-aio --repo-path ../penpot-aio
python -m aio_fleet cleanup-repo --repo penpot-aio --repo-path ../penpot-aio --verify
python -m aio_fleet sync-catalog --repo penpot-aio --catalog-path ../awesome-unraid --dry-run
```

## Release Model

App releases follow the fleet convention: upstream Penpot version plus an AIO revision. Shared workflow, registry, release, and catalog behavior is controlled by `aio-fleet`.
