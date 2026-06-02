from __future__ import annotations

import os
import uuid

import pytest

from tests.helpers import (
    DockerRuntime,
    docker_available,
    docker_exec,
    docker_network,
    run_command,
)

IMAGE_TAG = "penpot-aio:pytest"
pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def runtime() -> DockerRuntime:
    if not docker_available():
        pytest.skip("Docker is unavailable; integration tests require Docker/OrbStack.")

    runtime = DockerRuntime(IMAGE_TAG)
    runtime.build()
    return runtime


def test_happy_path_boot_and_restart_persists_generated_env(
    runtime: DockerRuntime,
) -> None:
    with runtime.container(
        env_overrides={"PENPOT_PUBLIC_URI": "http://127.0.0.1:9001"}
    ) as container:
        container.wait_for_http(path="/readyz")
        container.wait_for_http(path="/")

        assert container.path_exists("/appdata/config/generated.env")  # nosec B101
        generated = container.read_text("/appdata/config/generated.env")
        assert "PENPOT_SECRET_KEY=" in generated  # nosec B101
        assert "PENPOT_DATABASE_PASSWORD=" in generated  # nosec B101
        assert "PENPOT_AIO_REDIS_PASSWORD=" in generated  # nosec B101
        assert "PENPOT_AIO_MAILPIT_UI_PASSWORD=" in generated  # nosec B101

        secret_before = container.exec(
            "awk -F= '/^PENPOT_SECRET_KEY=/{print $2}' /appdata/config/generated.env"
        ).stdout.strip()
        redis_password = (
            container.exec(
                "awk -F= '/^PENPOT_AIO_REDIS_PASSWORD=/{print $2}' /appdata/config/generated.env"
            )
            .stdout.strip()
            .strip('"')
        )
        assert secret_before  # nosec B101
        assert redis_password  # nosec B101

        processes = container.exec("ps -eo comm=,args=").stdout
        for expected in (
            "postgres",
            "redis-server",
            "mailpit",
            "nginx",
            "java",
            "node",
        ):
            assert expected in processes  # nosec B101
        assert redis_password not in processes  # nosec B101
        listeners = container.exec("ss -ltn").stdout
        assert ":6060" in listeners  # nosec B101
        assert ":6061" in listeners  # nosec B101
        assert "Address already in use" not in container.logs()  # nosec B101
        nginx_config = container.read_text("/etc/nginx/nginx.conf")
        assert "${PENPOT_IPV6_LISTEN_DIRECTIVE}" not in nginx_config  # nosec B101
        assert "location /internal/assets" in nginx_config  # nosec B101
        assert "alias /appdata/assets;" in nginx_config  # nosec B101
        assert "alias /opt/data/assets;" not in nginx_config  # nosec B101

        container.restart()
        container.wait_for_http(path="/readyz")

        secret_after = container.exec(
            "awk -F= '/^PENPOT_SECRET_KEY=/{print $2}' /appdata/config/generated.env"
        ).stdout.strip()
        assert secret_after == secret_before  # nosec B101


def test_explicit_secret_overrides_skip_generated_values(
    runtime: DockerRuntime,
) -> None:
    with runtime.container(
        env_overrides={
            "PENPOT_PUBLIC_URI": "http://127.0.0.1:9001",
            "PENPOT_SECRET_KEY": "explicit-template-value",  # nosec B105
            "PENPOT_DATABASE_PASSWORD": "explicit-database-value",  # nosec B105
            "PENPOT_AIO_REDIS_PASSWORD": "explicit-redis-value",  # nosec B105
            "PENPOT_AIO_MAILPIT_UI_PASSWORD": "explicit-mailpit-value",  # nosec B105
        }
    ) as container:
        container.wait_for_http(path="/readyz")
        generated = container.read_text("/appdata/config/generated.env")
        for key in (
            "PENPOT_SECRET_KEY",
            "PENPOT_DATABASE_PASSWORD",
            "PENPOT_AIO_REDIS_PASSWORD",
            "PENPOT_AIO_MAILPIT_UI_PASSWORD",
        ):
            assert f"{key}=" not in generated  # nosec B101


def test_extra_env_file_overrides_generated_runtime_defaults(
    runtime: DockerRuntime,
) -> None:
    payload_marker = "/appdata/config/penpot-extra-env-executed"
    shell_payload = f"$(touch {payload_marker})"
    with runtime.container(
        env_overrides={"PENPOT_PUBLIC_URI": "http://127.0.0.1:9001"},
        preseed_appdata=[
            "install -d -m 700 /appdata/config && "
            "printf '%s\n' 'PENPOT_TELEMETRY_REFERER=extra-env-test' "
            "'PENPOT_FLAGS=enable-demo-users' "
            f"'PENPOT_AIO_LOG_LEVEL={shell_payload}' > /appdata/config/extra.env && "
            "chmod 600 /appdata/config/extra.env"
        ],
    ) as container:
        container.wait_for_http(path="/readyz")
        runtime_env = container.read_text("/run/penpot-aio/runtime.env")
        assert (
            "export PENPOT_TELEMETRY_REFERER=extra-env-test" in runtime_env
        )  # nosec B101
        assert "export PENPOT_FLAGS=enable-demo-users" in runtime_env  # nosec B101
        assert (
            f"export PENPOT_AIO_LOG_LEVEL='{shell_payload}'" in runtime_env
        )  # nosec B101
        assert not container.path_exists(payload_marker)  # nosec B101


def test_external_smtp_configuration_keeps_bundled_mailpit_idle(
    runtime: DockerRuntime,
) -> None:
    with runtime.container(
        env_overrides={
            "PENPOT_PUBLIC_URI": "http://127.0.0.1:9001",
            "PENPOT_SMTP_HOST": "smtp.example.test",
            "PENPOT_SMTP_PORT": "587",
            "PENPOT_SMTP_TLS": "true",
        }
    ) as container:
        container.wait_for_http(path="/readyz")
        runtime_env = container.read_text("/run/penpot-aio/runtime.env")
        assert "export PENPOT_SMTP_HOST=smtp.example.test" in runtime_env  # nosec B101
        assert "export PENPOT_SMTP_TLS=true" in runtime_env  # nosec B101
        assert (
            container.exec("pgrep -x mailpit", check=False).returncode != 0
        )  # nosec B101


def test_mcp_service_can_be_disabled_without_blocking_frontend(
    runtime: DockerRuntime,
) -> None:
    with runtime.container(
        env_overrides={
            "PENPOT_PUBLIC_URI": "http://127.0.0.1:9001",
            "PENPOT_AIO_ENABLE_MCP": "false",
        }
    ) as container:
        container.wait_for_http(path="/readyz")
        assert "Bundled MCP disabled" in container.logs()  # nosec B101
        probe = container.exec(
            "timeout 2 bash -lc 'echo >/dev/tcp/127.0.0.1/4401'",
            check=False,
        )
        assert probe.returncode != 0  # nosec B101


def test_frontend_config_encodes_public_uri_as_javascript_string(
    runtime: DockerRuntime,
) -> None:
    public_uri = 'http://127.0.0.1:9001/?next="quoted"'
    with runtime.container(
        env_overrides={"PENPOT_PUBLIC_URI": public_uri}
    ) as container:
        container.wait_for_http(path="/")
        config = container.read_text("/var/www/app/js/config.js")
        assert (
            'var penpotPublicURI = "http://127.0.0.1:9001/?next=\\"quoted\\"";'
            in config
        )  # nosec B101
        container.exec("node --check /var/www/app/js/config.js")


@pytest.mark.extended_integration
def test_external_postgres_and_redis_mode_boots_without_bundled_services(
    runtime: DockerRuntime,
) -> None:
    if os.environ.get("AIO_RUN_EXTENDED_INTEGRATION") != "true":
        pytest.skip(
            "Set AIO_RUN_EXTENDED_INTEGRATION=true to run external service matrix tests."
        )

    postgres_image = os.environ.get("AIO_TEST_POSTGRES_IMAGE", "postgres:16-alpine")
    redis_image = os.environ.get("AIO_TEST_REDIS_IMAGE", "redis:7-alpine")
    postgres_name = f"penpot-aio-ext-postgres-{uuid.uuid4().hex[:10]}"
    redis_name = f"penpot-aio-ext-redis-{uuid.uuid4().hex[:10]}"
    db_password = "penpot-external-db-pass"  # nosec B105
    redis_password = "penpot-external-redis-pass"  # nosec B105

    run_command(["docker", "pull", postgres_image], capture_output=False)
    run_command(["docker", "pull", redis_image], capture_output=False)

    with docker_network("penpot-aio-ext") as network:
        try:
            run_command(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    postgres_name,
                    "--network",
                    network,
                    "-e",
                    "POSTGRES_DB=penpot",
                    "-e",
                    "POSTGRES_USER=penpot",
                    "-e",
                    f"POSTGRES_PASSWORD={db_password}",
                    postgres_image,
                ]
            )
            run_command(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    redis_name,
                    "--network",
                    network,
                    redis_image,
                    "redis-server",
                    "--requirepass",
                    redis_password,
                ]
            )

            _wait_for_service(
                lambda: docker_exec(
                    postgres_name, "pg_isready -U penpot -d penpot", check=False
                ).returncode
                == 0,
                label="external PostgreSQL",
            )
            _wait_for_service(
                lambda: "PONG"
                in docker_exec(
                    redis_name,
                    f"redis-cli -a {redis_password} ping",
                    check=False,
                ).stdout,
                label="external Redis",
            )

            with runtime.container(
                network=network,
                env_overrides={
                    "PENPOT_PUBLIC_URI": "http://127.0.0.1:9001",
                    "PENPOT_AIO_ENABLE_INTERNAL_POSTGRES": "false",
                    "PENPOT_AIO_ENABLE_INTERNAL_REDIS": "false",
                    "PENPOT_DATABASE_URI": f"postgresql://{postgres_name}:5432/penpot",
                    "PENPOT_DATABASE_USERNAME": "penpot",
                    "PENPOT_DATABASE_PASSWORD": db_password,
                    "PENPOT_REDIS_URI": f"redis://default:{redis_password}@{redis_name}:6379/0",
                },
            ) as container:
                container.wait_for_http(path="/readyz")
                logs = container.logs()
                assert "External PostgreSQL configured" in logs  # nosec B101
                assert "External Redis/Valkey configured" in logs  # nosec B101
                processes = container.exec("ps -eo comm=,args=").stdout
                assert "postgres -D /appdata/postgres" not in processes  # nosec B101
                assert "redis-server --bind 127.0.0.1" not in processes  # nosec B101

                connection_count = docker_exec(
                    postgres_name,
                    "psql -U penpot -d penpot -tAc \"select count(*) from pg_stat_activity where usename = 'penpot' and datname = 'penpot';\"",
                ).stdout.strip()
                assert int(connection_count) > 0  # nosec B101
        finally:
            run_command(["docker", "rm", "-f", postgres_name, redis_name], check=False)


def _wait_for_service(predicate, *, label: str, timeout: int = 120) -> None:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(2)
    raise AssertionError(f"Timed out waiting for {label}.")
