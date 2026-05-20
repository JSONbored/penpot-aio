#!/usr/bin/env python3
from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get(
    "APP_HOST", "0.0.0.0"
)  # nosec B104 - container service binds intentionally
PORT = int(os.environ.get("APP_PORT", "8080"))
MAX_CONNECTIONS = max(1, int(os.environ.get("APP_MAX_CONNECTIONS", "32")))
REQUEST_TIMEOUT = max(1.0, float(os.environ.get("APP_REQUEST_TIMEOUT", "10")))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b"ok\n" if self.path == "/health" else b"aio-template starter app\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        max_connections: int = MAX_CONNECTIONS,
        request_timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self.request_queue_size = max_connections
        super().__init__(server_address, handler_class)
        self.request_timeout = request_timeout
        self._connection_slots = threading.BoundedSemaphore(max_connections)

    def get_request(self):  # type: ignore[no-untyped-def]
        request, client_address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, client_address

    def process_request(self, request, client_address):  # type: ignore[no-untyped-def]
        if not self._connection_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):  # type: ignore[no-untyped-def]
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


def main() -> None:
    print(
        f"[aio-template] starter app listening on {HOST}:{PORT} "
        f"max_connections={MAX_CONNECTIONS} request_timeout={REQUEST_TIMEOUT:g}s",
        flush=True,
    )
    BoundedThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
