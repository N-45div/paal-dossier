"""GET /changes: every feed entry's `learned_at` is the time of the build that added it, for every
change and correction, including a value that disappears (whose selected learned_at is null).
History entries keep the selected value's own learned_at (R3.56). Runs on records, no HTTP."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from app.feed import FeedRow, append_build
from app.history import feed_entries, history, views
from tests.unit.test_history import URL_A, URL_B, ready

DOMAIN = "acme.test"
T1 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)


def _replay(records) -> tuple[list[FeedRow], dict]:
    """Replay the records through the feed as apply_outcome does, and return the feed and the
    history of the same records."""
    feed: list[FeedRow] = []
    next_seq = 1
    previous = None
    for index, record in enumerate(records):
        if not record.ok:
            continue
        current = views(records[:index + 1])[-1][1]
        entries = feed_entries(previous, current, first=previous is None, built_at=record.time)
        next_seq = append_build(feed, next_seq, DOMAIN, entries)
        previous = current
    return feed, history(records)


class FeedLearnedAtTest(unittest.TestCase):

    def test_every_feed_entry_carries_the_adding_builds_time(self):
        records = [
            ready(0, T1, {URL_A: (date(2026, 1, 10), {"ceo": ["Dana Ruiz"],
                                                      "hq_city": ["Lisbon"]})}),
            # ceo changes and hq_city disappears: both entries are added by the second build.
            ready(1, T2, {URL_A: (date(2026, 3, 20), {"ceo": ["Lee Park"], "hq_city": []})}),
            # ceo changes back on another page: the third build adds its own entry.
            ready(2, T3, {URL_B: (date(2026, 2, 1), {"ceo": ["Dana Ruiz"]})}),
        ]
        feed, _ = _replay(records)
        self.assertEqual([(r.field, r.type) for r in feed],
                         [("hq_city", "change"), ("ceo", "change"), ("ceo", "correction")])
        self.assertEqual([r.learned_at for r in feed], [T2, T2, T3])
        self.assertEqual([r.seq for r in feed], [1, 2, 3])

    def test_history_keeps_the_selected_values_learned_at(self):
        records = [
            ready(0, T1, {URL_A: (date(2026, 1, 10), {"ceo": ["Dana Ruiz"]})}),
            ready(1, T2, {URL_A: (date(2026, 3, 20), {"ceo": ["Lee Park"]})}),
        ]
        _, hist = _replay(records)
        self.assertEqual([e.learned_at for e in hist["ceo"]], [T1, T2])

    def test_a_same_value_refresh_adds_no_feed_entry_and_no_learned_at_moves(self):
        records = [
            ready(0, T1, {URL_A: (date(2026, 1, 10), {"ceo": ["Dana Ruiz"]})}),
            ready(1, T2, {URL_A: (date(2026, 3, 20), {"ceo": ["Lee Park"]})}),
            ready(2, T3, {URL_A: (date(2026, 3, 20), {"ceo": ["Lee Park"]})}),
        ]
        feed, _ = _replay(records)
        self.assertEqual([r.learned_at for r in feed], [T2])
        self.assertEqual([r.seq for r in feed], [1])


class SeveralDomainsAndFieldsTest(unittest.TestCase):
    """Every change, correction and initial entry has a non-null learned_at equal to its build's
    time, across domains, fields, an A to B to A change and a field unknown at the first build."""

    def test_every_non_initial_entry_has_its_builds_time_across_domains(self):
        domains = {
            "acme.test": [
                ready(0, T1, {URL_A: (date(2026, 1, 1), {"ceo": ["Dana Ruiz"]})}),
                ready(1, T2, {URL_A: (date(2026, 3, 1), {"ceo": ["Lee Park"]})}),
                ready(2, T3, {URL_B: (date(2026, 2, 1), {"ceo": ["Dana Ruiz"]})}),
            ],
            "beta.test": [
                ready(0, T1, {URL_A: (date(2026, 1, 1), {"ceo": ["Sam Ortiz"]})}),
                # hq_city was unknown at the first build; its first value is a change.
                ready(1, T2, {URL_A: (date(2026, 1, 1), {"ceo": ["Sam Ortiz"],
                                                          "hq_city": ["Porto"]})}),
            ],
        }
        for domain, records in domains.items():
            feed, hist = _replay(records)
            for row in feed:
                self.assertIsNotNone(row.learned_at, (domain, row))
            non_initial = [(f, e) for f, entries in hist.items() for e in entries
                           if e.type != "initial"]
            for field, entry in non_initial:
                self.assertIsNotNone(entry.learned_at, (domain, field, entry))
            feed_times = {(r.field, r.type, r.value): r.learned_at for r in feed}
            for field, entry in non_initial:
                key = (field, entry.type, entry.value)
                self.assertEqual(feed_times[key], entry.learned_at, (domain, key))


class DisappearingValueTest(unittest.TestCase):
    """A value that becomes null: the history and feed entries carry the build's time, and the
    entry's value, true_from and citations are null or empty (R3.56, R3.62)."""

    def test_history_and_feed_take_the_build_time_when_the_value_disappears(self):
        records = [
            ready(0, T1, {URL_A: (date(2026, 1, 10), {"hq_city": ["Lisbon"]})}),
            ready(1, T2, {URL_A: (date(2026, 3, 20), {"hq_city": []})}),
        ]
        feed, hist = _replay(records)
        gone = [e for e in hist["hq_city"] if e.value is None]
        self.assertEqual(len(gone), 1)
        entry = gone[0]
        self.assertEqual((entry.type, entry.learned_at, entry.true_from, entry.citations),
                         ("change", T2, None, ()))
        self.assertEqual([(r.field, r.type, r.value, r.learned_at, r.true_from)
                          for r in feed],
                         [("hq_city", "change", None, T2, None)])
