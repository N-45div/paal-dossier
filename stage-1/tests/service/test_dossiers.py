"""Dossier API tests (PA2): builds, idempotency, listing, export/import, reset vs builds.

Research is the placeholder in app/research.py unless a test patches run_build."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app import research
from app.research import BuildOutcome, FieldResult
from app.server import build_app

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse",
         "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse",
         "display_name": "Bob"},
    ],
}
CITE = {"url": "https://acme-robotics.test/about",
        "excerpt": "Acme Robotics, Inc. was founded in 2014.", "provider": "nimble"}


def ready_outcome(domain: str) -> BuildOutcome:
    fields = research.unknown_fields()
    fields["legal_name"] = FieldResult("Acme Robotics, Inc.", [CITE])
    fields["founded_year"] = FieldResult(2014, [CITE])
    return BuildOutcome(ok=True, spent_units=34, fields=fields)


class DossierTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()
        await self.reset()
        self.token = await self.login("ada@example.com")

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def reset(self, body: dict | None = None) -> None:
        resp = await self.client.post("/_test/reset", json=body or FIXTURE)
        self.assertEqual(resp.status, 204)

    async def login(self, email: str) -> str:
        resp = await self.client.post("/auth/login",
                                      json={"email": email, "password": "correct horse"})
        return (await resp.json())["token"]

    def headers(self, key: str | None = "key-1", token: str | None = None) -> dict:
        out = {"Authorization": f"Bearer {token or self.token}"}
        if key is not None:
            out["Idempotency-Key"] = key
        return out

    async def settle(self) -> None:
        """Let background builds finish."""
        for _ in range(20):
            await asyncio.sleep(0)

    async def create(self, domain: str, key: str = "key-1") -> dict:
        resp = await self.client.post("/dossiers", json={"domain": domain},
                                      headers=self.headers(key))
        self.assertIn(resp.status, (200, 202))
        return await resp.json()

    async def test_create_starts_a_build_and_settles_failed_with_placeholder(self) -> None:
        resp = await self.client.post("/dossiers", json={"domain": " Acme-Robotics.TEST. "},
                                      headers=self.headers())
        self.assertEqual(resp.status, 202)
        body = await resp.json()
        self.assertEqual(body["domain"], "acme-robotics.test")
        self.assertEqual(body["state"], "building")
        await self.settle()
        dossier = await (await self.client.get("/dossiers/www.acme-robotics.test",
                                               headers=self.headers(None))).json()
        self.assertEqual(dossier["state"], "failed")
        self.assertEqual(dossier["spent_units"], 0)
        self.assertIsNone(dossier["researched_at"])
        for name, field in dossier["fields"].items():
            self.assertEqual(field, {"value": None, "status": "unknown", "citations": []}, name)

    async def test_second_create_for_same_domain_starts_no_build(self) -> None:
        first = await self.create("acme-robotics.test", "k1")
        resp = await self.client.post("/dossiers", json={"domain": "acme-robotics.test"},
                                      headers=self.headers("k2"))
        self.assertEqual(resp.status, 200)
        self.assertEqual((await resp.json())["dossier_id"], first["dossier_id"])

    async def test_ready_build_sets_fields_and_researched_at(self) -> None:
        with mock.patch("app.research.run_build", side_effect=ready_outcome):
            await self.create("acme-robotics.test")
            await self.settle()
        dossier = await (await self.client.get("/dossiers/acme-robotics.test",
                                               headers=self.headers(None))).json()
        self.assertEqual(dossier["state"], "ready")
        self.assertEqual(dossier["spent_units"], 34)
        self.assertEqual(dossier["researched_at"], "2026-03-01T09:00:00+00:00")
        self.assertEqual(dossier["fields"]["founded_year"]["value"], 2014)
        self.assertEqual(dossier["fields"]["founded_year"]["status"], "known")
        self.assertEqual(dossier["fields"]["founded_year"]["citations"], [CITE])
        self.assertEqual(dossier["fields"]["ceo"]["status"], "unknown")

    async def test_invalid_domain_is_422_and_missing_is_422(self) -> None:
        for body in ({"domain": "https://acme.test/x"}, {"domain": "localhost"}, {}):
            resp = await self.client.post("/dossiers", json=body, headers=self.headers(str(body)))
            self.assertEqual(resp.status, 422)
            self.assertEqual((await resp.json())["error"]["code"], "validation_failed")

    async def test_idempotency_key_rules(self) -> None:
        resp = await self.client.post("/dossiers", json={"domain": "a.test"},
                                      headers=self.headers(key=None))
        self.assertEqual((await resp.json())["error"]["code"], "missing_idempotency_key")
        resp = await self.client.post("/dossiers", json={"domain": "a.test"},
                                      headers={"Authorization": f"Bearer {self.token}",
                                               "Idempotency-Key": "x" * 256})
        self.assertEqual(resp.status, 422)
        resp = await self.client.post("/dossiers", json={"domain": "a.test"},
                                      headers={"Authorization": "Bearer bogus",
                                               "Idempotency-Key": ""})
        self.assertEqual(resp.status, 401)

    async def test_replay_returns_original_body_and_different_body_conflicts(self) -> None:
        first = await self.client.post("/dossiers", json={"domain": "a.test"},
                                       headers=self.headers("same"))
        original = await first.json()
        self.assertEqual(first.status, 202)
        replay = await self.client.post("/dossiers", json={"domain": "a.test", "extra": 1},
                                        headers=self.headers("same"))
        self.assertEqual(replay.status, 200)
        self.assertEqual(await replay.json(), original)
        conflict = await self.client.post("/dossiers", json={"domain": "b.test"},
                                          headers=self.headers("same"))
        self.assertEqual(conflict.status, 409)
        self.assertEqual((await conflict.json())["error"]["code"], "idempotency_key_reuse")

    async def test_failed_request_key_is_reusable_and_keys_are_scoped_per_user(self) -> None:
        bad = await self.client.post("/dossiers", json={"domain": "nope"},
                                     headers=self.headers("reuse"))
        self.assertEqual(bad.status, 422)
        good = await self.client.post("/dossiers", json={"domain": "ok.test"},
                                      headers=self.headers("reuse"))
        self.assertEqual(good.status, 202)
        bob = await self.login("bob@example.com")
        other = await self.client.post("/dossiers", json={"domain": "ok.test"},
                                       headers=self.headers("reuse", token=bob))
        self.assertEqual(other.status, 200)  # bob's own key, but the dossier already exists

    async def test_same_key_on_a_different_path_is_a_new_request(self) -> None:
        await self.create("acme-robotics.test", "shared")
        resp = await self.client.post("/dossiers/acme-robotics.test/refresh",
                                      headers=self.headers("shared"))
        self.assertEqual(resp.status, 202)

    async def test_refresh_of_unknown_domain_is_404_and_refresh_while_building_starts_nothing(
            self) -> None:
        resp = await self.client.post("/dossiers/nothere.test/refresh", headers=self.headers())
        self.assertEqual(resp.status, 404)
        await self.create("acme-robotics.test", "c1")
        resp = await self.client.post("/dossiers/acme-robotics.test/refresh",
                                      headers=self.headers("r1"))
        self.assertEqual(resp.status, 202)
        self.assertEqual((await resp.json())["state"], "building")

    async def test_refresh_spends_again_and_counts_in_spent_units(self) -> None:
        with mock.patch("app.research.run_build", side_effect=ready_outcome):
            await self.create("acme-robotics.test")
            await self.settle()
            resp = await self.client.post("/dossiers/acme-robotics.test/refresh",
                                          headers=self.headers("r-again"))
            self.assertEqual(resp.status, 202)
            await self.settle()
        dossier = await (await self.client.get("/dossiers/acme-robotics.test",
                                               headers=self.headers(None))).json()
        self.assertEqual(dossier["spent_units"], 68)

    async def test_auth_precedes_key_and_body_checks(self) -> None:
        resp = await self.client.post("/dossiers", data=b"not json",
                                      headers={"Authorization": "Bearer nope"})
        self.assertEqual(resp.status, 401)

    async def test_list_filters_orders_and_paginates(self) -> None:
        for domain in ("zeta.test", "alpha.test", "mid.test"):
            await self.create(domain, f"list-{domain}")
        resp = await self.client.get("/dossiers", headers=self.headers(None))
        body = await resp.json()
        self.assertEqual([d["domain"] for d in body["dossiers"]],
                         ["alpha.test", "mid.test", "zeta.test"])
        self.assertFalse(body["has_more"])
        page = await (await self.client.get("/dossiers?limit=2&offset=0",
                                            headers=self.headers(None))).json()
        self.assertTrue(page["has_more"])
        for bad in ("limit=0", "limit=201", "limit=1e9", "limit=4.0", "limit=%2B4",
                    "offset=-1"):
            resp = await self.client.get(f"/dossiers?{bad}", headers=self.headers(None))
            self.assertEqual(resp.status, 422, bad)
        found = await (await self.client.get("/dossiers?q=ALPHA", headers=self.headers(None))).json()
        self.assertEqual([d["domain"] for d in found["dossiers"]], ["alpha.test"])

    async def test_reset_during_build_discards_its_result(self) -> None:
        gate = asyncio.Event()

        async def slow(domain: str) -> BuildOutcome:
            await gate.wait()
            return ready_outcome(domain)

        with mock.patch("app.research.run_build", side_effect=slow):
            await self.create("acme-robotics.test")
            await self.reset()
            gate.set()
            await self.settle()
        self.token = await self.login("ada@example.com")  # reset cleared the old token
        resp = await self.client.get("/dossiers", headers=self.headers(None))
        self.assertEqual((await resp.json())["dossiers"], [])

    async def test_export_import_round_trip_keeps_identities_and_replays(self) -> None:
        with mock.patch("app.research.run_build", side_effect=ready_outcome):
            created = await self.create("acme-robotics.test", "round")
            await self.settle()
        exported = await (await self.client.get("/_test/export")).json()
        self.assertEqual(exported["track"], "dossier")
        self.assertEqual(exported["format_version"], 1)

        await self.reset({"now": "2030-01-01T00:00:00+00:00", "users": []})
        imp = await self.client.post("/_test/import", json=exported)
        self.assertEqual(imp.status, 204)
        again = await self.client.get("/dossiers/acme-robotics.test", headers=self.headers(None))
        dossier = await again.json()
        self.assertEqual(dossier["dossier_id"], created["dossier_id"])
        self.assertEqual(dossier["state"], "ready")
        self.assertEqual(dossier["spent_units"], 34)
        self.assertEqual(dossier["researched_at"], "2026-03-01T09:00:00+00:00")
        replay = await self.client.post("/dossiers", json={"domain": "acme-robotics.test"},
                                        headers=self.headers("round"))
        self.assertEqual(replay.status, 200)
        self.assertEqual((await replay.json())["dossier_id"], created["dossier_id"])
        still_valid = await self.client.get("/dossiers", headers=self.headers(None))
        self.assertEqual(still_valid.status, 200)  # the pre-export token still works

    async def test_invalid_import_changes_nothing(self) -> None:
        await self.create("keep.test", "keep")
        for bad in ({"track": "other", "format_version": 1, "state": {}},
                    {"track": "dossier", "format_version": 2, "state": {}},
                    {"track": "dossier", "format_version": 1}):
            resp = await self.client.post("/_test/import", json=bad)
            self.assertEqual(resp.status, 422)
        resp = await self.client.get("/dossiers/keep.test", headers=self.headers(None))
        self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
