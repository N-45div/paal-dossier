"""HTTP transport: a threaded stdlib server that hands every request to App.handle."""

import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .app import App
from .wire import encode_json

MAX_BODY_BYTES = 16 * 1024 * 1024  # RL20: bodies above this are 413 payload_too_large
REQUEST_QUEUE_SIZE = 128
_JSON_TYPE = "application/json; charset=utf-8"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "DossierService"
    sys_version = ""
    disable_nagle_algorithm = True
    timeout = 60
    app: App

    def do_GET(self) -> None:
        self._serve()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = do_GET

    def _serve(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0:
            self._send_error_envelope(400, "malformed_request", "invalid Content-Length")
            self.close_connection = True
            return
        if length > MAX_BODY_BYTES:
            # The body is not read; answer the envelope and close so the connection is not reused.
            self._send_error_envelope(413, "payload_too_large", "request body exceeds 16 MiB")
            self.close_connection = True
            return
        body = self.rfile.read(length) if length else b""
        headers = {name.lower(): value for name, value in self.headers.items()}
        reply = self.app.handle(self.command, self.path, headers, body)
        self._send(reply.status, reply.body)

    def _send(self, status: int, body: bytes | None) -> None:
        self.send_response(status)
        if body is None:
            self.end_headers()
            return
        self.send_header("Content-Type", _JSON_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None) -> None:  # type: ignore[override]
        # The stdlib answers protocol-level errors (bad request line, URI too long) with HTML.
        # Answer them with the §5 envelope instead.
        mapped = {404: "not_found", 405: "method_not_allowed"}.get(code, "malformed_request")
        self._send_error_envelope(code if code < 500 else 400, mapped, message or "bad request")
        self.close_connection = True

    def _send_error_envelope(self, status: int, code: str, message: str) -> None:
        self._send(status, encode_json({"error": {"code": code, "message": message}}))

    def log_message(self, format, *args) -> None:  # noqa: A002 - stdlib signature
        logging.getLogger("dossier.http").debug(format, *args)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = REQUEST_QUEUE_SIZE

    def handle_error(self, request, client_address) -> None:
        # A client that closes early (or a refused oversize body) is normal; keep stderr quiet.
        error = sys.exc_info()[1]
        if isinstance(error, (ConnectionError, TimeoutError)):
            return
        logging.getLogger("dossier.http").exception("request from %s failed", client_address)


def make_server(host: str, port: int, app: App) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"app": app})
    return _Server((host, port), handler)
