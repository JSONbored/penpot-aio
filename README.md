# Unraid AIO Template

A hardened starter for future `*-aio` repositories: one public repo per app, one Docker Hub-facing image, one Unraid CA XML, and one beginner-first experience that still leaves room for power-user overrides.

This template is opinionated on purpose. It is built for repos that should be:

- easy for newcomers to install
- honest about what is embedded versus external
- reproducible in CI before publishing `latest`
- cleanly syncable into `awesome-unraid`

## What This Template Ships With

- starter [`Dockerfile`](Dockerfile) for wrapping an upstream image with `s6-overlay`
- starter CA XML at [`template-aio.xml`](template-aio.xml)
- shared pytest harness under [`tests/`](tests)
- declarative fleet manifest at [`.aio-fleet.yml`](.aio-fleet.yml)
- app-owned Docker/rootfs/XML/docs/tests only; shared validation, release, registry, catalog, upstream, and Trunk behavior lives in `aio-fleet`
- starter docs, changelog, funding, issue templates, and security policy
- public repo checklists under [`docs/`](docs)

## Design Principles

- single-container first when it is realistic and not misleading
- safe defaults for beginners, advanced knobs for power users
- generated first-run secrets only when the app truly needs them
- no publish until placeholders are gone and pytest passes
- shared CI, Trunk, upstream tracking, changelog, release, and registry rules are declared in `aio-fleet`
- update automation opens PRs/checks, but merge decisions stay manual
- public repos stay public-facing and product-facing only

## Recommended Workflow

1. Create a new private repo from this template.
2. Rename `template-aio.xml` to the final app slug, for example `myapp-aio.xml`.
3. Replace placeholders in the Dockerfile, XML, rootfs scripts, pytest harness, README, funding file, and security policy.
4. Replace [`assets/app-icon.png`](assets/app-icon.png) with the real icon.
5. Follow [`docs/customization-guide.md`](docs/customization-guide.md).
6. Follow [`docs/repo-settings.md`](docs/repo-settings.md).
7. Add the repo to `aio-fleet/fleet.yml`, then export the app manifest with `python -m aio_fleet export-app-manifest --repo <repo> --write`.
8. Let `aio-fleet` own package publishing, downstream XML sync PRs, upstream monitoring, release preparation, and Trunk.
9. Keep the XML `<Changes>` block in the fleet-standard date-first format generated from `aio-fleet`.

For ecosystems that need companion images such as agents, workers, or proxies,
use the optional suite component pattern in
[`docs/suite-components.md`](docs/suite-components.md).
Most repos should still stay single-component unless the companion is tightly
bound to the same upstream product and support surface.

## Control Plane

Derived repos should not carry shared workflow, Trunk, release, upstream, or validator shims. `aio-fleet` owns those surfaces and reads the app repo through `.aio-fleet.yml` plus the central `fleet.yml`.

The final app repo surface should stay narrow:

- Dockerfile/rootfs/runtime logic
- XML or XML generator
- app-specific assets and docs
- app-specific tests
- `.aio-fleet.yml`

## Files To Customize First

- [`Dockerfile`](Dockerfile)
- [`template-aio.xml`](template-aio.xml)
- [`pyproject.toml`](pyproject.toml)
- [`tests/`](tests/)
- [`rootfs/etc/cont-init.d/01-bootstrap.sh`](rootfs/etc/cont-init.d/01-bootstrap.sh)
- [`rootfs/etc/services.d/app/run`](rootfs/etc/services.d/app/run)
- [`README.md`](README.md)
- [`.github/FUNDING.yml`](.github/FUNDING.yml)
- [`SECURITY.md`](SECURITY.md)
- [`.aio-fleet.yml`](.aio-fleet.yml)

## Validation Flow

Derived repos created from this template should follow this order:

1. local placeholder cleanup
2. `python3 -m venv .venv && . .venv/bin/activate && pip install -e "../aio-fleet[app-tests]"`
3. from `aio-fleet`: `python -m aio_fleet validate-repo --repo <repo> --repo-path ../<repo>`
4. `pytest tests/integration -m integration`
5. from `aio-fleet`: `python -m aio_fleet cleanup-repo --repo <repo> --verify`
6. from `aio-fleet`: `python -m aio_fleet control-check --repo <repo> --sha <sha> --event pull_request`
7. real Unraid install validation

Control-plane cost model for derived repos:

- run central validation and app-local unit/template tests for pull requests
- run Docker-backed integration tests on `main`, release, or manual control-plane checks
- require `aio-fleet / required` before protected-branch merges
- keep local integration runs explicit instead of binding them to every pre-commit or pre-push hook by default

Use [`docs/release-checklist.md`](docs/release-checklist.md) before making a derived repo public or submitting it to CA.

## Upstream Tracking

Use [`docs/upstream-tracking.md`](docs/upstream-tracking.md) to wire the derived repo to the stable upstream app it wraps.

## Releases

This template should use normal semver releases such as `v0.1.0`, not upstream-aligned app versions.

See [`docs/releases.md`](docs/releases.md) for the protected-branch-safe release workflow and changelog process.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JSONbored/unraid-aio-template&type=date&legend=top-left)](https://www.star-history.com/#JSONbored/unraid-aio-template&Date)
