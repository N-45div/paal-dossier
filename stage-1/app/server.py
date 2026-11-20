"""HTTP transport: a threaded stdlib server that hands every request to App.handle."""

import logging
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .app import App
from .wire import encode_json

MAX_BODY_BYTES = 16 * 1024 * 1024  # RL20: bodies above this are 413 payload_too_large
DRAIN_BYTES = 2 * MAX_BODY_BYTES  # RL28: most of an over-cap body read after the 413, then close
REQUEST_QUEUE_SIZE = 128
_JSON_TYPE = "application/json; charset=utf-8"
_DIGITS = re.compile(rb"[0-9]+")  # Content-Length: ASCII digits only
_CHUNK_SIZE = re.compile(rb"[0-9A-Fa-f]+")  # RFC 9112: chunk-size is bare hex digits, no sign or prefix
_FIELD_NAME = re.compile(rb"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")  # RFC 9110 token: a trailer field-name
_TOKEN = _FIELD_NAME.pattern  # RFC 9110 tchar run, shared by trailer names and chunk-extension names/values
_QUOTED = rb'"(?:[\t \x21\x23-\x5b\x5d-\x7e\x80-\xff]|\\[\t \x21-\x7e\x80-\xff])*"'  # RFC 9110 quoted-string
# RFC 9112 chunk-ext: *( BWS ";" BWS chunk-ext-name [ BWS "=" BWS chunk-ext-val ] ), value = token or quoted-string
_CHUNK_EXTENSIONS = re.compile(
    rb"(?:[ \t]*;[ \t]*" + _TOKEN + rb"(?:[ \t]*=[ \t]*(?:" + _TOKEN + rb"|" + _QUOTED + rb"))?)*[ \t]*"
)


def _content_length(raw: str | None) -> int:
    """A Content-Length of ASCII digits only; a huge value is returned as an over-cap size, never a 400 (RL30).

    Digits are parsed without int(): Python bounds decimal conversion, so a long digit run would raise.
    """
    if raw is None:
        return 0
    text = raw.strip().encode("ascii", "replace")
    if _DIGITS.fullmatch(text) is None:
        raise _BadFraming("invalid Content-Length")
    digits = text.lstrip(b"0") or b"0"
    if len(digits) > 12:  # far beyond any cap; the exact value does not matter once it is over
        return MAX_BODY_BYTES + 1
    return int(digits)


def _split_chunk_size_line(line: bytes) -> tuple[bytes, bytes]:
    """Split a chunk-size line into the size and its extension; a malformed extension is _BadFraming (RL53)."""
    size, separator, _rest = line.partition(b";")
    if not separator:
        return size, b""
    extension = line[len(size):]
    if _CHUNK_EXTENSIONS.fullmatch(extension) is None:
        raise _BadFraming("malformed chunk extension")
    return size.rstrip(b" \t"), extension


def _is_trailer_field(line: bytes) -> bool:
    """RFC 9110 field grammar for a trailer line: token name, no space before the colon, value without NUL or bare CR."""
    name, colon, value = line.partition(b":")
    if not colon or _FIELD_NAME.fullmatch(name) is None:
        return False
    return b"\x00" not in value and b"\r" not in value


class _TooLarge(Exception):
    def __init__(self, unread: int | None) -> None:
        super().__init__("body exceeds the cap")
        self.unread = unread


class _BadFraming(Exception):
    pass


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
            body = self._read_request_body()
        except _TooLarge as too_large:
            self._reject_too_large(too_large.unread)
            return
        except _BadFraming as bad:
            self._send_error_envelope(400, "malformed_request", str(bad))
            self.close_connection = True
            return
        headers = {name.lower(): value for name, value in self.headers.items()}
        reply = self.app.handle(self.command, self.path, headers, body)
        self._send(reply.status, reply.body)

    def _read_request_body(self) -> bytes:
        """The body under the 16 MiB cap; raises _TooLarge as soon as the cap is passed (RL20, RL28, RL54).

        Conflicting framing headers are malformed: Content-Length with Transfer-Encoding, or two
        Content-Length values that differ (RL54). Nothing is read for them, so nothing runs.
        """
        lengths = self.headers.get_all("Content-Length") or []
        encodings = self.headers.get_all("Transfer-Encoding") or []
        if encodings and lengths:
            raise _BadFraming("Content-Length with Transfer-Encoding")
        if len({value.strip() for value in lengths}) > 1:
            raise _BadFraming("conflicting Content-Length headers")
        if encodings:
            # RFC 9112 6.1: the only coding this server frames is a single final chunked (RL56).
            codings = [coding.strip().lower() for coding in ",".join(encodings).split(",")]
            if codings != ["chunked"]:
                raise _BadFraming("unsupported Transfer-Encoding")
            return self._read_chunked()
        length = _content_length(lengths[0] if lengths else None)
        if length > MAX_BODY_BYTES:
            raise _TooLarge(unread=length)
        return self.rfile.read(length) if length else b""

    def _read_chunk_line(self) -> bytes:
        """One CRLF-terminated chunk-framing line, without the CRLF; EOF, a bare LF or an overlong line is malformed."""
        line = self.rfile.readline(65537)
        if not line.endswith(b"\r\n") or len(line) > 65536:
            raise _BadFraming("malformed chunk framing")
        return line[:-2]

    def _read_chunked(self) -> bytes:
        """A strictly framed chunked body (RFC 9112 section 7.1): hex size, optional extension, CRLF-terminated data."""
        chunks: list[bytes] = []
        total = 0
        while True:
            size_line = self._read_chunk_line()
            size_text, extension = _split_chunk_size_line(size_line)
            if _CHUNK_SIZE.fullmatch(size_text) is None:
                raise _BadFraming("invalid chunk size")
            size = int(size_text, 16)
            if size == 0:
                while True:  # trailer fields, then the empty line that ends the body
                    trailer = self._read_chunk_line()
                    if trailer == b"":
                        return b"".join(chunks)
                    if not _is_trailer_field(trailer):
                        raise _BadFraming("malformed trailer field")
            total += size
            if total > MAX_BODY_BYTES:
                raise _TooLarge(unread=None)  # the rest of the stream is drained, bounded, after the 413
            data = self.rfile.read(size)
            if len(data) != size:
                raise _BadFraming("truncated chunk")
            if self.rfile.read(2) != b"\r\n":
                raise _BadFraming("chunk data is not followed by CRLF")
            chunks.append(data)

    def _reject_too_large(self, unread: int | None) -> None:
        """Answer 413 first, then drain a bounded amount of the body still in flight, then close.

        Answering before draining lets the client read the envelope; draining avoids a TCP reset
        while the client is still sending (RL28). Anything beyond the drain bound is abandoned.
        """
        self.close_connection = True
        self._send_error_envelope(413, "payload_too_large", "request body exceeds 16 MiB")
        try:
            self.connection.settimeout(5)
            remaining = min(unread, DRAIN_BYTES) if unread is not None else DRAIN_BYTES
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass  # the client went away; nothing more to send

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
