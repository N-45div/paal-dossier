"""R3.35: a ready build that selects the same value for a field adds nothing for it, even when
its candidates, citations or true_from differ; a failed build adds nothing; refreshes with the
same data leave history and feed unchanged and seq without gaps. Runs on records, no HTTP."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from app.candidates import Candidate
from app.feed import FeedRow, append_build
from app.history import feed_entries, history, views
from app.records import BuildRecord, versions_of
from tests.unit.test_history import URL_A, URL_B, T1, T2, T3, failed, ready

DOMAIN = "acme.test"
T4 = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def _feed_after(records) -> tuple[list[FeedRow], int]:
    """Replay the build records through the feed the way apply_outcome does."""
    feed: list[FeedRow] = []
    next_seq = 1
    previous = None
    for index in range(len(records)):
        prefix = records[:index + 1]
        if not prefix[-1].ok:
            continue
        current = views(prefix)[-1][1]
        entries = feed_entries(previous, current, first=previous is None)
        next_seq = append_build(feed, next_seq, DOMAIN, entries)
        previous = current
    return feed, next_seq


class SameValueReselectionTest(unittest.TestCase):

    def test_identical_refreshes_add_no_history_and_no_feed_entry(self):
        first = ready(0, T1, {URL_A: (date(2026, 1, 10), {"ceo": ["Dana Ruiz"]})})
        change = ready(1, T2, {URL_A: (date(2026, 3, 20), {"ceo": ["Lee Park"]})})
        again = ready(2, T3, {URL_A: (date(2026, 3, 20), {"ceo": ["Lee Park"]})})
        again2 = ready(3, T4, {URL_A: (date(2026, 3, 20), {"ceo": ["Lee Park"]})})

        feed, next_seq = _feed_after([first, change])
        self.assertEqual([(r.seq, r.type, r.previous, r.value) for r in feed],
                         [(1, "change", "Dana Ruiz", "Lee Park")])

        feed3, next3 = _feed_after([first, change, again, again2])
        self.assertEqual(feed3, feed)
        self.assertEqual(next3, next_seq)
        self.assertEqual([r.seq for r in feed3], list(range(1, len(feed3) + 1)))
        ceo = history([first, change, again, again2])["ceo"]
        self.assertEqual([e.type for e in ceo], ["initial", "change"])

    def test_same_value_with_different_true_from_and_citation_adds_nothing(self):
        first = ready(0, T1, {URL_A: (date(2026, 1, 10), {"ceo": ["Lee Park"]})})
        # Same value from another page with a later true_from: candidates and citations differ.
        again = ready(1, T2, {URL_B: (date(2026, 3, 20), {"ceo": ["Lee Park"]})})
        feed, next_seq = _feed_after([first, again])
        self.assertEqual(feed, [])
        self.assertEqual(next_seq, 1)
        self.assertEqual(history([first, again])["ceo"][0].type, "initial")
        self.assertEqual(len(history([first, again])["ceo"]), 1)

    def test_failed_build_adds_nothing(self):
        first = ready(0, T1, {URL_A: (date(2026, 1, 10), {"ceo": ["Dana Ruiz"]})})
        broken = failed(1, T2)
        feed, next_seq = _feed_after([first, broken])
        self.assertEqual(feed, [])
        self.assertEqual(next_seq, 1)

    def test_executives_same_selection_adds_nothing(self):

        def exec_build(index, when, true_from):
            found = {"executives": [Candidate(value="Ana Silva", url=URL_A, excerpt="Ana Silva is the chief financial officer.", provider="nimble", kind="own", title="cfo")]}
            versions = versions_of(found, {URL_A: true_from})
            return BuildRecord(index=index, time=when, ok=True, spent_units=1, versions=versions)

        first = exec_build(0, T1, date(2026, 1, 10))
        again = exec_build(1, T2, date(2026, 3, 20))
        feed, next_seq = _feed_after([first, again])
        self.assertEqual(feed, [])
        self.assertEqual(len(history([first, again])["executives"]), 1)
