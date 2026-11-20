"""Unit tests for stage-2/engine/selection.py (P5; R2.40-R2.46, RL62, RL64).

Provider-free. Run: python3 -I qa/stage-2/unit_engine/test_selection.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "stage-2"))

from engine.selection import assemble_field, rank, same_value, status_of  # noqa: E402

RETRIEVED = "2026-03-01T09:00:00+00:00"


def cand(value, url="https://acme-robotics.test/about", provider="nimble", kind="own",
         published_at=None, excerpt=None):
    return {
        "value": value,
        "url": url,
        "excerpt": excerpt if excerpt is not None else f"excerpt {value}",
        "provider": provider,
        "kind": kind,
        "published_at": published_at,
    }


def values(ranked):
    return [item["value"] for item in ranked]


class RankAuthorityTests(unittest.TestCase):
    def test_r2_41_own_and_filing_rank_equal_and_highest_then_news_then_aggregator(self):
        ranked = rank([
            cand("agg", kind="aggregator", url="https://a.test/1"),
            cand("news", kind="news", url="https://a.test/2"),
            cand("filing", kind="filing", url="https://z.test/3"),
            cand("own", kind="own", url="https://b.test/4"),
        ])
        self.assertEqual(values(ranked)[2:], ["news", "agg"])
        # own and filing are equal: the URL decides between them, the smaller URL first
        self.assertEqual(values(ranked)[:2], ["own", "filing"])

    def test_r2_41_null_kind_has_aggregator_authority(self):
        ranked = rank([cand("imported", kind=None, url="https://a.test/1"),
                       cand("news", kind="news", url="https://z.test/9")])
        self.assertEqual(values(ranked), ["news", "imported"])

    def test_r2_46_lower_authority_is_selected_only_when_no_higher_exists(self):
        result = assemble_field([cand("Sam", kind="aggregator", url="https://biz.test/x"),
                                 cand("Dana", kind="own")], RETRIEVED)
        self.assertEqual(result["value"], "Dana")
        only_low = assemble_field([cand("Sam", kind="aggregator")], RETRIEVED)
        self.assertEqual(only_low["value"], "Sam")


class RankRecencyTests(unittest.TestCase):
    def test_r2_42_later_published_at_ranks_higher_within_authority(self):
        ranked = rank([
            cand("older", published_at="2025-01-01T00:00:00+00:00", url="https://a.test/1"),
            cand("newer", published_at="2026-01-01T00:00:00+00:00", url="https://z.test/2"),
        ])
        self.assertEqual(values(ranked), ["newer", "older"])

    def test_r2_42_candidate_without_time_ranks_below_all_timed_of_same_authority(self):
        ranked = rank([
            cand("untimed", published_at=None, url="https://a.test/1"),
            cand("timed", published_at="2000-01-01T00:00:00+00:00", url="https://z.test/2"),
        ])
        self.assertEqual(values(ranked), ["timed", "untimed"])

    def test_r2_42_time_compares_as_an_instant_not_as_text(self):
        ranked = rank([
            cand("plus-two", published_at="2026-01-01T02:00:00+02:00", url="https://a.test/1"),
            cand("utc-later", published_at="2026-01-01T00:30:00+00:00", url="https://z.test/2"),
        ])
        self.assertEqual(values(ranked), ["utc-later", "plus-two"])


class RankUrlAndProviderTests(unittest.TestCase):
    def test_r2_43_smaller_url_by_code_point_ranks_higher_when_authority_and_time_equal(self):
        ranked = rank([cand("b", url="https://b.test/x"), cand("a", url="https://a.test/x")])
        self.assertEqual(values(ranked), ["a", "b"])

    def test_r2_43_same_url_ranks_by_provider_nimble_tavily_kernel_browserbase(self):
        url = "https://acme-robotics.test/about"
        ranked = rank([cand("v", url=url, provider=p) for p in ("browserbase", "tavily", "kernel", "nimble")])
        self.assertEqual([item["provider"] for item in ranked], ["nimble", "tavily", "kernel", "browserbase"])


class RankValueTests(unittest.TestCase):
    def test_r2_44_same_url_and_provider_smaller_value_ranks_higher(self):
        ranked = rank([cand("Sam Ortiz"), cand("Dana Ruiz")])
        self.assertEqual(values(ranked), ["Dana Ruiz", "Sam Ortiz"])

    def test_r2_44_integers_compare_as_numbers_not_as_text(self):
        ranked = rank([cand(10), cand(9)])
        self.assertEqual(values(ranked), [9, 10])

    def test_r2_44_strings_compare_after_removing_surrounding_whitespace(self):
        ranked = rank([cand("  b "), cand("a")])
        self.assertEqual(values(ranked), ["a", "  b "])

    def test_r2_44_strings_compare_by_code_point(self):
        ranked = rank([cand("é"), cand("z")])
        self.assertEqual(values(ranked), ["z", "é"])


class AssembleFieldTests(unittest.TestCase):
    def test_r2_45_selected_value_and_citations_in_rank_order(self):
        result = assemble_field([
            cand("Sam Ortiz", url="https://bizdata.test/acme-robotics", kind="aggregator"),
            cand("Dana Ruiz", url="https://acme-robotics.test/about", kind="own", excerpt="A"),
            cand("Dana Ruiz", url="https://acme-robotics.test/leadership", kind="own", excerpt="B"),
        ], RETRIEVED)
        self.assertEqual(result["value"], "Dana Ruiz")
        self.assertEqual(result["status"], "contested")
        self.assertEqual(
            result["citations"],
            [
                {"url": "https://acme-robotics.test/about", "excerpt": "A", "provider": "nimble"},
                {"url": "https://acme-robotics.test/leadership", "excerpt": "B", "provider": "nimble"},
            ],
        )

    def test_rl64_candidates_in_rank_order_with_selected_only_on_index_zero(self):
        result = assemble_field([cand("Sam Ortiz", kind="aggregator"), cand("Dana Ruiz")], RETRIEVED)
        self.assertEqual([c["value"] for c in result["candidates"]], ["Dana Ruiz", "Sam Ortiz"])
        self.assertEqual([c["selected"] for c in result["candidates"]], [True, False])
        self.assertEqual({c["retrieved_at"] for c in result["candidates"]}, {RETRIEVED})

    def test_rl64_a_page_may_support_several_values_one_candidate_each(self):
        result = assemble_field([cand("2014"), cand("2015")], RETRIEVED)
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["value"], "2014")

    def test_empty_candidates_give_unknown_with_null_value(self):
        self.assertEqual(assemble_field([], RETRIEVED),
                         {"value": None, "status": "unknown", "citations": [], "candidates": []})

    def test_status_known_when_all_candidates_share_one_value(self):
        result = assemble_field([cand("Dana Ruiz", url="https://a.test/1"),
                                 cand(" Dana Ruiz ", url="https://a.test/2")], RETRIEVED)
        self.assertEqual(result["status"], "known")
        self.assertEqual(result["value"], "Dana Ruiz")
        self.assertEqual(len(result["citations"]), 2)

    def test_status_contested_when_two_or_more_values(self):
        self.assertEqual(status_of([cand("a"), cand("b")]), "contested")

    def test_status_unknown_without_candidates(self):
        self.assertEqual(status_of([]), "unknown")

    def test_bool_is_not_an_integer(self):
        self.assertFalse(same_value(1, True))
        self.assertEqual(status_of([cand(1), cand(True)]), "contested")

    def test_rank_does_not_modify_its_input(self):
        original = [cand("b"), cand("a")]
        snapshot = [dict(item) for item in original]
        rank(original)
        self.assertEqual(original, snapshot)


if __name__ == "__main__":
    unittest.main()
