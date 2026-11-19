"""Unit tests for the P3 dossier API: idempotency, open/read/refresh/list, build lifecycle.

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app
"""

import json
import threading
import time
import unittest
from types import SimpleNamespace

from app.app import App
from app.clock import Clock

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
    ],
}
ENGINE_FIELDS = {
    "legal_name": {"value": "Acme Robotics, Inc.", "citations": [
        {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics, Inc. is the registered name.", "provider": "nimble"}]},
    "hq_city": {"value": None, "citations": []},
    "ceo": {"value": None, "citations": []},
    "founded_year": {"value": 2014, "citations": [
        {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics was founded in 2014.", "provider": "nimble"}]},
    "headcount_range": {"value": None, "citations": []},
    "funding_total": {"value": None, "citations": []},
}


def fake_engine(domain, *, budget=80, on_spend=None, cancelled=None):
    spent = 0
    if on_spend:
        on_spend(1)
        spent += 1
    return SimpleNamespace(ok=True, spent=spent, fields=ENGINE_FIELDS)


def failing_engine(domain, *, budget=80, on_spend=None, cancelled=None):
    return SimpleNamespace(ok=False, spent=0, fields={})


def call(app, method, path, body=None, headers=None):
    raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    reply = app.handle(method, path, headers or {}, raw)
    payload = json.loads(reply.body) if reply.body else None
    return reply.status, payload


class DossierTests(unittest.TestCase):
    def setUp(self):
        self.app = App(Clock(), engine=fake_engine)
        self.assertEqual(call(self.app, "POST", "/_test/reset", FIXTURE)[0], 204)
        self.token = self._login("ada@example.com")
        self.auth = {"authorization": f"Bearer {self.token}", "idempotency-key": "k1"}

    def _login(self, email):
        return call(self.app, "POST", "/auth/login", {"email": email, "password": "correct horse"})[1]["token"]

    def _wait_settled(self, domain, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            status, body = call(self.app, "GET", f"/dossiers/{domain}", headers=self.auth)
            if body["state"] != "building":
                return body
            time.sleep(0.02)
        self.fail("build did not settle")

    def _open(self, domain, key="k1", extra=None):
        headers = dict(self.auth, **{"idempotency-key": key})
        return call(self.app, "POST", "/dossiers", extra if extra is not None else {"domain": domain}, headers)

    # --- auth and idempotency -------------------------------------------

    def test_open_requires_bearer_before_key_check(self):
        status, body = call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, {})
        self.assertEqual((status, body["error"]["code"]), (401, "unauthenticated"))

    def test_missing_or_empty_key_is_400_and_long_key_is_422(self):
        headers = {"authorization": self.auth["authorization"]}
        self.assertEqual(call(self.app, "POST", "/dossiers", {"domain": "a.test"}, headers)[0], 400)
        headers["idempotency-key"] = ""
        self.assertEqual(call(self.app, "POST", "/dossiers", {"domain": "a.test"}, headers)[0], 400)
        headers["idempotency-key"] = "k" * 256
        self.assertEqual(call(self.app, "POST", "/dossiers", {"domain": "a.test"}, headers)[0], 422)

    def test_first_open_is_202_and_replay_is_200_with_same_body(self):
        status, first = self._open("Acme-Robotics.TEST.")
        self.assertEqual(status, 202)
        self.assertEqual(first["domain"], "acme-robotics.test")
        self.assertEqual(first["state"], "building")
        status, replay = self._open("Acme-Robotics.TEST.")
        self.assertEqual((status, replay), (200, first))

    def test_same_key_different_body_is_409(self):
        self._open("acme-robotics.test")
        self.assertEqual(self._open("other.test")[0], 409)

    def test_replay_survives_unknown_field_changes_but_invalid_body_is_409(self):
        self._open("acme-robotics.test")
        self.assertEqual(self._open("acme-robotics.test", extra={"domain": "acme-robotics.test", "x": 1})[0], 200)
        self.assertEqual(self._open(None, extra={"domain": 5})[0], 409)

    def test_failed_4xx_does_not_claim_key(self):
        self.assertEqual(self._open("not a domain")[0], 422)
        self.assertEqual(self._open("acme-robotics.test")[0], 202)

    def test_same_key_on_different_path_is_independent(self):
        self._open("acme-robotics.test")
        status, body = call(self.app, "POST", "/dossiers/acme-robotics.test/refresh", None, dict(self.auth, **{"idempotency-key": "k1"}))
        self.assertEqual(status, 202)

    def test_concurrent_identical_opens_create_one_dossier(self):
        results = []
        threads = [threading.Thread(target=lambda: results.append(self._open("acme-robotics.test"))) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(status for status, _ in results), [200] * 7 + [202])
        bodies = {json.dumps(body, sort_keys=True) for _, body in results}
        self.assertEqual(len(bodies), 1)

    # --- read, refresh, list, build lifecycle ----------------------------

    def test_build_becomes_ready_with_fields_and_spend(self):
        self._open("acme-robotics.test")
        body = self._wait_settled("acme-robotics.test")
        self.assertEqual(body["state"], "ready")
        self.assertEqual(body["spent_units"], 1)
        self.assertIsNotNone(body["researched_at"])
        self.assertEqual(body["fields"]["legal_name"]["status"], "known")
        self.assertEqual(body["fields"]["ceo"], {"value": None, "status": "unknown", "citations": []})
        self.assertEqual(set(body["fields"]), {"legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total"})

    def test_failed_build_leaves_fields_unknown(self):
        app = App(Clock(), engine=failing_engine)
        call(app, "POST", "/_test/reset", FIXTURE)
        token = call(app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[1]["token"]
        headers = {"authorization": f"Bearer {token}", "idempotency-key": "k"}
        call(app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, headers)
        for _ in range(100):
            _, body = call(app, "GET", "/dossiers/acme-robotics.test", headers=headers)
            if body["state"] != "building":
                break
            time.sleep(0.02)
        self.assertEqual(body["state"], "failed")
        self.assertEqual(body["spent_units"], 0)
        self.assertEqual(body["researched_at"], None)

    def test_read_normalises_path_and_404s_unknown(self):
        self._open("acme-robotics.test")
        self.assertEqual(call(self.app, "GET", "/dossiers/WWW.Acme-Robotics.test.", headers=self.auth)[0], 200)
        self.assertEqual(call(self.app, "GET", "/dossiers/unknown.test", headers=self.auth)[0], 404)
        self.assertEqual(call(self.app, "GET", "/dossiers/not%20valid", headers=self.auth)[0], 422)

    def test_refresh_is_404_without_dossier_and_202_with_one(self):
        headers = dict(self.auth, **{"idempotency-key": "r1"})
        self.assertEqual(call(self.app, "POST", "/dossiers/none.test/refresh", None, headers)[0], 404)
        self._open("acme-robotics.test")
        self._wait_settled("acme-robotics.test")
        status, body = call(self.app, "POST", "/dossiers/acme-robotics.test/refresh", None, headers)
        self.assertEqual((status, body["state"]), (202, "building"))
        self.assertEqual(self._wait_settled("acme-robotics.test")["spent_units"], 2)

    def test_list_filters_orders_and_pages(self):
        for domain in ["zeta.test", "alpha.test", "mid.test"]:
            self._open(domain, key=domain)
        for domain in ["zeta.test", "alpha.test", "mid.test"]:
            self._wait_settled(domain)
        status, body = call(self.app, "GET", "/dossiers?limit=2", headers=self.auth)
        self.assertEqual([d["domain"] for d in body["dossiers"]], ["alpha.test", "mid.test"])
        self.assertTrue(body["has_more"])
        status, body = call(self.app, "GET", "/dossiers?limit=2&offset=2", headers=self.auth)
        self.assertEqual([d["domain"] for d in body["dossiers"]], ["zeta.test"])
        self.assertFalse(body["has_more"])
        status, body = call(self.app, "GET", "/dossiers?q=ALPHA", headers=self.auth)
        self.assertEqual([d["domain"] for d in body["dossiers"]], ["alpha.test"])

    def test_list_rejects_bad_integers(self):
        for query in ["limit=0", "limit=201", "limit=1e9", "limit=4.0", "limit=+4", "offset=-1"]:
            with self.subTest(query=query):
                self.assertEqual(call(self.app, "GET", f"/dossiers?{query}", headers=self.auth)[0], 422)

    def test_reset_during_build_does_not_change_next_state(self):
        slow_started = threading.Event()
        release = threading.Event()

        def slow(domain, *, budget=80, on_spend=None, cancelled=None):
            slow_started.set()
            release.wait(5)
            return SimpleNamespace(ok=True, spent=0, fields=ENGINE_FIELDS)

        app = App(Clock(), engine=slow)
        call(app, "POST", "/_test/reset", FIXTURE)
        token = call(app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[1]["token"]
        headers = {"authorization": f"Bearer {token}", "idempotency-key": "k"}
        call(app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, headers)
        slow_started.wait(5)
        call(app, "POST", "/_test/reset", FIXTURE)
        release.set()
        time.sleep(0.2)
        token = call(app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[1]["token"]
        status, body = call(app, "GET", "/dossiers?q=", headers={"authorization": f"Bearer {token}"})
        self.assertEqual(body["dossiers"], [])

    def test_export_of_building_dossier_is_its_last_completed_state(self):
        self._open("acme-robotics.test")
        exported = call(self.app, "GET", "/_test/export")[1]
        record = exported["state"]["dossiers"][0]
        self.assertIn(record["state"], ("ready", "failed"))
        if record["state"] == "failed":
            self.assertTrue(all(f["value"] is None for f in record["fields"].values()))

    def test_export_import_keeps_dossiers_and_idempotent_replay(self):
        status, first = self._open("acme-robotics.test")
        self._wait_settled("acme-robotics.test")
        exported = call(self.app, "GET", "/_test/export")[1]
        call(self.app, "POST", "/_test/reset", FIXTURE)
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 204)
        token = call(self.app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[1]["token"]
        headers = {"authorization": f"Bearer {token}", "idempotency-key": "k1"}
        self.assertEqual(call(self.app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, headers), (200, first))
        status, body = call(self.app, "GET", "/dossiers/acme-robotics.test", headers=headers)
        self.assertEqual((body["state"], body["spent_units"]), ("ready", 1))


if __name__ == "__main__":
    unittest.main()
