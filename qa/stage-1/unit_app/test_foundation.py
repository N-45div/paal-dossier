"""Unit tests for the P1 foundation: control endpoints, clock, auth, export/import, envelope.

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app
"""

import json
import unittest

from app.app import App
from app.clock import Clock

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
    ],
}


def call(app, method, path, body=None, headers=None):
    raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    reply = app.handle(method, path, headers or {}, raw)
    payload = json.loads(reply.body) if reply.body else None
    return reply.status, payload


def reset(app, fixture=FIXTURE):
    return call(app, "POST", "/_test/reset", fixture)[0]


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.app = App(Clock())
        self.assertEqual(reset(self.app), 204)

    def test_health_is_ok_without_auth(self):
        self.assertEqual(call(self.app, "GET", "/health"), (200, {"status": "ok"}))

    def test_seeded_user_logs_in_with_given_password(self):
        status, body = call(self.app, "POST", "/auth/login", {"email": "ADA@example.com", "password": "correct horse"})
        self.assertEqual(status, 200)
        self.assertEqual(body["user_id"], "u_ada")
        self.assertEqual(body["display_name"], "Ada")

    def test_wrong_password_and_unknown_email_are_401(self):
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": "ada@example.com", "password": "nope"})[0], 401)
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": "x@example.com", "password": "nope"})[0], 401)

    def test_signup_then_duplicate_email_is_409(self):
        body = {"email": "cy@example.com", "password": "longenough", "display_name": "Cy"}
        status, created = call(self.app, "POST", "/auth/signup", body)
        self.assertEqual(status, 201)
        self.assertTrue(created["token"])
        self.assertEqual(call(self.app, "POST", "/auth/signup", dict(body, email="CY@example.com"))[0], 409)

    def test_signup_validation(self):
        base = {"email": "dan@example.com", "password": "longenough", "display_name": "Dan"}
        self.assertEqual(call(self.app, "POST", "/auth/signup", dict(base, password="short"))[0], 422)
        self.assertEqual(call(self.app, "POST", "/auth/signup", dict(base, email="not-an-email"))[0], 422)
        self.assertEqual(call(self.app, "POST", "/auth/signup", dict(base, display_name=""))[0], 422)
        self.assertEqual(call(self.app, "POST", "/auth/signup", dict(base, display_name="x" * 101))[0], 422)

    def test_wrong_json_type_is_400_and_missing_field_is_422(self):
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": 5, "password": "x"})[0], 400)
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": "a@b.test"})[0], 422)
        self.assertEqual(call(self.app, "POST", "/auth/login", b"{not json")[0], 400)
        self.assertEqual(call(self.app, "POST", "/auth/login", b"[1,2]")[0], 400)

    def test_unknown_fields_are_ignored(self):
        status, _ = call(self.app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse", "extra": 1})
        self.assertEqual(status, 200)

    def test_missing_or_unknown_bearer_token_is_401(self):
        from app.errors import ApiError

        with self.assertRaises(ApiError) as missing:
            self.app.store.authenticate(None)
        self.assertEqual(missing.exception.status, 401)
        with self.assertRaises(ApiError) as unknown:
            self.app.store.authenticate("not-a-token")
        self.assertEqual(unknown.exception.status, 401)

    def test_envelope_on_unknown_route_and_method(self):
        status, body = call(self.app, "GET", "/nope")
        self.assertEqual((status, body["error"]["code"]), (404, "not_found"))
        status, body = call(self.app, "DELETE", "/health")
        self.assertEqual((status, body["error"]["code"]), (405, "method_not_allowed"))

    def test_reset_rejects_duplicate_email_without_changing_state(self):
        bad = {"now": "2026-03-01T09:00:00+00:00", "users": [
            {"id": "u_1", "email": "a@x.test", "password": "pw", "display_name": "A"},
            {"id": "u_2", "email": "A@x.test", "password": "pw", "display_name": "B"},
        ]}
        self.assertEqual(call(self.app, "POST", "/_test/reset", bad)[0], 422)
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[0], 200)

    def test_reset_clears_previous_accounts(self):
        call(self.app, "POST", "/auth/signup", {"email": "zed@example.com", "password": "longenough", "display_name": "Zed"})
        reset(self.app)
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": "zed@example.com", "password": "longenough"})[0], 401)

    def test_clock_rejects_earlier_time_and_offsets_are_required(self):
        self.assertEqual(call(self.app, "POST", "/_test/clock", {"now": "2026-02-01T00:00:00+00:00"})[0], 422)
        self.assertEqual(call(self.app, "POST", "/_test/clock", {"now": "2026-04-01T00:00:00"})[0], 422)
        self.assertEqual(call(self.app, "POST", "/_test/clock", {"now": "2026-04-01T00:00:00+02:00"})[0], 204)

    def test_export_import_round_trip_keeps_tokens_and_accounts(self):
        _, created = call(self.app, "POST", "/auth/signup", {"email": "eve@example.com", "password": "longenough", "display_name": "Eve"})
        _, exported = call(self.app, "GET", "/_test/export")
        self.assertEqual(exported["track"], "dossier")
        self.assertEqual(exported["format_version"], 1)
        reset(self.app)  # wipe everything, then restore
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 204)
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": "eve@example.com", "password": "longenough"})[0], 200)
        self.assertEqual(call(self.app, "GET", "/health")[0], 200)
        self.assertEqual(self.app.store.authenticate(created["token"]), created["user_id"])

    def test_import_is_replacement_and_repeatable(self):
        _, exported = call(self.app, "GET", "/_test/export")
        for _ in range(2):
            self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 204)
        self.assertEqual(len(self.app.store.export_state()["users"]), 2)

    def test_invalid_import_is_422_and_changes_nothing(self):
        _, exported = call(self.app, "GET", "/_test/export")
        bad = dict(exported, format_version=2)
        self.assertEqual(call(self.app, "POST", "/_test/import", bad)[0], 422)
        self.assertEqual(call(self.app, "POST", "/_test/import", {"track": "other", "format_version": 1, "state": {}})[0], 422)
        self.assertEqual(call(self.app, "POST", "/_test/import", {"track": "dossier", "format_version": 1, "state": {"users": [{"id": "x"}]}})[0], 422)
        self.assertEqual(call(self.app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[0], 200)

    def test_import_rejects_token_pointing_at_missing_user(self):
        _, exported = call(self.app, "GET", "/_test/export")
        exported["state"]["tokens"] = [{"token": "t1", "user_id": "u_missing"}]
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 422)


if __name__ == "__main__":
    unittest.main()
