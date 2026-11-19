"""Exact clock values, offsets, surrogates, reset timing and counter bounds (R1.17, R1.25–R1.27, R1.29, R1.33, R1.62).

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app
"""

import json
import time
import unittest

from app.app import App
from app.clock import Clock


def call(app, method, path, body=None, headers=None):
    raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    reply = app.handle(method, path, headers or {}, raw)
    return reply.status, (json.loads(reply.body) if reply.body else None), reply


def fixture(now="2026-03-01T09:00:00+00:00", users=None):
    return {"now": now, "users": users or []}


class PrecisionTests(unittest.TestCase):
    def setUp(self):
        self.app = App(Clock())

    def test_R1_25_before_first_reset_the_clock_follows_system_time(self):
        before = int(time.time())
        status, _, _ = call(self.app, "POST", "/_test/clock", {"now": "2000-01-01T00:00:00+00:00"})
        self.assertEqual(status, 422, "a clock call earlier than system time must not move it")
        self.assertGreaterEqual(self.app.clock.now().ns // 10**9, before)

    def test_R1_24_and_R1_26_clock_moves_only_on_reset_or_clock_and_stands_still(self):
        call(self.app, "POST", "/_test/reset", fixture())
        first = self.app.clock.now()
        time.sleep(0.05)
        self.assertEqual(self.app.clock.now(), first)
        call(self.app, "POST", "/_test/clock", {"now": "2026-04-01T00:00:00+00:00"})
        self.assertGreater(self.app.clock.now().ns, first.ns)

    def test_R1_27_nine_digit_fractions_compare_exactly(self):
        call(self.app, "POST", "/_test/reset", fixture(now="2026-03-01T09:00:00.123456789+00:00"))
        status, _, _ = call(self.app, "POST", "/_test/clock", {"now": "2026-03-01T09:00:00.123456788+00:00"})
        self.assertEqual(status, 422)
        status, _, _ = call(self.app, "POST", "/_test/clock", {"now": "2026-03-01T09:00:00.123456789+00:00"})
        self.assertEqual(status, 204)

    def test_R1_27_offsets_out_of_range_are_rejected(self):
        for now in ["2026-03-02T09:00:00+00:99", "2026-03-02T09:00:00+24:00", "2026-03-02T09:00:00+01:60"]:
            with self.subTest(now=now):
                self.assertEqual(call(self.app, "POST", "/_test/reset", fixture(now=now))[0], 422)

    def test_R1_29_responses_are_json_utf8_and_ascii_escaped(self):
        call(self.app, "POST", "/_test/reset", fixture())
        _, _, reply = call(self.app, "GET", "/health")
        self.assertEqual(reply.body, b'{"status":"ok"}')

    def test_R1_62_lone_surrogate_in_display_name_is_answered_not_500(self):
        call(self.app, "POST", "/_test/reset", fixture())
        status, body, reply = call(
            self.app, "POST", "/auth/signup",
            json.dumps({"email": "s@example.test", "password": "longenough", "display_name": "\ud800"}).encode(),
        )
        self.assertEqual(status, 201)
        self.assertIn(b"\\ud800", reply.body)

    def test_R1_17_two_thousand_user_fixture_resets_within_budget(self):
        users = [
            {"id": f"u_{i}", "email": f"user{i}@example.test", "password": "abcdefgh", "display_name": f"U{i}"}
            for i in range(2000)
        ]
        started = time.monotonic()
        status, _, _ = call(self.app, "POST", "/_test/reset", fixture(users=users))
        elapsed = time.monotonic() - started
        self.assertEqual(status, 204)
        self.assertLess(elapsed, 10.0, f"reset took {elapsed:.1f}s")

    def test_R1_33_counter_is_bounded_so_ids_stay_within_64_characters(self):
        call(self.app, "POST", "/_test/reset", fixture())
        exported = call(self.app, "GET", "/_test/export")[1]
        exported["state"]["counters"] = {"user": 10**13}
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 422)
        exported["state"]["counters"] = {"user": 10**12}
        self.assertEqual(call(self.app, "POST", "/_test/import", exported)[0], 204)
        status, body, _ = call(self.app, "POST", "/auth/signup",
                               {"email": "z@example.test", "password": "longenough", "display_name": "Z"})
        self.assertEqual(status, 201)
        self.assertLessEqual(len(body["user_id"]), 64)


if __name__ == "__main__":
    unittest.main()
