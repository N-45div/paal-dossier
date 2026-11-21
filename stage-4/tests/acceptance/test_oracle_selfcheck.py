"""Self-check of the Prover's Appendix A oracle against the examples printed in the
specification. These tests need no service and no mock.

Covers: R1.108, R1.257-R1.310 (Appendix A examples), R1.104-R1.105, R1.113-R1.116.
"""
from oracle import (excerpt_in_prose, prose_sentences, split_header, split_sentences,
                    supported_values)

D = "acme-robotics.test"


def test_spec_examples_a2_table():
    # R1.273-R1.278
    assert supported_values(D, "Dana Ruiz has led Acme Robotics as chief executive since 2021.") == {
        "ceo": "Dana Ruiz"}
    assert supported_values(D, "Acme Robotics CEO: Sam Ortiz.") == {"ceo": "Sam Ortiz"}
    assert supported_values(D, "Acme Robotics was founded in 2014.") == {"founded_year": 2014}
    assert supported_values(D, "Acme Robotics employs about 120 people.") == {
        "headcount_range": "51-200"}
    assert supported_values(D, "Acme Robotics is reportedly in talks to raise $40M.") == {}
    assert supported_values(D, "Acme Robotics opened a sales office in Porto.") == {}


def test_spec_examples_funding_and_headcount_wording():
    # R1.108
    assert supported_values(D, "Acme Robotics has raised $12M.") == {"funding_total": 12000000}
    assert supported_values(D, "Acme Robotics has raised 12 million dollars.") == {
        "funding_total": 12000000}
    assert supported_values(D, "Acme Robotics employs about 120 people.")["headcount_range"] == "51-200"


def test_negation_blocks_every_field():
    # R1.268, R1.286
    assert supported_values(D, "Acme Robotics was not founded in 2014.") == {}
    assert supported_values(D, "Acme Robotics plans to raise $12M.") == {}
    assert supported_values(D, "Former CEO Dana Ruiz ran Acme Robotics.") == {}


def test_single_sentence_rule():
    # R1.265, R1.263
    assert supported_values(D, "Acme Robotics was founded in 2014. It is in Lisbon.") == {}


def test_legal_name_with_suffix_is_one_sentence():
    # R1.261, R1.295, R1.301-R1.302: "Inc." does not end a sentence
    assert supported_values(D, "The registered name is Acme Robotics, Inc.") == {
        "legal_name": "Acme Robotics, Inc."}
    assert supported_values(D, "Acme Robotics, Inc. was founded in 2014.") == {"founded_year": 2014}


def test_legal_name_requires_suffix_and_shortest_wins():
    assert supported_values(D, "The legal name is Acme Robotics.") == {}
    assert supported_values(D, "The registered name is Acme Robotics Inc. and it is big.") == {
        "legal_name": "Acme Robotics Inc."}


def test_hq_city_runs():
    # R1.296
    assert supported_values(D, "Acme Robotics is headquartered in Lisbon.") == {"hq_city": "Lisbon"}
    assert supported_values(D, "Acme Robotics is based in Zürich, Switzerland.") == {"hq_city": "Zürich"}
    assert supported_values(D, "Acme Robotics is based in Winston-Salem.") == {"hq_city": "Winston-Salem"}
    # two different cities in one sentence cannot both be the value
    assert supported_values(D, "Acme Robotics is based in Lisbon and headquartered in Porto.") == {}


def test_ceo_name_runs_and_multiple_names():
    # R1.297: two or three capitalised words; a longer run does not count
    assert supported_values(D, "Acme Robotics is led by Dana Ruiz Smith Jones as chief executive.") == {}
    assert supported_values(D, "Acme Robotics chief executive Dana Ruiz Smith is in Lisbon.") == {
        "ceo": "Dana Ruiz Smith"}
    assert supported_values(D, "Acme Robotics CEO Dana Ruiz and Sam Ortiz lead it.") == {}


def test_headcount_numbers_and_ranges():
    # R1.299: no decimal part, 1 or more; words before do not matter
    assert supported_values(D, "Acme Robotics has roughly 1,200 staff.") == {"headcount_range": "1001-5000"}
    assert supported_values(D, "Acme Robotics has 0 employees.") == {}
    assert supported_values(D, "Acme Robotics has 12.5 employees.") == {}
    assert supported_values(D, "Acme Robotics employs 51-200 employees.") == {"headcount_range": "51-200"}
    assert supported_values(D, "Acme Robotics employs 120 people in 2 offices.") == {}


def test_founded_year_bounds_and_form():
    # R1.298
    assert supported_values(D, "Acme Robotics was founded in 1799.") == {}
    assert supported_values(D, "Acme Robotics was founded in 1800.") == {"founded_year": 1800}
    assert supported_values(D, "Acme Robotics was founded in 2099.") == {"founded_year": 2099}
    assert supported_values(D, "Acme Robotics was founded in 2100.") == {}
    assert supported_values(D, "Acme Robotics was founded in 2,014.") == {}


def test_amounts_scales_and_whole_dollars():
    # R1.303-R1.306, R1.310
    assert supported_values(D, "Acme Robotics raised $12M in a round.") == {"funding_total": 12000000}
    assert supported_values(D, "Acme Robotics raised US$12.5 million.") == {"funding_total": 12500000}
    assert supported_values(D, "Acme Robotics raised USD 12 million.") == {"funding_total": 12000000}
    assert supported_values(D, "Acme Robotics raised $12,000,000.") == {"funding_total": 12000000}
    assert supported_values(D, "Acme Robotics raised 12,000,000 US dollars.") == {"funding_total": 12000000}
    assert supported_values(D, "Acme Robotics raised $12.5k.") == {"funding_total": 12500}
    assert supported_values(D, "Acme Robotics raised $12.5.") == {}  # not a whole number of dollars
    assert supported_values(D, "Acme Robotics raised €12 million.") == {}  # other currency


def test_amount_digits_are_not_years_or_headcounts():
    # R1.298-R1.299: "not part of an amount"
    assert supported_values(D, "Acme Robotics was founded in $2014.") == {}
    assert supported_values(D, "Acme Robotics raised $2014 in 2014.") == {"funding_total": 2014}


def test_company_name_must_be_named():
    # R1.266
    assert supported_values(D, "Dana Ruiz is CEO of Beta Labs.") == {}


def test_phrases_are_whole_words_and_case_insensitive():
    # R1.270: "people" must not match "peoples"; "based in" is case-insensitive
    assert supported_values(D, "Acme Robotics has many peoples.") == {}
    assert supported_values(D, "ACME ROBOTICS IS BASED IN LISBON.") == {}  # LISBON is not a capitalised word


def test_split_sentences_suffix_and_closers():
    # R1.260, R1.261
    assert split_sentences('He said "stop." Then left.') == ['He said "stop."', "Then left."]
    assert split_sentences("Acme Robotics L.P. was founded. Then more.") == [
        "Acme Robotics L.P. was founded.", "Then more."]
    assert len(split_sentences("Acme S.A.S. is here.")) == 1


def test_split_header_and_prose():
    # R1.113-R1.116
    headers, prose = split_header("Kind: news\nFacts: {\"ceo\": \"Dana Ruiz\"}\n\nAcme Robotics was founded in 2014.")
    assert headers == {"Kind": "news", "Facts": '{"ceo": "Dana Ruiz"}'}
    assert prose == "Acme Robotics was founded in 2014."
    headers, prose = split_header("Acme Robotics was founded in 2014.\nMore prose.")
    assert headers == {} and prose.startswith("Acme Robotics")
    assert prose_sentences("A is based in Lisbon. B.\nC was founded in 2014.") == [
        "A is based in Lisbon.", "B.", "C was founded in 2014."]


def test_excerpt_in_prose_whitespace_rule():
    # R1.104
    assert excerpt_in_prose("Dana   Ruiz\nhas led it.", "Dana Ruiz has led it.")
    assert not excerpt_in_prose("Dana Ruiz.", "Dana Ruiz. Extra")
    assert not excerpt_in_prose("x", "")
    assert not excerpt_in_prose("y" * 501, "y" * 501)
