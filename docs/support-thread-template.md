# Support: Penpot AIO for Unraid

## What this is

Penpot is an open-source design and prototyping platform for product teams, designers, developers, and self-hosted teams that want a Figma-style workflow under their own control.

This AIO package exists to make Penpot easier to install and maintain on Unraid without manually translating the official multi-container setup into a homelab-friendly template.

## Why this AIO exists

The default install bundles Penpot frontend, backend, exporter, MCP, PostgreSQL, Redis-compatible cache, Nginx, and Mailpit into one container with one AppData path. That keeps the first boot path small while still exposing the broader Penpot config surface in Advanced View.

## Quick Install Notes

- Image: `jsonbored/penpot-aio:latest`
- Default Web UI: `http://[IP]:9001`
- AppData: `/mnt/user/appdata/penpot-aio`
- Required fields: Web UI port, AppData path, and the `Public URL` users will actually visit

First boot can take a few minutes while the bundled database, cache, Mailpit, generated secrets, and Penpot services come up.

## Important Notes

- For local/lab use, the template defaults to Mailpit and disables email verification.
- For public HTTPS use, set a real HTTPS `PENPOT_PUBLIC_URI`, configure SMTP, and remove the default `disable-secure-session-cookies` and `disable-email-verification` flags.
- Penpot is a real multi-service stack. Plan for at least 2 CPU cores and 4 GiB RAM, with more for active teams or large files.
- The bundled Mailpit inbox is not a production mail relay.

## Persistence

Important persistent paths under AppData:

- `/appdata/config/generated.env`
- `/appdata/postgres`
- `/appdata/redis`
- `/appdata/assets`
- `/appdata/mailpit`
- `/appdata/logs`

## Support Scope

This thread covers the JSONbored Unraid AIO packaging for Penpot. For support, please include your Unraid version, relevant template settings, container logs, screenshots for UI issues, and what you expected to happen versus what happened.

If the issue is upstream Penpot behavior rather than the Unraid packaging layer, I may redirect you to upstream Penpot resources.

## Links

- Project repo: [JSONbored/penpot-aio](https://github.com/JSONbored/penpot-aio)
- Upstream project: [penpot/penpot](https://github.com/penpot/penpot)
- Catalog repo: [JSONbored/awesome-unraid](https://github.com/JSONbored/awesome-unraid)
- GitHub Sponsors: [JSONbored](https://github.com/sponsors/JSONbored)
