"""Tests for the gaps declared in the P1/P3 handoff (RL20 item 5).

Index: R1.12 -> test_r1_12_port_is_the_only_setting_p1_reads
       R1.20 -> test_r1_20_app_package_ships_no_runtime_assets
       R1.30 -> test_r1_30_researched_at_is_rfc3339_with_explicit_offset
       R1.72 -> test_r1_72_same_key_for_two_users_is_independent
       R1.84 -> test_r1_84_second_refresh_while_building_starts_no_second_build
       R1.89 -> test_r1_89_reads_make_no_provider_call

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app

Index of claimed ids covered in this module:
    R1.12 -> DeclaredGapTests.test_r1_12_port_is_the_only_setting_p1_reads
    R1.20 -> DeclaredGapTests.test_r1_20_app_package_ships_no_runtime_assets
    R1.30 -> DeclaredGapTests.test_r1_30_researched_at_is_rfc3339_with_explicit_offset
    R1.72 -> DeclaredGapTests.test_r1_72_same_key_for_two_users_is_independent
    R1.84 -> DeclaredGapTests.test_r1_84_second_refresh_while_building_starts_no_second_build
    R1.89 -> DeclaredGapTests.test_r1_89_reads_make_no_provider_call
"""

import json
import os
import pathlib
import threading
import time
import unittest
from types import SimpleNamespace

from app import __main__ as entry
from app.app import App
from app.clock import Clock

APP_DIR = pathlib.Path(__file__).resolve().parents[3] / "stage-1" / "app"

FIXTURE = {
    "now": "2026-03-01T09:00:00+02:00",
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
    ],
}


def call(app, method, path, body=None, headers=None):
    raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    reply = app.handle(method, path, headers or {}, raw)
    return reply.status, (json.loads(reply.body) if reply.body else None)


def counting_engine(calls, gate=None):
    def run(domain, *, budget=80, on_spend=None, cancelled=None):
        calls.append(domain)
        if gate is not None:
            gate.wait(5)
        return SimpleNamespace(ok=True, spent=0, fields={})
    return run


def login(app, email):
    return call(app, "POST", "/auth/login", {"email": email, "password": "correct horse"})[1]["token"]


def wait_settled(app, token, domain, timeout=5.0):
    end = time.monotonic() + timeout
    headers = {"authorization": f"Bearer {token}"}
    while time.monotonic() < end:
        _, body = call(app, "GET", f"/dossiers/{domain}", headers=headers)
        if body["state"] != "building":
            return body
        time.sleep(0.01)
    raise AssertionError("build did not settle")


class DeclaredGapTests(unittest.TestCase):
    def test_r1_12_port_is_the_only_setting_p1_reads(self):
        """Covers R1.12: P1 reads PORT only; provider variables are for the engine (P4)."""
        old = os.environ.get("PORT")
        try:
            os.environ["PORT"] = "18123"
            self.assertEqual(entry._port(), 18123)
            os.environ["PORT"] = "not-a-port"
            with self.assertRaises(SystemExit):
                entry._port()
        finally:
            if old is None:
                os.environ.pop("PORT", None)
            else:
                os.environ["PORT"] = old

    def test_r1_20_app_package_ships_no_runtime_assets(self):
        """Covers R1.20: the app package holds only Python source; no fonts, scripts or stylesheets are needed."""
        files = [p for p in APP_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        self.assertTrue(files)
        self.assertEqual([p.name for p in files if p.suffix != ".py"], [])

    def test_r1_30_researched_at_is_rfc3339_with_explicit_offset(self):
        """Covers R1.30: a timestamp the service returns carries its explicit offset."""
        app = App(Clock())
        call(app, "POST", "/_test/reset", FIXTURE)
        token = login(app, "ada@example.com")
        call(app, "POST", "/dossiers", {"domain": "acme-robotics.test"},
             {"authorization": f"Bearer {token}", "idempotency-key": "k"})
        body = wait_settled(app, token, "acme-robotics.test")
        self.assertEqual(body["researched_at"], "2026-03-01T09:00:00+02:00")

    def test_r1_72_same_key_for_two_users_is_independent(self):
        """Covers R1.72: the key is scoped to the user; the same key string from another user is a first use."""
        app = App(Clock(), engine=counting_engine([]))
        call(app, "POST", "/_test/reset", FIXTURE)
        ada = login(app, "ada@example.com")
        bob = login(app, "bob@example.com")
        first = call(app, "POST", "/dossiers", {"domain": "ada-co.test"},
                     {"authorization": f"Bearer {ada}", "idempotency-key": "same"})
        second = call(app, "POST", "/dossiers", {"domain": "bob-co.test"},
                      {"authorization": f"Bearer {bob}", "idempotency-key": "same"})
        self.assertEqual((first[0], second[0]), (202, 202))
        self.assertNotEqual(first[1]["dossier_id"], second[1]["dossier_id"])

    def test_r1_84_second_refresh_while_building_starts_no_second_build(self):
        """Covers R1.84: a refresh received while a build runs starts no second build."""
        calls: list[str] = []
        gate = threading.Event()
        app = App(Clock(), engine=counting_engine(calls, gate))
        call(app, "POST", "/_test/reset", FIXTURE)
        token = login(app, "ada@example.com")
        headers = {"authorization": f"Bearer {token}"}
        call(app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(headers, **{"idempotency-key": "o1"}))
        deadline = time.monotonic() + 5
        while not calls and time.monotonic() < deadline:
            time.sleep(0.01)
        status, body = call(app, "POST", "/dossiers/acme-robotics.test/refresh", None,
                            dict(headers, **{"idempotency-key": "r1"}))
        self.assertEqual((status, body["state"]), (202, "building"))
        time.sleep(0.1)
        self.assertEqual(len(calls), 1, "a second build started while one was running")
        gate.set()
        wait_settled(app, token, "acme-robotics.test")

    def test_r1_89_reads_make_no_provider_call(self):
        """Covers R1.89: reading a dossier or listing dossiers makes no provider call."""
        calls: list[str] = []
        app = App(Clock(), engine=counting_engine(calls))
        call(app, "POST", "/_test/reset", FIXTURE)
        token = login(app, "ada@example.com")
        headers = {"authorization": f"Bearer {token}"}
        call(app, "POST", "/dossiers", {"domain": "acme-robotics.test"}, dict(headers, **{"idempotency-key": "k"}))
        wait_settled(app, token, "acme-robotics.test")
        before = len(calls)
        call(app, "GET", "/dossiers/acme-robotics.test", headers=headers)
        call(app, "GET", "/dossiers?q=acme&limit=5", headers=headers)
        call(app, "GET", "/health")
        self.assertEqual(len(calls), before)


if __name__ == "__main__":
    unittest.main()
