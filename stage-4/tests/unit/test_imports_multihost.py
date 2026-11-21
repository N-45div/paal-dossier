"""Corroboration from imported stage-3 builds with candidates from several hosts (R4U, R4.17-R4.28).

A stage-3 export carries no origin on its candidates, so each candidate's origin is the host of its
URL. A value that a second host supports from a later build is corroborated from that build."""

import unittest
from datetime import datetime

from app.corroboration import corroboration
from app.snapshot import import_state

COMPANY = "history-co.test"


def candidate(city: str, url: str, kind: str) -> dict:
    return {"value": city, "url": url, "excerpt": f"HQ is in {city}.", "provider": "nimble",
            "kind": kind, "published_at": None, "title": None, "true_from": None}


def version(url: str, city: str, kind: str) -> dict:
    return {"url": url, "true_from": None, "candidates": {"hq_city": [candidate(city, url, kind)]}}


def build(index: int, time: str, versions: list[dict]) -> dict:
    return {"index": index, "ok": True, "spent_units": 7, "time": time, "versions": versions}


OWN = f"https://{COMPANY}/about"
WIRE = "https://news-wire.test/story"
TIMES = ["2026-03-01T10:00:00+00:00", "2026-03-06T10:00:00+00:00", "2026-03-11T10:00:00+00:00"]


def stage3_state() -> dict:
    records = [
        build(0, TIMES[0], [version(OWN, "Lisbon", "own")]),
        build(1, TIMES[1], [version(OWN, "Porto", "own")]),
        build(2, TIMES[2], [version(OWN, "Porto", "own"), version(WIRE, "Porto", "news")]),
    ]
    dossier = {"id": "d_multi", "domain": COMPANY, "building": False, "last_outcome": "ready",
               "spent_units": 21, "records": records}
    return {"schema": "stage3", "dossiers": [dossier], "users": [], "tokens": [],
            "idempotency": [], "feed": [], "next_seq": 1, "batches": []}


class ImportedMultiHostCorroborationTest(unittest.TestCase):
    def setUp(self) -> None:
        state = import_state(stage3_state())
        self.records = state.dossiers_by_domain[COMPANY].records

    def test_second_host_from_the_last_build_corroborates_from_that_build(self) -> None:
        result = corroboration("hq_city", self.records)
        self.assertTrue(result.corroborated)
        self.assertEqual(result.origins, [COMPANY, "news-wire.test"])
        self.assertEqual(result.corroborated_since, datetime.fromisoformat(TIMES[2]))

    def test_one_host_at_an_earlier_build_is_not_corroboration(self) -> None:
        earlier = corroboration("hq_city", self.records[:2])
        self.assertFalse(earlier.corroborated)
        self.assertIsNone(earlier.corroborated_since)
        self.assertEqual(earlier.origins, [COMPANY])


if __name__ == "__main__":
    unittest.main()
