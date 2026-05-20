# Release Checklist

## Before First Public Push

- replace every placeholder value and example hostname
- replace `assets/app-icon.png`
- rename `template-aio.xml`
- confirm README, SECURITY, and FUNDING are accurate
- confirm `Support`, `Project`, `TemplateURL`, and `Icon` URLs are correct
- pin the upstream version explicitly
- configure the repo in `aio-fleet/fleet.yml` and export `.aio-fleet.yml`
- add a screenshot or demo visual if the app has a UI
- set the repo About description, topics, and social preview image
- from `aio-fleet`, run `python -m aio_fleet validate-repo --repo <repo> --repo-path ../<repo>`
- run `pytest tests/integration -m integration`

## Before Enabling Actions

- add optional sync override variables only if you need to diverge from the repo-name defaults
- confirm the `aio-fleet` GitHub App is installed on this repo and `awesome-unraid`
- confirm shared dependency/upstream automation is represented in `aio-fleet`
- verify branch protection and secret scanning are enabled
- from `aio-fleet`, run `python -m aio_fleet signing doctor --repo <repo> --format json`
- confirm `aio-fleet / required` passes before allowing publish

## Before Unraid Submission

- install from the XML in a clean Unraid environment
- verify first boot works with defaults
- verify advanced settings stay optional
- verify generated credentials persist if applicable
- confirm the Docker Hub image is public and pullable
- confirm `awesome-unraid` contains the XML and icon
- confirm the README first-run notes match the real install behavior
- if using release tags, confirm version tags such as `v1.2.3` publish the expected image tags
- confirm the upstream monitor opens the expected PR or issue path
