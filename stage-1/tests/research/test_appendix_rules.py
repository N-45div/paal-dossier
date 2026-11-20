"""Appendix A rule coverage: every statement phrase, every negating phrase, sentence and digit edge cases."""

import pytest

from research.lexicon import NEGATING_PHRASES, STATEMENT_PHRASES
from research.sentences import split_sentences
from research.support import supports

ACME = "acme-robotics.test"

# A sentence per field that names the company, carries the field's value and has one
# slot ({p}) for a statement phrase. Nothing else in it is a phrase or a negation.
TEMPLATES = {
    "legal_name": ("Acme Robotics {p} Acme Robotics Inc.", ("legal_name", "Acme Robotics Inc.")),
    "hq_city": ("Acme Robotics {p} Lisbon.", ("hq_city", "Lisbon")),
    "ceo": ("Acme Robotics {p} Sam Ortiz.", ("ceo", "Sam Ortiz")),
    "founded_year": ("Acme Robotics {p} 2014.", ("founded_year", 2014)),
    "headcount_range": ("Acme Robotics {p} 120.", ("headcount_range", "51-200")),
    "funding_total": ("Acme Robotics {p} $12M.", ("funding_total", 12_000_000)),
}


def _phrase_cases():
    for field, phrases in STATEMENT_PHRASES.items():
        for phrase in phrases:
            yield pytest.param(field, phrase, id=f"{field}:{phrase}")


@pytest.mark.parametrize("field, phrase", list(_phrase_cases()))
def test_every_statement_phrase_supports_its_field(field, phrase):
    template, expected = TEMPLATES[field]
    assert expected in supports(template.format(p=phrase), ACME)


@pytest.mark.parametrize("field", list(STATEMENT_PHRASES))
def test_absent_statement_phrase_supports_nothing_for_field(field):
    template, _ = TEMPLATES[field]
    sentence = template.format(p="and nothing else")
    assert all(name != field for name, _ in supports(sentence, ACME))


@pytest.mark.parametrize("negation", NEGATING_PHRASES)
def test_every_negating_phrase_blocks_support(negation):
    base = "Acme Robotics raised $12M."
    assert ("funding_total", 12_000_000) in supports(base, ACME)
    assert supports(f"Acme Robotics {negation} raise $12M.", ACME) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "Acme Robotics cannot say it raised $12M.",  # "not" is not a whole word here
        "Acme Robotics raised $12M, nothing more.",  # "not" inside "nothing"
        "Acme Robotics raised $12M, knot tied.",  # "not" inside "knot"
        "Acme Robotics couldn't stop it: raised $12M.",  # "could" followed by a letter
    ],
)
def test_negation_is_whole_word_only(sentence):
    assert ("funding_total", 12_000_000) in supports(sentence, ACME)


def test_formerly_is_a_listed_negation_as_a_whole_word():
    assert supports("Acme Robotics formerly raised $12M.", ACME) == []


# Sentence rule (A.1, lead ruling G14) --------------------------------------

def test_partial_suffix_dot_ends_sentence():
    assert split_sentences("Anna S. Next sentence.") == ["Anna S.", "Next sentence."]


def test_listed_suffix_without_its_own_dot_does_not_protect_the_dot():
    assert split_sentences("Acme Ltd. Next sentence.") == ["Acme Ltd.", "Next sentence."]


def test_suffix_glued_to_letters_does_not_protect_the_dot():
    assert split_sentences("FooInc. Bar") == ["FooInc.", "Bar"]


def test_listed_suffix_with_own_dot_does_not_end_sentence():
    assert split_sentences("Acme, Inc. Next sentence.") == ["Acme, Inc. Next sentence."]


# ASCII digits only (lead ruling G14) -----------------------------------------

ARABIC_INDIC_2014 = "٢٠١٤"  # Unicode digits, not numbers


@pytest.mark.parametrize(
    "sentence",
    [
        f"Acme Robotics was founded in {ARABIC_INDIC_2014}.",
        f"Acme Robotics employs {ARABIC_INDIC_2014} people.",
        f"Acme Robotics raised ${ARABIC_INDIC_2014}M.",
        f"Acme Robotics raised {ARABIC_INDIC_2014} million dollars.",
    ],
)
def test_unicode_digits_are_not_numbers(sentence):
    assert supports(sentence, ACME) == []


def test_ascii_numbers_still_work_next_to_unicode_digits_elsewhere():
    assert supports(f"Acme Robotics {ARABIC_INDIC_2014} was founded in 2014.", ACME) == [("founded_year", 2014)]
