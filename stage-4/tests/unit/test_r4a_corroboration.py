"""R4A corroboration (stage 4, R4.19-R4.28): origins, corroborated and corroborated_since as pure
functions of the build records. No HTTP."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from app.candidates import Candidate
from app.corroboration import corroboration, origin_of
from app.records import BuildRecord, versions_of

T = [datetime(2026, 3, d, 9, tzinfo=timezone.utc) for d in (1, 2, 3, 4, 5)]
ACME = "https://acme-robotics.test/about"
REG = "https://registry.test/acme"
WIRE = "https://wire.test/story"


def build(index: int, when: datetime, items: list[tuple[str, str, str, str | None, str | None]]) -> BuildRecord:
    """A ready build. Each item is (field, value, url, origin, title)."""
    found: dict[str, list[Candidate]] = {}
    pages: dict[str, date | None] = {}
    origins: dict[str, str] = {}
    for field, value, url, origin, title in items:
        found.setdefault(field, []).append(Candidate(
            value=value, url=url, excerpt=value, provider="nimble", kind="own", title=title,
            origin=origin))
        pages.setdefault(url, date(2026, 1, 1))
        if origin is not None:
            origins[url] = origin
    return BuildRecord(index=index, time=when, ok=True, spent_units=1,
                       versions=versions_of(found, pages, origins))


class SixFieldCorroborationTest(unittest.TestCase):

    def test_unknown_field_has_no_origins_and_no_corroboration(self):
        result = corroboration("ceo", [build(0, T[0], [])])
        self.assertEqual((result.origins, result.corroborated, result.corroborated_since), ([], False, None))

    def test_two_origins_in_the_current_build_corroborate(self):
        records = [
            build(0, T[0], [("ceo", "Dana Ruiz", ACME, "acme-robotics.test", None)]),
            build(1, T[1], [("ceo", "Dana Ruiz", ACME, "acme-robotics.test", None),
                            ("ceo", "Dana Ruiz", REG, "registry.test", None)]),
        ]
        result = corroboration("ceo", records)
        self.assertEqual(result.origins, ["acme-robotics.test", "registry.test"])
        self.assertTrue(result.corroborated)
        self.assertEqual(result.corroborated_since, T[1])

    def test_since_counts_standing_origins_even_when_the_current_build_has_one(self):
        records = [
            build(0, T[0], [("ceo", "Dana Ruiz", ACME, "acme-robotics.test", None)]),
            build(1, T[1], [("ceo", "Dana Ruiz", REG, "registry.test", None)]),
        ]
        result = corroboration("ceo", records)
        self.assertEqual(result.origins, ["registry.test"])
        self.assertFalse(result.corroborated)
        self.assertEqual(result.corroborated_since, T[1])

    def test_one_origin_is_not_corroborated(self):
        records = [build(0, T[0], [("ceo", "Dana Ruiz", ACME, "acme-robotics.test", None)])]
        result = corroboration("ceo", records)
        self.assertEqual((result.origins, result.corroborated, result.corroborated_since),
                         (["acme-robotics.test"], False, None))

    def test_a_new_selected_value_starts_with_no_standing_origins(self):
        # Dana is selected, then Lee, then Dana again: only the builds since Dana's return count.
        records = [
            build(0, T[0], [("ceo", "Dana Ruiz", ACME, "acme-robotics.test", None)]),
            build(1, T[1], [("ceo", "Lee Park", WIRE, "wire.test", None)]),
            build(2, T[2], [("ceo", "Dana Ruiz", REG, "registry.test", None)]),
        ]
        result = corroboration("ceo", records)
        self.assertEqual(result.origins, ["registry.test"])
        self.assertFalse(result.corroborated)
        self.assertIsNone(result.corroborated_since)
        later = records + [build(3, T[3], [("ceo", "Dana Ruiz", ACME, "acme-robotics.test", None)])]
        result = corroboration("ceo", later)
        self.assertEqual(result.corroborated_since, T[3])

    def test_origins_of_a_later_build_count_even_if_not_gathered_again(self):
        records = [
            build(0, T[0], [("ceo", "Dana Ruiz", ACME, "acme-robotics.test", None)]),
            build(1, T[1], [("ceo", "Dana Ruiz", REG, "registry.test", None)]),
            build(2, T[2], [("ceo", "Dana Ruiz", WIRE, "wire.test", None)]),
        ]
        result = corroboration("ceo", records)
        self.assertEqual(result.origins, ["wire.test"])  # the current candidate set only
        self.assertFalse(result.corroborated)
        self.assertEqual(result.corroborated_since, T[1])  # standing: acme and registry by build 1


class MembersCorroborationTest(unittest.TestCase):

    def test_executives_need_two_origins_for_every_member(self):
        records = [
            build(0, T[0], [("executives", "Petra Garrow", ACME, "acme-robotics.test", "cfo"),
                            ("executives", "Mirela Ellery", ACME, "acme-robotics.test", "coo")]),
            build(1, T[1], [("executives", "Petra Garrow", REG, "registry.test", "cfo"),
                            ("executives", "Mirela Ellery", ACME, "acme-robotics.test", "coo")]),
        ]
        result = corroboration("executives", records)
        self.assertEqual(result.origins, ["acme-robotics.test", "registry.test"])
        self.assertFalse(result.corroborated)  # each member has one origin in the current set
        self.assertIsNone(result.corroborated_since)  # the coo has one standing origin

    def test_executives_corroborated_when_every_member_has_two(self):
        records = [
            build(0, T[0], [("executives", "Petra Garrow", ACME, "acme-robotics.test", "cfo"),
                            ("executives", "Mirela Ellery", ACME, "acme-robotics.test", "coo")]),
            build(1, T[1], [("executives", "Petra Garrow", ACME, "acme-robotics.test", "cfo"),
                            ("executives", "Petra Garrow", REG, "registry.test", "cfo"),
                            ("executives", "Mirela Ellery", ACME, "acme-robotics.test", "coo"),
                            ("executives", "Mirela Ellery", REG, "registry.test", "coo")]),
        ]
        result = corroboration("executives", records)
        self.assertTrue(result.corroborated)
        self.assertEqual(result.corroborated_since, T[1])

    def test_a_member_arriving_later_has_its_own_standing_origins(self):
        records = [
            build(0, T[0], [("executives", "Petra Garrow", ACME, "acme-robotics.test", "cfo")]),
            build(1, T[1], [("executives", "Petra Garrow", REG, "registry.test", "cfo"),
                            ("executives", "Mirela Ellery", REG, "registry.test", "coo")]),
            build(2, T[2], [("executives", "Petra Garrow", WIRE, "wire.test", "cfo"),
                            ("executives", "Petra Garrow", ACME, "acme-robotics.test", "cfo"),
                            ("executives", "Mirela Ellery", WIRE, "wire.test", "coo"),
                            ("executives", "Mirela Ellery", REG, "registry.test", "coo")]),
        ]
        result = corroboration("executives", records)
        self.assertTrue(result.corroborated)
        # Petra has acme and registry by build 1; the coo has registry (build 1) and wire by build 2.
        self.assertEqual(result.corroborated_since, T[2])


class ImportedOriginTest(unittest.TestCase):

    def test_a_candidate_without_an_origin_takes_its_urls_host(self):
        candidate = Candidate(value="Dana Ruiz", url="https://Acme-Robotics.test/x", excerpt="e",
                              provider="nimble", origin=None)
        self.assertEqual(origin_of(candidate), "acme-robotics.test")
