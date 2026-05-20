# Upstream Tracking

Penpot upstream tracking is declared in `aio-fleet/fleet.yml` and exported into `.aio-fleet.yml`.

Tracked upstream components:

- `penpotapp/frontend`
- `penpotapp/backend`
- `penpotapp/exporter`
- `penpotapp/mcp`
- `axllent/mailpit`

When Penpot updates, refresh the inventory and regenerate XML:

```sh
python3 scripts/refresh_upstream_inventory.py
python3 scripts/generate_penpot_template.py
```

Version and digest ARGs in `Dockerfile` must move together.
