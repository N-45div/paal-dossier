"""HTTP transport: reads each request, runs the router and writes the JSON reply.

Every method goes through the router, so an unlisted method gets 405 rather than the
standard library's 501. Anything unexpected becomes a §5 500 body, never a bare error page.
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .context import App
from .errors import ApiError, error_body, malformed
from .messages import Reply, Request
from .routes import Router

_CONTENT_LENGTH = re.compile(r"[0-9]+")
_LINE_LIMIT = 65537


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def __init__(self, address: tuple[str, int], app: App, router: Router) -> None:
        super().__init__(address, _Handler)
        self.app = app
        self.router = router


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "DossierService"
    sys_version = ""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("do_"):
            return self._serve
        raise AttributeError(name)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _serve(self) -> None:
        try:
            body = _read_body(self)
        except ApiError as error:
            # The body was not consumed, so the connection cannot be reused.
            self.close_connection = True
            self._send(Reply(error.status, error_body(error.code, error.message)))
            return
        parts = urlsplit(self.path)
        request = Request(
            method=self.command,
            path=parts.path,
            query=parse_qs(parts.query, keep_blank_values=True),
            headers=self.headers,
            body=body,
        )
        try:
            reply = self.server.router.dispatch(self.server.app, request)  # type: ignore[attr-defined]
        except ApiError as error:
            reply = Reply(error.status, error_body(error.code, error.message))
        except Exception:
            traceback.print_exc(file=sys.stderr)
            reply = Reply(500, error_body("internal_error", "internal server error"))
        self._send(reply)

    def _send(self, reply: Reply) -> None:
        payload = b"" if reply.body is None else json.dumps(reply.body).encode("utf-8")
        self.send_response(reply.status)
        if reply.body is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)


def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    if "chunked" in handler.headers.get("Transfer-Encoding", "").lower():
        return _read_chunked(handler.rfile)
    length = handler.headers.get("Content-Length")
    if length is None:
        return b""
    if _CONTENT_LENGTH.fullmatch(length.strip()) is None:
        raise malformed("Content-Length is not a number")
    return handler.rfile.read(int(length))


def _read_chunked(rfile: Any) -> bytes:
    chunks: list[bytes] = []
    while True:
        line = rfile.readline(_LINE_LIMIT)
        try:
            size = int(line.split(b";", 1)[0].strip(), 16)
        except ValueError as exc:
            raise malformed("invalid chunk size") from exc
        if size < 0:
            raise malformed("invalid chunk size")
        if size == 0:
            while rfile.readline(_LINE_LIMIT) not in (b"\r\n", b"\n", b""):
                pass
            return b"".join(chunks)
        chunks.append(rfile.read(size))
        rfile.readline(_LINE_LIMIT)


def create_server(app: App, router: Router, host: str, port: int) -> ThreadingHTTPServer:
    return _Server((host, port), app, router)
