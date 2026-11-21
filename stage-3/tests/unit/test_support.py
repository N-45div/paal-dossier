"""Unit tests for app/support.py: Appendix A and the §4 page and excerpt rules.

Run from stage-1/:  python -m pytest tests/unit
"""

import pytest

from app.support import (
    FIELDS,
    LEGAL_SUFFIXES,
    excerpt_in_prose,
    extract_supports,
    prose_sentences,
    split_header,
    split_sentences,
    supported_values,
)

DOMAIN = "acme-robotics.test"


def support(sentence, domain=DOMAIN):
    return supported_values(domain, sentence)


# --- §4 fields and Appendix A.2 examples -----------------------------------


def test_fields_are_the_six_names_in_order():
    assert FIELDS == (
        "legal_name",
        "hq_city",
        "ceo",
        "founded_year",
        "headcount_range",
        "funding_total",
    )


@pytest.mark.parametrize(
    "sentence, expected",
    [
        ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", {"ceo": "Dana Ruiz"}),
        ("Acme Robotics CEO: Sam Ortiz.", {"ceo": "Sam Ortiz"}),
        ("Acme Robotics was founded in 2014.", {"founded_year": 2014}),
        ("Acme Robotics employs about 120 people.", {"headcount_range": "51-200"}),
        ("Acme Robotics is reportedly in talks to raise $40M.", {}),
        ("Acme Robotics opened a sales office in Porto.", {}),
    ],
)
def test_appendix_a2_examples(sentence, expected):
    assert support(sentence) == expected


def test_funding_written_two_ways_normalises_identically():
    assert support("Acme Robotics has raised $12M.") == {"funding_total": 12_000_000}
    assert support("Acme Robotics has raised 12 million dollars.") == {"funding_total": 12_000_000}


def test_headcount_with_about_is_a_range():
    assert support("Acme Robotics has about 120 employees.") == {"headcount_range": "51-200"}


# --- A.1 sentences ------------------------------------------------------------


def test_legal_suffix_dot_does_not_end_a_sentence():
    assert split_sentences("Acme Robotics, Inc. was founded in 2014. It grew.") == [
        "Acme Robotics, Inc. was founded in 2014.",
        "It grew.",
    ]


def test_every_legal_suffix_with_its_dot_keeps_one_sentence():
    for suffix in LEGAL_SUFFIXES:
        if suffix.endswith("."):
            line = f"Acme Robotics {suffix} is based in Lisbon."
            assert split_sentences(line) == [line], suffix


def test_suffix_dot_needs_whole_word():
    # "XInc." ends with a letter before Inc, so the dot does end the sentence.
    assert split_sentences("Acme XInc. is based in Lisbon.") == [
        "Acme XInc.",
        "is based in Lisbon.",
    ]


def test_closing_quote_and_paren_stay_with_the_sentence():
    assert split_sentences('He said "Acme Robotics is in Lisbon." Then he left.') == [
        'He said "Acme Robotics is in Lisbon."',
        "Then he left.",
    ]
    assert split_sentences("Acme (founded 2014). Next.") == [
        "Acme (founded 2014).",
        "Next.",
    ]


def test_decimal_point_does_not_split():
    assert split_sentences("Revenue was 12.5 million.") == ["Revenue was 12.5 million."]


def test_exclamation_and_question_end_sentences():
    assert split_sentences("Wow! Who is the CEO? Dana Ruiz.") == [
        "Wow!",
        "Who is the CEO?",
        "Dana Ruiz.",
    ]


def test_empty_sentences_are_dropped():
    assert split_sentences("  .  ") == ["."]
    assert split_sentences("   ") == []


def test_prose_is_split_at_line_breaks_first():
    assert prose_sentences("First line\nSecond. Third") == [
        "First line",
        "Second.",
        "Third",
    ]


def test_excerpt_with_two_sentences_supports_nothing():
    assert support("Acme Robotics was founded in 2014. Acme Robotics raised $12M.") == {}


def test_whitespace_runs_are_one_space_for_single_sentence_test():
    assert support("Acme   Robotics\nwas founded\tin 2014.") == {"founded_year": 2014}


# --- A.2 rule: naming, statement, negation, uniqueness ----------------------


def test_company_named_by_domain_or_name_case_insensitively():
    assert support("ACME ROBOTICS WAS FOUNDED IN 2014.") == {"founded_year": 2014}
    assert support("acme-robotics.test was founded in 2014.") == {"founded_year": 2014}


def test_name_must_be_whole_word():
    assert support("Acme Roboticsy was founded in 2014.") == {}
    assert support("Acme Robotics2 was founded in 2014.") == {}


def test_sentence_without_company_supports_nothing():
    assert support("Globex was founded in 2014.") == {}


def test_statement_phrase_must_be_whole_word():
    assert support("Acme Robotics was foundedly 2014.") == {}


@pytest.mark.parametrize(
    "negation",
    [
        "in talks to",
        "plans to",
        "planning to",
        "wants to",
        "expects to",
        "hopes to",
        "aims to",
        "seeking",
        "could",
        "would",
        "might",
        "reportedly",
        "rumoured",
        "former",
        "formerly",
        "will become",
        "not",
    ],
)
def test_each_negating_phrase_blocks_support(negation):
    assert support(f"Acme Robotics {negation} employ 120 people.") == {}


def test_not_as_whole_word_only():
    assert support("Acme Robotics is notable and employs 120 people.") == {
        "headcount_range": "51-200"
    }


def test_two_different_values_for_a_field_support_nothing():
    assert support("Acme Robotics was founded in 2014 and incorporated in 2015.") == {}


def test_same_value_twice_is_one_value():
    assert support("Acme Robotics was founded in 2014, founded in 2014.") == {
        "founded_year": 2014
    }


def test_field_without_statement_phrase_is_not_supported():
    assert support("Acme Robotics opened a sales office in Porto.") == {}


def test_sentence_can_support_several_fields():
    result = support("Acme Robotics, Inc. is headquartered in Lisbon and employs 120 people.")
    assert result == {"hq_city": "Lisbon", "headcount_range": "51-200"}


def test_empty_excerpt_supports_nothing():
    assert support("") == {}
    assert support("   ") == {}


def test_domain_argument_case_is_ignored():
    assert supported_values("Acme-Robotics.TEST", "Acme Robotics was founded in 2014.") == {
        "founded_year": 2014
    }


# --- legal_name ----------------------------------------------------------------


def test_legal_name_with_comma_and_suffix():
    assert support("Acme Robotics, Inc. is a registered company.") == {
        "legal_name": "Acme Robotics, Inc."
    }


def test_legal_name_without_comma():
    assert support("Acme Robotics Ltd is a registered company.") == {
        "legal_name": "Acme Robotics Ltd"
    }


def test_legal_name_with_capitalised_and_uppercase_words():
    assert support("Acme Robotics Labs AI Corp. is a registered company.") == {
        "legal_name": "Acme Robotics Labs AI Corp."
    }


def test_legal_name_same_value_from_two_places_is_one_value():
    assert support("Registered as Acme Robotics Inc. and Acme Robotics Inc.") == {
        "legal_name": "Acme Robotics Inc."
    }


def test_legal_name_shortest_wins_at_same_start():
    assert support("Registered as Acme Robotics, Inc.") == {
        "legal_name": "Acme Robotics, Inc."
    }


def test_legal_name_suffix_needs_no_letter_after():
    assert support("Acme Robotics ASAP is a registered company.") == {}


def test_legal_name_suffix_is_case_sensitive():
    assert support("Acme Robotics, inc. is a registered company.") == {}


def test_legal_name_without_suffix_is_not_a_value():
    assert support("Acme Robotics is a registered company.") == {}


# --- hq_city ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence, city",
    [
        ("Acme Robotics is based in Lisbon.", "Lisbon"),
        ("Acme Robotics is headquartered in Lisbon, Portugal.", "Lisbon"),
        ("Acme Robotics is based in San Francisco, California.", "San Francisco"),
        ("Acme Robotics is based in Porto-Alegre.", "Porto-Alegre"),
        ("Acme Robotics is based in Zürich.", "Zürich"),
        ("Acme Robotics has its head office in Berlin.", "Berlin"),
        ("Acme Robotics has its registered seat in Oslo.", "Oslo"),
    ],
)
def test_hq_city_is_the_longest_capitalised_run(sentence, city):
    assert support(sentence) == {"hq_city": city}


def test_hq_city_needs_a_capitalised_word_after_phrase():
    assert support("Acme Robotics is based in the city.") == {}


def test_hq_city_lowercase_word_ends_the_run():
    assert support("Acme Robotics is based in Lisbon and Porto.") == {"hq_city": "Lisbon"}


def test_hq_city_is_nothing_when_two_cities_are_named():
    assert support("Acme Robotics is based in Lisbon, headquartered in Porto.") == {}


# --- ceo -----------------------------------------------------------------------


def test_ceo_three_word_name():
    assert support("Acme Robotics CEO: Dana Ana Ruiz.") == {"ceo": "Dana Ana Ruiz"}


def test_ceo_run_of_four_is_not_a_name():
    assert support("Acme Robotics CEO: Dana Ana Ana Ruiz.") == {}


def test_ceo_lowercase_name_is_not_a_name():
    assert support("Acme Robotics CEO: dana Ruiz.") == {}


def test_ceo_phrase_removed_and_name_separator():
    assert support("Dana Ruiz, chief executive of Acme Robotics.") == {"ceo": "Dana Ruiz"}


def test_ceo_two_names_is_nothing():
    assert support("Dana Ruiz is chief executive; Sam Ortiz is CEO of Acme Robotics.") == {}


def test_ceo_single_capitalised_word_is_not_a_name():
    assert support("Acme Robotics CEO: Dana.") == {}


# --- founded_year ----------------------------------------------------------------


@pytest.mark.parametrize("year", [1800, 1999, 2014, 2099])
def test_founded_year_range_edges(year):
    assert support(f"Acme Robotics was founded in {year}.") == {"founded_year": year}


@pytest.mark.parametrize("year", ["1799", "2100", "20140", "201"])
def test_founded_year_outside_range_or_digits(year):
    assert support(f"Acme Robotics was founded in {year}.") == {}


def test_founded_year_not_part_of_an_amount():
    assert support("Acme Robotics was founded in 2014 with $2014 in revenue.") == {
        "founded_year": 2014
    }
    assert support("Acme Robotics was founded in $2014.") == {}


def test_founded_year_with_decimal_is_not_a_year():
    assert support("Acme Robotics was founded in 2014.5.") == {}


# --- headcount_range -----------------------------------------------------------


@pytest.mark.parametrize(
    "count, label",
    [
        (1, "1-10"),
        (10, "1-10"),
        (11, "11-50"),
        (50, "11-50"),
        (51, "51-200"),
        (200, "51-200"),
        (201, "201-500"),
        (500, "201-500"),
        (501, "501-1000"),
        (1000, "501-1000"),
        (1001, "1001-5000"),
        (5000, "1001-5000"),
        (5001, "5001-10000"),
        (10000, "5001-10000"),
        (10001, "10001+"),
        (12_000_000, "10001+"),
    ],
)
def test_headcount_ranges_edges(count, label):
    assert support(f"Acme Robotics employs {count} people.") == {"headcount_range": label}


def test_headcount_with_comma_groups():
    assert support("Acme Robotics employs 1,200 people.") == {"headcount_range": "1001-5000"}


def test_headcount_zero_is_not_a_value():
    assert support("Acme Robotics employs 0 people.") == {}


def test_headcount_decimal_is_not_a_value():
    assert support("Acme Robotics employs 12.5 people.") == {}


def test_headcount_range_statement_holds_two_numbers():
    assert support("Acme Robotics has 51-200 employees.") == {"headcount_range": "51-200"}
    assert support("Acme Robotics has 10-50 employees.") == {}


def test_headcount_numbers_inside_amounts_are_excluded():
    assert support("Acme Robotics raised $120 and employs 80 people.") == {
        "funding_total": 120,
        "headcount_range": "51-200",
    }


def test_headcount_joined_digits_are_not_numbers():
    assert support("Acme Robotics employs x12 people.") == {}
    assert support("Acme Robotics employs 1,2345 people.") == {}


# --- funding_total -------------------------------------------------------------


@pytest.mark.parametrize(
    "amount, dollars",
    [
        ("$12M", 12_000_000),
        ("$12m", 12_000_000),
        ("$12mn", 12_000_000),
        ("$12.5 million", 12_500_000),
        ("US$12 million", 12_000_000),
        ("USD 12 million", 12_000_000),
        ("$12,000,000", 12_000_000),
        ("$1.2bn", 1_200_000_000),
        ("$2 billion", 2_000_000_000),
        ("$500k", 500_000),
        ("$500 thousand", 500_000),
        ("$0.5 million", 500_000),
        ("12 million dollars", 12_000_000),
        ("12,000,000 US dollars", 12_000_000),
        ("12 thousand dollars", 12_000),
        ("$ 12 million", 12_000_000),
    ],
)
def test_funding_amount_forms(amount, dollars):
    assert support(f"Acme Robotics has raised {amount}.") == {"funding_total": dollars}


def test_funding_not_whole_dollars_is_not_a_value():
    assert support("Acme Robotics has raised $12.5.") == {}


def test_funding_other_currency_is_not_an_amount():
    assert support("Acme Robotics has raised €12 million.") == {}
    assert support("Acme Robotics has raised 12 million euros.") == {}


def test_funding_amount_needs_boundary():
    assert support("Acme Robotics has raised A$12M.") == {}
    assert support("Acme Robotics has raised $12Mx.") == {}


def test_funding_two_different_amounts_is_nothing():
    assert support("Acme Robotics has raised $12M and $3M.") == {}


def test_funding_repeated_same_amount_is_one_value():
    assert support("Acme Robotics has raised $12M, $12 million in total.") == {
        "funding_total": 12_000_000
    }


def test_funding_case_insensitive_forms():
    assert support("Acme Robotics has raised usd 12 MILLION.") == {"funding_total": 12_000_000}


# --- split_header --------------------------------------------------------------


def test_text_without_header_is_all_prose():
    text = "Acme Robotics is based in Lisbon.\n\nMore."
    assert split_header(text) == ({}, text)


def test_header_runs_to_first_empty_line():
    text = "Title: Acme\nFacts: {\"founded_year\": 2014}\n\nAcme was founded in 2014.\nMore."
    headers, prose = split_header(text)
    assert headers == {"Title": "Acme", "Facts": '{"founded_year": 2014}'}
    assert prose == "Acme was founded in 2014.\nMore."


def test_header_name_may_be_joined_by_dash():
    headers, prose = split_header("Source-Name: Press\n\nBody.")
    assert headers == {"Source-Name": "Press"}
    assert prose == "Body."


def test_header_without_empty_line_has_empty_prose():
    headers, prose = split_header("Title: Acme\nAuthor: Ada")
    assert headers == {"Title": "Acme", "Author": "Ada"}
    assert prose == ""


def test_lowercase_name_is_not_a_header():
    text = "title: Acme\n\nBody."
    assert split_header(text) == ({}, text)


def test_first_occurrence_of_a_header_name_wins():
    headers, _ = split_header("Title: One\nTitle: Two\n\nBody.")
    assert headers == {"Title": "One"}


def test_empty_text_has_no_header():
    assert split_header("") == ({}, "")


def test_header_values_are_stripped():
    headers, _ = split_header("Title:   Acme   \n\nBody.")
    assert headers == {"Title": "Acme"}


# --- excerpt_in_prose ------------------------------------------------------------


def test_excerpt_is_verbatim_substring():
    prose = "Acme Robotics was founded in 2014. It grew."
    assert excerpt_in_prose(prose, "Acme Robotics was founded in 2014.")


def test_excerpt_whitespace_run_matches_any_run_in_prose():
    prose = "Acme\n  Robotics\twas founded in 2014."
    assert excerpt_in_prose(prose, "Acme Robotics was founded in 2014.")


def test_excerpt_must_not_be_reworded():
    prose = "Acme Robotics was founded in 2014."
    assert not excerpt_in_prose(prose, "Acme Robotics was founded in 2015.")
    assert not excerpt_in_prose(prose, "Acme Robotics was established in 2014.")


def test_excerpt_must_not_be_header_text():
    text = "Title: Acme Robotics was founded in 2014\n\nBody."
    _, prose = split_header(text)
    assert not excerpt_in_prose(prose, "Title: Acme Robotics was founded in 2014")


def test_excerpt_length_limits():
    assert not excerpt_in_prose("x", "")
    assert excerpt_in_prose("x" * 500, "x" * 500)
    assert not excerpt_in_prose("x" * 501, "x" * 501)


def test_excerpt_with_surrounding_whitespace_is_rejected():
    assert not excerpt_in_prose("Acme.", " Acme.")
    assert not excerpt_in_prose("Acme.", "Acme. ")


def test_excerpt_with_regex_metacharacters_is_literal():
    prose = "Price (approx.) is $12.5M."
    assert excerpt_in_prose(prose, "Price (approx.) is $12.5M.")
    assert not excerpt_in_prose(prose, "Price (approx.) is $12x5M.")


# --- extract_supports ----------------------------------------------------------


def test_extract_supports_gives_every_supported_sentence_in_order():
    prose = (
        "Acme Robotics was founded in 2014.\n\n"
        "Acme Robotics raised $12M.\n"
        "Acme Robotics is based in Lisbon.\n"
        "Acme Robotics opened a sales office in Porto."
    )
    result = extract_supports(DOMAIN, prose)
    assert [(s.field, s.value, s.excerpt) for s in result] == [
        ("founded_year", 2014, "Acme Robotics was founded in 2014."),
        ("funding_total", 12_000_000, "Acme Robotics raised $12M."),
        ("hq_city", "Lisbon", "Acme Robotics is based in Lisbon."),
    ]


def test_every_extracted_excerpt_is_in_prose():
    prose = "Intro. Acme Robotics was founded in 2014. Acme Robotics employs 120 people."
    for support_record in extract_supports(DOMAIN, prose):
        assert excerpt_in_prose(prose, support_record.excerpt)
        assert supported_values(DOMAIN, support_record.excerpt) == {
            support_record.field: support_record.value
        }


def test_extract_supports_skips_header_text():
    text = "Facts: {\"founded_year\": 2014}\n\nBody without facts."
    headers, prose = split_header(text)
    assert headers
    assert extract_supports(DOMAIN, prose) == []


def test_extract_supports_skips_sentences_over_500_characters():
    long_sentence = "Acme Robotics was founded in 2014 " + "and " * 200 + "today."
    assert len(long_sentence) > 500
    assert extract_supports(DOMAIN, long_sentence) == []


def test_extract_supports_output_is_normalised_whitespace():
    prose = "Acme Robotics was founded   in 2014."
    result = extract_supports(DOMAIN, prose)
    assert [s.excerpt for s in result] == ["Acme Robotics was founded in 2014."]
    assert excerpt_in_prose(prose, result[0].excerpt)


# --- review fixes (R1.257, A.4 character before a ceo word) ----------------------


def test_suffix_written_without_dot_ends_the_sentence():
    # "Ltd." is the suffix Ltd followed by a sentence-ending dot: the dot ends the sentence.
    assert split_sentences("Acme Robotics is registered as Acme Robotics Ltd. It employs 120 people.") == [
        "Acme Robotics is registered as Acme Robotics Ltd.",
        "It employs 120 people.",
    ]


def test_short_suffix_without_dot_at_sentence_end_splits():
    assert split_sentences("Acme Robotics is based in Oslo AS. It employs 120 people.") == [
        "Acme Robotics is based in Oslo AS.",
        "It employs 120 people.",
    ]


def test_plc_without_dot_at_sentence_end_splits():
    assert split_sentences("Acme Robotics PLC. It employs 120 people.") == [
        "Acme Robotics PLC.",
        "It employs 120 people.",
    ]


def test_ceo_word_preceded_by_digit_is_not_a_name():
    assert support("Acme Robotics CEO: 3Dana Ruiz.") == {}
    assert support("Acme Robotics CEO: Dana Ruiz.") == {"ceo": "Dana Ruiz"}
