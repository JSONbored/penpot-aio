# penpot-aio

![penpot-aio](https://socialify.git.ci/JSONbored/penpot-aio/image?custom_description=Unraid+CA+AIO+template+and+Docker+image+for+Penpot%2C+the+open-source+design+and+prototyping+platform%2C+with+bundled+PostgreSQL%2C+Redis%2C+Mailpit%2C+exporter%2C+and+MCP.&custom_language=Dockerfile&description=1&font=Raleway&forks=1&issues=1&language=1&logo=https%3A%2F%2Fraw.githubusercontent.com%2FJSONbored%2Fpenpot-aio%2Fmain%2Fassets%2Fapp-icon.png&name=1&owner=1&pattern=Formal+Invitation&pulls=1&stargazers=1&theme=Light)

An Unraid-first, single-container deployment of [Penpot](https://github.com/penpot/penpot) for people who want the easiest reliable self-hosted install without manually wiring PostgreSQL, Redis, SMTP capture, exporter, MCP, and the upstream compose stack on day one.

`penpot-aio` is opinionated for a predictable beginner install, but it does not hide the real tradeoffs: Penpot is still a heavier multi-service design platform, `PENPOT_PUBLIC_URI` still needs to match the URL users actually visit, and public production use still needs HTTPS, real SMTP, backups, and production-safe flags.

## What This Image Includes

- Penpot frontend served through an Nginx gateway on port `8080`
- Penpot backend on an internal service port
- Penpot exporter for render/export flows
- Penpot MCP server, proxied through the frontend by default
- Embedded PostgreSQL for the default beginner path
- Embedded Redis-compatible cache for the default beginner path
- Embedded Mailpit inbox for local or lab SMTP capture on port `8025`
- Filesystem object storage under `/appdata/assets` by default
- Persistent `/appdata` storage for database state, cache state, assets, generated secrets, Mailpit data, and optional overrides
- Automatic generation and persistence of `PENPOT_SECRET_KEY`, bundled database password, bundled Redis password, and bundled Mailpit UI password when you leave them blank
- Unraid CA template at [penpot-aio.xml](penpot-aio.xml)

## Beginner Install

If you want the simplest supported path:

1. Install the Unraid template.
2. Leave `Web UI Port` and `AppData` at their defaults unless you have a port or path conflict.
3. Set `Public URL` to the URL users will actually visit, such as `http://tower.local:9001` or your reverse-proxy HTTPS URL.
4. Start the container and wait a few minutes for first boot.
5. Open the web UI and create the first account.
6. If you need local mail capture, open the bundled Mailpit inbox on the advanced `Mailpit UI Port` and read the generated credentials from `/appdata/config/generated.env`.

If you leave the important secrets blank, the wrapper will:

- generate and persist `PENPOT_SECRET_KEY`
- generate and persist the bundled PostgreSQL password
- generate and persist the bundled Redis password
- generate and persist a bundled Mailpit UI password
- create and use internal PostgreSQL and Redis-compatible services
- use filesystem asset storage under `/appdata/assets`
- use bundled Mailpit for local email capture when external SMTP is blank
- disable telemetry by default

The default lab-friendly flags include `disable-email-verification`, `enable-smtp`, `disable-secure-session-cookies`, and `enable-mcp`. Those defaults make first boot easier on a private LAN; they are not the right final posture for a public HTTPS deployment.

## Power User Surface

This repo is deliberately not a stripped-down wrapper. The generated Unraid template tracks the practical Penpot self-hosted environment surface from upstream config, official compose examples, docs, frontend entrypoint behavior, MCP settings, and AIO-specific defaults. In Advanced View you can:

- move PostgreSQL out of the container with `PENPOT_AIO_ENABLE_INTERNAL_POSTGRES=false` and external `PENPOT_DATABASE_*` settings
- move Redis or Valkey out of the container with `PENPOT_AIO_ENABLE_INTERNAL_REDIS=false` and `PENPOT_REDIS_URI`
- keep local Mailpit for lab flows or configure external SMTP for real delivery
- use filesystem storage by default or configure S3-compatible object storage
- configure OAuth, OIDC, LDAP, GitHub, GitLab, Google, demo users, and allowed admin accounts
- tune telemetry, webhooks, file limits, RPC limits, worker/executor behavior, session cookies, rate limits, SSRF protections, and proxy behavior
- enable or disable the bundled MCP service and optionally publish direct MCP HTTP/WebSocket ports
- use raw `PENPOT_FLAGS` or the per-flag dropdown controls for known upstream flags
- use `/appdata/config/extra.env` as a final sanitized key/value escape hatch for rare supported variables

The wrapper still defaults to the internal bundled services so new Unraid users are not forced into extra containers on day one. External services should be configured intentionally, not half-filled alongside the internal defaults.

## Runtime Notes

- Penpot is a real multi-service stack. Plan for at least 2 CPU cores and 4 GiB RAM, with more for active teams, large files, or concurrent export work.
- `/appdata` stores generated secrets, PostgreSQL data, cache data, uploaded assets, Mailpit data, logs, and optional override files. Back it up before upgrades or serious use.
- `PENPOT_PUBLIC_URI` must be correct. Browser flows, links, cookies, callbacks, and reverse-proxy behavior can break when it does not match the URL users actually visit.
- Public exposure should sit behind a trusted HTTPS reverse proxy. Remove `disable-secure-session-cookies` and `disable-email-verification`, configure real SMTP, and review auth settings before production use.
- The bundled Mailpit inbox is for local or lab email capture. It is not a production mail relay and does not solve DNS, reputation, SPF, DKIM, DMARC, or deliverability.
- The bundled database/cache path is meant to make the first install reliable. For more serious production deployments, consider external PostgreSQL, external Redis/Valkey, object storage, and a real backup plan.
- `/appdata/config/extra.env` is parsed as dotenv-style `KEY=value` data. It is not shell-sourced; shell syntax is not executed, and only supported key prefixes/core runtime keys are accepted.

## Publishing and Releases

- Wrapper releases use the upstream version plus an AIO revision, such as `v2.15.3-aio.1`.
- Upstream monitoring, release preparation, registry publishing, and catalog sync are owned by `aio-fleet` from `.aio-fleet.yml`.
- Changelog generation and XML `<Changes>` sync are run centrally by `aio-fleet` during release preparation.
- `main` publishes `latest`, the pinned upstream version tag, the explicit AIO package tag, and `sha-<commit>` to Docker Hub.
- Publish jobs require Docker Hub credentials and push the CA-facing Docker Hub tags directly.

See [docs/releases.md](docs/releases.md) for the central release process details.

## Validation

Required local validation is split between app-specific tests and `aio-fleet`:

```bash
python3 -m venv .venv-local
.venv-local/bin/pip install -e "../aio-fleet[app-tests]"
python3 scripts/refresh_upstream_inventory.py
python3 scripts/generate_penpot_template.py --check
.venv-local/bin/pytest tests/template --junit-xml=reports/pytest-unit.xml -o junit_family=xunit1
.venv-local/bin/pytest tests/integration -m integration --junit-xml=reports/pytest-integration.xml -o junit_family=xunit1
cd ../aio-fleet
.venv/bin/python -m aio_fleet validate-repo --repo penpot-aio --repo-path ../penpot-aio
.venv/bin/python -m aio_fleet cleanup-repo --repo penpot-aio --repo-path ../penpot-aio --verify
.venv/bin/python -m aio_fleet sync-catalog --repo penpot-aio --catalog-path ../awesome-unraid --dry-run
```

The integration suite builds a Linux amd64 image and boots the full container stack, so it is intentionally more expensive than the unit and XML checks.

The extended runtime matrix is opt-in and covers external PostgreSQL, external Redis, S3-compatible storage, and external SMTP/Mailpit paths:

```bash
AIO_RUN_EXTENDED_INTEGRATION=true .venv-local/bin/pytest tests/integration -m extended_integration
```

CI cost model:

- relevant PRs and `main` pushes run the fast validation layers first
- Docker-backed integration tests run for build-relevant changes, for `main` release-metadata commits when publish is still in play, and for manual dispatches
- image publish stays gated behind the integration suite instead of treating skipped integration as acceptable
- extended provider coverage stays opt-in because it is materially more expensive than the required gate

## Community Apps Sync

This repo is the source repo. The CA-facing XML and icon should be synced into `JSONbored/awesome-unraid` only after:

1. local validation passes
2. the image is publishable
3. the support content is ready
4. the catalog metadata points at the published Docker Hub image and raw `awesome-unraid/main` assets

## Support

- Repo issues: [JSONbored/penpot-aio issues](https://github.com/JSONbored/penpot-aio/issues)
- Upstream app: [penpot/penpot](https://github.com/penpot/penpot)
- Official docs: [help.penpot.app](https://help.penpot.app/)
- Configuration docs: [Penpot configuration](https://help.penpot.app/technical-guide/configuration/)

## Funding

If this work saves you time, support it here:

- [GitHub Sponsors](https://github.com/sponsors/JSONbored)
- [Ko-fi](https://ko-fi.com/jsonbored)
- [Buy Me a Coffee](https://buymeacoffee.com/jsonbored)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JSONbored/penpot-aio&theme=dark)](https://star-history.com/#JSONbored/penpot-aio&Date)
