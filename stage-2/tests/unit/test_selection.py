"""The selection rule and status (stage 2 spec: 'The selection rule', 'Status'), checked
against the rule's own wording, not against the implementation."""

import unittest

from app.candidates import Candidate
from app.selection import decide_field


def cand(value, url, provider="nimble", kind="own", published=None, excerpt="e"):
    return Candidate(value=value, url=url, excerpt=excerpt, provider=provider, kind=kind,
                     published_at=published)


class SelectionRule(unittest.TestCase):
    def test_authority_beats_recency(self):
        newer_aggregator = cand("Sam Ortiz", "https://b.test/x", kind="aggregator",
                                published="2026-02-20T00:00:00+00:00")
        older_own = cand("Dana Ruiz", "https://a.test/about", kind="own",
                         published="2026-01-10T00:00:00+00:00")
        d = decide_field([newer_aggregator, older_own])
        self.assertEqual(d.value, "Dana Ruiz")
        self.assertEqual(d.status, "contested")

    def test_filing_ranks_equal_to_own(self):
        filing = cand("A", "https://z.test/f", kind="filing", published="2026-01-01T00:00:00+00:00")
        own = cand("B", "https://a.test/o", kind="own", published="2026-01-01T00:00:00+00:00")
        # equal authority and time: URL decides, so 'https://a.test/o' wins over 'https://z.test/f'
        self.assertEqual(decide_field([filing, own]).value, "B")

    def test_news_ranks_below_own_and_filing_and_above_aggregator(self):
        news = cand("N", "https://n.test/x", kind="news", published="2026-03-01T00:00:00+00:00")
        agg = cand("G", "https://g.test/x", kind="aggregator", published="2026-03-01T00:00:00+00:00")
        self.assertEqual(decide_field([agg, news]).value, "N")

    def test_recency_within_authority_later_wins(self):
        early = cand("E", "https://a.test/x", published="2026-01-01T00:00:00+00:00")
        late = cand("L", "https://b.test/x", published="2026-02-01T00:00:00+00:00")
        self.assertEqual(decide_field([early, late]).value, "L")

    def test_undated_ranks_below_dated_of_same_authority(self):
        undated = cand("U", "https://a.test/x", published=None)
        dated = cand("D", "https://b.test/x", published="2000-01-01T00:00:00+00:00")
        self.assertEqual(decide_field([undated, dated]).value, "D")

    def test_recency_compares_instants_not_strings(self):
        # 10:00+02:00 is 08:00Z, earlier than 09:00Z
        a = cand("A", "https://a.test/x", published="2026-03-01T10:00:00+02:00")
        b = cand("B", "https://b.test/x", published="2026-03-01T09:00:00+00:00")
        self.assertEqual(decide_field([a, b]).value, "B")

    def test_url_code_point_order(self):
        a = cand("A", "https://a.test/x", published="2026-01-01T00:00:00+00:00")
        b = cand("B", "https://b.test/x", published="2026-01-01T00:00:00+00:00")
        self.assertEqual(decide_field([b, a]).value, "A")

    def test_provider_order_on_same_url(self):
        tav = cand("T", "https://a.test/x", provider="tavily", published=None)
        nim = cand("N", "https://a.test/x", provider="nimble", published=None)
        self.assertEqual(decide_field([tav, nim]).value, "N")

    def test_value_order_on_same_url_and_provider_numbers_numerically(self):
        ten = cand(10, "https://a.test/x", published=None)
        nine = cand(9, "https://a.test/x", published=None)
        self.assertEqual(decide_field([ten, nine]).value, 9)

    def test_value_order_strings_after_trimming(self):
        b = cand(" Beta ", "https://a.test/x", published=None)
        a = cand("Alpha", "https://a.test/x", published=None)
        self.assertEqual(decide_field([b, a]).value, "Alpha")


class StatusAndCitations(unittest.TestCase):
    def test_no_candidates_is_unknown(self):
        d = decide_field([])
        self.assertEqual((d.status, d.value, d.citations), ("unknown", None, []))

    def test_same_values_are_known(self):
        d = decide_field([cand("Dana", "https://a.test/x"), cand("Dana", "https://b.test/y")])
        self.assertEqual(d.status, "known")

    def test_different_values_are_contested_and_keep_a_selected_value(self):
        d = decide_field([cand("Dana", "https://a.test/x"), cand("Sam", "https://b.test/y",
                                                                   kind="aggregator")])
        self.assertEqual(d.status, "contested")
        self.assertEqual(d.value, "Dana")

    def test_citations_are_the_selected_value_in_rank_order(self):
        top = cand("Dana", "https://a.test/x")
        second = cand("Dana", "https://b.test/y")
        other = cand("Sam", "https://c.test/z", kind="aggregator")
        d = decide_field([other, second, top])
        self.assertEqual([c["url"] for c in d.citations],
                         ["https://a.test/x", "https://b.test/y"])

    def test_imported_candidate_has_aggregator_authority(self):
        imported = Candidate(value="Old", url="https://a.test/x", excerpt="e", provider="nimble",
                             kind=None, published_at=None)
        own = cand("New", "https://b.test/y", kind="own", published=None)
        self.assertEqual(decide_field([imported, own]).value, "New")


if __name__ == "__main__":
    unittest.main()
