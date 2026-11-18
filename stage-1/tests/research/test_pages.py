from app.research.pages import split_page
from app.research.sentences import split_prose


def test_header_and_prose():
    text = "Kind: news\nFacts: {\"ceo\": \"X Y\"}\nFirst-Published-By: wire.test\n\nBody one.\nBody two."
    header, prose = split_page(text)
    assert len(header) == 3 and prose == "Body one.\nBody two."


def test_no_header_is_all_prose():
    text = "Acme is here.\nKind: news\n\nmore"
    assert split_page(text) == ([], text)


def test_header_without_blank_line_has_no_prose():
    assert split_page("Kind: news")[1] == ""


def test_lowercase_name_is_not_header():
    assert split_page("kind: news\n\nx")[0] == []


def test_sentences_split_lines_and_ends():
    prose = "One two. Three four!  Five?\n\nSix \"quoted.\" Seven"
    assert split_prose(prose) == ["One two.", "Three four!", "Five?", 'Six "quoted."', "Seven"]


def test_suffix_dot_not_a_sentence_end():
    assert split_prose("Acme Corp. is big. Beta S.p.A. too.") == ["Acme Corp. is big.", "Beta S.p.A. too."]


def test_suffix_must_be_whole_word():
    assert split_prose("We love Zinc. Next") == ["We love Zinc.", "Next"]
