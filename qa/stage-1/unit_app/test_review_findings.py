"""Regression tests for the P3 review findings on c2c42b65 (RL16–RL20).

Index of claimed ids covered in this module:
    R1.23 -> test_r1_23_token_removed_by_reset_is_refused, test_r1_23_controlled_reset_race_request_behaves_as_after_reset
    R1.40 -> test_r1_40_invalid_stored_values_are_refused_on_import, test_r1_40_each_invalid_import_field_is_refused_and_a_valid_one_is_accepted, test_r1_40_funding_total_zero_is_a_valid_known_value
    R1.61 -> test_r1_61_very_long_digit_offsets_answer_without_5xx, test_r1_61_leading_zero_and_huge_offsets_and_limits_are_plain_digits
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
from unittest import mock

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


    def test_r1_23_controlled_reset_race_request_behaves_as_after_reset(self):
        """Covers R1.23, R1.129: a request blocked between its arrival and its transaction sees the reset state."""
        reply = {}

        def request():
            reply["reply"] = call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"},
                                  dict(self.headers, **{"idempotency-key": "race"}))

        with self.app.store._lock:  # the test thread holds the state lock, as a reset in progress would
            worker = threading.Thread(target=request)
            worker.start()
            time.sleep(0.2)  # the request is now waiting on the lock, before authentication
            self.assertEqual(call(self.app, "POST", "/_test/reset", {"now": "2026-03-01T09:00:00+00:00", "users": []})[0], 204)
        worker.join(5)
        status, body = reply["reply"]
        self.assertEqual((status, body["error"]["code"]), (401, "unauthenticated"))
        exported = call(self.app, "GET", "/_test/export")[1]["state"]
        self.assertEqual((exported["dossiers"], exported["idempotency"]), ([], []))

    def test_r1_61_leading_zero_and_huge_offsets_and_limits_are_plain_digits(self):
        """Covers R1.61: leading zeros are valid digits; limit is 1-200; any-length offset is a page or empty."""
        call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(self.headers, **{"idempotency-key": "z"}))
        self.settle("acme-robotics.test")
        self.assertEqual(call(self.app, "GET", "/dossiers?offset=" + "0" * 100 + "0", headers=self.headers)[1]["has_more"], False)
        status, body = call(self.app, "GET", "/dossiers?offset=" + "0" * 5000 + "1", headers=self.headers)
        self.assertEqual((status, body["dossiers"], body["has_more"]), (200, [], False))
        self.assertEqual(call(self.app, "GET", "/dossiers?limit=00200", headers=self.headers)[0], 200)
        self.assertEqual(call(self.app, "GET", "/dossiers?limit=00201", headers=self.headers)[0], 422)
        self.assertEqual(call(self.app, "GET", "/dossiers?limit=" + "9" * 5000, headers=self.headers)[0], 422)
        self.assertEqual(call(self.app, "GET", "/dossiers?offset=1e3", headers=self.headers)[0], 422)

    def test_r1_40_each_invalid_import_field_is_refused_and_a_valid_one_is_accepted(self):
        """Covers R1.40, R1.126: each malformed field is 422 with no change; the valid positive control is 204."""
        call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(self.headers, **{"idempotency-key": "o"}))
        self.settle("acme-robotics.test")
        exported = call(self.app, "GET", "/_test/export")[1]
        before = copy.deepcopy(exported)
        cite = {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics was founded in 2014.", "provider": "nimble"}

        def fields(mutate):
            bad = copy.deepcopy(exported)
            mutate(bad["state"]["dossiers"][0]["fields"])
            return bad

        cases = {
            "legal_name with leading space": lambda f: f["legal_name"].update(value=" Acme Robotics, Inc."),
            "ceo empty string known": lambda f: f.update(ceo={"value": "", "status": "known", "citations": [cite]}),
            "funding_total negative": lambda f: f.update(funding_total={"value": -1, "status": "known", "citations": [cite]}),
            "status mismatch: known value marked unknown": lambda f: f["founded_year"].update(status="unknown"),
            "headcount outside the ranges": lambda f: f.update(headcount_range={"value": "7", "status": "known", "citations": [cite]}),
            "founded_year is a boolean": lambda f: f["founded_year"].update(value=True),
            "excerpt longer than 500": lambda f: f["founded_year"]["citations"][0].update(excerpt="x" * 501),
            "empty url": lambda f: f["founded_year"]["citations"][0].update(url=""),
            "unknown provider": lambda f: f["founded_year"]["citations"][0].update(provider="bing"),
            "unknown field carries citations": lambda f: f.update(ceo={"value": None, "status": "unknown", "citations": [cite]}),
            "known field without citations": lambda f: f["founded_year"].update(citations=[]),
            "field without status": lambda f: f["founded_year"].pop("status"),
            "field with an extra key": lambda f: f["founded_year"].update(score=1),
        }
        for why, mutate in cases.items():
            with self.subTest(why=why):
                self.assertEqual(call(self.app, "POST", "/_test/import", fields(mutate))[0], 422)
                self.assertEqual(call(self.app, "GET", "/_test/export")[1], before)
        valid = fields(lambda f: f.update(headcount_range={"value": "51-200", "status": "known", "citations": [cite]}))
        self.assertEqual(call(self.app, "POST", "/_test/import", valid)[0], 204)

    def test_r1_40_funding_total_zero_is_a_valid_known_value(self):
        """Covers R1.40, R1.126: $0 is an amount (RL24); funding_total 0 imports as known and round-trips."""
        call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(self.headers, **{"idempotency-key": "z"}))
        self.settle("acme-robotics.test")
        exported = call(self.app, "GET", "/_test/export")[1]
        cite = {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics raised $0.", "provider": "nimble"}
        zero = copy.deepcopy(exported)
        zero["state"]["dossiers"][0]["fields"]["funding_total"] = {"value": 0, "status": "known", "citations": [cite]}
        self.assertEqual(call(self.app, "POST", "/_test/import", zero)[0], 204)
        status, body = call(self.app, "GET", "/dossiers/acme-robotics.test", headers=self.headers)
        self.assertEqual(body["fields"]["funding_total"]["status"], "known")
        self.assertEqual(body["fields"]["funding_total"]["value"], 0)
        self.assertEqual(call(self.app, "GET", "/_test/export")[1], zero)


    def test_r1_125_counter_10_12_round_trips_after_a_signup(self):
        """Covers R1.125, R1.126: import counter 10^12, sign up, export, import (204) (RL27.1)."""
        exported = call(self.app, "GET", "/_test/export")[1]
        exported["state"]["counters"] = {"user": 10**12}
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 204)
        status, body = call(self.app, "POST", "/auth/signup",
                            {"email": "new@example.test", "password": "longenough", "display_name": "New"})
        self.assertEqual(status, 201)
        self.assertLessEqual(len(body["user_id"]), 64)
        again = call(self.app, "GET", "/_test/export")[1]
        self.assertEqual(again["state"]["counters"]["user"], 10**12 + 1)
        self.assertEqual(call(self.app, "POST", "/_test/import", again)[0], 204)

    def test_r1_85_injected_apply_failure_ends_the_build_failed_with_fields_unchanged(self):
        """Covers R1.85, R1.96: an exception while applying a result ends the build failed, fields unchanged (RL27.2)."""
        def boom(*args, **kwargs):
            raise RuntimeError("injected failure in the apply step")
        self.app.store.finish_build = boom
        call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(self.headers, **{"idempotency-key": "x1"}))
        body = self.settle("acme-robotics.test")
        self.assertEqual(body["state"], "failed")
        self.assertEqual(body["researched_at"], None)
        self.assertTrue(all(f["status"] == "unknown" for f in body["fields"].values()))

    def test_r1_85_failure_inside_the_apply_step_keeps_the_prior_fields_and_ends_failed(self):
        """Covers R1.85, R1.96: a ready dossier whose refresh fails inside the apply step ends failed with its prior fields."""
        calls = []

        def engine(domain, *, budget=80, on_spend=None, cancelled=None):
            calls.append(domain)
            later = dict(FIELDS_OK, founded_year=dict(FIELDS_OK["founded_year"], value=2019))
            return SimpleNamespace(ok=True, spent=0, fields=FIELDS_OK if len(calls) == 1 else later)

        app = App(Clock(), engine=engine)
        call(app, "POST", "/_test/reset", FIXTURE)
        _, login = call(app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})
        headers = {"authorization": f"Bearer {login['token']}"}

        def settled(timeout=5.0):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                _, body = call(app, "GET", "/dossiers/acme-robotics.test", headers=headers)
                if body["state"] != "building":
                    return body
                time.sleep(0.01)
            self.fail("build did not settle")

        call(app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(headers, **{"idempotency-key": "open"}))
        ready = settled()
        self.assertEqual(ready["state"], "ready")
        with mock.patch("app.store.format_ts", side_effect=RuntimeError("injected in the apply step")):
            call(app, "POST", "/dossiers/acme-robotics.test/refresh", None, dict(headers, **{"idempotency-key": "refresh"}))
            body = settled()
        self.assertEqual(body["state"], "failed")
        self.assertEqual(body["researched_at"], ready["researched_at"])
        self.assertEqual(body["fields"], ready["fields"])

    def test_r1_40_engine_returns_funding_zero_and_the_api_shows_known_zero(self):
        """Covers R1.40, R1.86: a supported $0 from the engine is a known value 0 (RL24, RL27)."""
        def zero_engine(domain, *, budget=80, on_spend=None, cancelled=None):
            cite = {"url": "https://acme-robotics.test/about", "excerpt": "Acme raised $0.", "provider": "nimble"}
            return SimpleNamespace(ok=True, spent=0, fields={
                "funding_total": {"value": 0, "citations": [cite]},
            })
        app = App(Clock(), engine=zero_engine)
        call(app, "POST", "/_test/reset", FIXTURE)
        token = call(app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[1]["token"]
        headers = {"authorization": f"Bearer {token}"}
        call(app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(headers, **{"idempotency-key": "z"}))
        body = None
        for _ in range(500):
            _, body = call(app, "GET", "/dossiers/acme-robotics.test", headers=headers)
            if body["state"] != "building":
                break
            time.sleep(0.01)
        self.assertEqual(body["fields"]["funding_total"]["status"], "known")
        self.assertEqual(body["fields"]["funding_total"]["value"], 0)

    def test_r1_17_only_the_parameter_sets_this_service_writes_are_imported(self):
        """Covers R1.17: scrypt records other than signup/login (n=2^13) and fixture (n=2^10) are 422 (RL27.3)."""
        from app.passwords import hash_password
        exported = call(self.app, "GET", "/_test/export")[1]
        before = copy.deepcopy(exported)
        for n in (2**14, 2**12):
            with self.subTest(n=n):
                bad = copy.deepcopy(exported)
                bad["state"]["users"][0]["password_hash"] = hash_password("correct horse", n=n)
                self.assertEqual(call(self.app, "POST", "/_test/import", bad)[0], 422)
                self.assertEqual(call(self.app, "GET", "/_test/export")[1], before)

    def test_r1_27_timestamps_outside_years_0001_to_9999_are_422(self):
        """Covers R1.27: an instant must be representable in UTC and in its offset; otherwise 422 with no change (RL27.2)."""
        before = call(self.app, "GET", "/_test/export")[1]
        for now in ["0001-01-01T00:00:00+23:59", "9999-12-31T23:59:59-23:59"]:
            with self.subTest(now=now):
                self.assertEqual(call(self.app, "POST", "/_test/reset", {"now": now, "users": []})[0], 422)
                self.assertEqual(call(self.app, "GET", "/_test/export")[1], before)
        self.assertEqual(call(self.app, "POST", "/_test/reset", {"now": "0001-01-01T00:00:00Z", "users": []})[0], 204)


if __name__ == "__main__":
    unittest.main()
