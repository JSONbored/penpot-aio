from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET

from tests.conftest import REPO_ROOT
from tests.helpers import run_command

XML_PATH = REPO_ROOT / "penpot-aio.xml"
INVENTORY_PATH = REPO_ROOT / "docs/upstream/penpot-config-inventory.json"
SECRET_HINTS = ("ACCESS_KEY", "API_KEY", "AUTH", "CREDENTIAL", "JWT", "KEY", "PASSWORD", "SECRET", "TOKEN")
NON_SECRET_TARGETS = {
    "PENPOT_ASSETS_PATH",
    "PENPOT_AUTH_TOKEN_COOKIE_MAX_AGE",
    "PENPOT_AUTH_TOKEN_COOKIE_NAME",
    "PENPOT_EMAIL_VERIFY_THRESHOLD",
    "PENPOT_HTTP_SERVER_MAX_BODY_SIZE",
    "PENPOT_HTTP_SERVER_MAX_MULTIPART_BODY_SIZE",
    "PENPOT_MCP_LOG_DIR",
    "PENPOT_MCP_LOG_LEVEL",
    "PENPOT_OBJECTS_STORAGE_S3_ENDPOINT",
    "PENPOT_OBJECTS_STORAGE_S3_REGION",
    "PENPOT_PUBLIC_URI",
    "PENPOT_TELEMETRY_ENABLED",
    "PENPOT_TELEMETRY_URI",
}


def configs() -> list[ET.Element]:
    root = ET.parse(XML_PATH).getroot()
    return list(root.findall("Config"))


def config_targets() -> set[str]:
    return {config.attrib["Target"] for config in configs()}


def config_by_target() -> dict[str, ET.Element]:
    return {config.attrib["Target"]: config for config in configs()}


def test_generated_penpot_template_is_current() -> None:
    result = run_command(
        [sys.executable, "scripts/generate_penpot_template.py", "--check"],
        cwd=REPO_ROOT,
    )
    assert "matches the generated template" in result.stdout  # nosec B101


def test_xml_parses_and_has_ca_metadata() -> None:
    root = ET.parse(XML_PATH).getroot()
    assert root.findtext("Name") == "penpot-aio"  # nosec B101
    assert root.findtext("Repository") == "jsonbored/penpot-aio:latest"  # nosec B101
    assert root.findtext("Project") == "https://github.com/JSONbored/penpot-aio"  # nosec B101
    assert root.findtext("Support") == "https://github.com/JSONbored/penpot-aio/issues"  # nosec B101
    assert root.findtext("TemplateURL") == "https://raw.githubusercontent.com/JSONbored/awesome-unraid/main/penpot-aio.xml"  # nosec B101
    assert root.findtext("Icon") == "https://raw.githubusercontent.com/JSONbored/awesome-unraid/main/icons/penpot.png"  # nosec B101
    assert "Productivity" in (root.findtext("Category") or "")  # nosec B101


def test_upstream_inventory_is_fully_represented() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())
    targets = config_targets()
    missing_env = sorted({item["name"] for item in inventory["env"]} - targets)
    assert missing_env == []  # nosec B101

    missing_flags = []
    for flag in inventory["flags"]:
        target = f"PENPOT_AIO_FLAG_{flag['name'].upper().replace('-', '_')}"
        if target not in targets:
            missing_flags.append(flag["name"])
    assert missing_flags == []  # nosec B101


def test_known_upstream_doc_typos_are_normalized() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())
    names = {item["name"] for item in inventory["env"]}
    targets = config_targets()
    assert "PENPOT_AUTO_FILE_SNAPSHOT_TIMEOUT" in names  # nosec B101
    assert "PENPOT_AUTO_FILE_SNAPSHOT_TIMEOUT" in targets  # nosec B101
    assert "PENPOT_AUTO_FILE_SNAPSHOT_TIIMEOUT" not in names  # nosec B101
    assert "PENPOT_AUTO_FILE_SNAPSHOT_TIIMEOUT" not in targets  # nosec B101


def test_beginner_surface_stays_minimal() -> None:
    always = {config.attrib["Target"] for config in configs() if config.attrib.get("Display") == "always"}
    assert always == {"8080", "/appdata", "PENPOT_PUBLIC_URI"}  # nosec B101

    required = {config.attrib["Target"] for config in configs() if config.attrib.get("Required") == "true"}
    assert required == {"8080", "/appdata"}  # nosec B101


def test_expected_configuration_groups_are_exposed() -> None:
    group_names = {
        (config.attrib["Name"].split("]", 1)[0].removeprefix("["))
        for config in configs()
        if config.attrib["Name"].startswith("[")
    }
    expected = {
        "AIO Runtime",
        "Access",
        "Advanced Upstream",
        "Auth",
        "Cache",
        "Core",
        "Database",
        "Flags",
        "Limits/Performance",
        "MCP",
        "SMTP",
        "Security/SSRF",
        "Storage",
        "Telemetry",
    }
    missing = sorted(expected - group_names)
    assert missing == []  # nosec B101


def test_aio_escape_hatch_is_present_but_not_substituting_for_inventory() -> None:
    by_target = config_by_target()
    assert by_target["PENPOT_AIO_EXTRA_ENV_FILE"].attrib["Display"] == "advanced"  # nosec B101
    assert by_target["PENPOT_AIO_EXTRA_ENV_FILE"].text == "/appdata/config/extra.env"  # nosec B101
    assert len(config_targets()) > 240  # nosec B101


def test_secret_like_fields_are_masked() -> None:
    failures = []
    for config in configs():
        target = config.attrib["Target"]
        if target.startswith("PENPOT_AIO_FLAG_") or target in NON_SECRET_TARGETS:
            continue
        if any(hint in target for hint in SECRET_HINTS) and config.attrib.get("Mask") != "true":
            failures.append(target)
    assert failures == []  # nosec B101


def test_dropdown_defaults_include_selected_value() -> None:
    failures = []
    for config in configs():
        default = config.attrib.get("Default", "")
        if "|" not in default:
            continue
        selected = config.text or ""
        if selected == default:
            continue
        if selected not in default.split("|"):
            failures.append(config.attrib["Target"])
    assert failures == []  # nosec B101


def test_literal_pipe_defaults_are_not_treated_as_dropdowns() -> None:
    ldap_query = config_by_target()["PENPOT_LDAP_USER_QUERY"]
    assert ldap_query.attrib["Default"] == "(|(uid=:username)(mail=:username))"  # nosec B101
    assert ldap_query.text == "(|(uid=:username)(mail=:username))"  # nosec B101
    raw_xml = XML_PATH.read_text()
    assert 'Target="PENPOT_LDAP_USER_QUERY" Default="(&#124;(uid=:username)(mail=:username))"' in raw_xml  # nosec B101


def test_dropdowns_use_pipe_delimited_values_without_nested_options() -> None:
    for config in configs():
        assert config.findall("Option") == []  # nosec B101

    by_target = config_by_target()
    expected_dropdowns = {
        "PENPOT_AIO_ENABLE_INTERNAL_POSTGRES": "true|false",
        "PENPOT_AIO_ENABLE_INTERNAL_REDIS": "true|false",
        "PENPOT_AIO_ENABLE_MAILPIT": "true|false",
        "PENPOT_AIO_ENABLE_MCP": "true|false",
        "PENPOT_AIO_REDIS_MAXMEMORY_POLICY": "volatile-lfu|allkeys-lfu|allkeys-lru|volatile-lru|noeviction",
        "PENPOT_MCP_LOG_LEVEL": "info|debug|warn|error|trace",
        "PENPOT_OBJECTS_STORAGE_BACKEND": "fs|s3",
        "PENPOT_OIDC_USER_INFO_SOURCE": "auto|userinfo|token",
        "PENPOT_TELEMETRY_ENABLED": "false|true",
    }
    for target, default in expected_dropdowns.items():
        assert by_target[target].attrib["Default"] == default  # nosec B101
