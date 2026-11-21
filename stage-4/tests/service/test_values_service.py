"""Stage 3 over HTTP: GET /dossiers/{domain}/values?true_at= (R3.44-R3.53)."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from datetime import date

from app import research
from app.candidates import Candidate
from app.outcome import BuildOutcome, FieldResult
from app.server import build_app
from app.support import FIELDS

URL = "https://acme-robotics.test/about"


def outcome(city: str) -> BuildOutcome:
    fields = research.unknown_fields()
    fields["hq_city"] = FieldResult(city, [{"url": URL, "excerpt": f"HQ is in {city}.",
                                            "provider": "nimble"}])
    candidates = {name: [] for name in FIELDS}
    candidates["hq_city"] = [Candidate(city, URL, f"HQ is in {city}.", "nimble", "own", None)]
    return BuildOutcome(ok=True, spent_units=7, fields=fields, candidates=candidates,
                        pages={URL: date(2025, 1, 1)})


class ValuesServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()
        signup = await self.client.post("/auth/signup", json={
            "email": "values@example.com", "password": "correct horse", "display_name": "Ada"})
        self.headers = {"Authorization": f"Bearer {(await signup.json())['token']}"}

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def _research(self, key: str, city: str) -> None:
        async def run(domain, on_spend=None):
            return outcome(city)

        with mock.patch("app.research.run_build", side_effect=run):
            response = await self.client.post("/dossiers", json={"domain": "acme-robotics.test"},
                                              headers={**self.headers, "Idempotency-Key": key})
            self.assertIn(response.status, (200, 202))
            for _ in range(200):
                body = await (await self.client.get("/dossiers/acme-robotics.test",
                                                   headers=self.headers)).json()
                if body["state"] != "building":
                    return
                await asyncio.sleep(0.01)
            self.fail("build did not finish")

    async def test_values_needs_a_valid_true_at_and_a_token(self) -> None:
        response = await self.client.get("/dossiers/acme-robotics.test/values?true_at=2026-13-40",
                                         headers=self.headers)
        self.assertEqual(response.status, 422)
        response = await self.client.get("/dossiers/acme-robotics.test/values?true_at=2026-01-01")
        self.assertEqual(response.status, 401)

    async def test_no_dossier_or_no_ready_build_is_404(self) -> None:
        response = await self.client.get("/dossiers/nobody.test/values?true_at=2026-01-01",
                                         headers=self.headers)
        self.assertEqual(response.status, 404)

    async def test_values_answers_for_every_field_with_seven_names(self) -> None:
        await self._research("values-1", "Lisbon")
        body = await (await self.client.get(
            "/dossiers/acme-robotics.test/values?true_at=2026-01-01"
            "&as_of=2030-01-01T00:00:00Z", headers=self.headers)).json()
        self.assertEqual(set(body["fields"]), {*FIELDS, "executives"})
        self.assertEqual(body["fields"]["hq_city"]["value"], "Lisbon")
        self.assertEqual(body["fields"]["hq_city"]["true_from"], "2025-01-01")


if __name__ == "__main__":
    unittest.main()
