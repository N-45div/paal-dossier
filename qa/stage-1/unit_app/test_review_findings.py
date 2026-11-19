"""Regression tests for the P3 review findings on c2c42b65 (RL16–RL20).

Index of claimed ids covered in this module:
    R1.23 -> test_r1_23_token_removed_by_reset_is_refused
    R1.40 -> test_r1_40_invalid_stored_values_are_refused_on_import
    R1.61 -> test_r1_61_very_long_digit_offsets_answer_without_5xx
    R1.125 -> test_r1_125_export_during_failed_refresh_shows_the_last_completed_build
    R1.126 -> test_r1_126_export_during_failed_refresh_round_trips_unchanged
    R1.128 -> test_r1_128_export_during_failed_refresh_shows_the_last_completed_build

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app
"""

import copy
import json
import threading
import time
import unittest
from types import SimpleNamespace

from app.app import App
from app.clock import Clock

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [{"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}],
}
FIELDS_OK = {
    "legal_name": {"value": "Acme Robotics, Inc.", "citations": [
        {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics, Inc. is the registered name.", "provider": "nimble"}]},
    "hq_city": {"value": None, "citations": []},
    "ceo": {"value": None, "citations": []},
    "founded_year": {"value": 2014, "citations": [
        {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics was founded in 2014.", "provider": "nimble"}]},
    "headcount_range": {"value": None, "citations": []},
    "funding_total": {"value": None, "citations": []},
}


def call(app, method, path, body=None, headers=None):
    raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    reply = app.handle(method, path, headers or {}, raw)
    return reply.status, (json.loads(reply.body) if reply.body else None)


def scripted_engine(outcomes):
    """Each build takes the next outcome: 'ok', 'fail', or a threading.Event to block on."""
    def run(domain, *, budget=80, on_spend=None, cancelled=None):
        outcome = outcomes.pop(0)
        if isinstance(outcome, threading.Event):
            outcome.wait(10)
            return SimpleNamespace(ok=True, spent=0, fields=FIELDS_OK)
        if outcome == "fail":
            return SimpleNamespace(ok=False, spent=0, fields={})
        return SimpleNamespace(ok=True, spent=0, fields=FIELDS_OK)
    return run


class ReviewFindingTests(unittest.TestCase):
    def setUp(self):
        self.gate = threading.Event()
        self.app = App(Clock(), engine=scripted_engine(["ok", "fail", self.gate]))
        call(self.app, "POST", "/_test/reset", FIXTURE)
        _, login = call(self.app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})
        self.token = login["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.gate.set()

    def settle(self, domain, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            _, body = call(self.app, "GET", f"/dossiers/{domain}", headers=self.headers)
            if body["state"] != "building":
                return body
            time.sleep(0.01)
        self.fail("build did not settle")

    def test_r1_125_export_during_failed_refresh_shows_the_last_completed_build(self):
        """Covers R1.125, R1.128: a building dossier exports as the state of its last completed build."""
        call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(self.headers, **{"idempotency-key": "o"}))
        self.assertEqual(self.settle("acme-robotics.test")["state"], "ready")
        call(self.app, "POST", "/dossiers/acme-robotics.test/refresh", None, dict(self.headers, **{"idempotency-key": "r1"}))
        self.assertEqual(self.settle("acme-robotics.test")["state"], "failed")
        call(self.app, "POST", "/dossiers/acme-robotics.test/refresh", None, dict(self.headers, **{"idempotency-key": "r2"}))
        _, body = call(self.app, "GET", "/dossiers/acme-robotics.test", headers=self.headers)
        self.assertEqual(body["state"], "building")
        exported = call(self.app, "GET", "/_test/export")[1]["state"]["dossiers"][0]
        self.assertEqual(exported["state"], "failed")
        self.assertIsNotNone(exported["researched_at"])
        self.assertEqual(exported["fields"]["founded_year"]["value"], 2014)

    def test_r1_126_export_during_failed_refresh_round_trips_unchanged(self):
        """Covers R1.126: the unchanged export of a failed dossier with researched_at is accepted on import."""
        call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(self.headers, **{"idempotency-key": "o"}))
        self.settle("acme-robotics.test")
        call(self.app, "POST", "/dossiers/acme-robotics.test/refresh", None, dict(self.headers, **{"idempotency-key": "r1"}))
        self.settle("acme-robotics.test")
        exported = call(self.app, "GET", "/_test/export")[1]
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 204)
        self.assertEqual(call(self.app, "GET", "/_test/export")[1], exported)

    def test_r1_23_token_removed_by_reset_is_refused(self):
        """Covers R1.23: after reset returns, a token from the old state is refused on every protected route."""
        call(self.app, "POST", "/_test/reset", {"now": "2026-03-01T09:00:00+00:00", "users": []})
        status, body = call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"},
                            dict(self.headers, **{"idempotency-key": "x"}))
        self.assertEqual((status, body["error"]["code"]), (401, "unauthenticated"))
        self.assertEqual(call(self.app, "GET", "/dossiers", headers=self.headers)[0], 401)

    def test_r1_61_very_long_digit_offsets_answer_without_5xx(self):
        """Covers R1.61: digit strings of any length are a page or an out-of-range value, never a 500."""
        cases = [
            "/dossiers?offset=" + "0" * 5000 + "5",
            "/dossiers?offset=" + "9" * 5000,
            "/dossiers?limit=" + "0" * 5000 + "1",
            "/dossiers?limit=" + "9" * 5000,
        ]
        for path in cases:
            with self.subTest(path=path[:30]):
                status, _ = call(self.app, "GET", path, headers=self.headers)
                self.assertIn(status, (200, 422))
                self.assertNotEqual(status, 500)
        self.assertEqual(call(self.app, "GET", "/dossiers?offset=" + "9" * 5000, headers=self.headers)[1]["dossiers"], [])
        self.assertEqual(call(self.app, "GET", "/dossiers?limit=" + "0" * 5000 + "1", headers=self.headers)[0], 200)

    def test_r1_40_invalid_stored_values_are_refused_on_import(self):
        """Covers R1.40: a stored value outside its type, range or citation shape is refused, state unchanged."""
        call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(self.headers, **{"idempotency-key": "o"}))
        self.settle("acme-robotics.test")
        exported = call(self.app, "GET", "/_test/export")[1]
        before = copy.deepcopy(exported)
        mutations = {
            "string founded_year": lambda f: f["founded_year"].update(value="garbage"),
            "founded_year before 1800": lambda f: f["founded_year"].update(value=1799),
            "founded_year after 2099": lambda f: f["founded_year"].update(value=2100),
            "empty citation excerpt": lambda f: f["founded_year"]["citations"][0].update(excerpt=""),
        }
        for why, mutate in mutations.items():
            with self.subTest(why=why):
                bad = copy.deepcopy(exported)
                mutate(bad["state"]["dossiers"][0]["fields"])
                self.assertEqual(call(self.app, "POST", "/_test/import", bad)[0], 422)
                self.assertEqual(call(self.app, "GET", "/_test/export")[1], before)


if __name__ == "__main__":
    unittest.main()
