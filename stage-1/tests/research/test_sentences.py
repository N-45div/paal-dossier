"""Appendix A.1 sentences, page headers and prose (stage-1.md section 4)."""

from research.sentences import candidate_excerpts, page_prose, split_sentences


def test_splits_after_terminator_followed_by_space():
    assert split_sentences("One is here. Two is here! Three? Four.") == [
        "One is here.",
        "Two is here!",
        "Three?",
        "Four.",
    ]


def test_closing_quote_and_paren_stay_with_sentence():
    assert split_sentences('He said "stop." Then (ok.) Next.') == [
        'He said "stop."',
        "Then (ok.)",
        "Next.",
    ]


def test_typographic_closers_are_attached():
    assert split_sentences("He said “stop.” Next.") == ["He said “stop.”", "Next."]


def test_legal_suffix_period_does_not_end_sentence():
    assert split_sentences("Acme Robotics, Inc. was founded in 2014. It grew.") == [
        "Acme Robotics, Inc. was founded in 2014.",
        "It grew.",
    ]


def test_legal_suffix_with_internal_dots():
    assert split_sentences("Acme S.A.S. raised money. Done.") == ["Acme S.A.S. raised money.", "Done."]


def test_period_inside_a_number_or_word_is_not_a_split():
    assert split_sentences("It costs 12.5 units. Done.") == ["It costs 12.5 units.", "Done."]


def test_lines_are_split_before_sentences():
    assert split_sentences("First line\nSecond line. Still second") == [
        "First line",
        "Second line.",
        "Still second",
    ]


def test_header_present_when_first_line_is_header_line():
    text = "Kind: news\nFacts: {\"ceo\": \"Dana\"}\n\nAcme Robotics was founded in 2014."
    assert page_prose(text) == "Acme Robotics was founded in 2014."


def test_no_header_when_first_line_is_not_header_line():
    text = "Acme Robotics was founded in 2014.\nKind: news"
    assert page_prose(text) == text


def test_header_name_may_join_capitalised_words_with_hyphens():
    text = "First-Published-By: wire.test\n\nBody text here."
    assert page_prose(text) == "Body text here."


def test_facts_header_is_not_prose():
    text = 'Facts: {"funding_total": "$12M"}\n\nAcme raised $12M.'
    assert candidate_excerpts(text) == ["Acme raised $12M."]


def test_candidate_excerpts_collapse_whitespace_and_skip_empty():
    assert candidate_excerpts("Acme   Robotics\twas founded in 2014.\n\n   \n") == [
        "Acme Robotics was founded in 2014."
    ]


def test_candidate_excerpts_drop_over_500_characters():
    long_sentence = "A" * 501 + "."
    assert candidate_excerpts(long_sentence) == []
    assert len(candidate_excerpts("A" * 499 + ".")[0]) == 500
