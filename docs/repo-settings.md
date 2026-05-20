# Recommended GitHub Settings

Apply these before the first public release or Community Apps submission.

## General

- Enable Issues for support until a dedicated Unraid forum thread exists.
- Disable Wikis unless there is a clear maintenance reason.
- Set the About description to: `Penpot packaged as an Unraid-first AIO container`.
- Add topics such as `unraid`, `penpot`, `self-hosted`, `design-tools`, `aio`.
- Confirm Docker Hub and GHCR images are public after the first publish.

## Branch Protection

Protect `main` with:

- pull request required before merge
- required status checks
- linear history
- force-push and deletion blocks

Suggested required check:

- `aio-fleet / required`

## Actions

Shared workflow, registry, release, and upstream-monitor behavior is controlled from `aio-fleet`. Keep repo-local workflow sprawl out of this repo unless the fleet control plane cannot express the need.

## Security

- Enable dependency graph and vulnerability alerts.
- Enable secret scanning and push protection.
- Keep generated secrets in `/appdata/config/generated.env`; never document or commit real runtime values.
