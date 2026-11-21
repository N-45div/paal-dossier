"""Upgrades for stage 4 (R4U): a stage-3 export imports with `investors` unknown and no history
entry; the first build with a value adds a change; batches survive an export round trip.
Builder-b, R4B/R4C/R4U."""

from __future__ import annotations

import asyncio
import copy
import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app import research
from app.candidates import Candidate
from app.research import BuildOutcome
from app.server import build_app
from app.state import STORE
from tests.service.test_dossiers import FIXTURE, ready_outcome
from tests.service.test_batches import spending_build

DOMAIN = "acme-robotics.test"


async def plain_build(domain, on_spend=None, shared=None) -> BuildOutcome:
    return ready_outcome(domain)


async def investor_build(domain, on_spend=None, shared=None) -> BuildOutcome:
    """A ready build whose only candidate is one investor name on an `own` page."""
    base = ready_outcome(domain)
    candidate = Candidate(value="Bluebird Capital", url="https://acme-robotics.test/team",
                          excerpt="Acme Robotics was backed by Bluebird Capital.",
                          provider="nimble", kind="own", published_at=None, true_from=None)
    return BuildOutcome(ok=True, spent_units=base.spent_units, fields=base.fields,
                        candidates={"investors": [candidate]})


class UpgradeS4Test(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()
        resp = await self.client.post("/_test/reset", json=FIXTURE)
        self.assertEqual(resp.status, 204)
        self.token = await self.login("ada@example.com")

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def login(self, email: str) -> str:
        resp = await self.client.post("/auth/login",
                                      json={"email": email, "password": "correct horse"})
        return (await resp.json())["token"]

    def headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Idempotency-Key": key}

    async def settle(self) -> None:
        store = self.client.server.app[STORE]
        while True:
            pending = [t for t in store.build_tasks if not t.done()]
            if not pending:
                return
            await asyncio.gather(*pending, return_exceptions=True)

    async def stage_three_export(self) -> dict:
        """An export shaped like a stage-3 service's: no `batches` key, no investors candidates."""
        with mock.patch.object(research, "run_build", plain_build):
            resp = await self.client.post("/dossiers", json={"domain": DOMAIN},
                                          headers=self.headers("up-1"))
            self.assertEqual(resp.status, 202)
            await self.settle()
        exported = await (await self.client.get("/_test/export")).json()
        state = copy.deepcopy(exported)
        state["state"].pop("batches", None)
        return state

    async def test_stage_three_export_imports_with_investors_unknown_and_no_history(self):
        state = await self.stage_three_export()
        imp = await self.client.post("/_test/import", json=state)
        self.assertEqual(imp.status, 204)
        dossier = await (await self.client.get(f"/dossiers/{DOMAIN}", headers=self.headers("up-get"))).json()
        self.assertEqual(dossier["fields"]["investors"]["status"], "unknown")
        self.assertIsNone(dossier["fields"]["investors"]["value"])
        history = await (await self.client.get(f"/dossiers/{DOMAIN}/history",
                                               headers=self.headers("up-h"))).json()
        self.assertEqual(history["fields"]["investors"], [])

    async def test_first_build_with_investors_after_import_adds_a_change(self):
        state = await self.stage_three_export()
        imp = await self.client.post("/_test/import", json=state)
        self.assertEqual(imp.status, 204)
        with mock.patch.object(research, "run_build", investor_build):
            resp = await self.client.post(f"/dossiers/{DOMAIN}/refresh", headers=self.headers("up-r"))
            self.assertEqual(resp.status, 202)
            await self.settle()
        history = await (await self.client.get(f"/dossiers/{DOMAIN}/history",
                                               headers=self.headers("up-h2"))).json()
        types = [e["type"] for e in history["fields"]["investors"]]
        self.assertEqual(types, ["change"])

    async def test_batches_survive_an_export_round_trip(self):
        with mock.patch.object(research, "run_build", spending_build):
            resp = await self.client.post("/batches", json={"domains": [DOMAIN], "budget_units": 200},
                                          headers=self.headers("up-b"))
            self.assertEqual(resp.status, 202)
            batch_id = (await resp.json())["batch_id"]
            await self.settle()
        before = await (await self.client.get(f"/batches/{batch_id}", headers=self.headers("up-g"))).json()
        exported = await (await self.client.get("/_test/export")).json()
        imp = await self.client.post("/_test/import", json=exported)
        self.assertEqual(imp.status, 204)
        after = await (await self.client.get(f"/batches/{batch_id}", headers=self.headers("up-g2"))).json()
        self.assertEqual(after, before)
