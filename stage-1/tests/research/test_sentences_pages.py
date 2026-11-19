"""A.1 sentences and §4 pages."""

from app.research.pages import ServedText, is_citation_of, parse_page, prose_sentences
from app.research.text import is_single_sentence, split_sentences


def test_split_on_terminators_followed_by_whitespace():
    assert split_sentences("One. Two! Three? Four") == ["One.", "Two!", "Three?", "Four"]


def test_terminator_with_closers():
    assert split_sentences('He said "stop." Then left. (Really.) Ok') == ['He said "stop."', "Then left.", "(Really.)", "Ok"]
    assert split_sentences("It’s “fine.” Yes") == ["It’s “fine.”", "Yes"]


def test_no_split_without_following_whitespace():
    assert split_sentences("Version 1.2 is out.Next") == ["Version 1.2 is out.Next"]


def test_lines_split_first():
    assert split_sentences("No end here\nSecond line\r\nThird") == ["No end here", "Second line", "Third"]


def test_legal_suffix_dot_does_not_end_sentence():
    assert split_sentences("Acme Inc. is big. Next") == ["Acme Inc. is big.", "Next"]
    assert split_sentences("Acme S.A.S. is big.") == ["Acme S.A.S. is big."]
    assert split_sentences("Acme B.V. said so.") == ["Acme B.V. said so."]


def test_suffix_dot_must_be_whole_word():
    assert split_sentences("The Winc. Next") == ["The Winc.", "Next"]


def test_empty_sentences_dropped():
    assert split_sentences("  \n\n  ") == []


def test_single_sentence_collapses_whitespace():
    assert is_single_sentence("Acme   Robotics\nwas founded.")
    assert not is_single_sentence("Acme was founded. Really.")


def test_header_and_prose():
    page = parse_page('Kind: news\nFirst-Published-By: wire.test\nFacts: {"ceo": "Dana Ruiz"}\n\nBody one.\nBody two.')
    assert [n for n, _ in page.headers] == ["Kind", "First-Published-By", "Facts"]
    assert page.prose == "Body one.\nBody two."
    assert page.facts == {"ceo": "Dana Ruiz"}


def test_no_header_when_first_line_is_prose():
    page = parse_page("Acme was founded in 2014.\n\nKind: news")
    assert page.headers == ()
    assert page.prose.startswith("Acme was")


def test_lowercase_name_is_not_a_header():
    assert parse_page("kind: news\n\nBody").headers == ()


def test_header_text_is_not_prose():
    served = ServedText("https://x.test/", "nimble", "Kind: news\nFacts: {}\n\nAcme was founded in 2014.")
    assert is_citation_of("Acme was founded in 2014.", served)
    assert not is_citation_of("Kind: news", served)


def test_citation_whitespace_and_length():
    served = ServedText("https://x.test/", "nimble", "Acme  was\nfounded   in 2014.")
    assert is_citation_of("Acme was founded in 2014.", served)
    assert not is_citation_of("Acme  was founded", served)
    assert not is_citation_of("", served)
    long = ServedText("https://x.test/", "nimble", "a" * 600)
    assert not is_citation_of("a" * 501, long)
    assert is_citation_of("a" * 500, long)


def test_truncated_text_drops_trailing_fragment():
    served = ServedText("https://x.test/", "nimble", "Whole one. Cut off hal", complete=False)
    assert prose_sentences(served) == ["Whole one."]
    assert prose_sentences(ServedText("https://x.test/", "nimble", "Whole one. Last")) == ["Whole one.", "Last"]
