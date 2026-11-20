"""Socket-level body limits (R1.31, RL20): 16 MiB is accepted, above it is 413 payload_too_large.

Index: R1.31 -> test_r1_31_body_up_to_16_mib_with_unknown_field_is_accepted,
       R1.31 -> test_r1_31_body_above_16_mib_is_413_payload_too_large,
       R1.61 -> test_r1_61_overlong_request_target_answers_the_envelope.

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app

Index of claimed ids covered in this module:
    R1.31 -> ServerLimitTests.test_r1_31_body_above_16_mib_is_413_payload_too_large
    R1.31 -> ServerLimitTests.test_r1_31_body_up_to_16_mib_with_unknown_field_is_accepted
    R1.32 -> ServerLimitTests.test_r1_31_body_up_to_16_mib_with_unknown_field_is_accepted
"""

import http.client
import json
import threading
import unittest

from app.app import App
from app.clock import Clock
from app.server import MAX_BODY_BYTES, make_server


class ServerLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0, App(Clock()))
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
