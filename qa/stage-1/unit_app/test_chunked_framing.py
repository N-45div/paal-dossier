"""Chunked request framing over real sockets (R1.31, RL30, RL49).

A malformed chunked body never reaches the handler: it answers 400 malformed_request in the
§5 envelope and changes no state. Valid extensions, trailers and the slow upload still parse.

Index of claimed ids covered in this module:
    R1.31 -> ChunkedFramingTests.test_r1_31_valid_chunked_reset_with_extension_and_trailer_is_parsed
    RL30  -> ChunkedFramingTests.test_rl30_plus_prefixed_chunk_size_is_400_and_changes_nothing
    RL30  -> ChunkedFramingTests.test_rl30_invalid_text_where_chunk_crlf_belongs_is_400_and_changes_nothing
    RL30  -> ChunkedFramingTests.test_rl30_eof_right_after_last_chunk_is_400_and_changes_nothing
    RL49  -> ChunkedFramingTests.test_rl49_0x_prefixed_chunk_size_is_400_and_changes_nothing
    RL49  -> ChunkedFramingTests.test_rl49_underscore_in_chunk_size_is_400_and_changes_nothing
    RL49  -> ChunkedFramingTests.test_rl49_missing_final_crlf_is_400_and_changes_nothing
    RL49  -> ChunkedFramingTests.test_rl49_slow_chunked_upload_completes_and_health_answers_meanwhile

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app
"""

import json
import socket
import threading
import time
import unittest

from app.app import App
from app.clock import Clock
from app.server import make_server

RESET = json.dumps({"now": "2026-03-01T09:00:00+00:00", "users": [{"id": "u_ada", "email": "ada@example.com",
                                                                    "password": "correct horse", "display_name": "Ada"}]}).encode()
OTHER_RESET = json.dumps({"now": "2030-01-01T00:00:00+00:00", "users": []}).encode()


def hex_size(data: bytes) -> bytes:
    return f"{len(data):x}".encode()


class ChunkedFramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App(Clock())
        cls.server = make_server("127.0.0.1", 0, cls.app)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.app.handle("POST", "/_test/reset", {}, RESET)
        self.before = self.app.handle("GET", "/_test/export", {}, b"").body

    def send_raw(self, body_bytes: bytes, half_close: bool = False):
        """Send a chunked POST /_test/reset with the given raw body bytes; return (status, payload)."""
        head = (b"POST /_test/reset HTTP/1.1\r\nHost: test\r\nConnection: close\r\n"
                b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n")
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            sock.sendall(head + body_bytes)
            if half_close:
                sock.shutdown(socket.SHUT_WR)
            buf = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        finally:
            sock.close()
        raw_head, _, payload = buf.partition(b"\r\n\r\n")
        return int(raw_head.split(b" ", 2)[1]), payload

    def assert_malformed_and_unchanged(self, body_bytes: bytes, half_close: bool = False):
        status, payload = self.send_raw(body_bytes, half_close=half_close)
        self.assertEqual(status, 400, payload)
        self.assertEqual(json.loads(payload)["error"]["code"], "malformed_request")
        self.assertEqual(self.app.handle("GET", "/_test/export", {}, b"").body, self.before)

    def test_r1_31_valid_chunked_reset_with_extension_and_trailer_is_parsed(self):
        """Covers R1.31, RL30: a valid chunk extension and a valid trailer field still parse; the reset runs (204)."""
        body = (hex_size(OTHER_RESET) + b";name=value\r\n" + OTHER_RESET + b"\r\n0\r\nX-Note: ok\r\n\r\n")
        status, payload = self.send_raw(body)
        self.assertEqual(status, 204, payload)
        self.assertNotEqual(self.app.handle("GET", "/_test/export", {}, b"").body, self.before)

    def test_rl30_plus_prefixed_chunk_size_is_400_and_changes_nothing(self):
        """Covers RL30: a '+'-prefixed chunk size is not hex; 400 malformed_request, no reset."""
        self.assert_malformed_and_unchanged(b"+" + hex_size(RESET) + b"\r\n" + RESET + b"\r\n0\r\n\r\n")

    def test_rl30_invalid_text_where_chunk_crlf_belongs_is_400_and_changes_nothing(self):
        """Covers RL30: text where the chunk-data CRLF belongs is 400, not silently discarded; no reset."""
        self.assert_malformed_and_unchanged(hex_size(RESET) + b"\r\n" + RESET + b"INVALID\r\n0\r\n\r\n")

    def test_rl30_eof_right_after_last_chunk_is_400_and_changes_nothing(self):
        """Covers RL30: EOF right after '0\\r\\n' is incomplete framing; 400 and no reset."""
        self.assert_malformed_and_unchanged(hex_size(RESET) + b"\r\n" + RESET + b"\r\n0\r\n", half_close=True)

    def test_rl49_0x_prefixed_chunk_size_is_400_and_changes_nothing(self):
        """Covers RL49: a '0x' prefix is not a chunk size; 400 and no reset."""
        self.assert_malformed_and_unchanged(b"0x" + hex_size(RESET) + b"\r\n" + RESET + b"\r\n0\r\n\r\n")

    def test_rl49_underscore_in_chunk_size_is_400_and_changes_nothing(self):
        """Covers RL49: an underscore inside the chunk size is rejected; 400 and no reset."""
        size = hex_size(RESET)
        self.assertGreaterEqual(len(size), 2)
        underscored = size[:1] + b"_" + size[1:]
        self.assert_malformed_and_unchanged(underscored + b"\r\n" + RESET + b"\r\n0\r\n\r\n")

    def test_rl49_missing_final_crlf_is_400_and_changes_nothing(self):
        """Covers RL49: a body without the final blank CRLF is incomplete; 400 and no reset."""
        self.assert_malformed_and_unchanged(hex_size(RESET) + b"\r\n" + RESET + b"\r\n0\r\n", half_close=True)

    def test_rl49_slow_chunked_upload_completes_and_health_answers_meanwhile(self):
        """Covers RL49: a slow chunked upload completes (204) and the server answers /health during it."""
        head = (b"POST /_test/reset HTTP/1.1\r\nHost: test\r\nConnection: close\r\n"
                b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n")
        body = hex_size(OTHER_RESET) + b"\r\n" + OTHER_RESET + b"\r\n0\r\n\r\n"
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            sock.sendall(head + body[:5])
            time.sleep(0.3)
            health = self.app.handle("GET", "/health", {}, b"")
            self.assertEqual(health.status, 200)
            sock.sendall(body[5:])
            buf = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        finally:
            sock.close()
        self.assertEqual(int(buf.split(b" ", 2)[1]), 204)


if __name__ == "__main__":
    unittest.main()
