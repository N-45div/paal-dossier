"""Import of a stage-1 export, then builds (R2.108 API halves, R2.109, RL59).

Run from the repository root:  PYTHONPATH=stage-2 python3 -m unittest discover -s qa/stage-2/unit_app -t qa/stage-2/unit_app
"""

import copy
import json
import time
import unittest
from types import SimpleNamespace

from app.app import App
from app.clock import Clock

DOMAIN = "acme-robotics.test"
URL = "https://acme-robotics.test/about"
NOW = "2026-03-01T09:00:00+00:00"
FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")


def citation(excerpt):
    return {"url": URL, "excerpt": excerpt, "provider": "nimble"}


def unknown():
    return {"value": None, "status": "unknown", "citations": [], "candidates": []}


def first_build_fields():
    fields = {name: unknown() for name in FIELD_NAMES}
    cit = citation("Acme Robotics, Inc. is the registered name.")
    fields["legal_name"] = {
        "value": "Acme Robotics, Inc.",
        "status": "known",
        "citations": [cit],
        "candidates": [{**cit, "value": "Acme Robotics, Inc.", "kind": "own", "published_at": None,
                        "retrieved_at": NOW, "selected": True}],
    }
    return fields


def second_build_fields():
    """Two candidates for ceo; legal_name keeps a single candidate with a new value."""
    fields = {name: unknown() for name in FIELD_NAMES}
    fields["legal_name"] = {
        "value": "Acme Robotics Ltd.",
        "status": "known",
        "citations": [citation("Acme Robotics Ltd. is the registered name.")],
        "candidates": [{**citation("Acme Robotics Ltd. is the registered name."), "value": "Acme Robotics Ltd.",
                        "kind": "own", "published_at": None, "retrieved_at": NOW, "selected": True}],
    }
    return fields


class ImportThenBuildTests(unittest.TestCase):
    def setUp(self):
        self.engine_fields = first_build_fields()
        self.app = App(Clock(), engine=self._engine)
        self.assertEqual(self.call("POST", "/_test/reset", {
            "now": NOW,
            "users": [{"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}],
        })[0], 204)
        self.token = self.call("POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[1]["token"]
        self.auth = {"authorization": f"Bearer {self.token}"}

    def _engine(self, domain, *, budget=80, on_spend=None, cancelled=None):
        return SimpleNamespace(ok=True, spent=0, fields=copy.deepcopy(self.engine_fields))

    def call(self, method, path, body=None, headers=None):
        raw = b"" if body is None else json.dumps(body).encode()
        reply = self.app.handle(method, path, headers or {}, raw)
        return reply.status, (json.loads(reply.body) if reply.body else None)

    def settle(self, headers):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            status, body = self.call("GET", f"/dossiers/{DOMAIN}", headers=headers)
            if body["state"] != "building":
                return body
            time.sleep(0.02)
        self.fail("build did not settle")

    def stage1_export(self):
        """A stage-1 form export: fields carry no status and no candidates."""
        export = self.call("GET", "/_test/export")[1]
        for entry in export["state"]["dossiers"]:
            for field in entry["fields"].values():
                field.pop("candidates", None)
                field.pop("status", None)
        return export

    def test_replay_after_import_returns_stored_body_and_get_shows_imported(self):
        headers = {**self.auth, "idempotency-key": "k1"}
        opened_status, opened = self.call("POST", "/dossiers", {"domain": DOMAIN}, headers)
        self.assertEqual(opened_status, 202)
        settled = self.settle(self.auth)
        self.assertEqual(settled["state"], "ready")
        export = self.stage1_export()
        self.assertEqual(self.call("POST", "/_test/import", export)[0], 204)

        replay_status, replay = self.call("POST", "/dossiers", {"domain": DOMAIN}, headers)
        self.assertEqual(replay_status, 200)
        self.assertEqual(replay, opened)
        after = self.call("GET", f"/dossiers/{DOMAIN}", headers=self.auth)[1]
        self.assertEqual(after["state"], "ready")
        self.assertEqual(after["fields"]["legal_name"]["value"], "Acme Robotics, Inc.")
        self.assertEqual(after["fields"]["legal_name"]["status"], "known")
        self.assertEqual(len(after["fields"]["legal_name"]["candidates"]), 1)

    def test_next_completed_build_replaces_imported_candidates(self):
        headers = {**self.auth, "idempotency-key": "k1"}
        self.call("POST", "/dossiers", {"domain": DOMAIN}, headers)
        self.settle(self.auth)
        self.assertEqual(self.call("POST", "/_test/import", self.stage1_export())[0], 204)
        imported = self.call("GET", f"/dossiers/{DOMAIN}", headers=self.auth)[1]
        self.assertEqual(imported["fields"]["legal_name"]["candidates"][0]["retrieved_at"], NOW)

        self.engine_fields = second_build_fields()
        status, _ = self.call("POST", f"/dossiers/{DOMAIN}/refresh", {}, {**self.auth, "idempotency-key": "r2"})
        self.assertEqual(status, 202)
        rebuilt = self.settle(self.auth)
        self.assertEqual(rebuilt["state"], "ready")
        expected = second_build_fields()["legal_name"]
        got = rebuilt["fields"]["legal_name"]
        self.assertEqual(got["value"], expected["value"])
        self.assertEqual(got["status"], expected["status"])
        self.assertEqual(got["candidates"], expected["candidates"])


if __name__ == "__main__":
    unittest.main()
