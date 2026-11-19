"""Unit tests for the engine's ledger, discovery, evidence and decision rules (RL4-RL7).

Provider-free. The end-to-end test against the mock web runs only when DOSSIER_MOCK_WEB
names its base URL (for example http://127.0.0.1:18100), with NIMBLE_API_KEY set.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "stage-1"))

from engine.discovery import rank_urls, support_queries  # noqa: E402
from engine.evidence import Evidence  # noqa: E402
from engine.ledger import Ledger  # noqa: E402

D = "acme-robotics.test"
PROSE = (
    "Acme Robotics, Inc. is headquartered in Lisbon.\n"
    "Dana Ruiz is CEO of Acme Robotics.\n"
    "Acme Robotics was founded in 2014."
)


class LedgerTests(unittest.TestCase):
    def test_reserve_never_exceeds_budget(self):
        ledger = Ledger(10)
        self.assertTrue(ledger.reserve(6))
        self.assertFalse(ledger.reserve(5))
        self.assertTrue(ledger.reserve(4))

    def test_settle_releases_reservation_and_records_spend(self):
        spent = []
        ledger = Ledger(10, on_spend=spent.append)
        self.assertTrue(ledger.reserve(5))
        ledger.settle(5, 0)  # refused call: nothing charged, reservation released
        self.assertEqual(ledger.spent, 0)
        self.assertTrue(ledger.reserve(10))
        ledger.settle(10, 7)
        self.assertEqual(ledger.spent, 7)
        self.assertEqual(spent, [7])

    def test_keep_leaves_units_free(self):
        ledger = Ledger(10)
        self.assertTrue(ledger.reserve(4, keep=6))
        self.assertFalse(ledger.reserve(1, keep=6))

    def test_failing_spend_callback_does_not_break_accounting(self):
        def boom(_units):
            raise RuntimeError("bookkeeping failed")

        ledger = Ledger(10, on_spend=boom)
        ledger.reserve(3)
        ledger.settle(3, 3)
        self.assertEqual(ledger.spent, 3)


class DiscoveryTests(unittest.TestCase):
    def test_support_queries_name_the_company(self):
        self.assertEqual(
            support_queries(D),
            [
                "Acme Robotics headquarters city",
                "Acme Robotics CEO chief executive",
                "Acme Robotics founded year",
                "Acme Robotics employees headcount",
                "Acme Robotics funding raised",
                "Acme Robotics legal name registered",
            ],
        )

    def test_company_pages_first_then_best_rank(self):
        hits = [
            ("https://news.test/a", 0),
            ("https://acme-robotics.test/about", 3),
            ("https://news.test/a", 1),
            ("https://www.acme-robotics.test/team", 5),
            ("https://news.test/b", 2),
        ]
        self.assertEqual(
            rank_urls(hits, D),
            [
                "https://acme-robotics.test/about",
                "https://www.acme-robotics.test/team",
                "https://news.test/a",
                "https://news.test/b",
            ],
        )


class EvidenceDecisionTests(unittest.TestCase):
    def test_supported_fields_are_known_with_verbatim_citations(self):
        evidence = Evidence(D)
        evidence.add_page("https://acme-robotics.test/about", "Kind: own\n\n" + PROSE, "nimble")
        fields = evidence.decide()
        self.assertEqual(fields["hq_city"]["value"], "Lisbon")
        self.assertEqual(fields["ceo"]["value"], "Dana Ruiz")
        self.assertEqual(fields["founded_year"]["value"], 2014)
        self.assertIsNone(fields["funding_total"]["value"])
        self.assertEqual(fields["funding_total"]["citations"], [])
        citation = fields["hq_city"]["citations"][0]
        self.assertEqual(citation["excerpt"], "Acme Robotics, Inc. is headquartered in Lisbon.")
        self.assertEqual(citation["provider"], "nimble")
        self.assertEqual(citation["url"], "https://acme-robotics.test/about")

    def test_most_distinct_pages_wins(self):
        evidence = Evidence(D)
        evidence.add_page("https://a.test/1", "X: y\n\nAcme Robotics was founded in 2014.", "nimble")
        evidence.add_page("https://a.test/2", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        evidence.add_page("https://a.test/3", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2015)

    def test_tie_prefers_company_page_then_smallest_value(self):
        evidence = Evidence(D)
        evidence.add_page("https://news.test/1", "X: y\n\nAcme Robotics was founded in 2015.", "nimble")
        evidence.add_page("https://news.test/2", "X: y\n\nAcme Robotics was founded in 2016.", "nimble")
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2015)
        evidence.add_page("https://acme-robotics.test/x", "X: y\n\nAcme Robotics was founded in 2016.", "nimble")
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2016)

    def test_citations_come_from_distinct_pages_capped_at_three(self):
        evidence = Evidence(D)
        for index in range(5):
            evidence.add_page(
                f"https://news.test/{index}",
                f"X: y\n\nAcme Robotics was founded in 2014 (story {index}).",
                "nimble",
            )
        citations = evidence.decide()["founded_year"]["citations"]
        self.assertEqual(len(citations), 3)
        self.assertEqual(len({c["url"] for c in citations}), 3)

    def test_research_claim_on_a_negated_sentence_is_not_asserted(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        page = "X: y\n\nAcme Robotics reportedly was founded in 2014."
        evidence.add_page(url, page, "nimble")
        evidence.add_research_claim(url, "founded_year", 2014, "Acme Robotics reportedly was founded in 2014.")
        self.assertIsNone(evidence.decide()["founded_year"]["value"])

    def test_research_claim_with_supported_value_and_verbatim_citation_counts(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_page(url, "X: y\n\nAcme Robotics was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", "2014", "Acme Robotics was founded in 2014.")
        self.assertEqual(set(evidence.support["founded_year"]), {2014})
        self.assertEqual(evidence.decide()["founded_year"]["value"], 2014)

    def test_research_claim_with_wrong_value_is_discarded(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_page(url, "X: y\n\nAcme Robotics was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", 2001, "Acme Robotics was founded in 2014.")
        self.assertEqual(set(evidence.support["founded_year"]), {2014})

    def test_research_excerpt_not_verbatim_in_page_is_discarded(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_page(url, "X: y\n\nAcme Robotics reportedly was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", 2015, "Acme Robotics was founded in 2015.")
        self.assertNotIn(2015, evidence.support.get("founded_year", {}))

    def test_research_claim_from_unknown_page_is_discarded(self):
        evidence = Evidence(D)
        evidence.add_research_claim(
            "https://other.test/", "founded_year", 2014, "Acme Robotics was founded in 2014."
        )
        self.assertEqual(evidence.support, {})

    def test_non_numeric_claim_is_discarded_not_raised(self):
        evidence = Evidence(D)
        url = "https://acme-robotics.test/about"
        evidence.add_page(url, "X: y\n\nAcme Robotics reportedly was founded in 2014.", "nimble")
        evidence.add_research_claim(url, "founded_year", "around 2014", "Acme Robotics was founded in 2014.")
        self.assertNotIn("around 2014", evidence.support.get("founded_year", {}))
        self.assertIsNone(evidence.decide()["founded_year"]["value"])

    def test_excerpt_over_500_characters_is_not_cited(self):
        evidence = Evidence(D)
        long_sentence = "Acme Robotics was founded in 2014 " + "and " * 200 + "today."
        evidence.add_page("https://acme-robotics.test/x", "X: y\n\n" + long_sentence, "nimble")
        self.assertIsNone(evidence.decide()["founded_year"]["value"])


@unittest.skipUnless(os.environ.get("DOSSIER_MOCK_WEB"), "needs the mock web (DOSSIER_MOCK_WEB)")
class MockWebBuildTests(unittest.TestCase):
    def test_halvorsen_build_within_budget_and_one_exact_domain_search(self):
        os.environ.setdefault("NIMBLE_API_KEY", "local")
        os.environ["NIMBLE_BASE_URL"] = os.environ["DOSSIER_MOCK_WEB"].rstrip("/") + "/nimble"
        from engine import run_build

        spend = []
        result = run_build("halvorsen-robotics.test", on_spend=spend.append)
        self.assertTrue(result.ok)
        self.assertLessEqual(result.spent, 80)
        self.assertEqual(sum(spend), result.spent)
        self.assertEqual(result.fields["founded_year"]["value"], 2019)


if __name__ == "__main__":
    unittest.main()
