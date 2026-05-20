# Upstream Tracking

Upstream tracking is owned by `aio-fleet`, not by app-local scripts. Derived repos declare upstream metadata in `.aio-fleet.yml`; the central `aio-fleet/fleet.yml` remains the source for generated manifests and control-plane policy.

## Required Inputs

- upstream name and source repository
- Dockerfile ARG that pins the upstream version
- optional digest ARGs for images that should be immutable
- update strategy: `pr` for safe single-image bumps, `notify` for multi-image stacks that need manual review

## Dify-Style Multi-Image Stacks

Dify pins multiple companion images. Keep those bumps explicit so API, web, sandbox, plugin daemon, and digest changes move together in one reviewed release task.

## Validation

Run this from `aio-fleet` after changing upstream metadata or Dockerfile pins:

```sh
python -m aio_fleet validate --repo <repo>
python -m aio_fleet release status --repo <repo>
```
