# Releases

`unraid-aio-template` uses normal semver releases such as `v0.1.0`.

This repository is not tied to a single wrapped upstream application, so it should not use the app-style `upstream-version-aio.N` format that the derived AIO repos use.

## What a template release means

A template release is a versioned milestone for the scaffolding itself, including:

- CI and workflow changes
- release automation updates
- documentation and support-thread templates
- XML and catalog sync defaults
- generic Docker and rootfs scaffolding improvements

## Release flow

1. From `aio-fleet`, run `python -m aio_fleet release status --repo unraid-aio-template` to inspect the next semver release.
2. Run `python -m aio_fleet release prepare --repo unraid-aio-template` on a release branch, then open a `chore(release): <version>` PR.
3. Review and merge that PR into `main`.
4. Run the central `aio-fleet` control check for the release target commit and require `aio-fleet / required` to pass.
5. Run `python -m aio_fleet release publish --repo unraid-aio-template` from `aio-fleet` to create the GitHub Release.
