"""Durable state (stage 3, R3D): the service answers after a restart as it did before the stop."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app import research
from app.candidates import Candidate
from app.outcome import BuildOutcome, FieldResult
from app.server import build_app
from app.support import FIELDS

URL = "https://acme-robotics.test/about"


def ready(city: str) -> BuildOutcome:
    fields = research.unknown_fields()
    fields["hq_city"] = FieldResult(city, [{"url": URL, "excerpt": f"HQ is in {city}.",
                                            "provider": "nimble"}])
    candidates = {name: [] for name in FIELDS}
    candidates["hq_city"] = [Candidate(city, URL, f"HQ is in {city}.", "nimble", "own", None)]
    return BuildOutcome(ok=True, spent_units=7, fields=fields, candidates=candidates)


def _builder(city: str):
    async def run(domain, on_spend=None):
        return ready(city)
    return run


class DurabilityTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)

    async def asyncTearDown(self) -> None:
        self.tmp.cleanup()

    async def _start(self) -> TestClient:
        client = TestClient(TestServer(build_app(data_dir=self.data)))
        await client.start_server()
        return client

    async def _wait_idle(self, client: TestClient, domain: str, headers: dict) -> dict:
        for _ in range(400):
            body = await (await client.get(f"/dossiers/{domain}", headers=headers)).json()
            if body["state"] != "building":
                return body
            await asyncio.sleep(0.01)
        self.fail("build did not finish")

    async def test_answers_after_restart_match_answers_before(self) -> None:
        client = await self._start()
        signup = await client.post("/auth/signup", json={
            "email": "dur@example.com", "password": "correct horse", "display_name": "Ada"})
        token = (await signup.json())["token"]
        headers = {"Authorization": f"Bearer {token}"}
        with mock.patch("app.research.run_build", side_effect=_builder("Lisbon")):
            await client.post("/dossiers", json={"domain": "acme-robotics.test"},
                              headers={**headers, "Idempotency-Key": "dur-1"})
            before = await self._wait_idle(client, "acme-robotics.test", headers)
        before_feed = await (await client.get("/changes", headers=headers)).json()
        before_history = await (await client.get("/dossiers/acme-robotics.test/history",
                                                 headers=headers)).json()
        await client.close()

        restarted = await self._start()
        after = await self._wait_idle(restarted, "acme-robotics.test", headers)
        self.assertEqual(after, before)
        self.assertEqual(await (await restarted.get("/changes", headers=headers)).json(),
                         before_feed)
        self.assertEqual(await (await restarted.get("/dossiers/acme-robotics.test/history",
                                                    headers=headers)).json(), before_history)
        # The same key and body is still a replay after the restart (§7).
        replay = await restarted.post("/dossiers", json={"domain": "acme-robotics.test"},
                                      headers={**headers, "Idempotency-Key": "dur-1"})
        self.assertEqual(replay.status, 200)
        await restarted.close()

    async def test_a_build_running_at_the_stop_becomes_failed_with_no_entries(self) -> None:
        client = await self._start()
        signup = await client.post("/auth/signup", json={
            "email": "stop@example.com", "password": "correct horse", "display_name": "Ada"})
        headers = {"Authorization": f"Bearer {(await signup.json())['token']}"}
        never = asyncio.Event()

        async def hangs(domain, on_spend=None):
            await never.wait()
            return ready("Porto")

        with mock.patch("app.research.run_build", side_effect=hangs):
            response = await client.post("/dossiers", json={"domain": "acme-robotics.test"},
                                         headers={**headers, "Idempotency-Key": "stop-1"})
            self.assertEqual(response.status, 202)
        await client.close()  # the abrupt stop: the build never finishes

        restarted = await self._start()
        body = await (await restarted.get("/dossiers/acme-robotics.test", headers=headers)).json()
        self.assertEqual(body["state"], "failed")
        self.assertEqual(await (await restarted.get("/changes", headers=headers)).json(),
                         {"changes": [], "has_more": False})
        await restarted.close()

    async def test_seq_continues_after_restart(self) -> None:
        client = await self._start()
        signup = await client.post("/auth/signup", json={
            "email": "seq@example.com", "password": "correct horse", "display_name": "Ada"})
        headers = {"Authorization": f"Bearer {(await signup.json())['token']}"}
        with mock.patch("app.research.run_build", side_effect=_builder("Lisbon")):
            await client.post("/dossiers", json={"domain": "acme-robotics.test"},
                              headers={**headers, "Idempotency-Key": "seq-1"})
            await self._wait_idle(client, "acme-robotics.test", headers)
        with mock.patch("app.research.run_build", side_effect=_builder("Porto")):
            await client.post("/dossiers/acme-robotics.test/refresh",
                              headers={**headers, "Idempotency-Key": "seq-2"})
            await self._wait_idle(client, "acme-robotics.test", headers)
        await client.close()

        restarted = await self._start()
        with mock.patch("app.research.run_build", side_effect=_builder("Lisbon")):
            await restarted.post("/dossiers/acme-robotics.test/refresh",
                                 headers={**headers, "Idempotency-Key": "seq-3"})
            await self._wait_idle(restarted, "acme-robotics.test", headers)
        feed = (await (await restarted.get("/changes", headers=headers)).json())["changes"]
        self.assertEqual([row["seq"] for row in feed], [1, 2])
        await restarted.close()


if __name__ == "__main__":
    unittest.main()
