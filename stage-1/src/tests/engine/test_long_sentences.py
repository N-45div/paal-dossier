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
    # the word "2014." ends at its full stop, the word boundary the window cuts at
    assert found == [("founded_year", 2014, "Acme Robotics was founded in 2014.")]


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


def test_ceo_name_inside_a_longer_capitalised_run_is_cited():
    # A.4 takes the company name and CEO phrases out before reading names, so the name
    # "Dana Ruiz" stands alone although "Dana Ruiz Acme Robotics" is one capitalised run.
    sentence = "Dana Ruiz Acme Robotics CEO " + ("x" * 510)
    assert len(sentence) > EXCERPT_MAX_CHARS
    found = fragment_values(sentence)
    assert found == [("ceo", "Dana Ruiz", "Dana Ruiz Acme Robotics CEO")]
    assert supports(found[0][2], D, "ceo", "Dana Ruiz")


def test_headcount_fragment_in_a_long_sentence():
    sentence = "Acme Robotics employs 120 people " + ("zeta " * 103).strip()
    assert len(sentence) > EXCERPT_MAX_CHARS
    found = fragment_values(sentence)
    # "employs" alone with the number is the shortest window that supports the range
    assert found == [("headcount_range", "51-200", "Acme Robotics employs 120")]
    assert supports(found[0][2], D, "headcount_range", "51-200")


def test_funding_fragment_in_a_long_sentence():
    sentence = "Acme Robotics has raised $12M " + ("zeta " * 103).strip()
    assert len(sentence) > EXCERPT_MAX_CHARS
    found = fragment_values(sentence)
    assert found == [("funding_total", 12_000_000, "Acme Robotics has raised $12M")]
    assert supports(found[0][2], D, "funding_total", 12_000_000)


def test_ceo_fragment_for_name_inside_a_longer_run_is_the_exact_window():
    sentence = "Dana Ruiz Acme Robotics CEO " + ("x" * 510)
    found = fragment_values(sentence)
    assert found == [("ceo", "Dana Ruiz", "Dana Ruiz Acme Robotics CEO")]
