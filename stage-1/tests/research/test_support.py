"""Appendix A: which excerpts support which values (stage-1.md section 4 and Appendix A)."""

import pytest

from research.support import supports

ACME = "acme-robotics.test"
HALV = "halvorsen-robotics.test"


@pytest.mark.parametrize(
    "excerpt, domain, expected",
    [
        ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", ACME, [("ceo", "Dana Ruiz")]),
        ("Acme Robotics CEO: Sam Ortiz.", ACME, [("ceo", "Sam Ortiz")]),
        ("Acme Robotics was founded in 2014.", ACME, [("founded_year", 2014)]),
        ("Acme Robotics employs about 120 people.", ACME, [("headcount_range", "51-200")]),
        ("Acme Robotics is reportedly in talks to raise $40M.", ACME, []),
        ("Acme Robotics opened a sales office in Porto.", ACME, []),
    ],
)
def test_spec_table_examples(excerpt, domain, expected):
    assert supports(excerpt, domain) == expected


@pytest.mark.parametrize(
    "excerpt",
    [
        "Acme Robotics has raised $12M.",
        "Acme Robotics has raised 12 million dollars.",
        "Acme Robotics has raised US$12 million.",
        "Acme Robotics has raised USD 12 million.",
        "Acme Robotics has raised $12,000,000.",
        "Acme Robotics has raised $12000k.",
        "Acme Robotics has raised 12,000,000 US dollars.",
        "Acme Robotics has raised $12m.",
        "ACME ROBOTICS HAS RAISED $12 MILLION.",
    ],
)
def test_funding_forms_normalise_to_whole_dollars(excerpt):
    assert supports(excerpt, ACME) == [("funding_total", 12_000_000)]


def test_funding_bn_and_thousand():
    assert supports("Acme Robotics has raised $1.5 billion.", ACME) == [("funding_total", 1_500_000_000)]
    assert supports("Acme Robotics has raised 250 thousand dollars.", ACME) == [("funding_total", 250_000)]


def test_non_whole_dollar_amount_is_not_a_value():
    assert supports("Acme Robotics has raised $1.5.", ACME) == []


def test_other_currency_is_not_an_amount():
    assert supports("Acme Robotics has raised 12 million euros.", ACME) == []


def test_conflicting_funding_values_support_neither():
    assert supports("Acme Robotics has raised $12M and $40M.", ACME) == []


def test_company_must_be_named():
    assert supports("Dana Ruiz has led Globex as chief executive since 2021.", ACME) == []


def test_domain_names_the_company():
    assert supports("acme-robotics.test was founded in 2014.", ACME) == [("founded_year", 2014)]


def test_name_match_is_case_insensitive_and_whole_word():
    assert supports("acme robotics was founded in 2014.", ACME) == [("founded_year", 2014)]
    assert supports("Acme Roboticsx was founded in 2014.", ACME) == []


def test_multiple_fields_in_one_excerpt():
    assert sorted(supports("Acme Robotics raised $12M and was founded in 2014.", ACME)) == [
        ("founded_year", 2014),
        ("funding_total", 12_000_000),
    ]


def test_two_years_in_one_excerpt_support_neither():
    assert supports("Acme Robotics was founded in 2014 after 2010.", ACME) == []


def test_negation_blocks_every_field():
    assert supports("Acme Robotics was not founded in 2014.", ACME) == []
    assert supports("Acme Robotics, formerly known as Acme, was founded in 2014.", ACME) == []


def test_two_sentences_are_not_a_single_excerpt():
    assert supports("Acme Robotics was founded in 2014. It grew fast.", ACME) == []


@pytest.mark.parametrize(
    "excerpt, expected",
    [
        ("Acme Robotics, Inc. was founded in 2014.", [("founded_year", 2014)]),
        ("Acme Robotics is registered as Acme Robotics, Inc. in Delaware.", [("legal_name", "Acme Robotics, Inc.")]),
        ("The registered name is Acme Robotics Pty Ltd today.", [("legal_name", "Acme Robotics Pty Ltd")]),
        ("Acme Robotics legal name: Acme Robotics GmbH and partners.", [("legal_name", "Acme Robotics GmbH")]),
    ],
)
def test_legal_name_with_suffix(excerpt, expected):
    assert supports(excerpt, ACME) == expected


def test_legal_name_shortest_at_same_start_wins():
    assert supports("Acme Robotics Inc. is the registered name Acme Robotics Inc.", ACME) == [
        ("legal_name", "Acme Robotics Inc.")
    ]


def test_legal_name_requires_suffix():
    assert supports("Acme Robotics is the registered name in Delaware.", ACME) == []


def test_legal_name_with_uppercase_word_and_suffix():
    assert supports("Acme Robotics AI Corp. has a legal name.", ACME) == [("legal_name", "Acme Robotics AI Corp.")]


def test_legal_suffix_must_not_run_into_a_word():
    assert supports("Acme Robotics registered name Acme Robotics ASAP.", ACME) == []


def test_hq_city_longest_capitalised_run_after_phrase():
    assert supports("Acme Robotics is headquartered in New York City.", ACME) == [("hq_city", "New York City")]


def test_hq_city_stops_at_punctuation():
    assert supports("Based in Valencia, Acme Robotics serves customers.", ACME) == [("hq_city", "Valencia")]


def test_hq_city_hyphen_join():
    assert supports("Acme Robotics is based in Porto-Alegre.", ACME) == [("hq_city", "Porto-Alegre")]


def test_hq_city_unicode_capitalised_word():
    assert supports("Acme Robotics is based in Zürich.", ACME) == [("hq_city", "Zürich")]


def test_hq_city_needs_exactly_one_space_after_phrase():
    assert supports("Acme Robotics is based in  Zürich.", ACME) == [("hq_city", "Zürich")]
    assert supports("Acme Robotics is based in the Zürich area.", ACME) == []


def test_ceo_run_of_two_or_three_words():
    assert supports("Acme Robotics is led by chief executive Marcus Abbott Jr today.", ACME) == [
        ("ceo", "Marcus Abbott Jr")
    ]


def test_ceo_run_of_four_words_is_not_a_name():
    assert supports("Acme Robotics is led by Marcus Van Der Berg.", ACME) == []


def test_ceo_name_next_to_company_name_is_separated():
    assert supports("Dana Ruiz, CEO of Acme Robotics, leads the team.", ACME) == [("ceo", "Dana Ruiz")]


def test_headcount_stated_range_holds_two_numbers_in_one_band():
    assert supports("Acme Robotics employs 51-200 employees.", ACME) == [("headcount_range", "51-200")]


def test_headcount_range_across_bands_supports_neither():
    assert supports("Acme Robotics employs 101-500 employees.", ACME) == []


def test_headcount_comma_number():
    assert supports("Estimated staff at Acme Robotics: 3,148 employees.", ACME) == [
        ("headcount_range", "1001-5000")
    ]


def test_headcount_boundaries():
    assert supports("Acme Robotics employs 10 people.", ACME) == [("headcount_range", "1-10")]
    assert supports("Acme Robotics employs 10001 people.", ACME) == [("headcount_range", "10001+")]


def test_headcount_decimal_is_not_a_value():
    assert supports("Acme Robotics employs 12.5 people.", ACME) == []


def test_headcount_number_inside_amount_is_not_a_value():
    assert supports("Acme Robotics employs people and raised $12M.", ACME) == [
        ("funding_total", 12_000_000)
    ]


def test_founded_year_bounds_and_format():
    assert supports("Acme Robotics was founded in 1799.", ACME) == []
    assert supports("Acme Robotics was founded in 1800.", ACME) == [("founded_year", 1800)]
    assert supports("Acme Robotics was founded in 2099.", ACME) == [("founded_year", 2099)]
    assert supports("Acme Robotics was founded in 2,014.", ACME) == []


def test_digit_next_to_letter_is_not_a_number():
    assert supports("Acme Robotics was founded in x2014.", ACME) == []


def test_empty_excerpt_supports_nothing():
    assert supports("   ", ACME) == []


def test_halvorsen_examples_from_corpus_shapes():
    assert supports(
        "Halvorsen Robotics trades under the registered name Halvorsen Robotics AS in all of its markets.", HALV
    ) == [("legal_name", "Halvorsen Robotics AS")]
    assert supports("As CEO of Halvorsen Robotics, Priya Dalton sets the company's direction.", HALV) == [
        ("ceo", "Priya Dalton")
    ]
