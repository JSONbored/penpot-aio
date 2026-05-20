from __future__ import annotations

import importlib.util
import socket
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "rootfs/usr/local/bin/aio-template-app.py"


def _load_app_module():
    spec = importlib.util.spec_from_file_location("aio_template_app", APP_PATH)
    assert spec is not None  # nosec B101
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None  # nosec B101
    spec.loader.exec_module(module)
    return module


def test_starter_app_limits_slow_connections_and_recovers_health() -> None:
    app = _load_app_module()
    server = app.BoundedThreadingHTTPServer(
        ("127.0.0.1", 0),
        app.Handler,
        max_connections=2,
        request_timeout=0.2,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    held: list[socket.socket] = []

    try:
        for _ in range(2):
            sock = socket.create_connection((host, port), timeout=1)
            sock.sendall(b"GET /")
            held.append(sock)

        time.sleep(0.4)

        with urllib.request.urlopen(  # nosec B310 - local test server only
            f"http://{host}:{port}/health",
            timeout=2,
        ) as response:
            assert response.read() == b"ok\n"  # nosec B101
    finally:
        for sock in held:
            sock.close()
        server.shutdown()
        server.server_close()
