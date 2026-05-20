#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "docs/upstream/penpot-config-inventory.json"
OUTPUT_PATH = ROOT / "penpot-aio.xml"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

SECRET_HINTS = (
    "ACCESS_KEY",
    "API_KEY",
    "AUTH",
    "CREDENTIAL",
    "JWT",
    "KEY",
    "PASSWORD",
    "SECRET",
    "TOKEN",
)

NON_SECRET_TARGETS = {
    "PENPOT_ASSETS_PATH",
    "PENPOT_AUTH_TOKEN_COOKIE_MAX_AGE",
    "PENPOT_AUTH_TOKEN_COOKIE_NAME",
    "PENPOT_EMAIL_VERIFY_THRESHOLD",
    "PENPOT_HTTP_SERVER_MAX_BODY_SIZE",
    "PENPOT_HTTP_SERVER_MAX_MULTIPART_BODY_SIZE",
    "PENPOT_MCP_LOG_LEVEL",
    "PENPOT_MCP_LOG_DIR",
    "PENPOT_OBJECTS_STORAGE_S3_ENDPOINT",
    "PENPOT_OBJECTS_STORAGE_S3_REGION",
    "PENPOT_PUBLIC_URI",
    "PENPOT_TELEMETRY_ENABLED",
    "PENPOT_TELEMETRY_URI",
}

ENUM_OVERRIDES = {
    "PENPOT_FILE_DATA_BACKEND": ("legacy-db", "db", "storage"),
    "PENPOT_OBJECTS_STORAGE_BACKEND": ("fs", "s3"),
    "PENPOT_ASSETS_STORAGE_BACKEND": ("fs", "s3"),
    "PENPOT_OIDC_USER_INFO_SOURCE": ("auto", "userinfo", "token"),
    "PENPOT_MCP_LOG_LEVEL": ("info", "debug", "warn", "error", "trace"),
    "PENPOT_AIO_LOG_LEVEL": ("info", "debug", "warn", "error"),
}

BOOLEAN_DEFAULTS = {
    "PENPOT_AIO_ENABLE_INTERNAL_POSTGRES": "true|false",
    "PENPOT_AIO_ENABLE_INTERNAL_REDIS": "true|false",
    "PENPOT_AIO_ENABLE_MAILPIT": "true|false",
    "PENPOT_AIO_ENABLE_MCP": "true|false",
    "PENPOT_AIO_GENERATE_MISSING_SECRETS": "true|false",
    "PENPOT_DATABASE_READONLY": "false|true",
    "PENPOT_LDAP_SSL": "false|true",
    "PENPOT_LDAP_STARTTLS": "false|true",
    "PENPOT_MCP_REMOTE_MODE": "true|false",
    "PENPOT_SMTP_SSL": "false|true",
    "PENPOT_SMTP_TLS": "false|true",
    "PENPOT_TELEMETRY_ENABLED": "false|true",
    "PENPOT_TELEMETRY_WITH_TAIGA": "false|true",
}

CURATED_DEFAULTS = {
    "PENPOT_PUBLIC_URI": "http://localhost:9001",
    "PENPOT_HTTP_SERVER_HOST": "127.0.0.1",
    "PENPOT_HTTP_SERVER_PORT": "6060",
    "PENPOT_HTTP_SERVER_MAX_BODY_SIZE": "367001600",
    "PENPOT_HTTP_SERVER_MAX_MULTIPART_BODY_SIZE": "367001600",
    "PENPOT_DATABASE_URI": "",
    "PENPOT_DATABASE_USERNAME": "penpot",
    "PENPOT_DATABASE_PASSWORD": "",
    "PENPOT_REDIS_URI": "",
    "PENPOT_OBJECTS_STORAGE_BACKEND": "fs|s3",
    "PENPOT_OBJECTS_STORAGE_FS_DIRECTORY": "/appdata/assets",
    "PENPOT_FILE_DATA_BACKEND": "storage|legacy-db|db",
    "PENPOT_SMTP_HOST": "",
    "PENPOT_SMTP_PORT": "",
    "PENPOT_SMTP_USERNAME": "",
    "PENPOT_SMTP_PASSWORD": "",
    "PENPOT_SMTP_TLS": "false|true",
    "PENPOT_SMTP_SSL": "false|true",
    "PENPOT_SMTP_DEFAULT_FROM": "Penpot <no-reply@penpot.local>",
    "PENPOT_SMTP_DEFAULT_REPLY_TO": "Penpot <no-reply@penpot.local>",
    "PENPOT_TELEMETRY_ENABLED": "false|true",
    "PENPOT_TELEMETRY_REFERER": "unraid-aio",
    "PENPOT_BACKEND_URI": "http://127.0.0.1:6060",
    "PENPOT_EXPORTER_URI": "http://127.0.0.1:6061",
    "PENPOT_MCP_URI": "http://127.0.0.1:4401",
    "PENPOT_MCP_URI_WS": "http://127.0.0.1:4402",
    "PENPOT_MCP_SERVER_HOST": "127.0.0.1",
    "PENPOT_MCP_SERVER_PORT": "4401",
    "PENPOT_MCP_WEBSOCKET_PORT": "4402",
    "PENPOT_MCP_REPL_PORT": "",
    "PENPOT_MCP_REMOTE_MODE": "true|false",
    "PENPOT_MCP_LOG_LEVEL": "info|debug|warn|error|trace",
    "PENPOT_MCP_LOG_DIR": "/appdata/logs/mcp",
    "PENPOT_FLAGS": "",
    "PENPOT_SECRET_KEY": "",
}

AIO_CONFIGS = [
    ("PENPOT_AIO_ENABLE_INTERNAL_POSTGRES", "true|false", "Use the bundled PostgreSQL database. Set false only when PENPOT_DATABASE_URI points at an external PostgreSQL server.", False),
    ("PENPOT_AIO_ENABLE_INTERNAL_REDIS", "true|false", "Use the bundled Redis-compatible cache. Set false only when PENPOT_REDIS_URI points at an external Redis or Valkey service.", False),
    ("PENPOT_AIO_ENABLE_MAILPIT", "true|false", "Use bundled Mailpit when SMTP_HOST is blank so local email-dependent flows work on first boot.", False),
    ("PENPOT_AIO_ENABLE_MCP", "true|false", "Run Penpot MCP inside the AIO container and expose it through the frontend /mcp routes.", False),
    ("PENPOT_AIO_DEFAULT_FLAGS", "disable-email-verification enable-smtp disable-secure-session-cookies enable-mcp", "Default flags used when PENPOT_FLAGS is blank. Remove disable-* entries before public HTTPS production use.", False),
    ("PENPOT_AIO_EXTRA_ENV_FILE", "/appdata/config/extra.env", "Optional dotenv-style escape hatch loaded after generated defaults. Use only for rare upstream variables or temporary debugging.", False),
    ("PENPOT_AIO_WAIT_TIMEOUT_SECONDS", "360", "Startup wait timeout for internal PostgreSQL, Redis, and Mailpit readiness checks.", False),
    ("PENPOT_AIO_DATABASE_NAME", "penpot", "Database name used by the bundled PostgreSQL cluster.", False),
    ("PENPOT_AIO_REDIS_PASSWORD", "", "Optional manual password for bundled Redis. Leave blank to generate and persist one on first boot.", True),
    ("PENPOT_AIO_REDIS_MAXMEMORY", "256mb", "Bundled Redis maxmemory setting.", False),
    ("PENPOT_AIO_REDIS_MAXMEMORY_POLICY", "volatile-lfu|allkeys-lfu|allkeys-lru|volatile-lru|noeviction", "Bundled Redis memory eviction policy.", False),
    ("PENPOT_AIO_MAILPIT_UI_USERNAME", "", "Optional Mailpit UI username. Leave blank to persist the default penpot username.", False),
    ("PENPOT_AIO_MAILPIT_UI_PASSWORD", "", "Optional Mailpit UI password. Leave blank to generate and persist one on first boot.", True),
    ("PENPOT_AIO_MAILPIT_MAX_MESSAGES", "500", "Maximum messages retained by the bundled Mailpit inbox.", False),
    ("PENPOT_AIO_MAILPIT_MAX_AGE", "14d", "Maximum age for messages retained by bundled Mailpit.", False),
    ("PENPOT_AIO_LOG_LEVEL", "info|debug|warn|error", "Wrapper log level. This does not replace upstream Penpot logging controls.", False),
]


@dataclass
class Config:
    name: str
    target: str
    default: str = ""
    value: str | None = None
    mode: str = ""
    description: str = ""
    type: str = "Variable"
    display: str = "advanced"
    required: bool = False
    mask: bool = False

    def render(self) -> str:
        value = selected_value(self.default, self.value)
        literal_pipe_default = "|" in self.default and not is_dropdown_default(self.default)
        attrs = {
            "Name": self.name,
            "Target": self.target,
            "Default": self.default,
            "Mode": self.mode,
            "Description": self.description,
            "Type": self.type,
            "Display": self.display,
            "Required": "true" if self.required else "false",
            "Mask": "true" if self.mask else "false",
        }
        attr_text = " ".join(
            f'{key}="{escape(attr_value, escape_pipe=(key == "Default" and literal_pipe_default))}"'
            for key, attr_value in attrs.items()
        )
        if value == "":
            return f"  <Config {attr_text}/>"
        return f"  <Config {attr_text}>{escape(value, escape_pipe=literal_pipe_default)}</Config>"


def escape(value: str, *, escape_pipe: bool = False) -> str:
    escaped = html.escape(str(value), quote=True)
    if escape_pipe:
        escaped = escaped.replace("|", "&#124;")
    return escaped


def selected_value(default: str, explicit: str | None = None) -> str:
    if explicit is not None:
        return explicit
    if is_dropdown_default(default):
        return default.split("|", 1)[0]
    return default


def is_dropdown_default(default: str) -> bool:
    if "|" not in default:
        return False
    options = default.split("|")
    if any(option == "" for option in options):
        return False
    return all(re.fullmatch(r"[A-Za-z0-9_.:/@+-]+", option) for option in options)


def display_name(target: str) -> str:
    name = target
    if name.startswith("PENPOT_AIO_"):
        name = name.removeprefix("PENPOT_AIO_")
    elif name.startswith("PENPOT_"):
        name = name.removeprefix("PENPOT_")
    return name.replace("_", " ").title().replace("Uri", "URI").replace("Ssrf", "SSRF").replace("Mcp", "MCP").replace("Oidc", "OIDC").replace("Ldap", "LDAP").replace("Smtp", "SMTP").replace("Aws", "AWS").replace("S3", "S3")


def group_for(target: str) -> str:
    if target.startswith("PENPOT_AIO_"):
        return "AIO Runtime"
    if target in {
        "PENPOT_BACKEND_URI",
        "PENPOT_EXPORTER_URI",
        "PENPOT_HOST",
        "PENPOT_HTTP_SERVER_HOST",
        "PENPOT_HTTP_SERVER_PORT",
        "PENPOT_INTERNAL_RESOLVER",
        "PENPOT_NITRATE_URI",
        "PENPOT_PUBLIC_URI",
    }:
        return "Access"
    if target.startswith(("PENPOT_DATABASE_",)):
        return "Database"
    if target.startswith("PENPOT_REDIS_"):
        return "Cache"
    if target.startswith("PENPOT_SMTP_") or target.startswith(("PENPOT_EMAIL_",)):
        return "SMTP"
    if any(part in target for part in ("GITHUB", "GITLAB", "GOOGLE", "OIDC", "LDAP", "REGISTRATION", "AUTH_TOKEN")):
        return "Auth"
    if "STORAGE" in target or "ASSETS" in target or target.startswith(("AWS_", "PENPOT_MEDIA_", "PENPOT_FONT_", "PENPOT_FILE_DATA")):
        return "Storage"
    if "MCP" in target:
        return "MCP"
    if "TELEMETRY" in target or "WEBHOOK" in target or "FEEDBACK" in target:
        return "Telemetry"
    if any(part in target for part in ("MAX", "THREAD", "POOL", "PARALLELISM", "LIMIT", "QUOTES", "DELAY", "SNAPSHOT")):
        return "Limits/Performance"
    if "SSRF" in target or "CORS" in target or "COOKIE" in target:
        return "Security/SSRF"
    if target in {"PENPOT_FLAGS", "PENPOT_SECRET_KEY", "PENPOT_TENANT"}:
        return "Core"
    return "Advanced Upstream"


def mask_for(target: str) -> bool:
    if target.startswith("PENPOT_AIO_FLAG_"):
        return False
    if target in NON_SECRET_TARGETS:
        return False
    return any(hint in target for hint in SECRET_HINTS)


def description_for(target: str) -> str:
    custom = {
        "PENPOT_PUBLIC_URI": "Canonical URL users will visit, including http or https. For LAN installs use your Unraid host and mapped port; for public installs use the reverse-proxy HTTPS URL.",
        "PENPOT_SECRET_KEY": "Penpot master secret key. Leave blank to generate and persist a strong value on first boot. Changing this later can invalidate sessions and encrypted data.",
        "PENPOT_DATABASE_URI": "Leave blank for bundled PostgreSQL. Set a PostgreSQL URI only when using an external database.",
        "PENPOT_DATABASE_USERNAME": "PostgreSQL username. The bundled database uses penpot.",
        "PENPOT_DATABASE_PASSWORD": "PostgreSQL password. Leave blank to generate and persist one for the bundled database.",
        "PENPOT_REDIS_URI": "Leave blank for bundled Redis-compatible cache. Set an external Redis or Valkey URI only when disabling the internal cache.",
        "PENPOT_OBJECTS_STORAGE_BACKEND": "Object storage backend. The AIO default stores assets on the AppData filesystem; S3 requires the matching S3 fields.",
        "PENPOT_OBJECTS_STORAGE_FS_DIRECTORY": "Filesystem asset directory for the bundled storage path.",
        "PENPOT_FLAGS": "Raw upstream Penpot flags. Leave blank to use AIO defaults plus per-flag dropdown controls.",
        "PENPOT_SMTP_HOST": "External SMTP hostname. Leave blank to use bundled Mailpit for local/lab email capture.",
        "PENPOT_SMTP_PORT": "External SMTP port. Leave blank with SMTP Host to use bundled Mailpit on internal port 1025.",
        "PENPOT_TELEMETRY_ENABLED": "Usage telemetry toggle. The AIO default is false for privacy-first self-hosting.",
        "PENPOT_MCP_REMOTE_MODE": "MCP remote mode. Keep true for the bundled HTTP/WebSocket MCP server path.",
        "PENPOT_MCP_LOG_LEVEL": "MCP log verbosity.",
    }
    if target in custom:
        return custom[target]
    return f"Advanced upstream Penpot environment variable {target}."


def default_for(item: dict[str, object]) -> str:
    target = str(item["name"])
    if target in CURATED_DEFAULTS:
        return CURATED_DEFAULTS[target]
    if target in BOOLEAN_DEFAULTS:
        return BOOLEAN_DEFAULTS[target]
    if target in ENUM_OVERRIDES:
        return "|".join(ENUM_OVERRIDES[target])
    enum = item.get("enum") or []
    if enum:
        return "|".join(str(value) for value in enum)
    if item.get("kind") == "boolean":
        raw_default = str(item.get("default") or "").lower()
        return "true|false" if raw_default == "true" else "false|true"
    raw = str(item.get("default") or "")
    if "<" in raw or raw.startswith("${"):
        return ""
    return raw


def build_configs(inventory: dict[str, object]) -> list[Config]:
    configs: list[Config] = [
        Config("Web UI Port", "8080", "9001", mode="tcp", description="Penpot frontend, API gateway, exporter routes, and MCP proxy.", type="Port", display="always", required=True),
        Config("Mailpit UI Port", "8025", "8026", mode="tcp", description="Bundled Mailpit inbox UI for local/lab mail capture. Advanced because normal Penpot use starts through the Web UI.", type="Port"),
        Config("MCP HTTP Port", "4401", "", mode="tcp", description="Optional direct host port for the Penpot MCP HTTP endpoint. Leave blank unless you need direct MCP access outside the frontend /mcp route.", type="Port"),
        Config("MCP WebSocket Port", "4402", "", mode="tcp", description="Optional direct host port for the Penpot MCP WebSocket endpoint. Leave blank unless you need direct MCP access outside the frontend /mcp route.", type="Port"),
        Config("AppData", "/appdata", "/mnt/user/appdata/penpot-aio", mode="rw", description="Persistent Penpot data, PostgreSQL data, cache data, generated secrets, assets, Mailpit data, logs, and optional extra.env.", type="Path", display="always", required=True),
        Config("Public URL", "PENPOT_PUBLIC_URI", "http://localhost:9001", description=description_for("PENPOT_PUBLIC_URI"), display="always"),
    ]

    seen = {config.target for config in configs}
    for target, default, description, masked in AIO_CONFIGS:
        configs.append(
            Config(
                f"[AIO Runtime] {display_name(target)}",
                target,
                default,
                description=description,
                mask=masked,
            )
        )
        seen.add(target)

    env_items = inventory.get("env", [])
    assert isinstance(env_items, list)
    for item in env_items:
        target = str(item["name"])
        if target in seen:
            continue
        group = group_for(target)
        configs.append(
            Config(
                f"[{group}] {display_name(target)}",
                target,
                default_for(item),
                description=description_for(target),
                mask=mask_for(target),
            )
        )
        seen.add(target)

    flags = inventory.get("flags", [])
    assert isinstance(flags, list)
    for flag in flags:
        flag_name = str(flag["name"])
        target = f"PENPOT_AIO_FLAG_{flag_name.upper().replace('-', '_')}"
        configs.append(
            Config(
                f"[Flags] {flag_name}",
                target,
                "default|enable|disable",
                description=f"Per-flag control for Penpot flag {flag_name}. default leaves upstream/AIO defaults alone; enable or disable appends the matching flag token when PENPOT_FLAGS is blank.",
            )
        )
    return configs


def changes_body() -> str:
    return "\n".join(
        [
            "### 2026-05-20",
            "- Generated from CHANGELOG.md during release preparation. Do not edit manually.",
            "- Initial Penpot AIO implementation with bundled frontend, backend, exporter, MCP, PostgreSQL, Redis-compatible cache, Mailpit, generated secrets, and exhaustive upstream config exposure.",
        ]
    )


def template_overview() -> str:
    return textwrap.dedent("""
        Penpot is an open-source design and prototyping platform for product teams, designers, and developers.

        [b]All-In-One Unraid Edition[/b]
        `penpot-aio` packages Penpot frontend, backend, exporter, MCP server, PostgreSQL, Redis-compatible cache, Nginx, and Mailpit into one practical Unraid-first container.

        [b]Quick Install (Beginners)[/b]
        1. Install this template and leave [code]Web UI Port[/code] and [code]AppData[/code] at their defaults unless you have a port or path conflict.
        2. Set [code]Public URL[/code] to the URL users will actually visit, such as [code]http://tower.local:9001[/code] or your reverse-proxy HTTPS URL.
        3. Start the container and give first boot a few minutes. The wrapper initializes bundled PostgreSQL, Redis-compatible cache, filesystem assets, Mailpit, MCP, and generated secrets.
        4. Open the Web UI and create your first account. The default lab path disables email verification and uses local Mailpit; change the flags and SMTP settings before public production use.

        [b]Power Users (Advanced View)[/b]
        - Advanced View exposes upstream Penpot configuration, Penpot flags, external PostgreSQL, external Redis/Valkey, SMTP, S3-compatible object storage, OAuth/OIDC/LDAP, telemetry, MCP, SSRF controls, rate/limit/performance tuning, and AIO runtime controls.
        - Leave database, cache, SMTP, and storage fields blank/defaulted for the bundled one-container path. Set the matching external fields only when intentionally moving that service out of the AIO container.
        - Blank secret fields generate and persist values in [code]/appdata/config/generated.env[/code]. Explicit template values override generated values.
        - [code]/appdata/config/extra.env[/code] is loaded as a final escape hatch, not a substitute for the exposed template options.

        [b]Important Notes[/b]
        - Penpot is a real multi-service stack. Plan for at least 2 CPU cores and 4 GiB RAM, with more for active teams or large files.
        - Public exposure should sit behind a trusted HTTPS reverse proxy. Remove [code]disable-secure-session-cookies[/code] and [code]disable-email-verification[/code] for production.
        - The bundled Mailpit inbox is for local/lab capture, not real mail deliverability.
        """).strip()


def encode_multiline(value: str) -> str:
    return html.escape(value, quote=False).replace("\n", "&#xD;\n")


def render_template(configs: list[Config]) -> str:
    config_lines = "\n".join(config.render() for config in configs)
    return f"""<?xml version="1.0"?>
<Container version="2">
  <Name>penpot-aio</Name>
  <Repository>jsonbored/penpot-aio:latest</Repository>
  <Registry>https://hub.docker.com/r/jsonbored/penpot-aio</Registry>
  <Network>bridge</Network>
  <MyIP/>
  <Shell>sh</Shell>
  <Privileged>false</Privileged>
  <Support>https://github.com/JSONbored/penpot-aio/issues</Support>
  <Project>https://github.com/JSONbored/penpot-aio</Project>
  <Overview>{encode_multiline(template_overview())}</Overview>
  <Changes>{encode_multiline(changes_body())}</Changes>
  <Category>Productivity Tools:Utilities</Category>
  <WebUI>http://[IP]:[PORT:8080]</WebUI>
  <TemplateURL>https://raw.githubusercontent.com/JSONbored/awesome-unraid/main/penpot-aio.xml</TemplateURL>
  <ReadMe>https://github.com/JSONbored/penpot-aio#readme</ReadMe>
  <Icon>https://raw.githubusercontent.com/JSONbored/awesome-unraid/main/icons/penpot.png</Icon>
  <ExtraSearchTerms>design prototype figma alternative whiteboard mcp ux ui product design self-hosted</ExtraSearchTerms>
  <Requires>Penpot is a heavier multi-service application. Plan for at least 2 CPU cores and 4 GiB RAM. Use HTTPS and production-safe flags before exposing it publicly.</Requires>
  <ExtraParams/>
  <PostArgs/>
  <CPUset/>
  <DateInstalled/>
  <DonateText>Support JSONbored on GitHub Sponsors.</DonateText>
  <DonateLink>https://github.com/sponsors/JSONbored</DonateLink>
  <Description/>
  <Networking>
    <Mode>bridge</Mode>
    <Publish>
      <Port>
        <HostPort>9001</HostPort>
        <ContainerPort>8080</ContainerPort>
        <Protocol>tcp</Protocol>
      </Port>
      <Port>
        <HostPort>8026</HostPort>
        <ContainerPort>8025</ContainerPort>
        <Protocol>tcp</Protocol>
      </Port>
    </Publish>
  </Networking>
  <Data>
    <Volume>
      <HostDir>/mnt/user/appdata/penpot-aio</HostDir>
      <ContainerDir>/appdata</ContainerDir>
      <Mode>rw</Mode>
    </Volume>
  </Data>
  <Environment/>

{config_lines}
</Container>
"""


def validate_configs(configs: list[Config], inventory: dict[str, object]) -> None:
    targets = [config.target for config in configs]
    duplicates = sorted(target for target in set(targets) if targets.count(target) > 1)
    if duplicates:
        raise SystemExit(f"Duplicate Config targets: {', '.join(duplicates)}")
    for config in configs:
        if (
            is_dropdown_default(config.default)
            and selected_value(config.default, config.value) not in config.default.split("|")
        ):
            raise SystemExit(f"{config.target}: selected value is not in dropdown default")
        if (
            any(hint in config.target for hint in SECRET_HINTS)
            and config.target not in NON_SECRET_TARGETS
            and not config.target.startswith("PENPOT_AIO_FLAG_")
            and not config.mask
        ):
            raise SystemExit(f"{config.target}: secret-like target is not masked")
    env_names = {str(item["name"]) for item in inventory.get("env", [])}
    missing_env = sorted(env_names - set(targets))
    if missing_env:
        raise SystemExit(f"Inventory env vars missing from XML: {', '.join(missing_env)}")
    missing_flags = []
    for flag in inventory.get("flags", []):
        target = f"PENPOT_AIO_FLAG_{str(flag['name']).upper().replace('-', '_')}"
        if target not in targets:
            missing_flags.append(str(flag["name"]))
    if missing_flags:
        raise SystemExit(f"Inventory flags missing from XML: {', '.join(sorted(missing_flags))}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    inventory = json.loads(INVENTORY_PATH.read_text())
    configs = build_configs(inventory)
    validate_configs(configs, inventory)
    output = render_template(configs)
    if args.check:
        if OUTPUT_PATH.read_text() != output:
            raise SystemExit("penpot-aio.xml is not current; run scripts/generate_penpot_template.py")
        print("penpot-aio.xml matches the generated template.")
        return 0
    OUTPUT_PATH.write_text(output)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(configs)} Config entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
