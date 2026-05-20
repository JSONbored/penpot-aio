# Suite Components

Suite/component metadata is declared in `aio-fleet/fleet.yml` and exported into the app repo `.aio-fleet.yml`. App repos should not carry `components.toml` or component helper scripts.

Use this pattern only when one product genuinely needs multiple published images or XML templates under the same support surface, such as `signoz-aio` plus `signoz-agent`.

## Component Fields

Declare component-specific fields in `aio-fleet/fleet.yml`:

- `image_name`
- `docker_cache_scope`
- `pytest_image_tag`
- `context`
- `dockerfile`
- `xml_paths`
- `integration_pytest_args`
- `upstream_version_key`
- `release_suffix`

Then export the manifest:

```sh
python -m aio_fleet export-app-manifest --repo <repo> --write
```

The app repo keeps only `.aio-fleet.yml` plus the actual component Dockerfile/XML/runtime files.
