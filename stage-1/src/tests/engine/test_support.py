"""Appendix A: when an excerpt supports a value (R1.146-R1.162)."""

import pytest

from dossier.engine.support import supported_values, supports

D = "acme-robotics.test"


def sv(text, domain=D):
    return supported_values(text, domain)


# R1.148: the examples of A.2, verbatim.
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", [("ceo", "Dana Ruiz")]),
        ("Acme Robotics CEO: Sam Ortiz.", [("ceo", "Sam Ortiz")]),
        ("Acme Robotics was founded in 2014.", [("founded_year", 2014)]),
        ("Acme Robotics employs about 120 people.", [("headcount_range", "51-200")]),
        ("Acme Robotics is reportedly in talks to raise $40M.", []),
        ("Acme Robotics opened a sales office in Porto.", []),
    ],
)
def test_spec_examples(text, expected):
    assert sv(text) == expected


# R1.55: the funding and headcount examples.
def test_funding_examples_support_the_same_value():
    assert sv("Acme Robotics has raised $12M.") == [("funding_total", 12000000)]
    assert sv("Acme Robotics has raised 12 million dollars.") == [("funding_total", 12000000)]


def test_headcount_example_supports_range_containing_the_number():
    assert supports("Acme Robotics employs about 120 people.", D, "headcount_range", "51-200")


# R1.145 / R1.146 item 1: a single sentence only.
def test_two_sentences_support_nothing():
    assert sv("Acme Robotics was founded in 2014. It is big.") == []


def test_sentence_with_legal_suffix_dot_is_single():
    assert sv("Acme Robotics, Inc. was founded in 2014.") == [("founded_year", 2014)]


def test_newline_inside_excerpt_is_a_space_so_it_is_one_sentence():
    assert sv("Acme Robotics was\nfounded in 2014.") == [("founded_year", 2014)]


def test_empty_excerpt_supports_nothing():
    assert sv("   ") == []


# R1.146 item 2: naming the company, by name or domain, whole words, any case.
@pytest.mark.parametrize(
    "text",
    [
        "ACME ROBOTICS was founded in 2014.",
        "acme robotics was founded in 2014.",
        "Acme-Robotics.test was founded in 2014.",
        "The acme-robotics.test site: founded in 2014.",
    ],
)
def test_company_named_by_name_or_domain_any_case(text):
    assert ("founded_year", 2014) in sv(text)


@pytest.mark.parametrize(
    "text",
    [
        "Acme RoboticsX was founded in 2014.",  # name followed by a letter
        "Acme RoboticsX was founded in 2014.",
        "Acme was founded in 2014.",  # the first label alone is not the name
        "Other Robotics was founded in 2014.",
        "Xacme Robotics was founded in 2014.",  # name preceded by a letter
    ],
)
def test_other_company_names_do_not_match(text):
    assert sv(text) == []


def test_name_alone_for_single_label_domain():
    assert ("founded_year", 2014) in sv("Acme was founded in 2014.", "acme.test")


# R1.146 item 3 and 4: a statement phrase, and no negating phrase.
@pytest.mark.parametrize(
    "negator",
    [
        "in talks to", "plans to", "planning to", "wants to", "expects to", "hopes to",
        "aims to", "seeking", "could", "would", "might", "reportedly", "rumoured",
        "former", "formerly", "will become", "not",
    ],
)
def test_each_negating_phrase_blocks_support(negator):
    assert sv(f"Acme Robotics {negator} be founded in 2014.") == []


def test_negating_phrase_matches_whole_words_only():
    assert sv("Acme Robotics cannot be undone; it was founded in 2014.") == [("founded_year", 2014)]
    assert sv("Acme Robotics Notes: it was founded in 2014.") == [("founded_year", 2014)]


def test_negation_is_case_insensitive():
    assert sv("Acme Robotics REPORTEDLY was founded in 2014.") == []


def test_statement_phrase_must_be_present():
    assert sv("Acme Robotics is 2014 years old.") == []


def test_statement_phrase_matches_whole_words_only():
    assert sv("Acme Robotics was foundedly born in 2014.") == []


# R1.149: the statement phrases of each field.
@pytest.mark.parametrize(
    "phrase",
    ["legal name", "registered name", "registered as", "registered company",
     "legal entity", "name of record"],
)
def test_legal_name_statement_phrases(phrase):
    assert ("legal_name", "Acme Robotics, Inc.") in sv(f"Its {phrase} is Acme Robotics, Inc.")


@pytest.mark.parametrize(
    "phrase",
    ["headquartered in", "headquarters in", "head office in", "based in",
     "registered office in", "registered seat in"],
)
def test_hq_city_statement_phrases(phrase):
    assert sv(f"Acme Robotics is {phrase} Lisbon.") == [("hq_city", "Lisbon")]


@pytest.mark.parametrize("phrase", ["founding", "established", "incorporated"])
def test_founded_year_statement_phrases(phrase):
    assert sv(f"Acme Robotics {phrase} in 2014.") == [("founded_year", 2014)]


@pytest.mark.parametrize("phrase", ["employees", "staff", "headcount", "workforce"])
def test_headcount_statement_phrases(phrase):
    assert sv(f"Acme Robotics has 120 {phrase}.") == [("headcount_range", "51-200")]


@pytest.mark.parametrize("phrase", ["funding", "invested", "investment"])
def test_funding_statement_phrases(phrase):
    assert sv(f"Acme Robotics {phrase} of $12M.") == [("funding_total", 12000000)]


@pytest.mark.parametrize("phrase", ["chief executive officer", "chief executive", "CEO"])
def test_ceo_statement_phrases(phrase):
    assert sv(f"Dana Ruiz is the {phrase} of Acme Robotics.") == [("ceo", "Dana Ruiz")]


def test_ceo_phrase_is_case_insensitive():
    assert sv("Acme Robotics ceo: Sam Ortiz.") == [("ceo", "Sam Ortiz")]


# R1.151-R1.152: the building blocks of the formats.
def test_capitalised_word_accepts_unicode_letters():
    assert sv("Acme Robotics is headquartered in Zürich.") == [("hq_city", "Zürich")]
    assert sv("Acme Robotics is headquartered in Müller.") == [("hq_city", "Müller")]


def test_capitalised_word_rejects_mixed_case_inside_word():
    assert sv("Acme Robotics is headquartered in McDonald.") == []
    assert sv("Acme Robotics is headquartered in LISBON.") == []


def test_number_joined_to_letters_is_not_a_number():
    assert sv("Acme Robotics was founded in Q2014.") == []
    assert sv("Acme Robotics was founded in 2014x.") == []


def test_digits_joined_by_separators_are_not_a_number():
    assert sv("Acme Robotics was founded in 2.014.") == []
    assert sv("Acme Robotics was founded in 2,014.") == []
    assert sv("Acme Robotics was founded in 20.14.") == []


def test_year_and_number_boundaries_before_and_after_punctuation():
    assert sv("Acme Robotics was founded in 2014.") == [("founded_year", 2014)]
    assert sv("Acme Robotics was founded (2014).") == [("founded_year", 2014)]


# R1.156: founded_year is a four-digit number from 1800 to 2099.
@pytest.mark.parametrize("year", ["1800", "2014", "2099"])
def test_founded_year_bounds_inclusive(year):
    assert sv(f"Acme Robotics was founded in {year}.") == [("founded_year", int(year))]


@pytest.mark.parametrize("year", ["1799", "2100", "999", "20140", "2014.0"])
def test_founded_year_out_of_range_or_not_four_digits(year):
    assert sv(f"Acme Robotics was founded in {year}.") == []


# R1.157: headcount numbers are integers of 1 or more, ranges per §4.
@pytest.mark.parametrize(
    "count, label",
    [
        (1, "1-10"), (10, "1-10"), (11, "11-50"), (50, "11-50"), (51, "51-200"),
        (200, "51-200"), (201, "201-500"), (500, "201-500"), (501, "501-1000"),
        (1000, "501-1000"), (1001, "1001-5000"), (5000, "1001-5000"),
        (5001, "5001-10000"), (10000, "5001-10000"), (10001, "10001+"),
        (1_000_000, "10001+"),
    ],
)
def test_headcount_range_boundaries(count, label):
    assert sv(f"Acme Robotics employs {count} people.") == [("headcount_range", label)]


def test_headcount_with_thousands_separator():
    assert sv("Acme Robotics employs 1,200 people.") == [("headcount_range", "1001-5000")]


def test_headcount_zero_is_not_a_value():
    assert sv("Acme Robotics employs 0 people.") == []


def test_headcount_decimal_is_not_a_value():
    assert sv("Acme Robotics employs 12.5 people.") == []


def test_headcount_words_before_number_do_not_matter():
    assert sv("Acme Robotics employs roughly 120 people.") == [("headcount_range", "51-200")]


def test_headcount_stated_range_holds_two_numbers_in_one_range():
    assert sv("Acme Robotics has 51-200 employees.") == [("headcount_range", "51-200")]


def test_headcount_stated_range_across_ranges_is_unsupported():
    assert sv("Acme Robotics has 40-120 employees.") == []


def test_headcount_two_different_ranges_is_unsupported():
    assert sv("Acme Robotics employs 20 and 300 people.") == []


def test_headcount_with_year_in_same_sentence_conflicts():
    # 2014 is a headcount number too (1001-5000), so the two values disagree.
    assert sv("Acme Robotics was founded in 2014 and employs 120 people.") == [
        ("founded_year", 2014)
    ]


# R1.160-R1.162: amounts and their normalisation.
@pytest.mark.parametrize(
    "amount, dollars",
    [
        ("$12M", 12_000_000),
        ("$12m", 12_000_000),
        ("$12.5 million", 12_500_000),
        ("US$12 million", 12_000_000),
        ("USD 12 million", 12_000_000),
        ("$12,000,000", 12_000_000),
        ("$12k", 12_000),
        ("$12 thousand", 12_000),
        ("$12mn", 12_000_000),
        ("$1.5bn", 1_500_000_000),
        ("$2 billion", 2_000_000_000),
        ("12 million dollars", 12_000_000),
        ("12,000,000 US dollars", 12_000_000),
        ("12 US dollars", 12),
        ("$ 12", 12),
        ("usd 12 MILLION", 12_000_000),
        ("12 Million Dollars", 12_000_000),
    ],
)
def test_amount_forms_and_scales(amount, dollars):
    assert sv(f"Acme Robotics has raised {amount}.") == [("funding_total", dollars)]


def test_amount_that_is_not_whole_dollars_is_not_a_value():
    assert sv("Acme Robotics has raised $0.5.") == []
    assert sv("Acme Robotics has raised $1.0001 thousand.") == []


def test_non_whole_amount_is_ignored_next_to_a_whole_one():
    assert sv("Acme Robotics has raised $12M and $0.5.") == [("funding_total", 12_000_000)]


def test_other_currencies_are_not_amounts():
    assert sv("Acme Robotics has raised €12 million.") == []
    assert sv("Acme Robotics has raised 12 million euros.") == []


def test_amount_must_not_be_followed_by_a_letter():
    assert sv("Acme Robotics has raised $12Mx.") == []
    assert sv("Acme Robotics has raised 12 million dollarsx.") == []


def test_amount_must_not_be_preceded_by_a_letter():
    assert sv("Acme Robotics has raised A$12M.") == []


def test_different_amounts_are_unsupported():
    assert sv("Acme Robotics has raised $12M and $40M.") == []


def test_same_amount_written_twice_is_supported():
    assert sv("Acme Robotics has raised $12M, or 12 million dollars.") == [
        ("funding_total", 12_000_000)
    ]


def test_amount_numbers_are_not_headcount():
    assert sv("Acme Robotics has raised $12 million dollars.") == [
        ("funding_total", 12_000_000)
    ]


def test_amount_number_is_not_a_founded_year():
    assert sv("Acme Robotics was founded and raised $2014.") == [("funding_total", 2014)]


# R1.153: legal_name.
@pytest.mark.parametrize(
    "text, value",
    [
        ("Acme Robotics, Inc. was registered as a company.", "Acme Robotics, Inc."),
        ("Its registered name is Acme Robotics Inc.", "Acme Robotics Inc."),
        ("Its legal name is Acme Robotics Systems, LLC.", "Acme Robotics Systems, LLC"),
        ("Its legal name is Acme Robotics Holdings Inc.", "Acme Robotics Holdings Inc."),
        ("Its legal name is Acme Robotics GmbH.", "Acme Robotics GmbH"),
        ("Its legal name is Acme Robotics A/S.", "Acme Robotics A/S"),
        ("Its legal name is Acme Robotics S.A.S.", "Acme Robotics S.A.S."),
        ("Its legal name is Acme Robotics Pty Ltd.", "Acme Robotics Pty Ltd"),
        ("Its legal name is acme-robotics.test, Inc.", "acme-robotics.test, Inc."),
        ("Its legal name is acme robotics Inc.", "acme robotics Inc."),
    ],
)
def test_legal_name_values(text, value):
    assert ("legal_name", value) in sv(text)


def test_legal_name_shortest_text_wins_at_same_start():
    assert ("legal_name", "Acme Robotics Inc.") in sv("Its legal name is Acme Robotics Inc. ok.")


def test_legal_name_requires_the_suffix():
    assert sv("Its legal name is Acme Robotics Systems.") == []


def test_legal_name_suffix_must_not_run_into_letters():
    assert sv("Its legal name is Acme Robotics Incorporated.") == []


def test_legal_name_suffix_is_case_sensitive():
    assert sv("Its legal name is Acme Robotics inc.") == []


def test_legal_name_must_start_with_company_name():
    assert sv("Its legal name is Beta Robotics Inc.") == []


def test_legal_name_word_must_be_capitalised_or_uppercase():
    assert sv("Its legal name is Acme Robotics systems Inc.") == []
    assert sv("Its legal name is Acme Robotics AI Inc.") == [
        ("legal_name", "Acme Robotics AI Inc.")
    ]


def test_legal_name_two_different_values_is_unsupported():
    assert sv("Its legal name is Acme Robotics Inc., formerly Acme Robotics Corp.") == []
    assert sv("Acme Robotics Inc. acquired Acme Robotics Corp. as a legal name.") == []


def test_legal_name_is_as_the_excerpt_writes_it():
    assert ("legal_name", "Acme Robotics, Inc.") in sv("Its legal name is Acme Robotics, Inc. today.")


# R1.154: hq_city.
@pytest.mark.parametrize(
    "text, city",
    [
        ("Acme Robotics is headquartered in Lisbon, Portugal.", "Lisbon"),
        ("Acme Robotics is headquartered in New York City.", "New York City"),
        ("Acme Robotics is based in Winston-Salem, NC.", "Winston-Salem"),
        ("Acme Robotics is based in Rio de Janeiro.", "Rio"),
        ("Acme Robotics is based in Zürich.", "Zürich"),
        ("Acme Robotics is based in Porto Alegre and Lisbon.", "Porto Alegre"),
    ],
)
def test_hq_city_longest_run(text, city):
    assert sv(text) == [("hq_city", city)]


def test_hq_city_must_follow_phrase_directly():
    assert sv("Acme Robotics is based, in fact, Lisbon.") == []
    assert sv("Acme Robotics is based in the Lisbon area.") == []


def test_hq_city_uppercase_word_is_not_a_place():
    assert sv("Acme Robotics is based in NYC.") == []


def test_hq_city_two_places_is_unsupported():
    assert sv("Acme Robotics is based in Lisbon and headquartered in Porto.") == []


# R1.154: the sentence about a non-HQ office is not an HQ statement.
def test_office_location_is_not_hq():
    assert sv("Acme Robotics opened a sales office in Porto.") == []


# R1.155: ceo.
@pytest.mark.parametrize(
    "text, name",
    [
        ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", "Dana Ruiz"),
        ("Acme Robotics CEO: Sam Ortiz.", "Sam Ortiz"),
        ("Acme Robotics chief executive Dana Maria Ruiz.", "Dana Maria Ruiz"),
        ("Acme Robotics chief executive officer Ana Bela Costa.", "Ana Bela Costa"),
        ("Dana Ruiz, chief executive of Acme Robotics.", "Dana Ruiz"),
        ("Acme Robotics chief executive Müller Zürich.", "Müller Zürich"),
    ],
)
def test_ceo_names(text, name):
    assert ("ceo", name) in sv(text)


def test_ceo_single_capitalised_word_is_not_a_name():
    assert sv("Acme Robotics CEO: Ruiz.") == []


def test_ceo_run_of_four_words_is_not_a_name():
    assert sv("Acme Robotics CEO: Dana Maria Ruiz Gomez.") == []


def test_ceo_company_name_separates_words():
    assert sv("Dana Ruiz Acme Robotics CEO.") == [("ceo", "Dana Ruiz")]


def test_ceo_two_different_people_is_unsupported():
    assert sv("Dana Ruiz is CEO of Acme Robotics, succeeding Sam Ortiz.") == []


def test_ceo_same_person_twice_is_supported():
    assert sv("Dana Ruiz is CEO of Acme Robotics; Dana Ruiz leads it.") == [
        ("ceo", "Dana Ruiz")
    ]


def test_ceo_lowercase_word_breaks_run():
    assert sv("Acme Robotics CEO: Dana ruiz Gomez.") == []


def test_ceo_run_joined_by_hyphen_is_not_a_space_run():
    assert sv("Acme Robotics CEO: Jean-Luc Picard.") == [("ceo", "Luc Picard")]


def test_ceo_with_company_name_only_as_domain_is_not_removed():
    # Only the company's name is taken out; the lower-case domain is not a capitalised word.
    assert sv("Dana Ruiz, CEO of acme-robotics.test.") == [("ceo", "Dana Ruiz")]


# Support is decided per field; a sentence can support several fields.
def test_one_sentence_supports_several_fields():
    text = "Acme Robotics, Inc. was founded in 2014 and is headquartered in Lisbon."
    assert sv(text) == [("hq_city", "Lisbon"), ("founded_year", 2014)]


def test_supports_compares_string_and_integer_values():
    assert supports("Acme Robotics was founded in 2014.", D, "founded_year", "2014")
    assert supports("Acme Robotics was founded in 2014.", D, "founded_year", 2014)
    assert not supports("Acme Robotics was founded in 2014.", D, "founded_year", 2015)
    assert not supports("Acme Robotics was founded in 2014.", D, "ceo", "Dana Ruiz")


def test_domain_argument_is_case_insensitive():
    assert sv("Acme Robotics was founded in 2014.", "Acme-Robotics.test") == [
        ("founded_year", 2014)
    ]
