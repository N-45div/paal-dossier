"""RL17 structural import validation (R1.126, R1.125): every rejection is 422 with no change.

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app
"""

import copy
import json
import unittest

from app.app import App
from app.clock import Clock

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [{"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}],
}


def call(app, method, path, body=None):
    raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    reply = app.handle(method, path, {}, raw)
    return reply.status, (json.loads(reply.body) if reply.body else None)


def valid_dossier(**overrides):
    record = {
        "dossier_id": "d_1",
        "domain": "acme-robotics.test",
        "state": "failed",
        "researched_at": "2026-03-01T09:00:00+00:00",
        "spent_units": 3,
        "fields": {name: {"value": None, "citations": []} for name in
                   ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")},
    }
    record.update(overrides)
    return record


def valid_citation():
    return {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics was founded in 2014.", "provider": "nimble"}


class ImportValidationTests(unittest.TestCase):
    def setUp(self):
        self.app = App(Clock())
        call(self.app, "POST", "/_test/reset", FIXTURE)
        self.export = call(self.app, "GET", "/_test/export")[1]
        self.before = copy.deepcopy(self.export)

    def assert_rejected(self, state, why):
        body = {"track": "dossier", "format_version": 1, "state": state}
        status, _ = call(self.app, "POST", "/_test/import", body)
        self.assertEqual(status, 422, why)
        self.assertEqual(call(self.app, "GET", "/_test/export")[1], self.before, f"{why}: destination changed")

    def base(self):
        return copy.deepcopy(self.before["state"])

    def test_empty_object_state_is_rejected(self):
        self.assert_rejected({}, "{} is never a valid state")

    def test_non_object_state_and_missing_state_are_422(self):
        self.assertEqual(call(self.app, "POST", "/_test/import", {"track": "dossier", "format_version": 1, "state": []})[0], 422)
        self.assertEqual(call(self.app, "POST", "/_test/import", {"track": "dossier", "format_version": 1})[0], 422)

    def test_wrong_track_or_version_and_unparseable_bodies(self):
        self.assertEqual(call(self.app, "POST", "/_test/import", {"track": "other", "format_version": 1, "state": self.base()})[0], 422)
        self.assertEqual(call(self.app, "POST", "/_test/import", {"track": "dossier", "format_version": 2, "state": self.base()})[0], 422)
        self.assertEqual(call(self.app, "POST", "/_test/import", b"{not json")[0], 400)
        self.assertEqual(call(self.app, "POST", "/_test/import", b"[1]")[0], 400)

    def test_missing_section_or_extra_section_is_rejected(self):
        for section in ("users", "tokens", "counters", "dossiers", "idempotency"):
            state = self.base()
            del state[section]
            self.assert_rejected(state, f"missing {section}")
        state = self.base()
        state["extra"] = []
        self.assert_rejected(state, "extra section")

    def test_entries_with_extra_or_missing_keys_are_rejected(self):
        state = self.base()
        state["users"][0]["role"] = "admin"
        self.assert_rejected(state, "user with an extra key")
        state = self.base()
        del state["tokens"]
        state["tokens"] = [{"token": "t", "user_id": "u_ada", "extra": 1}]
        self.assert_rejected(state, "token with an extra key")

    def test_duplicate_user_id_and_token_to_missing_user(self):
        state = self.base()
        state["users"].append(dict(state["users"][0], email="other@example.com"))
        self.assert_rejected(state, "duplicate user id")
        state = self.base()
        state["tokens"] = [{"token": "t", "user_id": "u_nobody"}]
        self.assert_rejected(state, "token for a missing user")

    def test_counters_must_cover_issued_ids_and_stay_bounded(self):
        state = self.base()
        state["users"].append(dict(state["users"][0], id="u_5", email="five@example.com"))
        state["counters"] = {"user": 1}
        self.assert_rejected(state, "user counter below the highest issued id")
        state = self.base()
        state["counters"] = {"user": 10**13}
        self.assert_rejected(state, "counter above the bound")
        state = self.base()
        state["counters"] = {"user": True}
        self.assert_rejected(state, "boolean counter")
        state = self.base()
        state["counters"] = {"other": 1}
        self.assert_rejected(state, "unknown counter name")

    def test_password_hash_outside_the_service_parameters_is_rejected(self):
        state = self.base()
        state["users"][0]["password_hash"] = "scrypt$3$8$1$" + "AAAAAAAAAAAAAAAAAAAAAA==$" + "A" * 43 + "="
        self.assert_rejected(state, "scrypt work factor that is not a power of two")
        state = self.base()
        state["users"][0]["password_hash"] = "scrypt$1024$8$1$not-base64$x"
        self.assert_rejected(state, "malformed hash")

    def test_dossier_shape_and_field_rules(self):
        cases = {
            "unknown dossier key": valid_dossier(extra=1),
            "bad state": valid_dossier(state="building"),
            "ready without researched_at": valid_dossier(state="ready", researched_at=None),
            "negative spend": valid_dossier(spent_units=-1),
            "bool spend": valid_dossier(spent_units=True),
            "field with a wrong type": valid_dossier(fields=dict(valid_dossier()["fields"], founded_year={"value": "2014", "citations": [valid_citation()]})),
            "headcount outside the ranges": valid_dossier(fields=dict(valid_dossier()["fields"], headcount_range={"value": "7", "citations": [valid_citation()]})),
            "known value without citations": valid_dossier(fields=dict(valid_dossier()["fields"], founded_year={"value": 2014, "citations": []})),
            "unknown value with citations": valid_dossier(fields=dict(valid_dossier()["fields"], ceo={"value": None, "citations": [valid_citation()]})),
            "citation with an unknown provider": valid_dossier(fields=dict(valid_dossier()["fields"], founded_year={"value": 2014, "citations": [dict(valid_citation(), provider="bing")]})),
            "citation with an extra key": valid_dossier(fields=dict(valid_dossier()["fields"], founded_year={"value": 2014, "citations": [dict(valid_citation(), score=1)]})),
            "known field in a dossier without researched_at": valid_dossier(researched_at=None, fields=dict(valid_dossier()["fields"], founded_year={"value": 2014, "citations": [valid_citation()]})),
            "domain not normalised": valid_dossier(domain="Acme-Robotics.test."),
        }
        for why, dossier in cases.items():
            with self.subTest(why=why):
                state = self.base()
                state["counters"] = {"user": 1, "dossier": 1}
                state["dossiers"] = [dossier]
                self.assert_rejected(state, why)

    def test_failed_dossier_keeps_its_last_ready_fields_on_round_trip(self):
        state = self.base()
        state["counters"] = {"user": 1, "dossier": 1}
        state["dossiers"] = [valid_dossier()]
        status, _ = call(self.app, "POST", "/_test/import", {"track": "dossier", "format_version": 1, "state": state})
        self.assertEqual(status, 204)
        exported = call(self.app, "GET", "/_test/export")[1]["state"]["dossiers"][0]
        self.assertEqual((exported["state"], exported["researched_at"]), ("failed", "2026-03-01T09:00:00+00:00"))

    def test_idempotency_records_are_checked(self):
        record = {
            "user_id": "u_ada", "method": "POST", "path": "/dossiers", "key": "k1",
            "identity": {"domain": "acme-robotics.test"}, "status": 202,
            "body": {"dossier_id": "d_1", "domain": "acme-robotics.test", "state": "building"},
        }
        cases = {
            "unknown path": dict(record, path="/other"),
            "wrong method": dict(record, method="PUT"),
            "non-2xx status": dict(record, status=409),
            "unknown user": dict(record, user_id="u_nobody"),
            "identity with an extra field": dict(record, identity={"domain": "a.test", "x": 1}),
            "body missing a key": dict(record, body={"dossier_id": "d_1", "domain": "a.test"}),
            "refresh record with an identity": dict(record, path="/dossiers/a.test/refresh", identity={"domain": "a.test"}),
        }
        for why, bad in cases.items():
            with self.subTest(why=why):
                state = self.base()
                state["counters"] = {"user": 1, "dossier": 1}
                state["idempotency"] = [bad]
                self.assert_rejected(state, why)

    def test_valid_state_with_a_refresh_record_round_trips(self):
        state = self.base()
        state["counters"] = {"user": 1, "dossier": 1}
        state["dossiers"] = [valid_dossier()]
        state["idempotency"] = [{
            "user_id": "u_ada", "method": "POST", "path": "/dossiers/acme-robotics.test/refresh", "key": "r1",
            "identity": {}, "status": 202,
            "body": {"dossier_id": "d_1", "domain": "acme-robotics.test", "state": "building"},
        }]
        status, _ = call(self.app, "POST", "/_test/import", {"track": "dossier", "format_version": 1, "state": state})
        self.assertEqual(status, 204)
        again = call(self.app, "GET", "/_test/export")[1]
        self.assertEqual(again["state"]["idempotency"][0]["path"], "/dossiers/acme-robotics.test/refresh")

    def test_fresh_reset_export_is_itself_a_valid_import(self):
        exported = call(self.app, "GET", "/_test/export")[1]
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 204)


if __name__ == "__main__":
    unittest.main()
