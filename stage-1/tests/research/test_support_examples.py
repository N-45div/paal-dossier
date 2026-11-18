"""Appendix A examples and edge rules."""
import pytest

from app.research.support import supported_values, supports

D = "acme-robotics.test"


@pytest.mark.parametrize("excerpt,field,value", [
    ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", "ceo", "Dana Ruiz"),
    ("Acme Robotics CEO: Sam Ortiz.", "ceo", "Sam Ortiz"),
    ("Acme Robotics was founded in 2014.", "founded_year", 2014),
    ("Acme Robotics employs about 120 people.", "headcount_range", "51-200"),
    ("Acme Robotics has raised $12M.", "funding_total", 12000000),
    ("Acme Robotics has raised 12 million dollars.", "funding_total", 12000000),
    ("Acme Robotics has raised US$12.5 million.", "funding_total", 12500000),
    ("Acme Robotics has raised USD 12 million.", "funding_total", 12000000),
    ("Acme Robotics has raised $12,000,000.", "funding_total", 12000000),
    ("Acme Robotics has raised 1.5 billion US dollars.", "funding_total", 1500000000),
    ("Acme Robotics is headquartered in Lisbon.", "hq_city", "Lisbon"),
    ("Acme Robotics is based in Winston-Salem, USA.", "hq_city", "Winston-Salem"),
    ("Acme Robotics is based in New York.", "hq_city", "New York"),
    ("The registered name of Acme Robotics is Acme Robotics, Inc. today.", "legal_name", "Acme Robotics, Inc."),
    ("Acme Robotics Holdings GmbH is the legal entity of acme-robotics.test.", "legal_name", "Acme Robotics Holdings GmbH"),
    ("Acme Robotics has 51-200 employees.", "headcount_range", "51-200"),
    ("Acme Robotics has 1,200 employees.", "headcount_range", "1001-5000"),
    ("Acme Robotics has 20000 employees.", "headcount_range", "10001+"),
    ("Acme Robotics employs 5,001 people.", "headcount_range", "5001-10000"),
])
def test_supported(excerpt, field, value):
    assert supports(excerpt, D, field) == value


@pytest.mark.parametrize("excerpt,field", [
    ("Acme Robotics is reportedly in talks to raise $40M.", "funding_total"),
    ("Acme Robotics opened a sales office in Porto.", "hq_city"),
    ("Acme Robotics was founded in 2014 and has raised $13M and $12M.", "funding_total"),
    ("Acme Robotics employs 120 people. It was founded in 2014.", "headcount_range"),
    ("Acme Robotics has raised EUR 12 million.", "funding_total"),
    ("Acme Robotics has raised C$12M.", "funding_total"),
    ("Acme Robotics has raised $12.0000001 million.", "funding_total"),
    ("Acme Robotics employs 51 to 300 people.", "headcount_range"),
    ("Acme Robotics employs 51-300 people.", "headcount_range"),
    ("Acme Robotics was founded in 1799.", "founded_year"),
    ("Acme Robotics was founded in $2014.", "founded_year"),
    ("Acme Robotics employs 0 people.", "headcount_range"),
    ("Acme Robotics employs 12.5 people.", "headcount_range"),
    ("Acme Robotics is headquartered in lisbon.", "hq_city"),
    ("Acme Robotics is based in Lisbon and headquartered in Porto.", "hq_city"),
    ("Dana Ruiz is chief executive. Acme Robotics grew.", "ceo"),
    ("Acme Robotics chief executive is Dana.", "ceo"),
    ("Acme Robotics chief executive is Dana Marie Anne Ruiz.", "ceo"),
    ("Acme Robotics CEO Dana Ruiz is not here.", "ceo"),
    ("Acme Robotics is based in Lisbon.", "ceo"),
    ("Other Corp was founded in 2014.", "founded_year"),
    ("Acme Robotics was founded in 2014", "hq_city"),
])
def test_not_supported(excerpt, field):
    assert supports(excerpt, D, field) is None


def test_domain_names_the_company():
    assert supports("acme-robotics.test was founded in 2014.", D, "founded_year") == 2014
    assert supports("See www.acme-robotics.test: founded in 2014.", D, "founded_year") == 2014


def test_company_word_boundaries():
    assert supports("Acme Roboticsx was founded in 2014.", D, "founded_year") is None
    assert supports("Notacme Robotics was founded in 2014.", D, "founded_year") is None


def test_case_insensitive_phrases_and_company():
    assert supports("ACME ROBOTICS WAS FOUNDED IN 2014.", D, "founded_year") == 2014


@pytest.mark.parametrize("neg", ["could", "would", "might", "former", "formerly", "reportedly",
                                 "rumoured", "seeking", "plans to", "will become", "not"])
def test_negating_phrases(neg):
    assert supports(f"Acme Robotics {neg} be founded in 2014.", D, "founded_year") is None


def test_negation_is_whole_word():
    assert supports("Acme Robotics, a notable firm, was founded in 2014.", D, "founded_year") == 2014


def test_two_sentences_are_not_supported():
    assert supports("Acme Robotics was founded in 2014. It grew.", D, "founded_year") is None
    assert supports("Acme Robotics was founded in 2014! Wow", D, "founded_year") is None


def test_legal_form_suffix_does_not_end_sentence():
    text = "Acme Robotics, Inc. was founded in 2014."
    assert supports(text, D, "founded_year") == 2014


def test_sentence_end_with_closer():
    assert supports("(Acme Robotics was founded in 2014.) Next", D, "founded_year") is None


def test_whitespace_runs_collapse():
    assert supports("Acme   Robotics\twas founded\n in 2014.", D, "founded_year") == 2014


def test_ceo_run_not_part_of_longer_run():
    assert supports("Acme Robotics CEO Anna Maria Lopez Perez leads.", D, "ceo") is None
    assert supports("Acme Robotics CEO Anna Maria Lopez leads.", D, "ceo") == "Anna Maria Lopez"


def test_ceo_non_latin_names():
    assert supports("Müller Schmidt is CEO of Acme Robotics.", D, "ceo") == "Müller Schmidt"
    assert supports("Zoë Ünal is CEO of Acme Robotics.", D, "ceo") == "Zoë Ünal"


def test_ceo_removal_separates_words():
    assert supports("Anna Acme Robotics Lopez CEO.", D, "ceo") is None


def test_amount_requires_boundaries():
    assert supports("Acme Robotics has raised $12Mx.", D, "funding_total") is None
    assert supports("Acme Robotics has raised x$12M.", D, "funding_total") is None
    assert supports("Acme Robotics has raised $1,2 million.", D, "funding_total") is None
    assert supports("Acme Robotics has raised $12k.", D, "funding_total") == 12000
    assert supports("Acme Robotics has raised $2bnx.", D, "funding_total") is None
    assert supports("Acme Robotics has raised $2bn.", D, "funding_total") == 2000000000
    assert supports("Acme Robotics has raised $2 billion.", D, "funding_total") == 2000000000
    assert supports("Acme Robotics has raised $12 thousand.", D, "funding_total") == 12000


def test_amount_does_not_leak_into_year_or_headcount():
    assert supports("Acme Robotics founded 2014 raised $2,015.", D, "founded_year") == 2014
    assert supports("Acme Robotics founded $2,015.", D, "founded_year") is None
    assert supports("Acme Robotics employs 120 people and raised $12M.", D, "headcount_range") == "51-200"


def test_numbers_joined_by_separators_are_not_numbers():
    assert supports("Acme Robotics was founded in 2014,2015.", D, "founded_year") is None
    assert supports("Acme Robotics was founded in 2014a.", D, "founded_year") is None
    assert supports("Acme Robotics was founded in 2014.", D, "founded_year") == 2014


def test_multiple_agreeing_values_support():
    assert supports("Acme Robotics was founded in 2014, established 2014.", D, "founded_year") == 2014
    assert supports("Acme Robotics employs 60 to 150 people.", D, "headcount_range") == "51-200"
