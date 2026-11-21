"""Stage 3 over HTTP: two builds with different outcomes, then the feed, the history, as_of."""

from __future__ import annotations

import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app import research
from app.candidates import Candidate
from app.outcome import BuildOutcome, FieldResult
from app.server import build_app
from app.support import FIELDS

URL = "https://acme-robotics.test/about"


def outcome(city: str, true_from_url: str | None = None) -> BuildOutcome:
    fields = research.unknown_fields()
    cites = [{"url": URL, "excerpt": f"HQ is in {city}.", "provider": "nimble"}]
    fields["hq_city"] = FieldResult(city, cites)
    candidates = {name: [] for name in FIELDS}
    candidates["hq_city"] = [Candidate(city, URL, f"HQ is in {city}.", "nimble", "own", None)]
    return BuildOutcome(ok=True, spent_units=7, fields=fields, candidates=candidates)


class HistoryServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()
        signup = await self.client.post("/auth/signup", json={
            "email": "hist@example.com", "password": "correct horse", "display_name": "Ada"})
        self.headers = {"Authorization": f"Bearer {(await signup.json())['token']}"}

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def _research(self, key: str, run) -> None:
        with mock.patch("app.research.run_build", side_effect=run):
            response = await self.client.post(
                "/dossiers", json={"domain": "acme-robotics.test"},
                headers={**self.headers, "Idempotency-Key": key})
            self.assertIn(response.status, (200, 202))
            for _ in range(200):
                body = await (await self.client.get("/dossiers/acme-robotics.test",
                                                   headers=self.headers)).json()
                if body["state"] != "building":
                    return
                import asyncio
                await asyncio.sleep(0.01)
            self.fail("build did not finish")

    async def test_change_appears_once_in_feed_and_history(self) -> None:
        async def first(domain, on_spend=None):
            return outcome("Lisbon")

        async def second(domain, on_spend=None):
            return outcome("Porto")

        await self._research("k-first", first)
        await self.client.post("/dossiers/acme-robotics.test/refresh",
                               headers={**self.headers, "Idempotency-Key": "k-refresh"})
        with mock.patch("app.research.run_build", side_effect=second):
            await self.client.post("/dossiers/acme-robotics.test/refresh",
                                   headers={**self.headers, "Idempotency-Key": "k-refresh-2"})
            import asyncio
            for _ in range(200):
                body = await (await self.client.get("/dossiers/acme-robotics.test",
                                                   headers=self.headers)).json()
                if body["state"] != "building":
                    break
                await asyncio.sleep(0.01)
        feed = await (await self.client.get("/changes", headers=self.headers)).json()
        changes = [c for c in feed["changes"] if c["field"] == "hq_city"]
        self.assertEqual([(c["from"], c["to"], c["type"]) for c in changes],
                         [("Lisbon", "Porto", "change")])
        history = await (await self.client.get("/dossiers/acme-robotics.test/history",
                                               headers=self.headers)).json()
        self.assertEqual([e["type"] for e in history["fields"]["hq_city"]],
                         ["initial", "change"])
        self.assertEqual(set(history["fields"]), {*FIELDS, "executives", "investors"})  # eight fields (stage 4)

    async def test_as_of_before_first_build_is_not_found_and_invalid_is_422(self) -> None:
        async def first(domain, on_spend=None):
            return outcome("Lisbon")

        await self._research("k-first-2", first)
        bad = await self.client.get("/dossiers/acme-robotics.test?as_of=yesterday",
                                    headers=self.headers)
        self.assertEqual(bad.status, 422)
        early = await self.client.get(
            "/dossiers/acme-robotics.test?as_of=2000-01-01T00:00:00%2B00:00",
            headers=self.headers)
        self.assertEqual(early.status, 404)

    async def test_changes_pages_with_since_and_limit(self) -> None:
        response = await self.client.get("/changes?since=0&limit=1", headers=self.headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"changes": [], "has_more": False})
        self.assertEqual((await self.client.get("/changes?limit=0", headers=self.headers)).status,
                         422)


if __name__ == "__main__":
    unittest.main()
