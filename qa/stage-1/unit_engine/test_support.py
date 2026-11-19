"""Unit tests for engine/support.py (Appendix A of the stage-1 specification)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "stage-1"))

from engine.support import (  # noqa: E402
    candidate_values,
    headcount_range_for,
    is_single_sentence,
    is_verbatim_in_prose,
    names_company,
    page_claims,
    parse_page,
    split_sentences,
    supports,
)

D = "acme-robotics.test"


class SentenceSplitTests(unittest.TestCase):
    def test_splits_after_terminators(self):
        self.assertEqual(
            split_sentences("It is good! Really? Yes."), ["It is good!", "Really?", "Yes."]
        )

    def test_closers_stay_with_sentence(self):
        self.assertEqual(
            split_sentences('He said "Yes." Then left.'),
            ['He said "Yes."', "Then left."],
        )

    def test_terminator_without_following_space_does_not_split(self):
        self.assertEqual(split_sentences("Version 1.5 shipped."), ["Version 1.5 shipped."])

    def test_legal_suffix_dot_does_not_end_sentence(self):
        for suffix in ("Inc.", "Corp.", "L.P.", "S.A.S.", "s.r.o.", "a.s.", "K.K.", "B.V."):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    split_sentences(f"Acme {suffix} is based in Lisbon. Done."),
                    [f"Acme {suffix} is based in Lisbon.", "Done."],
                )

    def test_suffix_inside_a_word_still_ends_sentence(self):
        # "Lin." is not the suffix "Inc." as a whole word.
        self.assertEqual(split_sentences("Call Lin. Then go."), ["Call Lin.", "Then go."])

    def test_empty_sentences_dropped(self):
        self.assertEqual(split_sentences("   "), [])
        self.assertEqual(split_sentences(""), [])


class SingleSentenceTests(unittest.TestCase):
    def test_one_sentence(self):
        self.assertTrue(is_single_sentence("Acme Robotics, Inc. was founded in 2014."))

    def test_two_sentences(self):
        self.assertFalse(is_single_sentence("Acme was founded in 2014. It sells robots."))

    def test_whitespace_runs_count_as_one_space(self):
        self.assertTrue(is_single_sentence("Acme\n\n   was   founded in 2014."))


class NameMatchTests(unittest.TestCase):
    def test_name_from_domain(self):
        self.assertTrue(names_company("Acme Robotics was founded in 2014.", D))

    def test_domain_matches(self):
        self.assertTrue(names_company("acme-robotics.test is listed.", D))

    def test_case_insensitive(self):
        self.assertTrue(names_company("ACME ROBOTICS was founded in 2014.", D))

    def test_whole_word_only(self):
        self.assertFalse(names_company("Acme Roboticsish was founded in 2014.", D))
        self.assertFalse(names_company("Xacme Robotics was founded in 2014.", D))

    def test_other_company_not_named(self):
        self.assertFalse(names_company("Other Co was founded in 2014.", D))


class PhraseAndNegationTests(unittest.TestCase):
    def test_statement_phrase_required(self):
        self.assertIsNone(supports("Acme Robotics opened a sales office in Porto.", D, "hq_city"))

    def test_negating_phrase_rejects(self):
        self.assertIsNone(
            supports("Acme Robotics is reportedly in talks to raise $40M.", D, "funding_total")
        )

    def test_not_is_a_whole_word(self):
        self.assertEqual(
            supports("Acme Robotics was founded in 2014 and cannot be wrong.", D, "founded_year"),
            2014,
        )
        self.assertIsNone(
            supports("Acme Robotics was not founded in 2014.", D, "founded_year")
        )

    def test_each_negating_phrase_rejects(self):
        for word in ("could", "would", "former", "seeking", "plans to"):
            with self.subTest(word=word):
                self.assertIsNone(
                    supports(f"Acme Robotics {word} be founded in 2014.", D, "founded_year")
                )


class CeoTests(unittest.TestCase):
    def test_spec_examples(self):
        self.assertEqual(
            supports("Dana Ruiz has led Acme Robotics as chief executive since 2021.", D, "ceo"),
            "Dana Ruiz",
        )
        self.assertEqual(supports("Acme Robotics CEO: Sam Ortiz.", D, "ceo"), "Sam Ortiz")

    def test_three_word_name(self):
        self.assertEqual(
            supports("Acme Robotics CEO: Maria de Silva.", D, "ceo"), None
        )  # "de" is lowercase; two runs, so ambiguous
        self.assertEqual(
            supports("Acme Robotics CEO: Maria Jose Silva.", D, "ceo"), "Maria Jose Silva"
        )

    def test_single_word_run_is_not_a_name(self):
        self.assertIsNone(supports("Acme Robotics CEO: Sam.", D, "ceo"))

    def test_four_word_run_is_not_a_name(self):
        self.assertEqual(candidate_values("Acme Robotics CEO: Ann Bo Cy Dee.", D, "ceo"), set())

    def test_two_names_conflict(self):
        self.assertIsNone(
            supports("Dana Ruiz and Sam Ortiz lead Acme Robotics as CEO.", D, "ceo")
        )

    def test_phrase_words_do_not_form_a_name(self):
        self.assertEqual(
            candidate_values("Acme Robotics chief executive officer Dana Ruiz.", D, "ceo"),
            {"Dana Ruiz"},
        )


class HqCityTests(unittest.TestCase):
    def test_city_after_phrase(self):
        self.assertEqual(
            supports("Acme Robotics, Inc. is headquartered in Lisbon, Portugal.", D, "hq_city"),
            "Lisbon",
        )

    def test_unicode_capitalised(self):
        self.assertEqual(supports("Acme Robotics is based in Zürich.", D, "hq_city"), "Zürich")

    def test_hyphen_and_space_runs(self):
        self.assertEqual(
            supports("Acme Robotics is based in New-York City.", D, "hq_city"), "New-York City"
        )

    def test_longest_run(self):
        self.assertEqual(
            candidate_values("Acme Robotics is based in Porto Alegre.", D, "hq_city"),
            {"Porto Alegre"},
        )

    def test_lowercase_after_phrase_is_not_a_city(self):
        self.assertIsNone(supports("Acme Robotics is based in the north.", D, "hq_city"))


class LegalNameTests(unittest.TestCase):
    def test_comma_inc(self):
        self.assertEqual(
            supports("Acme Robotics, Inc. is registered as a company.", D, "legal_name"),
            "Acme Robotics, Inc.",
        )

    def test_space_suffix(self):
        self.assertEqual(
            supports("Acme Robotics is a registered name of Acme Robotics Ltd.", D, "legal_name"),
            "Acme Robotics Ltd",
        )

    def test_words_before_suffix(self):
        self.assertEqual(
            supports("Acme Robotics Holdings GmbH is the legal entity.", D, "legal_name"),
            "Acme Robotics Holdings GmbH",
        )

    def test_shortest_counts(self):
        self.assertEqual(
            candidate_values("Acme Robotics Ltd Holdings Ltd is the legal name.", D, "legal_name"),
            {"Acme Robotics Ltd"},
        )

    def test_suffix_needs_no_letter_after(self):
        self.assertIsNone(
            supports("Acme Robotics ABC is the legal name.", D, "legal_name")
        )

    def test_suffix_with_space_before_comma_form_only(self):
        self.assertIsNone(
            supports("Acme Robotics; Inc. is the legal name.", D, "legal_name")
        )

    def test_two_different_legal_names_conflict(self):
        self.assertIsNone(
            supports(
                "Acme Robotics Ltd, formerly Acme Robotics Inc, is the legal name.",
                D,
                "legal_name",
            )
        )


class FoundedYearTests(unittest.TestCase):
    def test_year(self):
        self.assertEqual(supports("Acme Robotics was founded in 2014.", D, "founded_year"), 2014)

    def test_bounds(self):
        self.assertEqual(supports("Acme Robotics was founded in 1800.", D, "founded_year"), 1800)
        self.assertEqual(supports("Acme Robotics was founded in 2099.", D, "founded_year"), 2099)
        self.assertIsNone(supports("Acme Robotics was founded in 1799.", D, "founded_year"))
        self.assertIsNone(supports("Acme Robotics was founded in 2100.", D, "founded_year"))

    def test_five_digits_not_a_year(self):
        self.assertIsNone(supports("Acme Robotics was founded in 20140.", D, "founded_year"))

    def test_comma_grouped_not_a_year(self):
        self.assertIsNone(supports("Acme Robotics was founded in 2,014.", D, "founded_year"))

    def test_decimal_not_a_year(self):
        self.assertIsNone(supports("Acme Robotics was founded in 2014.5.", D, "founded_year"))

    def test_year_inside_letters_not_a_year(self):
        self.assertIsNone(supports("Acme Robotics was founded in Q2014.", D, "founded_year"))

    def test_year_part_of_amount_is_excluded(self):
        self.assertIsNone(
            supports("Acme Robotics was founded and raised $2014.", D, "founded_year")
        )


class HeadcountTests(unittest.TestCase):
    def test_about_120_is_51_200(self):
        self.assertEqual(
            supports("Acme Robotics employs about 120 people.", D, "headcount_range"), "51-200"
        )

    def test_range_holds_two_numbers(self):
        self.assertEqual(
            supports("Acme Robotics employs 51-200 employees.", D, "headcount_range"), "51-200"
        )

    def test_range_straddling_two_bands_is_not_supported(self):
        self.assertIsNone(
            supports("Acme Robotics employs 10-20 employees.", D, "headcount_range")
        )

    def test_comma_grouped(self):
        self.assertEqual(
            supports("Acme Robotics has 1,200 employees.", D, "headcount_range"), "1001-5000"
        )

    def test_decimal_not_a_headcount(self):
        self.assertIsNone(supports("Acme Robotics employs 12.5 people.", D, "headcount_range"))

    def test_zero_not_a_headcount(self):
        self.assertIsNone(supports("Acme Robotics employs 0 people.", D, "headcount_range"))

    def test_amount_is_not_a_headcount(self):
        self.assertEqual(
            supports("Acme Robotics raised $2 million and employs 120 people.", D, "headcount_range"),
            "51-200",
        )

    def test_range_boundaries(self):
        cases = {
            1: "1-10",
            10: "1-10",
            11: "11-50",
            50: "11-50",
            51: "51-200",
            200: "51-200",
            201: "201-500",
            500: "201-500",
            501: "501-1000",
            1000: "501-1000",
            1001: "1001-5000",
            5000: "1001-5000",
            5001: "5001-10000",
            10000: "5001-10000",
            10001: "10001+",
        }
        for count, label in cases.items():
            with self.subTest(count=count):
                self.assertEqual(headcount_range_for(count), label)


class FundingTests(unittest.TestCase):
    def test_dollar_m(self):
        self.assertEqual(supports("Acme Robotics has raised $12M.", D, "funding_total"), 12_000_000)

    def test_spec_example_words(self):
        self.assertEqual(
            supports("Acme Robotics has raised 12 million dollars.", D, "funding_total"),
            12_000_000,
        )

    def test_us_dollars_and_comma_number(self):
        self.assertEqual(
            supports("Acme Robotics has raised 12,000,000 US dollars.", D, "funding_total"),
            12_000_000,
        )

    def test_us_prefix_and_space_scale(self):
        self.assertEqual(
            supports("Acme Robotics has raised US$12.5 million in funding.", D, "funding_total"),
            12_500_000,
        )

    def test_usd_prefix(self):
        self.assertEqual(
            supports("Acme Robotics has raised USD 12 million.", D, "funding_total"), 12_000_000
        )

    def test_thousand_scale(self):
        self.assertEqual(supports("Acme Robotics raised $12.5k.", D, "funding_total"), 12_500)

    def test_non_whole_dollars_not_a_value(self):
        self.assertIsNone(supports("Acme Robotics raised 12.5 dollars.", D, "funding_total"))
        self.assertIsNone(supports("Acme Robotics raised $12.5.", D, "funding_total"))

    def test_other_currency_not_an_amount(self):
        self.assertIsNone(supports("Acme Robotics raised €12 million.", D, "funding_total"))

    def test_letter_before_currency_not_an_amount(self):
        self.assertIsNone(supports("Acme Robotics raised A$12M.", D, "funding_total"))

    def test_scale_must_be_directly_or_one_space(self):
        self.assertEqual(
            supports("Acme Robotics raised $12 millions.", D, "funding_total"), 12
        )

    def test_mixed_amounts_conflict(self):
        self.assertIsNone(
            supports("Acme Robotics raised $12M and $3M in total.", D, "funding_total")
        )


class NumberGrammarTests(unittest.TestCase):
    def test_joined_digits_are_not_numbers(self):
        self.assertIsNone(supports("Acme Robotics was founded in 12,34.", D, "founded_year"))
        self.assertIsNone(supports("Acme Robotics was founded in 2014.1.2.", D, "founded_year"))


class NormalisationAndPageTests(unittest.TestCase):
    def test_unique_value_per_sentence(self):
        self.assertEqual(
            candidate_values("Acme Robotics was founded in 2014.", D, "founded_year"), {2014}
        )

    def test_excerpt_must_be_verbatim_in_prose(self):
        prose = "Acme Robotics was founded\nin 2014. Other text."
        self.assertTrue(is_verbatim_in_prose("Acme Robotics was founded in 2014.", prose))
        self.assertFalse(is_verbatim_in_prose("Acme Robotics was founded in 2015.", prose))

    def test_parse_page_with_header(self):
        header, prose = parse_page(
            'Title: About\nFacts: {"ceo": "Dana Ruiz"}\n\nAcme Robotics was founded in 2014.'
        )
        self.assertEqual(header["Title"], "About")
        self.assertEqual(prose, "Acme Robotics was founded in 2014.")

    def test_parse_page_without_header(self):
        header, prose = parse_page("Acme Robotics was founded in 2014.\nMore.")
        self.assertEqual(header, {})
        self.assertEqual(prose, "Acme Robotics was founded in 2014.\nMore.")

    def test_header_name_must_be_capitalised_words(self):
        header, prose = parse_page("lower: x\n\nBody")
        self.assertEqual(header, {})
        self.assertEqual(prose, "lower: x\n\nBody")

    def test_header_joined_by_dash(self):
        header, _ = parse_page("Last-Modified: today\n\nBody")
        self.assertEqual(header["Last-Modified"], "today")

    def test_page_claims_lists_sentence_field_value(self):
        claims = page_claims(
            "Acme Robotics, Inc. is headquartered in Lisbon.\nDana Ruiz is CEO of Acme Robotics.",
            D,
        )
        self.assertIn(("Acme Robotics, Inc. is headquartered in Lisbon.", "hq_city", "Lisbon"), claims)
        self.assertIn(("Dana Ruiz is CEO of Acme Robotics.", "ceo", "Dana Ruiz"), claims)


class SpecTableTests(unittest.TestCase):
    """The Appendix A.2 example table, row for row."""

    def test_table_rows(self):
        self.assertEqual(
            supports("Dana Ruiz has led Acme Robotics as chief executive since 2021.", D, "ceo"),
            "Dana Ruiz",
        )
        self.assertEqual(supports("Acme Robotics CEO: Sam Ortiz.", D, "ceo"), "Sam Ortiz")
        self.assertEqual(supports("Acme Robotics was founded in 2014.", D, "founded_year"), 2014)
        self.assertEqual(
            supports("Acme Robotics employs about 120 people.", D, "headcount_range"), "51-200"
        )
        self.assertIsNone(
            supports("Acme Robotics is reportedly in talks to raise $40M.", D, "funding_total")
        )
        self.assertIsNone(
            supports("Acme Robotics opened a sales office in Porto.", D, "hq_city")
        )


if __name__ == "__main__":
    unittest.main()
