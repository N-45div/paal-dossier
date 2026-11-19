"""Unit checks for the platform package: normalisation, clock, auth and the HTTP contract."""

import json
import threading
import unittest
import urllib.error
import urllib.request
from datetime import timezone

from dossier.server.domains import is_valid_host, normalise
from dossier.server.service import make_service
from dossier.server.timestamps import format_timestamp, parse_rfc3339
from dossier.server.transport import Server
from fake_engine import FakeEngine


class DomainTests(unittest.TestCase):
    def test_equivalent_spellings_normalise_to_one_domain(self):
        self.assertEqual(normalise("  Acme-Robotics.TEST. "), "acme-robotics.test")
        self.assertEqual(normalise("www.acme-robotics.test"), "acme-robotics.test")

    def test_only_one_trailing_dot_and_one_www_are_removed(self):
        self.assertEqual(normalise("acme.test.."), "acme.test.")
        self.assertEqual(normalise("www.www.acme.test"), "www.acme.test")

    def test_host_validity(self):
        self.assertTrue(is_valid_host("acme-robotics.test"))
        self.assertFalse(is_valid_host("localhost"))
        self.assertFalse(is_valid_host("-acme.test"))
        self.assertFalse(is_valid_host("acme_robotics.test"))
        self.assertFalse(is_valid_host("a" * 64 + ".test"))
        self.assertFalse(is_valid_host("https://acme.test"))


class TimestampTests(unittest.TestCase):
    def test_offset_is_kept_when_printed(self):
        instant = parse_rfc3339("2026-09-24T19:00:00+02:00")
        self.assertEqual(format_timestamp(instant), "2026-09-24T19:00:00+02:00")

    def test_z_prints_as_zero_offset(self):
        instant = parse_rfc3339("2026-03-01T09:30:00Z")
        self.assertEqual(instant.utcoffset(), timezone.utc.utcoffset(None))
        self.assertEqual(format_timestamp(instant), "2026-03-01T09:30:00+00:00")

    def test_missing_offset_is_rejected(self):
        self.assertIsNone(parse_rfc3339("2026-03-01T09:30:00"))
        self.assertIsNone(parse_rfc3339("2026-03-01"))


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server(("127.0.0.1", 0), make_service(FakeEngine()))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                text = response.read()
                return response.status, json.loads(text) if text else None
        except urllib.error.HTTPError as error:
            text = error.read()
            return error.code, json.loads(text) if text else None

    def fixture(self, users=()):
        return {"now": "2026-03-01T09:00:00+00:00", "users": list(users)}

    def test_health_is_ok_before_any_reset(self):
        self.assertEqual(self.call("GET", "/health"), (200, {"status": "ok"}))

    def test_reset_seeds_users_who_can_log_in(self):
        seed = {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}
        self.assertEqual(self.call("POST", "/_test/reset", self.fixture([seed]))[0], 204)
        status, body = self.call("POST", "/auth/login", {"email": "ADA@example.com", "password": "correct horse"})
        self.assertEqual(status, 200)
        self.assertEqual(body["user_id"], "u_ada")
        self.assertEqual(self.call("POST", "/auth/login", {"email": "ada@example.com", "password": "wrong one"})[0], 401)

    def test_signup_is_case_insensitive_on_email(self):
        self.assertEqual(self.call("POST", "/_test/reset", self.fixture())[0], 204)
        signup = {"email": "a@example.com", "password": "correct horse", "display_name": "Ada"}
        status, body = self.call("POST", "/auth/signup", signup)
        self.assertEqual(status, 201)
        self.assertTrue(body["user_id"].startswith("u_"))
        again = dict(signup, email="A@Example.com")
        self.assertEqual(self.call("POST", "/auth/signup", again)[1]["error"]["code"], "email_taken")

    def test_signup_validation_precedes_conflict_and_types_precede_missing(self):
        self.assertEqual(self.call("POST", "/_test/reset", self.fixture())[0], 204)
        short = {"email": "a@example.com", "password": "short", "display_name": "Ada"}
        self.assertEqual(self.call("POST", "/auth/signup", short)[0], 422)
        bad_type = {"email": 5, "password": "correct horse"}
        self.assertEqual(self.call("POST", "/auth/signup", bad_type)[0], 400)
        missing = {"email": "a@example.com", "password": "correct horse"}
        self.assertEqual(self.call("POST", "/auth/signup", missing)[0], 422)

    def test_bodies_that_are_not_objects_are_malformed(self):
        self.assertEqual(self.call("POST", "/auth/login", raw=b"")[1]["error"]["code"], "malformed_request")
        self.assertEqual(self.call("POST", "/auth/login", raw=b"[1]")[0], 400)
        self.assertEqual(self.call("POST", "/auth/login", raw=b"{nope")[0], 400)

    def test_clock_moves_forward_only(self):
        self.assertEqual(self.call("POST", "/_test/reset", self.fixture())[0], 204)
        self.assertEqual(self.call("POST", "/_test/clock", {"now": "2026-03-02T00:00:00+00:00"})[0], 204)
        status, body = self.call("POST", "/_test/clock", {"now": "2026-03-01T00:00:00+00:00"})
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "validation_failed")

    def test_unknown_route_is_not_found(self):
        self.assertEqual(self.call("GET", "/nope")[1]["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
