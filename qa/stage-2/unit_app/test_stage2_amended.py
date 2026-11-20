"""Amended stage-2 versions of two superseded stage-1 assertions (lead rulings on ea040f68)."""
"""Run: PYTHONPATH=stage-2 python3 -m unittest discover -s qa/stage-2/unit_app -t qa/stage-2/unit_app"""
import copy
import json
import time
import unittest
from types import SimpleNamespace
from app.app import App
from app.clock import Clock
NOW = "2026-03-01T09:00:00+00:00"
DOMAIN = "amended-shape.test"
ABOUT = "https://amended-shape.test/about"
NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
def cite(url, excerpt, provider="nimble"):
    return {"url": url, "excerpt": excerpt, "provider": provider}
def unknown():
    return {"value": None, "citations": []}
def hdr(auth, key):
    h = dict(auth)
    h["idempotency-key"] = key
    return h
def shape_engine(domain, budget=80, on_spend=None, cancelled=None):
    mira = dict(cite(ABOUT, "Amended Shape CEO Mira Stone."), value="Mira Stone", kind="own", published_at=None, retrieved_at=NOW, selected=True)
    sam = dict(cite("https://aggregator.test/amended-shape", "Amended Shape CEO Sam Ortiz.", "tavily"), value="Sam Ortiz", kind="aggregator", published_at=None, retrieved_at=NOW, selected=False)
    return SimpleNamespace(ok=True, spent=0, fields={"legal_name": {"value": "Amended Shape Inc.", "citations": [cite(ABOUT, "Amended Shape Inc. is the registered name.")]}, "hq_city": unknown(), "ceo": {"value": "Mira Stone", "status": "contested", "citations": [cite(ABOUT, "Amended Shape CEO Mira Stone.")], "candidates": [mira, sam]}, "founded_year": unknown(), "headcount_range": unknown(), "funding_total": unknown()})
def zero_engine(domain, budget=80, on_spend=None, cancelled=None):
    fields = {n: unknown() for n in NAMES}
    fields["funding_total"] = {"value": 0, "citations": [cite(ABOUT, "Amended Shape raised $0.")]}
    return SimpleNamespace(ok=True, spent=0, fields=fields)
class AmendedTests(unittest.TestCase):
    def make_app(self, engine):
        app = App(Clock(), engine=engine)
        self.assertEqual(self.call(app, "POST", "/_test/reset", {"now": NOW, "users": [{"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"}]})[0], 204)
        token = self.call(app, "POST", "/auth/login", {"email": "ada@example.com", "password": "correct horse"})[1]["token"]
        return app, {"authorization": "Bearer " + token}
    def call(self, app, method, path, body=None, headers=None):
        import json as j
        raw = b"" if body is None else j.dumps(body).encode()
        reply = app.handle(method, path, headers or {}, raw)
        return reply.status, (j.loads(reply.body) if reply.body else None)
    def settle(self, app, auth):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            s, b = self.call(app, "GET", "/dossiers/" + DOMAIN, headers=auth)
            if b["state"] != "building":
                return b
            time.sleep(0.02)
        self.fail("build did not settle")
    def strip_candidates(self, export):
        s1 = copy.deepcopy(export)
        for e in s1["state"]["dossiers"]:
            for f in e["fields"].values():
                f.pop("candidates", None)
                f.pop("status", None)
        return s1
    def check_shape(self, fields):
        self.assertEqual(set(fields), set(NAMES))
        for name, f in fields.items():
            with self.subTest(field=name):
                self.assertEqual(set(f), {"value", "status", "citations", "candidates"})
                self.assertIn(f["status"], ("known", "contested", "unknown"))
                if f["value"] is None:
                    self.assertEqual(f["status"], "unknown")
                    self.assertEqual(f["citations"], [])
                    self.assertEqual(f["candidates"], [])
                else:
                    self.assertIn(f["status"], ("known", "contested"))
                    self.assertTrue(f["citations"])
                    self.assertTrue(f["candidates"])
                sel = [c for c in f["candidates"] if c["selected"]]
                if f["candidates"]:
                    self.assertEqual(len(sel), 1)
                    self.assertTrue(f["candidates"][0]["selected"])
    def test_R2_38_every_field_carries_candidates(self):
        app, auth = self.make_app(shape_engine)
        self.assertEqual(self.call(app, "POST", "/dossiers", {"domain": DOMAIN}, hdr(auth, "k1"))[0], 202)
        body = self.settle(app, auth)
        self.assertEqual(body["state"], "ready")
        self.check_shape(body["fields"])
        self.assertEqual(body["fields"]["legal_name"]["status"], "known")
        self.assertEqual(len(body["fields"]["legal_name"]["candidates"]), 1)
        self.assertIsNone(body["fields"]["legal_name"]["candidates"][0]["kind"])
        self.assertEqual(body["fields"]["ceo"]["status"], "contested")
    def test_RL32_funding_zero_export_keeps_candidates_and_round_trips(self):
        app, auth = self.make_app(zero_engine)
        self.call(app, "POST", "/dossiers", {"domain": DOMAIN}, hdr(auth, "k1"))
        body = self.settle(app, auth)
        self.check_shape(body["fields"])
        self.assertEqual(body["fields"]["funding_total"]["value"], 0)
        self.assertEqual(body["fields"]["funding_total"]["status"], "known")
        e1 = self.call(app, "GET", "/_test/export")[1]
        self.assertTrue(e1["state"]["dossiers"][0]["fields"]["funding_total"]["candidates"])
        self.assertEqual(self.call(app, "POST", "/_test/import", e1)[0], 204)
        e2 = self.call(app, "GET", "/_test/export")[1]
        self.assertEqual(e2, e1)
    def test_R1_76_R2_108_replay_after_import_returns_original_body(self):
        app, auth = self.make_app(zero_engine)
        st, opened = self.call(app, "POST", "/dossiers", {"domain": DOMAIN}, hdr(auth, "k1"))
        self.assertEqual(st, 202)
        self.settle(app, auth)
        export = self.call(app, "GET", "/_test/export")[1]
        self.assertEqual(self.call(app, "POST", "/_test/import", self.strip_candidates(export))[0], 204)
        rs, replay = self.call(app, "POST", "/dossiers", {"domain": DOMAIN}, hdr(auth, "k1"))
        self.assertEqual(rs, 200)
        self.assertEqual(replay, opened)
        after = self.call(app, "GET", "/dossiers/" + DOMAIN, headers=auth)[1]
        self.assertEqual(after["state"], "ready")
        self.assertEqual(after["fields"]["funding_total"]["value"], 0)
    def test_R2_109_next_build_replaces_imported_candidates(self):
        app, auth = self.make_app(zero_engine)
        self.call(app, "POST", "/dossiers", {"domain": DOMAIN}, hdr(auth, "k1"))
        self.settle(app, auth)
        export = self.call(app, "GET", "/_test/export")[1]
        self.assertEqual(self.call(app, "POST", "/_test/import", self.strip_candidates(export))[0], 204)
        before = self.call(app, "GET", "/dossiers/" + DOMAIN, headers=auth)[1]
        old_ret = before["fields"]["funding_total"]["candidates"][0]["retrieved_at"]
        self.assertEqual(self.call(app, "POST", "/_test/clock", {"now": "2026-03-02T09:00:00+00:00"})[0], 204)
        def new_engine(domain, budget=80, on_spend=None, cancelled=None):
            val = {"value": "Amended Shape Ltd.", "citations": [cite(ABOUT, "Amended Shape Ltd. is the registered name.")]}
            return SimpleNamespace(ok=True, spent=0, fields=dict({n: unknown() for n in NAMES}, legal_name=val))
        app.runner._run_build = new_engine
        self.assertEqual(self.call(app, "POST", "/dossiers/" + DOMAIN + "/refresh", {}, hdr(auth, "r2"))[0], 202)
        rebuilt = self.settle(app, auth)
        self.assertEqual(rebuilt["state"], "ready")
        self.check_shape(rebuilt["fields"])
        self.assertEqual(rebuilt["fields"]["legal_name"]["value"], "Amended Shape Ltd.")
        self.assertNotEqual(rebuilt["fields"]["legal_name"]["candidates"][0]["retrieved_at"], old_ret)
        self.assertEqual(rebuilt["fields"]["funding_total"]["candidates"], [])
if __name__ == "__main__":
    unittest.main()
