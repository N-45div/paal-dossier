"""Dossier API checks over HTTP, with a scripted engine (no providers)."""

import json
import threading
import unittest
import urllib.error
import urllib.request

from dossier.server.service import make_service
from ports import bind_server
from fake_engine import FakeEngine, citation, result

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
    ],
}
ACME_VALUES = {
    "legal_name": ("Acme Robotics, Inc.", [citation("https://acme-robotics.test/about", "Acme Robotics, Inc. is ...")]),
    "founded_year": (2014, [citation("https://acme-robotics.test/about", "Acme Robotics was founded in 2014.")]),
}


class Api:
    def __init__(self, base):
        self.base = base

    def call(self, method, path, body=None, token=None, key=None, raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("Authorization", "Bearer " + token)
        if key is not None:
            request.add_header("Idempotency-Key", key)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                text = response.read()
                return response.status, json.loads(text) if text else None
        except urllib.error.HTTPError as error:
            text = error.read()
            return error.code, json.loads(text) if text else None


class DossierApiTests(unittest.TestCase):
    engine: FakeEngine

    @classmethod
    def setUpClass(cls):
        cls.engine = FakeEngine()
        cls.server = bind_server(make_service(cls.engine))
        cls.api = Api(f"http://127.0.0.1:{cls.server.server_address[1]}")
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.engine.outcome = result(ok=True, spent=5, values=ACME_VALUES)
        self.engine.calls.clear()
        self.engine.gate.set()
        self.assertEqual(self.api.call("POST", "/_test/reset", FIXTURE)[0], 204)
        status, body = self.api.call("POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})
        self.token = body["token"]

    def wait_ready(self, domain):
        for _ in range(200):
            status, body = self.api.call("GET", f"/dossiers/{domain}", token=self.token)
            if body["state"] != "building":
                return body
            threading.Event().wait(0.02)
        self.fail("build did not finish")

    def test_create_then_replay_returns_original_body_as_200(self):
        body = {"domain": "acme-robotics.test"}
        status, first = self.api.call("POST", "/dossiers", body, token=self.token, key="k1")
        self.assertEqual(status, 202)
        self.assertEqual(first["state"], "building")
        status, replay = self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="k1")
        self.assertEqual((status, replay), (200, first))

    def test_same_key_different_body_is_409_and_unknown_fields_do_not_count(self):
        self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="k2")
        status, body = self.api.call("POST", "/dossiers", {"domain": "other.test"}, token=self.token, key="k2")
        self.assertEqual((status, body["error"]["code"]), (409, "idempotency_key_reuse"))
        status, body = self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test", "note": "x"}, token=self.token, key="k2")
        self.assertEqual(status, 200)

    def test_missing_key_is_400_but_missing_token_is_401_first(self):
        self.assertEqual(self.api.call("POST", "/dossiers", {"domain": "a.test"}, token=self.token)[0], 400)
        self.assertEqual(self.api.call("POST", "/dossiers", {"domain": "a.test"}, key="k")[0], 401)

    def test_domain_spellings_are_one_dossier(self):
        _, first = self.api.call("POST", "/dossiers", {"domain": "Acme-Robotics.TEST."}, token=self.token, key="k3")
        status, second = self.api.call("POST", "/dossiers", {"domain": "www.acme-robotics.test"}, token=self.token, key="k4")
        self.assertEqual((status, second["dossier_id"]), (200, first["dossier_id"]))
        self.assertEqual(second["domain"], "acme-robotics.test")

    def test_concurrent_identical_requests_start_one_build(self):
        self.engine.gate.clear()
        answers = []

        def post():
            answers.append(self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="same"))

        threads = [threading.Thread(target=post) for _ in range(8)]
        for thread in threads:
            thread.start()
        threading.Event().wait(0.2)
        self.engine.gate.set()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(status for status, _ in answers), [200] * 7 + [202])
        self.assertEqual(len({json.dumps(body, sort_keys=True) for _, body in answers}), 1)
        self.assertEqual(len(self.engine.calls), 1)

    def test_refresh_during_build_starts_no_second_build(self):
        self.engine.gate.clear()
        self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="c1")
        status, body = self.api.call("POST", "/dossiers/acme-robotics.test/refresh", token=self.token, key="r1")
        self.assertEqual((status, body["state"]), (202, "building"))
        self.engine.gate.set()
        self.wait_ready("acme-robotics.test")
        self.assertEqual(len(self.engine.calls), 1)

    def test_ready_build_fills_known_fields_and_spend(self):
        self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="b1")
        body = self.wait_ready("acme-robotics.test")
        self.assertEqual(body["state"], "ready")
        self.assertEqual(body["spent_units"], 5)
        self.assertEqual(body["fields"]["legal_name"]["status"], "known")
        self.assertEqual(body["fields"]["ceo"], {"value": None, "status": "unknown", "citations": []})
        self.assertIsNotNone(body["researched_at"])

    def test_failed_build_leaves_unknown_fields_and_counts_spend(self):
        self.engine.outcome = result(ok=False, spent=7)
        self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="f1")
        body = self.wait_ready("acme-robotics.test")
        self.assertEqual((body["state"], body["spent_units"], body["researched_at"]), ("failed", 7, None))

    def test_reset_during_build_is_not_changed_by_the_stale_build(self):
        self.engine.gate.clear()
        self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="x1")
        self.api.call("POST", "/_test/reset", FIXTURE)
        self.engine.gate.set()
        threading.Event().wait(0.2)
        _, login = self.api.call("POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})
        status, _ = self.api.call("GET", "/dossiers/acme-robotics.test", token=login["token"])
        self.assertEqual(status, 404)

    def test_listing_filters_orders_and_pages(self):
        self.engine.outcome = result(ok=False)  # only acme-robotics.test should get Acme's legal name
        for domain, key in [("zeta.test", "l1"), ("acme-robotics.test", "l2"), ("beta.test", "l3")]:
            self.api.call("POST", "/dossiers", {"domain": domain}, token=self.token, key=key)
        status, body = self.api.call("GET", "/dossiers?limit=2&offset=0", token=self.token)
        self.assertEqual([row["domain"] for row in body["dossiers"]], ["acme-robotics.test", "beta.test"])
        self.assertTrue(body["has_more"])
        status, body = self.api.call("GET", "/dossiers?q=ACME", token=self.token)
        self.assertEqual([row["domain"] for row in body["dossiers"]], ["acme-robotics.test"])
        self.assertEqual(body["dossiers"][0]["legal_name"], None)
        self.assertEqual(self.api.call("GET", "/dossiers?limit=", token=self.token)[0], 422)
        self.assertEqual(self.api.call("GET", "/dossiers?limit=1e2", token=self.token)[0], 422)

    def test_export_then_import_keeps_dossiers_tokens_and_claims(self):
        self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="e1")
        before = self.wait_ready("acme-robotics.test")
        status, document = self.api.call("GET", "/_test/export")
        self.assertEqual((status, document["track"], document["format_version"]), (200, "dossier", 1))
        self.assertEqual(self.api.call("POST", "/_test/reset", FIXTURE)[0], 204)
        self.assertEqual(self.api.call("GET", "/dossiers/acme-robotics.test", token=self.token)[0], 401)
        self.assertEqual(self.api.call("POST", "/_test/import", document)[0], 204)
        self.assertEqual(self.api.call("GET", "/dossiers/acme-robotics.test", token=self.token)[1], before)
        self.assertEqual(self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="e1")[0], 200)
        self.assertEqual(len(self.engine.calls), 1)

    def test_import_rejects_bad_documents_without_change(self):
        self.api.call("POST", "/dossiers", {"domain": "acme-robotics.test"}, token=self.token, key="e2")
        self.wait_ready("acme-robotics.test")
        self.assertEqual(self.api.call("POST", "/_test/import", {"track": "other", "format_version": 1, "state": {}})[0], 422)
        self.assertEqual(self.api.call("POST", "/_test/import", raw=b"[]")[0], 400)
        self.assertEqual(self.api.call("GET", "/dossiers/acme-robotics.test", token=self.token)[0], 200)


if __name__ == "__main__":
    unittest.main()
