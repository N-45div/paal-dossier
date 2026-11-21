"""Batch API tests (R4C, R4.42-R4.56): validation, shape, shared budget, ownership, states.

Research is replaced by a fake build that spends through the batch's shared budget, so the
budget rule is exercised without a provider."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app import research
from app.research import BuildOutcome, FieldResult
from app.server import build_app
from app.state import STORE
from tests.service.test_dossiers import FIXTURE, ready_outcome

CALL_UNITS = 25


async def spending_build(domain, on_spend=None, shared=None):
    """A build that makes calls of CALL_UNITS while the shared budget allows, then completes."""
    spent = 0
    calls = 0
    for _ in range(4):
        if shared is not None and not shared.reserve(CALL_UNITS):
            break
        if on_spend is not None:
            on_spend(CALL_UNITS)
        spent += CALL_UNITS
        calls += 1
        await asyncio.sleep(0)
    fields = research.unknown_fields()
    if calls:
        fields["legal_name"] = FieldResult("Acme Robotics, Inc.", [])
    return BuildOutcome(ok=True, spent_units=spent, fields=fields)


class BatchTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()
        resp = await self.client.post("/_test/reset", json=FIXTURE)
        self.assertEqual(resp.status, 204)
        self.token = await self.login("ada@example.com")
        self.counter = 0

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def login(self, email: str) -> str:
        resp = await self.client.post("/auth/login",
                                      json={"email": email, "password": "correct horse"})
        return (await resp.json())["token"]

    def headers(self, token: str | None = None, key: str | None = None) -> dict:
        self.counter += 1
        return {"Authorization": f"Bearer {token or self.token}",
                "Idempotency-Key": key or f"batch-key-{self.counter}"}

    async def post_batch(self, body, token=None, key=None):
        return await self.client.post("/batches", json=body, headers=self.headers(token, key))

    async def settle(self) -> None:
        """Wait until every build task of the service has finished."""
        store = self.client.server.app[STORE]
        while True:
            pending = [t for t in store.build_tasks if not t.done()]
            if not pending:
                return
            await asyncio.gather(*pending, return_exceptions=True)

    async def test_missing_domains_is_422(self):
        resp = await self.post_batch({"budget_units": 200})
        self.assertEqual(resp.status, 422)

    async def test_empty_domains_is_422(self):
        resp = await self.post_batch({"domains": [], "budget_units": 200})
        self.assertEqual(resp.status, 422)

    async def test_more_than_fifty_domains_is_422(self):
        domains = [f"co{i}.test" for i in range(51)]
        resp = await self.post_batch({"domains": domains, "budget_units": 200})
        self.assertEqual(resp.status, 422)

    async def test_invalid_entry_after_normalisation_is_422(self):
        resp = await self.post_batch({"domains": ["not a domain!"], "budget_units": 200})
        self.assertEqual(resp.status, 422)

    async def test_duplicate_after_normalisation_is_422(self):
        resp = await self.post_batch({"domains": ["Acme-Robotics.test", "acme-robotics.test"],
                                      "budget_units": 200})
        self.assertEqual(resp.status, 422)

    async def test_budget_of_wrong_json_type_is_422_whatever_its_type(self):
        for value in ("200", True, 1.5, None):
            resp = await self.post_batch({"domains": ["acme-robotics.test"], "budget_units": value})
            self.assertEqual(resp.status, 422, value)

    async def test_budget_out_of_range_is_422(self):
        for value in (0, 100001):
            resp = await self.post_batch({"domains": ["acme-robotics.test"], "budget_units": value})
            self.assertEqual(resp.status, 422, value)

    async def test_missing_key_is_400(self):
        resp = await self.client.post("/batches", json={"domains": ["acme-robotics.test"],
                                                        "budget_units": 200},
                                      headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(resp.status, 400)

    async def test_accepted_batch_has_its_shape_and_starts_builds(self):
        """R4.45: POST /batches takes domains and budget_units under an Idempotency-Key."""
        with mock.patch.object(research, "run_build", spending_build):
            resp = await self.post_batch({"domains": ["Acme-Robotics.test", "brightgear.test"],
                                          "budget_units": 200})
            body = await resp.json()
            await self.settle()
        self.assertEqual(resp.status, 202)
        self.assertTrue(body["batch_id"].startswith("b_"))
        self.assertEqual(body["budget_units"], 200)
        self.assertEqual([d["domain"] for d in body["dossiers"]],
                         ["acme-robotics.test", "brightgear.test"])
        self.assertEqual(body["dossiers"][0]["state"], "building")

    async def test_existing_dossier_is_not_researched_and_costs_nothing(self):
        with mock.patch.object(research, "run_build", spending_build):
            resp = await self.client.post("/dossiers", json={"domain": "acme-robotics.test"},
                                          headers=self.headers())
            self.assertEqual(resp.status, 202)
            await self.settle()
            resp = await self.post_batch({"domains": ["acme-robotics.test"], "budget_units": 200})
            body = await resp.json()
            await self.settle()
        self.assertEqual(body["spent_units"], 0)
        self.assertEqual(body["dossiers"][0]["state"], "ready")

    async def test_shared_budget_is_never_exceeded(self):
        with mock.patch.object(research, "run_build", spending_build):
            resp = await self.post_batch({"domains": ["acme-robotics.test", "brightgear.test",
                                                       "ferncliff-foods.test"],
                                          "budget_units": 60})
            await self.settle()
            batch_id = (await resp.json())["batch_id"]
            got = await (await self.client.get(f"/batches/{batch_id}", headers=self.headers())).json()
        self.assertLessEqual(got["spent_units"], 60)
        self.assertEqual(got["state"], "done")

    async def test_another_users_batch_and_unknown_batch_are_404(self):
        with mock.patch.object(research, "run_build", spending_build):
            resp = await self.post_batch({"domains": ["acme-robotics.test"], "budget_units": 200})
            batch_id = (await resp.json())["batch_id"]
            await self.settle()
        bob = await self.login("bob@example.com")
        resp = await self.client.get(f"/batches/{batch_id}", headers=self.headers(token=bob))
        self.assertEqual(resp.status, 404)
        resp = await self.client.get("/batches/b_missing", headers=self.headers())
        self.assertEqual(resp.status, 404)

    async def test_get_reports_running_then_done(self):
        with mock.patch.object(research, "run_build", spending_build):
            resp = await self.post_batch({"domains": ["acme-robotics.test"], "budget_units": 200})
            batch_id = (await resp.json())["batch_id"]
            running = await (await self.client.get(f"/batches/{batch_id}", headers=self.headers())).json()
            await self.settle()
            done = await (await self.client.get(f"/batches/{batch_id}", headers=self.headers())).json()
        self.assertEqual(running["state"], "running")
        self.assertEqual(done["state"], "done")
