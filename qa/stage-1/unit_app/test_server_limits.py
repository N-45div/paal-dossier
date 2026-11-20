"""Socket-level body limits (R1.31, RL20): 16 MiB is accepted, above it is 413 payload_too_large.

Index: R1.31 -> test_r1_31_body_up_to_16_mib_with_unknown_field_is_accepted,
       R1.31 -> test_r1_31_body_above_16_mib_is_413_payload_too_large,
       R1.61 -> test_r1_61_overlong_request_target_answers_the_envelope.

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app

Index of claimed ids covered in this module:
    R1.31 -> ServerLimitTests.test_r1_31_body_above_16_mib_is_413_payload_too_large
    R1.31 -> ServerLimitTests.test_r1_31_body_up_to_16_mib_with_unknown_field_is_accepted
    R1.31 -> ServerLimitTests.test_r1_31_rl30_five_thousand_nines_content_length_is_413_not_400
    R1.31 -> ServerLimitTests.test_r1_31_rl30_leading_zeros_then_over_cap_content_length_is_413
    R1.31 -> ServerLimitTests.test_r1_31_rl30_non_digit_content_length_is_still_400
    R1.31 -> ServerLimitTests.test_r1_31_rl54_zero_padded_exact_cap_content_length_with_a_valid_reset_is_204
    R1.31 -> ServerLimitTests.test_r1_31_rl54_zero_padded_zero_content_length_is_an_empty_body
    R1.31 -> ServerLimitTests.test_r1_31_rl54_zero_padded_41_byte_reset_is_204
    R1.31 -> ServerLimitTests.test_r1_31_rl54_plus_sign_content_length_is_400_and_changes_nothing
    R1.31 -> ServerLimitTests.test_r1_31_rl54_underscore_content_length_is_400_and_changes_nothing
    R1.31 -> ServerLimitTests.test_r1_31_rl54_conflicting_content_length_values_are_400_and_never_execute
    R1.31 -> ServerLimitTests.test_r1_31_rl54_content_length_with_transfer_encoding_is_400_and_never_executes
    RL49  -> ServerLimitTests.test_rl56_valid_transfer_encoding_chunked_is_parsed
    RL56  -> ServerLimitTests.test_rl56_transfer_encoding_gzip_then_chunked_is_400_and_changes_nothing
    RL56  -> ServerLimitTests.test_rl56_two_transfer_encoding_header_lines_are_400_and_change_nothing
    RL56  -> ServerLimitTests.test_rl56_transfer_encoding_with_a_trailing_empty_coding_is_400_and_changes_nothing
    RL56  -> ServerLimitTests.test_rl56_transfer_encoding_case_and_trailing_space_positive_controls_are_204
    RL56  -> ServerLimitTests.test_rl56_transfer_encoding_chunked_then_gzip_is_400_and_never_executes
    RL56  -> ServerLimitTests.test_rl56_transfer_encoding_chunked_twice_is_400_and_never_executes
    RL56  -> ServerLimitTests.test_rl56_transfer_encoding_xchunked_is_400_and_never_executes
    R1.32 -> ServerLimitTests.test_r1_31_body_up_to_16_mib_with_unknown_field_is_accepted
"""

import http.client
import socket
import json
import threading
import unittest

from app.app import App
from app.clock import Clock
from app.server import MAX_BODY_BYTES, make_server


RESET_BODY = json.dumps({"now": "2026-03-01T09:00:00+00:00", "users": []}).encode()


class ServerLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App(Clock())
        cls.server = make_server("127.0.0.1", 0, cls.app)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, body: bytes):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        connection.request("POST", "/auth/login", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def test_r1_31_body_up_to_16_mib_with_unknown_field_is_accepted(self):
        """Covers R1.31: a body of exactly the cap with an ignored field is parsed, not refused. Covers R1.31, R1.32."""
        padding = "x" * (MAX_BODY_BYTES - 200)
        body = json.dumps({"email": "a@example.test", "password": "longenough", "note": padding}).encode()
        self.assertLessEqual(len(body), MAX_BODY_BYTES)
        status, data = self.post(body)
        self.assertEqual(status, 401, data)  # parsed, unknown account: login refuses, not a size error

    def test_r1_31_body_above_16_mib_is_413_payload_too_large(self):
        """Covers R1.31: above the cap the answer is the envelope with 413 payload_too_large, never 400 or 5xx."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        connection.putrequest("POST", "/auth/login")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(MAX_BODY_BYTES + 1))
        connection.endheaders()
        response = connection.getresponse()
        data = json.loads(response.read())
        connection.close()
        self.assertEqual(response.status, 413)
        self.assertEqual(data["error"]["code"], "payload_too_large")


    def test_r1_61_overlong_request_target_answers_the_envelope(self):
        """Covers R1.61, R1.62: a request line beyond the server's limit gets the §5 envelope, never 500 or a dropped reply."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        connection.putrequest("GET", "/dossiers?q=" + "a" * 120000)
        connection.endheaders()
        response = connection.getresponse()
        data = json.loads(response.read())
        connection.close()
        self.assertIn(response.status, (400, 414))
        self.assertEqual(data["error"]["code"], "malformed_request")


    def _reset_body(self, total: int) -> bytes:
        head = b'{"now":"2026-03-01T09:00:00+00:00","users":[],"note":"'
        tail = b'"}'
        padding = total - len(head) - len(tail)
        assert padding >= 0
        return head + b"x" * padding + tail

    def test_r1_31_exact_16_mib_reset_body_is_accepted_over_a_real_socket(self):
        """Covers R1.31: a Content-Length of exactly 16 MiB with an ignored padding field gets 204 (RL28)."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        connection.request("POST", "/_test/reset", body=self._reset_body(MAX_BODY_BYTES),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        response.read()
        connection.close()
        self.assertEqual(response.status, 204)

    def test_r1_31_16_mib_plus_one_gets_the_413_envelope_over_a_real_socket(self):
        """Covers R1.31: a Content-Length of 16 MiB + 1 gets 413 payload_too_large, and the client reads it (RL28)."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        connection.request("POST", "/_test/reset", body=self._reset_body(MAX_BODY_BYTES + 1),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = json.loads(response.read())
        connection.close()
        self.assertEqual(response.status, 413)
        self.assertEqual(data["error"]["code"], "payload_too_large")

    def raw_declared_length(self, length_header: str):
        """Declare a Content-Length over a real socket and send no body; return the status."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            sock.sendall((f"POST /_test/reset HTTP/1.1\r\nHost: test\r\nConnection: close\r\n"
                          f"Content-Type: application/json\r\nContent-Length: {length_header}\r\n\r\n").encode())
            buf = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        finally:
            sock.close()
        return int(buf.split(b" ", 2)[1]), buf

    def test_r1_31_rl30_five_thousand_nines_content_length_is_413_not_400(self):
        """Covers R1.31, RL30: a digits-only Content-Length over the cap is 413 payload_too_large, never 400."""
        status, buf = self.raw_declared_length("9" * 5000)
        self.assertEqual(status, 413, buf[:200])
        self.assertIn(b"payload_too_large", buf)

    def test_r1_31_rl30_leading_zeros_then_over_cap_content_length_is_413(self):
        """Covers R1.31, RL30: 5,000 leading zeros then 16777217 is over the cap, so 413; never 400."""
        status, buf = self.raw_declared_length("0" * 5000 + str(MAX_BODY_BYTES + 1))
        self.assertEqual(status, 413, buf[:200])
        self.assertIn(b"payload_too_large", buf)

    def raw_request(self, header_lines: str, body: bytes = b""):
        """Send a raw POST /_test/reset with the given header lines and body; return (status, bytes)."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=30)
        try:
            sock.sendall((f"POST /_test/reset HTTP/1.1\r\nHost: test\r\nConnection: close\r\n"
                          f"Content-Type: application/json\r\n{header_lines}\r\n").encode() + body)
            buf = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        finally:
            sock.close()
        return int(buf.split(b" ", 2)[1]), buf

    def test_r1_31_rl54_zero_padded_exact_cap_content_length_with_a_valid_reset_is_204(self):
        """Covers R1.31, RL30, RL54: 5,000 leading zeros then 16777216 is exactly the cap; a valid reset body is accepted (204)."""
        base = json.dumps({"now": "2026-03-01T09:00:00+00:00", "users": [], "pad": ""}).encode()
        body = json.dumps({"now": "2026-03-01T09:00:00+00:00", "users": [], "pad": "x" * (MAX_BODY_BYTES - len(base))}).encode()
        self.assertEqual(len(body), MAX_BODY_BYTES)
        status, buf = self.raw_request(f"Content-Length: {'0' * 5000}{MAX_BODY_BYTES}\r\n", body)
        self.assertEqual(status, 204, buf[:200])

    def test_r1_31_rl54_zero_padded_zero_content_length_is_an_empty_body(self):
        """Covers R1.31, RL54: 5,000 zeros then 0 is an empty body; the reset has no JSON and answers 400 malformed_request."""
        status, buf = self.raw_request(f"Content-Length: {'0' * 5000}0\r\n")
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def exact_41_byte_reset(self) -> bytes:
        base = b'{"now":"2026-03-01T09:00:00+00:00"}'
        body = base + b" " * (41 - len(base))
        self.assertEqual(len(body), 41)
        return body

    def test_r1_31_rl54_zero_padded_41_byte_reset_is_204(self):
        """Covers R1.31, RL30, RL54: 5,000 leading zeros then 41 with a valid 41-byte reset body is accepted (204)."""
        status, buf = self.raw_request(f"Content-Length: {'0' * 5000}41\r\n", self.exact_41_byte_reset())
        self.assertEqual(status, 204, buf[:200])

    def test_r1_31_rl54_plus_sign_content_length_is_400_and_changes_nothing(self):
        """Covers R1.31, RL54: 'Content-Length: +41' is not 1*DIGIT; 400 malformed_request, the reset never runs."""
        status, buf = self.raw_request("Content-Length: +41\r\n", self.exact_41_byte_reset())
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def test_r1_31_rl54_underscore_content_length_is_400_and_changes_nothing(self):
        """Covers R1.31, RL54: 'Content-Length: 4_1' contains an underscore; 400 malformed_request, the reset never runs."""
        status, buf = self.raw_request("Content-Length: 4_1\r\n", self.exact_41_byte_reset())
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def test_r1_31_rl54_conflicting_content_length_values_are_400_and_never_execute(self):
        """Covers R1.31, RL54: two Content-Length headers with different values are malformed; 400, the request never runs."""
        status, buf = self.raw_request("Content-Length: 5\r\nContent-Length: 7\r\n", b"abcde")
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def chunked_reset(self) -> bytes:
        return f"{len(RESET_BODY):x}".encode() + b"\r\n" + RESET_BODY + b"\r\n0\r\n\r\n"

    def assert_rl56_refused_and_unchanged(self, header_lines: str):
        """A malformed framing answers 400 malformed_request, the handler never runs, the export is unchanged."""
        self.app.handle("POST", "/_test/reset", {}, RESET_BODY)
        before = self.app.handle("GET", "/_test/export", {}, b"").body
        status, buf = self.raw_request(header_lines, self.chunked_reset())
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)
        self.assertEqual(self.app.handle("GET", "/_test/export", {}, b"").body, before)

    def test_rl56_transfer_encoding_gzip_then_chunked_is_400_and_changes_nothing(self):
        """Covers R1.31, RL49, RL56: 'gzip, chunked' names an unsupported coding first; 400, export unchanged."""
        self.assert_rl56_refused_and_unchanged("Transfer-Encoding: gzip, chunked\r\n")

    def test_rl56_two_transfer_encoding_header_lines_are_400_and_change_nothing(self):
        """Covers R1.31, RL49, RL56: 'chunked' then 'gzip' on two Transfer-Encoding lines combine to an unsupported list; 400, export unchanged."""
        self.assert_rl56_refused_and_unchanged("Transfer-Encoding: chunked\r\nTransfer-Encoding: gzip\r\n")

    def test_rl56_transfer_encoding_with_a_trailing_empty_coding_is_400_and_changes_nothing(self):
        """Covers R1.31, RL49, RL56: 'chunked,' ends with an empty coding, which is not the chunked coding; 400, export unchanged."""
        self.assert_rl56_refused_and_unchanged("Transfer-Encoding: chunked,\r\n")

    def test_rl56_transfer_encoding_case_and_trailing_space_positive_controls_are_204(self):
        """Covers R1.31, RL49, RL56: 'Chunked' and 'chunked ' (trailing space) are the chunked coding; both reset (204)."""
        for value in ("Chunked", "chunked "):
            with self.subTest(value=value):
                status, buf = self.raw_request(f"Transfer-Encoding: {value}\r\n", self.chunked_reset())
                self.assertEqual(status, 204, buf[:200])

    def test_rl56_valid_transfer_encoding_chunked_is_parsed(self):
        """Covers R1.31, RL49, RL56: a sole 'Transfer-Encoding: chunked' with a valid reset body is parsed (204)."""
        status, buf = self.raw_request("Transfer-Encoding: chunked\r\n", self.chunked_reset())
        self.assertEqual(status, 204, buf[:200])

    def test_rl56_transfer_encoding_chunked_then_gzip_is_400_and_never_executes(self):
        """Covers R1.31, RL56: final coding 'gzip' is not chunked; 400 malformed_request, the request never runs."""
        status, buf = self.raw_request("Transfer-Encoding: chunked, gzip\r\n", self.chunked_reset())
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def test_rl56_transfer_encoding_chunked_twice_is_400_and_never_executes(self):
        """Covers R1.31, RL56: chunked applied twice is not allowed; 400 malformed_request, the request never runs."""
        status, buf = self.raw_request("Transfer-Encoding: chunked, chunked\r\n", self.chunked_reset())
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def test_rl56_transfer_encoding_xchunked_is_400_and_never_executes(self):
        """Covers R1.31, RL56: 'xchunked' is not the chunked coding; 400 malformed_request, the request never runs."""
        status, buf = self.raw_request("Transfer-Encoding: xchunked\r\n", self.chunked_reset())
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def test_r1_31_rl54_content_length_with_transfer_encoding_is_400_and_never_executes(self):
        """Covers R1.31, RL54: Content-Length together with Transfer-Encoding is malformed; 400, the request never runs."""
        body = b"%x\r\n" % len(RESET_BODY) + RESET_BODY + b"\r\n0\r\n\r\n"
        status, buf = self.raw_request(f"Content-Length: {len(body)}\r\nTransfer-Encoding: chunked\r\n", body)
        self.assertEqual(status, 400, buf[:200])
        self.assertIn(b"malformed_request", buf)

    def test_r1_31_rl30_non_digit_content_length_is_still_400(self):
        """Covers R1.31, RL30: a Content-Length that is not digits only (here '+5') stays 400 malformed_request."""
        status, buf = self.raw_declared_length("+5")
        self.assertEqual(status, 400, buf[:200])

    def test_r1_31_chunked_upload_over_the_cap_gets_413_and_under_it_is_parsed(self):
        """Covers R1.31: a chunked upload is counted against the cap; over it is 413, under it is parsed (RL28)."""
        chunk = b"x" * (1024 * 1024)
        over = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        over.request("POST", "/auth/login", body=iter([chunk] * 17),
                     headers={"Content-Type": "application/json", "Transfer-Encoding": "chunked"}, encode_chunked=True)
        response = over.getresponse()
        data = json.loads(response.read())
        over.close()
        self.assertEqual(response.status, 413)
        self.assertEqual(data["error"]["code"], "payload_too_large")

        body = b'{"email":"a@example.test","password":"longenough","note":"' + b"x" * (1024 * 1024) + b'"}'
        under = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        under.request("POST", "/auth/login", body=iter([body[i:i + 65536] for i in range(0, len(body), 65536)]),
                      headers={"Content-Type": "application/json", "Transfer-Encoding": "chunked"}, encode_chunked=True)
        response = under.getresponse()
        response.read()
        under.close()
        self.assertEqual(response.status, 401)

    def test_r1_31_the_cap_applies_to_signup_dossiers_and_import(self):
        """Covers R1.31: POST /auth/signup, POST /dossiers and POST /_test/import all answer 413 over the cap (RL28)."""
        for path in ("/auth/signup", "/dossiers", "/_test/import"):
            with self.subTest(path=path):
                connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
                connection.putrequest("POST", path)
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(MAX_BODY_BYTES + 1))
                connection.endheaders()
                response = connection.getresponse()
                data = json.loads(response.read())
                connection.close()
                self.assertEqual((response.status, data["error"]["code"]), (413, "payload_too_large"))


if __name__ == "__main__":
    unittest.main()
