"""Sentences longer than 500 characters cite the shortest supporting fragment (R1.53, R1.104)."""

from dossier.engine.support import EXCERPT_MAX_CHARS, supporting_excerpts, supports

D = "acme-robotics.test"
FILLER = " ".join(["plain"] * 100)  # 599 characters of lowercase words, no triggers


def fragment_values(text):
    return [(field, value, excerpt) for field, value, excerpt in supporting_excerpts(text, D)]


def test_fragment_of_a_545_character_sentence_supports_the_value():
    filler = ("zeta " * 103).strip()  # lowercase only, no negating phrase
    sentence = "Acme Robotics was founded in 2014 and " + filler
    assert len(sentence) > EXCERPT_MAX_CHARS
    found = fragment_values(sentence)
    assert found == [("founded_year", 2014, "Acme Robotics was founded in 2014")]
    assert len(found[0][2]) <= EXCERPT_MAX_CHARS
    assert supports(found[0][2], D, "founded_year", 2014)
    assert found[0][2] in sentence


def test_fragment_at_the_end_of_a_long_sentence_is_found():
    filler = ("zeta " * 105).strip()
    sentence = filler + " and Acme Robotics was founded in 2014."
    assert len(sentence) > EXCERPT_MAX_CHARS
    found = fragment_values(sentence)
    assert found == [("founded_year", 2014, "Acme Robotics was founded in 2014")]


def test_no_fragment_when_the_whole_sentence_has_a_negating_phrase():
    filler = ("zeta " * 103).strip()
    sentence = "Acme Robotics was not founded in 2014 and " + filler
    assert len(sentence) > EXCERPT_MAX_CHARS
    assert fragment_values(sentence) == []
    # the fragment alone would support the year, so only the whole sentence blocks it
    assert supports("Acme Robotics was founded in 2014", D, "founded_year", 2014)


def test_no_fragment_when_the_whole_sentence_has_a_conflicting_value():
    filler = ("zeta " * 103).strip()
    sentence = "Acme Robotics was founded in 2014 and in 2019, " + filler
    assert len(sentence) > EXCERPT_MAX_CHARS
    assert fragment_values(sentence) == []


def test_short_sentence_cites_the_whole_sentence():
    sentence = "Acme Robotics was founded in 2014."
    assert fragment_values(sentence) == [("founded_year", 2014, sentence)]


def test_fragment_never_exceeds_the_limit():
    filler = ("zeta " * 200).strip()
    sentence = "Acme Robotics was founded in 2014 " + filler + " and that is all."
    for _, _, excerpt in fragment_values(sentence):
        assert 1 <= len(excerpt) <= EXCERPT_MAX_CHARS
