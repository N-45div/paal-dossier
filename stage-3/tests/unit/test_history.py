"""Build records and their derived views (stage 3): learned times, history typing, feed entries,
and `as_of` snapshots. These run on records directly, with no HTTP."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from app.candidates import Candidate
from app.feed import append_build
from app.history import feed_entries, history, snapshot_at, views
from app.records import BuildRecord, versions_of

T1 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
URL_A = "https://acme.test/about"
URL_B = "https://news.test/moves"


def cand(value, url, provider="nimble", kind="own", published_at=None) -> Candidate:
    return Candidate(value=value, url=url, excerpt=f"{value} at {url}", provider=provider,
                     kind=kind, published_at=published_at)


def ready(index: int, when: datetime, pages: dict[str, tuple[date | None, dict]]) -> BuildRecord:
    """A ready build from {url: (true_from, {field: [values...]})}."""
    versions = []
    for url, (true_from, by_field) in pages.items():
        found = {name: [cand(value, url) for value in values]
                 for name, values in by_field.items()}
        versions.extend(versions_of(found, {url: true_from}))
    return BuildRecord(index=index, time=when, ok=True, spent_units=10, versions=tuple(versions))


def failed(index: int, when: datetime) -> BuildRecord:
    return BuildRecord(index=index, time=when, ok=False, spent_units=5)


class LearnedTimesTest(unittest.TestCase):
    def test_selected_value_keeps_its_learned_time_while_unchanged(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
        ]
        selected = views(records)[1][1]["hq_city"]
        self.assertEqual(selected.learned_at, T1)

    def test_a_changed_value_learned_at_the_build_that_made_it_selected(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (None, {"hq_city": ["Porto"]})}),
        ]
        self.assertEqual(views(records)[1][1]["hq_city"].learned_at, T2)

    def test_candidate_learned_at_is_the_first_build_with_the_same_key(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (None, {"hq_city": ["Lisbon"]}),
                          URL_B: (None, {"hq_city": ["Lisbon"]})}),
        ]
        ranked = views(records)[1][1]["hq_city"].ranked
        learned = {candidate.url: when for candidate, when in ranked}
        self.assertEqual(learned[URL_A], T1)
        self.assertEqual(learned[URL_B], T2)


class HistoryTypingTest(unittest.TestCase):
    def test_first_build_gives_initial_entries_and_no_feed(self) -> None:
        records = [ready(0, T1, {URL_A: (date(2025, 1, 1), {"hq_city": ["Lisbon"]})})]
        self.assertEqual([e.type for e in history(records)["hq_city"]], ["initial"])
        self.assertEqual(feed_entries(None, views(records)[0][1], first=True), [])

    def test_same_selected_value_adds_nothing_even_if_true_from_changes(self) -> None:
        records = [
            ready(0, T1, {URL_A: (date(2025, 1, 1), {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (date(2025, 6, 1), {"hq_city": ["Lisbon"]})}),
        ]
        self.assertEqual(len(history(records)["hq_city"]), 1)

    def test_newer_true_from_for_a_new_value_is_a_change(self) -> None:
        records = [
            ready(0, T1, {URL_A: (date(2025, 1, 1), {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (date(2026, 3, 20), {"hq_city": ["Porto"]})}),
        ]
        self.assertEqual([e.type for e in history(records)["hq_city"]], ["initial", "change"])

    def test_earlier_or_equal_true_from_for_a_new_value_is_a_correction(self) -> None:
        records = [
            ready(0, T1, {URL_A: (date(2025, 6, 1), {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (date(2025, 1, 1), {"hq_city": ["Porto"]})}),
        ]
        self.assertEqual([e.type for e in history(records)["hq_city"]],
                         ["initial", "correction"])

    def test_value_disappearing_is_a_change_to_null(self) -> None:
        records = [
            ready(0, T1, {URL_A: (date(2025, 1, 1), {"ceo": ["Dana Ruiz"]})}),
            ready(1, T2, {URL_A: (None, {})}),
        ]
        entries = history(records)["ceo"]
        self.assertEqual(entries[-1].type, "change")
        self.assertIsNone(entries[-1].value)

    def test_null_true_from_makes_a_change_not_a_correction(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"ceo": ["Dana Ruiz"]})}),
            ready(1, T2, {URL_A: (date(2020, 1, 1), {"ceo": ["Lee Park"]})}),
        ]
        self.assertEqual(history(records)["ceo"][-1].type, "change")

    def test_feed_entries_are_the_non_initial_ones(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (None, {"hq_city": ["Porto"]})}),
        ]
        current = views(records)
        self.assertEqual([e.type for e in feed_entries(current[0][1], current[1][1], False)],
                         ["change"])


class FailedBuildTest(unittest.TestCase):
    def test_failed_build_adds_nothing_but_its_spending(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            failed(1, T2),
        ]
        self.assertEqual(len(history(records)["hq_city"]), 1)
        self.assertEqual(snapshot_at(records, T3)[2], 10 + 5)


class SnapshotTest(unittest.TestCase):
    def test_picks_the_latest_ready_build_at_or_before_as_of(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (None, {"hq_city": ["Porto"]})}),
        ]
        chosen, selected, spent = snapshot_at(records, datetime(2026, 3, 15, tzinfo=timezone.utc))
        self.assertEqual(chosen.time, T1)
        self.assertEqual(selected["hq_city"].value, "Lisbon")
        self.assertEqual(spent, 10)

    def test_no_ready_build_before_as_of_is_none(self) -> None:
        records = [ready(0, T2, {URL_A: (None, {"hq_city": ["Lisbon"]})})]
        self.assertIsNone(snapshot_at(records, T1))

    def test_equal_times_go_to_the_later_build(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T1, {URL_A: (None, {"hq_city": ["Porto"]})}),
        ]
        self.assertEqual(snapshot_at(records, T2)[1]["hq_city"].value, "Porto")

    def test_as_of_uses_no_later_history_for_learned_times(self) -> None:
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
        ]
        selected = snapshot_at(records, T1)[1]["hq_city"]
        self.assertEqual(selected.learned_at, T1)


class FeedSequenceTest(unittest.TestCase):
    def test_seq_continues_across_builds(self) -> None:
        feed: list = []
        next_seq = append_build(feed, 1, "a.test", [])
        records = [
            ready(0, T1, {URL_A: (None, {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (None, {"hq_city": ["Porto"]})}),
        ]
        current = views(records)
        entries = feed_entries(current[0][1], current[1][1], False)
        next_seq = append_build(feed, next_seq, "a.test", entries)
        self.assertEqual([row.seq for row in feed], [1])
        self.assertEqual(next_seq, 2)


if __name__ == "__main__":
    unittest.main()
