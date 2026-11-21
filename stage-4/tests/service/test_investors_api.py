"""The `investors` field in the service's responses (stage 4, R4B): its place among the fields,
its shape and candidates, and the values answer at a date. Builder-b, R4B."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from app import research
from app.candidates import Candidate
from app.outcome import BuildOutcome
from app.server import build_app
from app.state import STORE
from tests.service.test_dossiers import FIXTURE, ready_outcome

DOMAIN = "acme-robotics.test"
BLUEBIRD_URL = "https://acme-robotics.test/team"
NORTHWIND_URLS = ("https://dealwire.test/northwind", "https://registry.test/northwind")


def investor(value: str, url: str, kind: str, published: str | None) -> Candidate:
    return Candidate(value=value, url=url, excerpt=f"{value} led the round.", provider="nimble",
                     kind=kind, published_at=published, true_from=None)


async def investor_build(domain, on_spend=None, shared=None) -> BuildOutcome:
    base = ready_outcome(domain)
    candidates = {
        "investors": [
            investor("Northwind Ventures", NORTHWIND_URLS[0], "news", "2024-05-02T00:00:00+00:00"),
            investor("Northwind Ventures", NORTHWIND_URLS[1], "news", "2024-05-02T00:00:00+00:00"),
            investor("Bluebird Capital", BLUEBIRD_URL, "own", "2024-05-02T00:00:00+00:00"),
            investor("Lone Fund", "https://dealwire.test/lone", "news", None),
        ],
    }
    return BuildOutcome(ok=True, spent_units=base.spent_units, fields=base.fields,
                        candidates=candidates)


class InvestorsApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()
        await self.client.post("/_test/reset", json=FIXTURE)
        tok = (await (await self.client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "correct horse"})).json())["token"]
        self.headers = {"Authorization": f"Bearer {tok}"}
        with mock.patch.object(research, "run_build", investor_build):
            resp = await self.client.post("/dossiers", json={"domain": DOMAIN},
                                          headers={**self.headers, "Idempotency-Key": "inv-1"})
            self.assertEqual(resp.status, 202)
            await self._settle()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def _settle(self) -> None:
        store = self.client.server.app[STORE]
        while True:
            pending = [t for t in store.build_tasks if not t.done()]
            if not pending:
                return
            await asyncio.gather(*pending, return_exceptions=True)

    async def dossier(self) -> dict:
        return await (await self.client.get(f"/dossiers/{DOMAIN}", headers=self.headers)).json()

    async def test_r4_29_investors_is_the_eighth_field_after_executives(self) -> None:
        """R4.29: investors is the eighth field, after executives."""
        fields = list((await self.dossier())["fields"])
        self.assertEqual(len(fields), 8)
        self.assertEqual(fields[-2:], ["executives", "investors"])

    async def test_r4_34_investors_carries_the_value_status_and_corroboration_keys(self) -> None:
        """R4.34: investors carries value, status, citations, candidates, origins, corroborated and corroborated_since."""
        inv = (await self.dossier())["fields"]["investors"]
        self.assertEqual(inv["value"], ["Bluebird Capital", "Northwind Ventures"])
        self.assertEqual(inv["status"], "known")
        self.assertIn("citations", inv)
        self.assertEqual(inv["origins"], sorted({"acme-robotics.test", "dealwire.test", "registry.test"}))
        self.assertIs(inv["corroborated"], False)  # Bluebird Capital has one origin
        self.assertIn("corroborated_since", inv)

    async def test_r4_35_selected_is_true_on_members_and_false_on_the_others(self) -> None:
        """R4.35: selected is true on members and false on the others."""
        candidates = (await self.dossier())["fields"]["investors"]["candidates"]
        by_value = {c["value"]: c["selected"] for c in candidates}
        self.assertTrue(by_value["Northwind Ventures"])
        self.assertTrue(by_value["Bluebird Capital"])
        self.assertFalse(by_value["Lone Fund"])

    async def test_r4_36_candidates_lists_every_candidate(self) -> None:
        """R4.36: candidates lists every candidate."""
        candidates = (await self.dossier())["fields"]["investors"]["candidates"]
        self.assertEqual(len(candidates), 4)
        self.assertEqual(sorted(c["value"] for c in candidates),
                         sorted(["Northwind Ventures", "Northwind Ventures", "Bluebird Capital", "Lone Fund"]))

    async def test_r4_37_citations_follow_members_in_value_order(self) -> None:
        """R4.37: citations follow the members in value order, each with its candidates."""
        citations = (await self.dossier())["fields"]["investors"]["citations"]
        urls = [c["url"] for c in citations]
        # Bluebird Capital (first in value order) then Northwind Ventures, each with its candidates.
        self.assertEqual(urls[0], BLUEBIRD_URL)
        self.assertEqual(sorted(urls[1:]), sorted(NORTHWIND_URLS))
        self.assertNotIn("https://dealwire.test/lone", urls)

    async def test_r4_39_values_decides_membership_at_true_at(self) -> None:
        """R4.39: GET /dossiers/{domain}/values decides membership at true_at."""
        url = f"/dossiers/{DOMAIN}/values?true_at=2024-05-03"
        later = await (await self.client.get(url, headers=self.headers)).json()
        self.assertEqual(later["fields"]["investors"]["value"],
                         ["Bluebird Capital", "Northwind Ventures"])
        earlier = await (await self.client.get(
            f"/dossiers/{DOMAIN}/values?true_at=2024-05-01", headers=self.headers)).json()
        self.assertIsNone(earlier["fields"]["investors"]["value"])


if __name__ == "__main__":
    unittest.main()
