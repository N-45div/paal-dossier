"""Adversarial cross-check of app/support.py against Appendix A (independent reading).

Expectations below follow the spec text of Appendix A, not the implementation."""

from __future__ import annotations

import unittest

from app.support import (
    excerpt_in_prose,
    extract_supports,
    prose_sentences,
    split_header,
    split_sentences,
    supported_values,
)

D = "acme-robotics.test"


def sv(excerpt: str) -> dict:
    return supported_values(D, excerpt)


class SentenceSplitting(unittest.TestCase):
    def test_legal_suffix_period_does_not_split(self):
        self.assertEqual(
            split_sentences("Acme Robotics Inc. was founded in 2014. Next one."),
            ["Acme Robotics Inc. was founded in 2014.", "Next one."])

    def test_suffix_as_part_of_longer_word_splits(self):
        # "MegaCorp." does not end the suffix "Corp." as a whole word, so it splits.
        self.assertEqual(split_sentences("Built by MegaCorp. Dana leads."),
                         ["Built by MegaCorp.", "Dana leads."])

    def test_dotted_suffixes_do_not_split(self):
        self.assertEqual(len(split_sentences("Acme S.A. was founded in 2014.")), 1)
        self.assertEqual(len(split_sentences("Acme Robotics S.A.S. was founded in 2014.")), 1)

    def test_closer_after_terminator_belongs_to_sentence(self):
        self.assertEqual(split_sentences('"Acme was founded in 2014." Dana leads.'),
                         ['"Acme was founded in 2014."', "Dana leads."])
        self.assertEqual(split_sentences("Acme (founded 2014.) Dana leads."),
                         ["Acme (founded 2014.)", "Dana leads."])

    def test_no_split_without_following_whitespace(self):
        self.assertEqual(len(split_sentences("Acme raised 12.5M.Next")), 1)
        self.assertEqual(len(split_sentences('said "Acme was founded in 2014."')), 1)

    def test_exclamation_and_question_split(self):
        self.assertEqual(len(split_sentences("Acme was founded in 2014! Really?")), 2)

    def test_decimal_point_does_not_split(self):
        self.assertEqual(len(split_sentences("Acme had 1.5 offices.")), 1)

    def test_line_breaks_split_before_sentences(self):
        self.assertEqual(prose_sentences("Acme Robotics was founded in 2014.\nAcme\nRobotics"),
                         ["Acme Robotics was founded in 2014.", "Acme", "Robotics"])
        self.assertEqual(sv("Acme\nRobotics was founded in 2014."), {"founded_year": 2014})

    def test_multi_sentence_excerpt_is_not_a_single_sentence(self):
        self.assertEqual(sv("Acme Robotics was founded in 2014 by Dr. Jane Doe."), {})


class PhraseMatching(unittest.TestCase):
    def test_company_name_is_case_insensitive(self):
        self.assertEqual(sv("ACME ROBOTICS was founded in 2014.")["founded_year"], 2014)
        self.assertEqual(sv("acme robotics was founded in 2014.")["founded_year"], 2014)

    def test_company_name_whole_word_only(self):
        self.assertEqual(sv("Acme Roboticsish was founded in 2014."), {})

    def test_domain_names_the_company(self):
        self.assertEqual(sv("acme-robotics.test was founded in 2014.")["founded_year"], 2014)

    def test_statement_phrase_whole_word(self):
        self.assertEqual(sv("Acme Robotics staffing firm was founded in 2014."),
                         {"founded_year": 2014})
        self.assertEqual(sv("Acme Robotics staffing 120."), {})

    def test_statement_phrase_case_insensitive_ceo(self):
        self.assertEqual(sv("Acme Robotics ceo Dana Ruiz."), {"ceo": "Dana Ruiz"})

    def test_plural_ceo_is_not_a_phrase(self):
        self.assertEqual(sv("Acme Robotics CEOs include Dana Ruiz."), {})

    def test_spec_examples(self):
        self.assertEqual(sv("Dana Ruiz has led Acme Robotics as chief executive since 2021."),
                         {"ceo": "Dana Ruiz"})
        self.assertEqual(sv("Acme Robotics CEO: Sam Ortiz."), {"ceo": "Sam Ortiz"})
        self.assertEqual(sv("Acme Robotics was founded in 2014."), {"founded_year": 2014})
        self.assertEqual(sv("Acme Robotics employs about 120 people."),
                         {"headcount_range": "51-200"})
        self.assertEqual(sv("Acme Robotics opened a sales office in Porto."), {})
        self.assertEqual(sv("Acme Robotics is reportedly in talks to raise $40M."), {})


class NegatingPhrases(unittest.TestCase):
    def test_not_whole_word_only(self):
        self.assertEqual(sv("Acme Robotics, notably, was founded in 2014.")["founded_year"], 2014)

    def test_not_negates(self):
        self.assertEqual(sv("Acme Robotics was founded in 2014, not 2015."), {})

    def test_negation_case_insensitive(self):
        self.assertEqual(sv("Acme Robotics was REPORTEDLY founded in 2014."), {})

    def test_couldn_is_not_could(self):
        self.assertEqual(sv("Acme Robotics couldn't be founded in 2014.")["founded_year"], 2014)

    def test_former_ceo_negated(self):
        self.assertEqual(sv("Former CEO Dana Ruiz of Acme Robotics."), {})


class CeoNames(unittest.TestCase):
    def test_three_word_name(self):
        self.assertEqual(sv("Dana Maria Ruiz is CEO of Acme Robotics."),
                         {"ceo": "Dana Maria Ruiz"})

    def test_four_word_run_is_not_a_name(self):
        self.assertEqual(sv("Anna Maria Lopez Ruiz is CEO of Acme Robotics."), {})

    def test_lowercase_word_breaks_run(self):
        self.assertEqual(sv("Dana van Ruiz is CEO of Acme Robotics."), {})

    def test_company_name_removed_from_run(self):
        self.assertEqual(sv("Acme Robotics CEO Dana Ruiz."), {"ceo": "Dana Ruiz"})

    def test_comma_separates_name(self):
        self.assertEqual(sv("Dana Ruiz, CEO of Acme Robotics."), {"ceo": "Dana Ruiz"})

    def test_chief_executive_officer_removed(self):
        self.assertEqual(
            sv("Dana Ruiz is chief executive officer of Acme Robotics."), {"ceo": "Dana Ruiz"})


class HqCity(unittest.TestCase):
    def test_city_and_country_after_comma(self):
        self.assertEqual(sv("Acme Robotics is headquartered in Lisbon, Portugal."),
                         {"hq_city": "Lisbon"})

    def test_hyphen_run(self):
        self.assertEqual(sv("Acme Robotics is headquartered in Zürich-Oerlikon."),
                         {"hq_city": "Zürich-Oerlikon"})

    def test_space_run_of_capitalised_words(self):
        self.assertEqual(sv("Acme Robotics is headquartered in New York City, USA."),
                         {"hq_city": "New York City"})

    def test_lowercase_after_phrase_is_no_city(self):
        self.assertEqual(sv("Acme Robotics is headquartered in the city of Lisbon."), {})

    def test_two_cities_is_unsupported(self):
        self.assertEqual(sv("Acme Robotics is headquartered in Lisbon, based in Porto."), {})

    def test_negated_city_is_unsupported(self):
        self.assertEqual(sv("Acme Robotics plans to be based in Lisbon."), {})


class Amounts(unittest.TestCase):
    def funding(self, excerpt):
        return sv(excerpt).get("funding_total")

    def test_dollar_forms(self):
        self.assertEqual(self.funding("Acme Robotics has raised $12M."), 12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $12mn."), 12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $12m."), 12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $12.5 million."), 12_500_000)
        self.assertEqual(self.funding("Acme Robotics has raised US$12 million."), 12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised USD 12 million."), 12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $12,000,000."), 12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $3bn."), 3_000_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $2 billion."), 2_000_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $12K."), 12_000)
        self.assertEqual(self.funding("Acme Robotics has raised $ 12M."), 12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised $0.5 thousand."), 500)

    def test_number_dollars_forms(self):
        self.assertEqual(self.funding("Acme Robotics has raised 12 million dollars."),
                         12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised 12,000,000 US dollars."),
                         12_000_000)
        self.assertEqual(self.funding("Acme Robotics has raised 12 dollars."), 12)

    def test_non_whole_amounts_are_not_values(self):
        self.assertIsNone(self.funding("Acme Robotics has raised 1.5 dollars."))
        self.assertIsNone(self.funding("Acme Robotics has raised $0.5."))

    def test_other_currencies_and_bad_forms(self):
        self.assertIsNone(self.funding("Acme Robotics has raised €12M."))
        self.assertIsNone(self.funding("Acme Robotics has raised 12 million euros."))
        self.assertIsNone(self.funding("Acme Robotics has raised £12 million."))
        self.assertIsNone(self.funding("Acme Robotics has raised 12m dollars."))

    def test_amount_must_not_touch_letters(self):
        self.assertIsNone(self.funding("Acme Robotics has raised $12Mx."))

    def test_bad_thousands_grouping_is_no_number(self):
        self.assertIsNone(self.funding("Acme Robotics has raised $1,2,000."))

    def test_two_amounts_is_unsupported(self):
        self.assertIsNone(self.funding("Acme Robotics has raised $12M and $3M."))

    def test_negated_funding_unsupported(self):
        self.assertEqual(sv("Acme Robotics is reportedly in talks to raise $40M."), {})


class Years(unittest.TestCase):
    def test_year_not_part_of_amount(self):
        self.assertEqual(sv("Acme Robotics was founded and raised $2014."), {"funding_total": 2014})

    def test_founded_with_no_outside_year(self):
        self.assertEqual(sv("Acme Robotics was founded and raised $2014."),
                         {"funding_total": 2014})

    def test_year_bounds(self):
        self.assertEqual(sv("Acme Robotics was founded in 1800."), {"founded_year": 1800})
        self.assertEqual(sv("Acme Robotics was founded in 2099."), {"founded_year": 2099})
        self.assertEqual(sv("Acme Robotics was founded in 1799."), {})
        self.assertEqual(sv("Acme Robotics was founded in 2100."), {})

    def test_five_digits_not_a_year(self):
        self.assertEqual(sv("Acme Robotics was founded in 02014."), {})

    def test_two_years_unsupported(self):
        self.assertEqual(sv("Acme Robotics was founded in 2014-2015."), {})

    def test_year_mixed_with_headcount_takes_only_year(self):
        out = sv("Acme Robotics founded in 2014 with 120 employees.")
        self.assertEqual(out, {"founded_year": 2014})


class Headcount(unittest.TestCase):
    def test_range_holds_two_numbers_same_range(self):
        self.assertEqual(sv("Acme Robotics has 51-200 employees."),
                         {"headcount_range": "51-200"})
        self.assertEqual(sv("Acme Robotics has 11-50 employees."),
                         {"headcount_range": "11-50"})

    def test_range_spanning_two_ranges_unsupported(self):
        self.assertEqual(sv("Acme Robotics has 50-200 employees."), {})

    def test_thousands_separator(self):
        self.assertEqual(sv("Acme Robotics employs 1,200 people."),
                         {"headcount_range": "1001-5000"})

    def test_bounds_of_ranges(self):
        self.assertEqual(sv("Acme Robotics employs 10 people."), {"headcount_range": "1-10"})
        self.assertEqual(sv("Acme Robotics employs 10,001 people."),
                         {"headcount_range": "10001+"})
        self.assertEqual(sv("Acme Robotics employs 10,000 people."),
                         {"headcount_range": "5001-10000"})

    def test_decimal_number_is_not_headcount(self):
        self.assertEqual(sv("Acme Robotics employs 12.5 people."), {})

    def test_zero_is_not_headcount(self):
        self.assertEqual(sv("Acme Robotics employs 0 people."), {})

    def test_amount_is_not_headcount(self):
        self.assertEqual(sv("Acme Robotics employs $5M people."), {})

    def test_staff_inside_word_not_phrase(self):
        self.assertEqual(sv("Acme Robotics staffing 120."), {})


class LegalName(unittest.TestCase):
    def test_name_with_inc_suffix(self):
        self.assertEqual(sv("Acme Robotics Inc. is a registered company."),
                         {"legal_name": "Acme Robotics Inc."})

    def test_comma_inc(self):
        self.assertEqual(sv("Its legal name is Acme Robotics, Inc."),
                         {"legal_name": "Acme Robotics, Inc."})

    def test_capitalised_words_before_suffix(self):
        self.assertEqual(sv("Registered as Acme Robotics Holdings Ltd."),
                         {"legal_name": "Acme Robotics Holdings Ltd"})

    def test_uppercase_word_allowed(self):
        self.assertEqual(sv("Registered as Acme Robotics AI Inc."),
                         {"legal_name": "Acme Robotics AI Inc."})

    def test_dotted_suffix(self):
        self.assertEqual(sv("Registered as Acme Robotics S.A.S."),
                         {"legal_name": "Acme Robotics S.A.S."})

    def test_suffix_followed_by_letter_is_not_suffix(self):
        self.assertEqual(sv("Registered as Acme Robotics Incorporated."), {})

    def test_no_suffix_no_name(self):
        self.assertEqual(sv("Registered as Acme Robotics."), {})


class Headers(unittest.TestCase):
    def test_header_then_prose(self):
        headers, prose = split_header('Facts: {"ceo": "x"}\nTitle: Acme\n\nAcme was founded.')
        self.assertEqual(headers["Facts"], '{"ceo": "x"}')
        self.assertEqual(headers["Title"], "Acme")
        self.assertEqual(prose, "Acme was founded.")

    def test_no_header_when_first_line_is_not_header(self):
        headers, prose = split_header("Acme Robotics: the company\n\nBody.")
        self.assertEqual(headers, {})
        self.assertEqual(prose, "Acme Robotics: the company\n\nBody.")

    def test_header_without_empty_line_has_no_prose(self):
        headers, prose = split_header("Title: x\nBody")
        self.assertEqual(headers, {"Title": "x"})
        self.assertEqual(prose, "")

    def test_hyphenated_name(self):
        headers, _ = split_header("Last-Updated: 2026\n\nBody.")
        self.assertIn("Last-Updated", headers)


class ExcerptInProse(unittest.TestCase):
    def test_whitespace_runs_collapse(self):
        self.assertTrue(excerpt_in_prose("Acme  Robotics\nwas founded.", "Acme Robotics was founded."))

    def test_case_must_match(self):
        self.assertFalse(excerpt_in_prose("Acme Robotics was founded.", "acme robotics was founded."))

    def test_regex_characters_are_literal(self):
        self.assertTrue(excerpt_in_prose("price $12M (approx.) here", "$12M (approx.)"))
        self.assertFalse(excerpt_in_prose("price $12M here", "$12M (approx.)"))

    def test_length_bounds(self):
        self.assertFalse(excerpt_in_prose("abc", ""))
        self.assertFalse(excerpt_in_prose("x" * 501, "x" * 501))
        self.assertTrue(excerpt_in_prose("x" * 500, "x" * 500))

    def test_edge_whitespace_is_rejected_by_implementation(self):
        # Spec §4 lets whitespace runs be written as one space; leading space is not stated.
        # Recorded as an ambiguity to rule on.
        self.assertFalse(excerpt_in_prose("x Acme", " Acme"))


class ExtractSupports(unittest.TestCase):
    def test_suffix_keeps_one_sentence(self):
        supports = extract_supports(D, "Acme Robotics Inc. was founded in 2014.")
        self.assertEqual([(s.field, s.value) for s in supports], [("founded_year", 2014)])

    def test_mega_corp_splits(self):
        supports = extract_supports(
            D, "Acme Robotics was founded in 2014 by MegaCorp. Dana Ruiz leads it.")
        self.assertEqual(supports[0].excerpt,
                         "Acme Robotics was founded in 2014 by MegaCorp.")


if __name__ == "__main__":
    unittest.main()
