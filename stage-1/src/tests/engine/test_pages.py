"""Header/prose split (R1.58) and the sentence split of A.1 (R1.144-R1.145)."""

import pytest

from dossier.engine.pages import collapse_whitespace, prose_of, sentences


def test_text_without_header_is_all_prose():
    text = "Acme Robotics was founded in 2014.\n\nIt makes robots."
    assert prose_of(text) == text


def test_header_ends_at_first_empty_line():
    text = "Title: Acme\nFacts: {\"ceo\": \"Dana Ruiz\"}\n\nAcme Robotics was founded in 2014."
    assert prose_of(text) == "Acme Robotics was founded in 2014."


def test_header_line_with_joined_name_is_a_header():
    text = "Content-Type: text/html\n\nBody sentence."
    assert prose_of(text) == "Body sentence."


def test_lowercase_first_word_is_not_a_header():
    text = "note: Acme Robotics was founded in 2014.\n\nMore."
    assert prose_of(text) == text


def test_header_without_empty_line_leaves_no_prose():
    assert prose_of("Title: Acme\nFacts: {}") == ""


def test_non_header_line_inside_header_block_is_still_header_block():
    text = "Title: Acme\nthis line is not a header\n\nProse here."
    assert prose_of(text) == "Prose here."


def test_header_name_must_start_with_capitalised_word():
    text = "Title1: x\n\nProse."
    assert prose_of(text) == text


@pytest.mark.parametrize(
    "prose, expected",
    [
        ("One. Two.", ["One.", "Two."]),
        ("Wow! Really? Yes.", ["Wow!", "Really?", "Yes."]),
        ('He said "stop." Then left.', ['He said "stop."', "Then left."]),
        ("A ” quote. B ’ quote.", ["A ” quote.", "B ’ quote."]),
        ("Aside (see note.) Next.", ["Aside (see note.)", "Next."]),
        ("Dot.Joined and 3.5 million.", ["Dot.Joined and 3.5 million."]),
        ("Ends without dot", ["Ends without dot"]),
        ("", []),
        ("   \t  ", []),
    ],
)
def test_sentence_split(prose, expected):
    assert sentences(prose) == expected


@pytest.mark.parametrize(
    "prose, expected",
    [
        ("Acme Robotics, Inc. was founded.", ["Acme Robotics, Inc. was founded."]),
        ("Acme Robotics L.P. grew.", ["Acme Robotics L.P. grew."]),
        ("Data.s. is not a suffix. Next", ["Data.s.", "is not a suffix.", "Next"]),
        ("Zinc Inc. wins. Next", ["Zinc Inc. wins.", "Next"]),
        ("We bought Acme Pty Ltd. Next", ["We bought Acme Pty Ltd.", "Next"]),
        ("Based at Müller S.A.S. today.", ["Based at Müller S.A.S. today."]),
        ("Known as x a.s. here.", ["Known as x a.s. here."]),
        ("Ends with Corp.", ["Ends with Corp."]),
    ],
)
def test_legal_suffix_dot_does_not_end_sentence(prose, expected):
    assert sentences(prose) == expected


def test_each_line_break_splits_lines_and_sentences_are_stripped():
    assert sentences("  First line  \r\nSecond.\rThird\nFourth. ") == [
        "First line",
        "Second.",
        "Third",
        "Fourth.",
    ]


def test_closing_quote_without_following_space_does_not_end_sentence():
    assert sentences('He said "stop."Then') == ['He said "stop."Then']


def test_collapse_whitespace_runs_and_trims():
    assert collapse_whitespace("  a \t\n b\r\n\r\n c  ") == "a b c"
