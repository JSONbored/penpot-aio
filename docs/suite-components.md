# Suite Components

`penpot-aio` currently publishes one AIO image and one Unraid template.

The image still contains multiple supervised services:

- frontend
- Nginx gateway
- backend
- exporter
- MCP
- PostgreSQL
- Redis-compatible cache
- Mailpit

Do not split these into separate published images unless the fleet control plane and support surface are updated deliberately. The purpose of this repo is the one-container Unraid install path.
