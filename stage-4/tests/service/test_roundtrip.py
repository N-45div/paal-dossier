"""Stage-3 export and import round trip (Upgrades, stage 3): a stage-3 import keeps history, the
feed and the builds, so as_of and history answer as the exporting service did."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app.server import build_app
from tests.service.test_history_service import outcome


class RoundTripTest(unittest.IsolatedAsyncioTestCase):
    async def _wait_idle(self, client, headers) -> None:
        for _ in range(400):
            body = await (await client.get("/dossiers/acme-robotics.test", headers=headers)).json()
            if body["state"] != "building":
                return
            await asyncio.sleep(0.01)
        self.fail("build did not finish")

    async def test_stage3_export_then_import_answers_the_same(self) -> None:
        source = TestClient(TestServer(build_app()))
        await source.start_server()
        signup = await source.post("/auth/signup", json={
            "email": "rt@example.com", "password": "correct horse", "display_name": "Ada"})
        headers = {"Authorization": f"Bearer {(await signup.json())['token']}"}
        with mock.patch("app.research.run_build", side_effect=_async_outcome("Lisbon")):
            await source.post("/dossiers", json={"domain": "acme-robotics.test"},
                              headers={**headers, "Idempotency-Key": "rt-1"})
            await self._wait_idle(source, headers)
        with mock.patch("app.research.run_build", side_effect=_async_outcome("Porto")):
            await source.post("/dossiers/acme-robotics.test/refresh",
                              headers={**headers, "Idempotency-Key": "rt-2"})
            await self._wait_idle(source, headers)
        export = await (await source.get("/_test/export")).json()
        before = {
            "dossier": await (await source.get("/dossiers/acme-robotics.test",
                                               headers=headers)).json(),
            "history": await (await source.get("/dossiers/acme-robotics.test/history",
                                               headers=headers)).json(),
            "changes": await (await source.get("/changes", headers=headers)).json(),
        }
        await source.close()

        target = TestClient(TestServer(build_app()))
        await target.start_server()
        imported = await target.post("/_test/import", json={
            "track": "dossier", "format_version": 1, "state": export["state"]})
        self.assertEqual(imported.status, 204)
        after = {
            "dossier": await (await target.get("/dossiers/acme-robotics.test",
                                               headers=headers)).json(),
            "history": await (await target.get("/dossiers/acme-robotics.test/history",
                                               headers=headers)).json(),
            "changes": await (await target.get("/changes", headers=headers)).json(),
        }
        self.assertEqual(after, before)
        await target.close()


def _async_outcome(city: str):
    async def run(domain, on_spend=None):
        return outcome(city)
    return run


if __name__ == "__main__":
    unittest.main()
