# Release Checklist

## Before Merge

- `python3 scripts/generate_penpot_template.py --check`
- `pytest tests/template`
- `pytest tests/integration -m integration`
- `python -m aio_fleet validate-repo --repo penpot-aio --repo-path ../penpot-aio`
- `python -m aio_fleet cleanup-repo --repo penpot-aio --repo-path ../penpot-aio --verify`
- `python -m aio_fleet control-check --repo penpot-aio --repo-path ../penpot-aio --event pull_request --dry-run`

## Before CA Submission

- verify Docker Hub and GHCR images are public and pullable
- sync `penpot-aio.xml` and `assets/app-icon.png` into `awesome-unraid`
- validate a clean Unraid install with default settings
- validate restart persistence for generated secrets and database state
- create a dedicated Unraid support thread or keep GitHub issues as the temporary support target
