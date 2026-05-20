#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/upstream/penpot-config-inventory.json"
UPSTREAM_VERSION = "2.15.3"
RAW_BASE = f"https://raw.githubusercontent.com/penpot/penpot/{UPSTREAM_VERSION}"

SOURCES = {
    "backend_config": f"{RAW_BASE}/backend/src/app/config.clj",
    "flags": f"{RAW_BASE}/common/src/app/common/flags.cljc",
    "compose": f"{RAW_BASE}/docker/images/docker-compose.yaml",
    "frontend_entrypoint": f"{RAW_BASE}/docker/images/files/nginx-entrypoint.sh",
    "mcp_tree": f"https://api.github.com/repos/penpot/penpot/git/trees/{UPSTREAM_VERSION}?recursive=1",
    "docs_config": "https://help.penpot.app/technical-guide/configuration/",
}

ENV_NAME_ALIASES = {
    # Penpot 2.15.3 docs contain this misspelling, but backend config only
    # recognizes PENPOT_AUTO_FILE_SNAPSHOT_TIMEOUT.
    "PENPOT_AUTO_FILE_SNAPSHOT_TIIMEOUT": "PENPOT_AUTO_FILE_SNAPSHOT_TIMEOUT",
}


def fetch(url: str) -> str:
    try:
        request = Request(
            url, headers={"User-Agent": "penpot-aio-config-inventory/1.0"}
        )
        with urlopen(
            request, timeout=45
        ) as response:  # nosec B310 - fixed upstream HTTPS URLs.
            return response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"Unable to fetch {url}: {exc}") from exc


def env_name(config_key: str) -> str:
    return f"PENPOT_{config_key.upper().replace('-', '_')}"


def canonical_env_name(name: str) -> str:
    return ENV_NAME_ALIASES.get(name, name)


def simple_default(raw: str) -> str | None:
    raw = raw.strip().rstrip(",")
    if raw.startswith('"'):
        match = re.match(r'"([^"]*)"', raw)
        return match.group(1) if match else None
    if raw in {"true", "false"}:
        return raw
    if re.match(r"^-?\d+$", raw):
        return raw
    if raw.startswith(":"):
        return raw[1:]
    return None


def parse_backend_config(source: str) -> dict[str, dict[str, object]]:
    items: dict[str, dict[str, object]] = {}
    defaults: dict[str, str] = {}
    in_defaults = False
    for line in source.splitlines():
        if line.startswith("(def default"):
            in_defaults = True
            continue
        if in_defaults and line.startswith("   :"):
            match = re.match(r"\s+:([a-z0-9-]+)\s+(.+)$", line)
            if match and (value := simple_default(match.group(2))) is not None:
                defaults[match.group(1)] = value
        if in_defaults and line.strip() == "})":
            in_defaults = False

        match = re.match(r"\s+\[:([a-z0-9-]+)\s+\{[^}]*\}\s+(.+)$", line)
        if not match:
            continue
        key, schema = match.groups()
        name = env_name(key)
        item = items.setdefault(
            name,
            {
                "name": name,
                "config_key": key,
                "sources": [],
                "kind": "string",
                "default": defaults.get(key, ""),
                "enum": [],
            },
        )
        item["sources"].append("backend_config")
        if "::sm/boolean" in schema:
            item["kind"] = "boolean"
        elif "::sm/int" in schema:
            item["kind"] = "integer"
        elif "::ct/duration" in schema:
            item["kind"] = "duration"
        elif "::sm/uri" in schema:
            item["kind"] = "uri"
        elif "::fs/path" in schema:
            item["kind"] = "path"
        enum = re.findall(r'"([^"]+)"', schema) if "[:enum" in schema else []
        if enum:
            item["kind"] = "enum"
            item["enum"] = enum
    for key, value in defaults.items():
        items.setdefault(
            env_name(key),
            {
                "name": env_name(key),
                "config_key": key,
                "sources": ["backend_default"],
                "kind": "string",
                "default": value,
                "enum": [],
            },
        )
    return items


def parse_compose_env(source: str) -> dict[str, dict[str, object]]:
    items: dict[str, dict[str, object]] = {}
    for line in source.splitlines():
        mapping = re.match(r"\s*(PENPOT_[A-Z0-9_]+|AWS_[A-Z0-9_]+):\s*(.*)$", line)
        list_item = re.match(r"\s*-\s*(PENPOT_[A-Z0-9_]+|AWS_[A-Z0-9_]+)=(.*)$", line)
        match = mapping or list_item
        if not match:
            continue
        name = canonical_env_name(match.group(1))
        raw_default = match.group(2).strip()
        default = "" if raw_default in {"", "null", "~"} else raw_default.strip('"')
        items[name] = {
            "name": name,
            "sources": ["compose"],
            "kind": "string",
            "default": default,
            "enum": [],
        }
    return items


def parse_env_names(source: str, source_name: str) -> dict[str, dict[str, object]]:
    items: dict[str, dict[str, object]] = {}
    for raw_name in sorted(set(re.findall(r"\b(?:PENPOT|AWS)_[A-Z0-9_]+\b", source))):
        name = canonical_env_name(raw_name)
        items[name] = {
            "name": name,
            "sources": [source_name],
            "kind": "string",
            "default": "",
            "enum": [],
        }
    return items


def parse_mcp_envs() -> dict[str, dict[str, object]]:
    tree = json.loads(fetch(SOURCES["mcp_tree"]))
    paths = [
        item["path"]
        for item in tree.get("tree", [])
        if item.get("type") == "blob"
        and (
            item["path"].startswith("mcp/packages/server/")
            or item["path"].startswith("mcp/packages/common/")
        )
        and item["path"].rsplit(".", 1)[-1] in {"ts", "js", "json", "md"}
    ]
    items: dict[str, dict[str, object]] = {}
    for path in paths:
        source = fetch(f"{RAW_BASE}/{path}")
        for name, item in parse_env_names(source, "mcp").items():
            items.setdefault(name, item)
    return items


def parse_flags(source: str) -> list[dict[str, object]]:
    flag_names = set()
    in_group = False
    for line in source.splitlines():
        if re.match(r"\(def (login|email|varia)\b", line):
            in_group = True
        if in_group:
            flag_names.update(re.findall(r":([a-z0-9-]+)", line))
        if in_group and line.strip().endswith("})"):
            in_group = False

    default_states: dict[str, str] = {}
    default_block = source[source.find("(def default") :]
    for raw in re.findall(r":(enable|disable)-([a-z0-9-]+)", default_block):
        state, name = raw
        flag_names.add(name)
        default_states[name] = "enabled" if state == "enable" else "disabled"

    return [
        {
            "name": name,
            "default_state": default_states.get(name, "upstream-default"),
            "sources": ["flags"],
        }
        for name in sorted(flag_names)
    ]


def merge_items(*groups: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for group in groups:
        for name, item in group.items():
            current = merged.setdefault(name, dict(item))
            current.setdefault("sources", [])
            current.setdefault("enum", [])
            current["sources"] = sorted(
                set(current["sources"]) | set(item.get("sources", []))
            )
            if not current.get("default") and item.get("default"):
                current["default"] = item["default"]
            if item.get("kind") not in {"", "string", None}:
                current["kind"] = item["kind"]
            if item.get("enum"):
                current["enum"] = item["enum"]
    return [merged[name] for name in sorted(merged)]


def main() -> int:
    backend = fetch(SOURCES["backend_config"])
    flags = fetch(SOURCES["flags"])
    compose = fetch(SOURCES["compose"])
    frontend_entrypoint = fetch(SOURCES["frontend_entrypoint"])
    docs = fetch(SOURCES["docs_config"])

    env_items = merge_items(
        parse_backend_config(backend),
        parse_compose_env(compose),
        parse_env_names(frontend_entrypoint, "frontend_entrypoint"),
        parse_env_names(docs, "docs_config"),
        parse_mcp_envs(),
    )
    payload = {
        "upstream": {
            "repo": "penpot/penpot",
            "version": UPSTREAM_VERSION,
            "release": f"https://github.com/penpot/penpot/releases/tag/{UPSTREAM_VERSION}",
        },
        "sources": SOURCES,
        "env": env_items,
        "flags": parse_flags(flags),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"Wrote {OUT.relative_to(ROOT)} with {len(env_items)} env vars and {len(payload['flags'])} flags."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
