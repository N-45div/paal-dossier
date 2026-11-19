"""Appendix A: the spec's own examples and the rule's edge cases."""

import pytest

from app.research.support import company_name, supported_values, supports

D = "acme-robotics.test"


@pytest.mark.parametrize(
    "excerpt,field,value",
    [
        ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", "ceo", "Dana Ruiz"),
        ("Acme Robotics CEO: Sam Ortiz.", "ceo", "Sam Ortiz"),
        ("Acme Robotics was founded in 2014.", "founded_year", 2014),
        ("Acme Robotics employs about 120 people.", "headcount_range", "51-200"),
        ("Acme Robotics has raised $12M.", "funding_total", 12_000_000),
        ("Acme Robotics has raised 12 million dollars.", "funding_total", 12_000_000),
    ],
)
def test_spec_examples_support(excerpt, field, value):
    assert supports(excerpt, D, field, value)
    assert supported_values(excerpt, D) == {field: value}


@pytest.mark.parametrize(
    "excerpt",
    [
        "Acme Robotics is reportedly in talks to raise $40M.",
        "Acme Robotics opened a sales office in Porto.",
    ],
)
def test_spec_examples_support_nothing(excerpt):
    assert supported_values(excerpt, D) == {}


def test_company_name_is_first_label_with_spaces():
    assert company_name(D) == "acme robotics"


def test_domain_names_the_company():
    assert supports("acme-robotics.test was founded in 2014.", D, "founded_year", 2014)


def test_unnamed_company_supports_nothing():
    assert supported_values("Other Corp was founded in 2014.", D) == {}


def test_whole_word_company_name():
    assert supported_values("Acme Roboticsx was founded in 2014.", D) == {}


def test_two_sentences_is_not_single():
    assert supported_values("Acme Robotics was founded in 2014. It is nice.", D) == {}


@pytest.mark.parametrize("negation", ["could", "would", "might", "not", "plans to", "formerly", "former", "seeking"])
def test_negating_phrases_block(negation):
    assert supported_values(f"Acme Robotics {negation} be founded in 2014.", D) == {}


def test_negation_is_whole_word():
    assert supports("Acme Robotics was founded in 2014 in Knotting Hill.", D, "founded_year", 2014)


def test_missing_statement_phrase():
    assert supported_values("Acme Robotics launched in 2014.", D) == {}


def test_case_insensitive_phrases():
    assert supports("ACME ROBOTICS WAS FOUNDED IN 2014.", D, "founded_year", 2014)


# founded_year
def test_year_must_be_four_digits_in_range():
    assert supported_values("Acme Robotics was founded in 1799.", D) == {}
    assert supported_values("Acme Robotics was founded in 2100.", D) == {}
    assert supports("Acme Robotics was founded in 1800.", D, "founded_year", 1800)
    assert supports("Acme Robotics was founded in 2099.", D, "founded_year", 2099)


def test_conflicting_years_support_nothing():
    assert supported_values("Acme Robotics was founded in 2014 and incorporated in 2015.", D) == {}


def test_agreeing_years_support():
    assert supports("Acme Robotics was founded in 2014 and incorporated in 2014.", D, "founded_year", 2014)


def test_year_in_amount_is_not_a_year():
    assert supported_values("Acme Robotics was founded after it raised $2014.", D).get("founded_year") is None


# headcount_range
@pytest.mark.parametrize(
    "count,expected",
    [("1", "1-10"), ("10", "1-10"), ("11", "11-50"), ("50", "11-50"), ("51", "51-200"), ("200", "51-200"),
     ("201", "201-500"), ("500", "201-500"), ("501", "501-1000"), ("1,000", "501-1000"),
     ("1,001", "1001-5000"), ("5000", "1001-5000"), ("5001", "5001-10000"), ("10,000", "5001-10000"),
     ("10,001", "10001+"), ("250000", "10001+")],
)
def test_headcount_boundaries(count, expected):
    assert supports(f"Acme Robotics employs {count} people.", D, "headcount_range", expected)


def test_headcount_zero_and_decimal_are_no_value():
    assert supported_values("Acme Robotics employs 0 people.", D) == {}
    assert supported_values("Acme Robotics employs 12.5 people.", D) == {}


def test_headcount_range_inside_one_range_supports():
    assert supports("Acme Robotics has 51-200 employees.", D, "headcount_range", "51-200")
    assert supports("Acme Robotics has 60-90 employees.", D, "headcount_range", "51-200")


def test_headcount_range_across_ranges_supports_nothing():
    assert supported_values("Acme Robotics has 40-90 employees.", D) == {}


def test_headcount_ignores_amounts():
    assert supports("Acme Robotics employs 120 people and raised $5M.", D, "headcount_range", "51-200")


# funding_total
@pytest.mark.parametrize(
    "amount,value",
    [
        ("$12M", 12_000_000), ("$12m", 12_000_000), ("$12.5 million", 12_500_000), ("US$12 million", 12_000_000),
        ("USD 12 million", 12_000_000), ("$12,000,000", 12_000_000), ("$800k", 800_000), ("$800 thousand", 800_000),
        ("$1.5bn", 1_500_000_000), ("$3 billion", 3_000_000_000), ("$7mn", 7_000_000), ("12,000,000 US dollars", 12_000_000),
        ("12 million dollars", 12_000_000), ("500 dollars", 500), ("$12 Million", 12_000_000), ("usd12m", 12_000_000),
    ],
)
def test_amount_forms(amount, value):
    assert supports(f"Acme Robotics has raised {amount}.", D, "funding_total", value)


@pytest.mark.parametrize("amount", ["EUR 12 million", "€12M", "12 euros", "£5m", "AUD$12M", "$12Mx", "$1.0000005M"])
def test_not_an_amount(amount):
    assert "funding_total" not in supported_values(f"Acme Robotics has raised {amount}.", D)


def test_two_different_amounts_support_nothing():
    assert supported_values("Acme Robotics has raised $12M and $14M.", D) == {}


def test_two_equal_amounts_support():
    assert supports("Acme Robotics has raised $12M, or 12 million dollars.", D, "funding_total", 12_000_000)


def test_fractional_dollar_amount_is_not_a_value():
    assert supports("Acme Robotics has raised $12M and $0.5.", D, "funding_total", 12_000_000)


# hq_city
def test_hq_city_runs():
    assert supports("Acme Robotics is headquartered in Lisbon.", D, "hq_city", "Lisbon")
    assert supports("Acme Robotics is based in San Francisco, California.", D, "hq_city", "San Francisco")
    assert supports("Acme Robotics is based in Stratford-Upon-Avon.", D, "hq_city", "Stratford-Upon-Avon")
    assert supports("Acme Robotics has its registered office in Zürich.", D, "hq_city", "Zürich")


def test_hq_city_needs_capitalised_word():
    assert supported_values("Acme Robotics is based in the north.", D) == {}
    assert supported_values("Acme Robotics is based in USA.", D) == {}


def test_hq_city_two_places_conflict():
    assert supported_values("Acme Robotics is based in Lisbon and headquartered in Porto.", D) == {}


def test_hq_city_phrases():
    for phrase in ["headquarters in", "head office in", "registered seat in"]:
        assert supports(f"Acme Robotics has its {phrase} Oslo.", D, "hq_city", "Oslo")


# ceo
def test_ceo_two_or_three_words():
    assert supports("Dana Maria Ruiz is chief executive officer of Acme Robotics.", D, "ceo", "Dana Maria Ruiz")


def test_ceo_one_or_four_words_is_nothing():
    assert supported_values("Dana is the CEO of Acme Robotics.", D) == {}
    assert supported_values("Anna Maria Lucia Ruiz is the CEO of Acme Robotics.", D) == {}


def test_ceo_company_name_separates_words():
    assert supports("Acme Robotics CEO Dana Ruiz.", D, "ceo", "Dana Ruiz")
    assert supported_values("Dana Acme Robotics Ruiz is the CEO.", D) == {}


def test_ceo_two_names_conflict():
    assert supported_values("Dana Ruiz succeeded Sam Ortiz as chief executive of Acme Robotics.", D) == {}


# legal_name
def test_legal_name_forms():
    cases = [
        ("The registered name of Acme Robotics is Acme Robotics, Inc., and so on.", "Acme Robotics, Inc."),
        ("Acme Robotics Inc. is the registered company.", "Acme Robotics Inc."),
        ("Acme Robotics Ltd is the legal entity.", "Acme Robotics Ltd"),
        ("The legal name is Acme Robotics Holdings GmbH.", "Acme Robotics Holdings GmbH"),
        ("registered as acme-robotics.test S.p.A. for Acme Robotics.", "acme-robotics.test S.p.A."),
        ("Acme Robotics Pty Ltd is the registered company.", "Acme Robotics Pty Ltd"),
        ("Acme Robotics, S.A.S. is the registered name.", "Acme Robotics, S.A.S."),
    ]
    for excerpt, value in cases:
        assert supports(excerpt, D, "legal_name", value), excerpt


def test_legal_name_shortest_wins():
    assert supports("Acme Robotics AS Corp. is the registered name.", D, "legal_name", "Acme Robotics AS")


def test_legal_name_needs_suffix():
    assert supported_values("Acme Robotics is the registered name of the firm.", D) == {}


def test_legal_name_suffix_not_followed_by_letter():
    assert supported_values("The registered name Acme Robotics ASx.", D) == {}


def test_legal_suffix_is_case_sensitive():
    assert supported_values("The registered name Acme Robotics inc.", D) == {}


def test_amount_prefix_must_not_follow_a_letter():
    assert "funding_total" not in supported_values("Acme Robotics has raised xUSD12M.", D)


def test_four_digit_year_written_with_a_thousands_comma_counts():
    assert supports("Acme Robotics was founded in 2,014.", D, "founded_year", 2014)
    assert supported_values("Acme Robotics founded 1800 and 2,014.", D) == {}


def test_legal_name_shortest_text_wins_even_when_the_suffix_word_repeats():
    sentence = "THE REGISTER RECORDS ACME ROBOTICS AS AS THE REGISTERED NAME OF THE COMPANY TRADING AS ACME ROBOTICS."
    assert supported_values(sentence, D)["legal_name"] == "ACME ROBOTICS AS"
