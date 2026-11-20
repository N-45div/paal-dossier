"""Unit tests for candidate gathering from rendered pages (P5; R2.5-R2.9, R2.31-R2.39, RL7, RL59-RL64).

Provider-free. Run: python3 -I qa/stage-2/unit_engine/test_candidates.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "stage-2"))

from engine.evidence import Evidence  # noqa: E402
from engine.pages import page_kind, parse_published, read_page  # noqa: E402

DOMAIN = "acme-robotics.test"
RETRIEVED = "2026-03-01T09:00:00+00:00"
OWN = "https://acme-robotics.test/about"
NEWS = "https://wire.test/acme-raises"
AGG = "https://bizdata.test/acme-robotics"


def served(prose, kind=None, published=None):
    """Served text: header lines, a blank line, then the prose (the mock's layout)."""
    lines = []
    if kind is not None:
        lines.append(f"Kind: {kind}")
    if published is not None:
        lines.append(f"Published: {published}")
    return "\n".join(lines) + "\n\n" + prose


class PageReadingTests(unittest.TestCase):
    def test_r2_6_explicit_kind_is_taken(self):
        self.assertEqual(page_kind("news", NEWS, DOMAIN), "news")

    def test_r2_8_no_kind_line_on_company_host_is_own(self):
        self.assertEqual(page_kind(None, OWN, DOMAIN), "own")

    def test_r2_8_no_kind_line_elsewhere_is_aggregator(self):
        self.assertEqual(page_kind(None, AGG, DOMAIN), "aggregator")

    def test_r2_8_unlisted_kind_value_takes_the_default(self):
        self.assertEqual(page_kind("Own", OWN, DOMAIN), "own")
        self.assertEqual(page_kind("blog", AGG, DOMAIN), "aggregator")

    def test_r2_7_valid_published_is_emitted_as_written(self):
        self.assertEqual(parse_published("2026-02-20T00:00:00Z"), "2026-02-20T00:00:00Z")

    def test_r2_8_invalid_published_has_no_time(self):
        self.assertIsNone(parse_published("2026-02-20"))
        self.assertIsNone(parse_published(None))

    def test_r2_9_read_page_gives_kind_time_and_prose(self):
        read = read_page(served("Body.", kind="news", published="2026-02-20T00:00:00Z"), NEWS, DOMAIN)
        self.assertEqual((read.kind, read.published_at, read.prose), ("news", "2026-02-20T00:00:00Z", "Body."))


class CandidateGatheringTests(unittest.TestCase):
    def test_r2_31_one_candidate_per_page_and_value(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(OWN, served("Dana Ruiz has led Acme Robotics as chief executive since 2021."))
        evidence.add_rendered_page(AGG, served("Acme Robotics CEO: Sam Ortiz."))
        fields = evidence.decide()
        ceo = fields["ceo"]
        self.assertEqual(ceo["status"], "contested")
        self.assertEqual(ceo["value"], "Dana Ruiz")
        self.assertEqual([c["value"] for c in ceo["candidates"]], ["Dana Ruiz", "Sam Ortiz"])
        self.assertEqual([c["selected"] for c in ceo["candidates"]], [True, False])
        self.assertEqual(ceo["candidates"][0]["kind"], "own")
        self.assertEqual(ceo["candidates"][1]["kind"], "aggregator")
        self.assertEqual(ceo["candidates"][0]["retrieved_at"], RETRIEVED)

    def test_r2_31_same_value_from_one_page_is_one_candidate(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(
            OWN,
            served("Dana Ruiz has led Acme Robotics as chief executive since 2021. "
                   "Dana Ruiz has led Acme Robotics as chief executive since 2021."),
        )
        ceo = evidence.decide()["ceo"]
        self.assertEqual(len(ceo["candidates"]), 1)
        self.assertEqual(ceo["status"], "known")

    def test_r2_31_one_page_may_support_several_values(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(
            NEWS,
            served("Dana Ruiz has led Acme Robotics as chief executive since 2021.\n"
                   "Acme Robotics CEO: Sam Ortiz."),
        )
        ceo = evidence.decide()["ceo"]
        self.assertEqual(sorted(c["value"] for c in ceo["candidates"]), ["Dana Ruiz", "Sam Ortiz"])
        self.assertEqual(ceo["status"], "contested")

    def test_r2_34_citations_carry_the_smallest_excerpt_of_the_page(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(
            OWN,
            served("Acme Robotics CEO: Sam Ortiz.\nAcme Robotics chief executive is Sam Ortiz since 2020."),
        )
        ceo = evidence.decide()["ceo"]
        self.assertEqual(ceo["value"], "Sam Ortiz")
        self.assertEqual(ceo["citations"][0]["excerpt"], min(
            "Acme Robotics CEO: Sam Ortiz.", "Acme Robotics chief executive is Sam Ortiz since 2020."))
        self.assertEqual(ceo["citations"][0]["provider"], "nimble")

    def test_r2_9_text_not_rendered_gives_no_candidate(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_research_claim(OWN, "ceo", "Dana Ruiz", "Dana Ruiz has led Acme Robotics as chief executive.")
        self.assertEqual(evidence.decide()["ceo"], {
            "value": None, "status": "unknown", "citations": [], "candidates": []})

    def test_rl7_research_claim_with_verbatim_citation_adds_candidate(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(
            NEWS, served("Dana Ruiz has led Acme Robotics as chief executive since 2021.", kind="news"))
        evidence.add_research_claim(NEWS, "ceo", "Dana Ruiz",
                                    "Dana Ruiz has led Acme Robotics as chief executive since 2021.")
        ceo = evidence.decide()["ceo"]
        self.assertEqual(ceo["value"], "Dana Ruiz")
        self.assertEqual(ceo["candidates"][0]["kind"], "news")

    def test_rl7_research_claim_not_in_page_text_is_discarded(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(NEWS, served("Unrelated text about the weather."))
        evidence.add_research_claim(NEWS, "ceo", "Dana Ruiz",
                                    "Dana Ruiz has led Acme Robotics as chief executive since 2021.")
        self.assertEqual(evidence.decide()["ceo"]["candidates"], [])

    def test_r2_41_own_page_beats_aggregator_page_in_selection(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(AGG, served("Acme Robotics was founded in 2015.", published="2026-02-20T00:00:00Z"))
        evidence.add_rendered_page(OWN, served("Acme Robotics was founded in 2014."))
        fields = evidence.decide()["founded_year"]
        self.assertEqual(fields["value"], 2014)
        self.assertEqual(fields["candidates"][0]["kind"], "own")
        self.assertEqual(fields["status"], "contested")

    def test_r2_35_numeric_values_stay_numbers(self):
        evidence = Evidence(DOMAIN, RETRIEVED)
        evidence.add_rendered_page(OWN, served("Acme Robotics was founded in 2014."))
        self.assertIs(type(evidence.decide()["founded_year"]["value"]), int)

    def test_r2_32_no_pages_gives_every_field_unknown(self):
        fields = Evidence(DOMAIN, RETRIEVED).decide()
        self.assertEqual(sorted(fields), sorted(["legal_name", "hq_city", "ceo", "founded_year",
                                                  "headcount_range", "funding_total"]))
        for name, field in fields.items():
            self.assertEqual(field["status"], "unknown", name)
            self.assertEqual(field["candidates"], [], name)


if __name__ == "__main__":
    unittest.main()
