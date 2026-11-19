"""The HTTP layer: one process, a thread per request, JSON in and out (spec 3.1, 3.5)."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dossier.server import routes
from dossier.server.errors import ApiError, malformed
from dossier.server.store import Store

MAX_BODY_BYTES = 1024 * 1024


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def __init__(self, address: tuple[str, int], store: Store) -> None:
        self.store = store
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "dossier"
    sys_version = ""
    timeout = 5  # per-request socket timeout, spec section 2

    def do_GET(self) -> None:
        self._handle()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_GET

    def _handle(self) -> None:
        try:
            body = self._read_body()
            status, payload = routes.dispatch(
                self.server.store,
                self.command,
                self.path,
                self.headers.get("Authorization"),
                body,
            )
        except ApiError as error:
            status, payload = error.status, error.payload()
        except Exception:  # never let an internal fault leave the socket hanging
            status, payload = 500, {"error": {"code": "internal", "message": "internal error"}}
        self._send(status, payload)

    def _read_body(self) -> bytes:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return b""
        try:
            length = int(raw_length)
        except ValueError:
            raise malformed("invalid Content-Length") from None
        if length < 0 or length > MAX_BODY_BYTES:
            raise malformed("request body is too large or has a negative length")
        return self.rfile.read(length) if length else b""

    def _send(self, status: int, payload: dict | None) -> None:
        data = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return  # keep the container log quiet; requests are checked by the acceptance tests
