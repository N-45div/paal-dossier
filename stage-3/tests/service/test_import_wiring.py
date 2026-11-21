"""The stage-1 and stage-2 export dossiers, imported through POST /_test/import, become build
records of the store (R3C part 1, Rul-S3-8). The dossiers are the real exports in tests/fixtures."""

from __future__ import annotations

import json
import pathlib
import unittest
from datetime import date

from aiohttp.test_utils import TestClient, TestServer

from app.server import build_app
from app.snapshot import SCHEMA
from app.state import STORE

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


def dossier(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["dossier"]


class ImportWiringTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def _import(self, state: dict) -> None:
        response = await self.client.post("/_test/import",
                                          json={"track": "dossier", "format_version": 1, "state": state})
        self.assertEqual(response.status, 204, await response.text())

    async def test_stage2_export_imports_as_one_ready_build_with_page_true_from(self) -> None:
        item = dossier("export_stage2_dossier.json")
        await self._import({"schema": SCHEMA, "users": [], "tokens": [], "dossiers": [item],
                            "idempotency": []})
        (domain,) = self.client.app[STORE].state.dossiers_by_domain.values()
        (record,) = domain.records
        self.assertTrue(record.ok)
        self.assertEqual(record.spent_units, 34)
        self.assertEqual(record.versions[0].true_from, date(2026, 1, 11))

    async def test_stage1_export_imports_as_one_ready_build_without_true_from(self) -> None:
        item = dossier("export_stage1_dossier.json")
        await self._import({"users": [], "tokens": [], "dossiers": [item], "idempotency": []})
        (domain,) = self.client.app[STORE].state.dossiers_by_domain.values()
        (record,) = domain.records
        self.assertIsNone(record.versions[0].true_from)
        self.assertEqual(record.index, 1)  # records are numbered from 1 by the converters
