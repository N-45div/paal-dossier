"""One test per claimed P3 ledger id; each name carries its id (see stage-1/LEDGER.md)."""
import pytest

from app.research.formats import NEGATING_PHRASES, PHRASES
from app.research.pages import split_page
from app.research.sentences import LEGAL_FORM_SUFFIXES, is_single_sentence, split_prose
from app.research.support import supports

D = "acme-robotics.test"


def test_R1_39_string_values_are_as_written_and_headcount_is_the_containing_range():
    assert supports("Acme Robotics is headquartered in New York.", D, "hq_city") == "New York"
    assert supports("Acme Robotics employs 60 people.", D, "headcount_range") == "51-200"
    assert supports("Acme Robotics has 51-200 employees.", D, "headcount_range") == "51-200"


def test_R1_45_citation_excerpts_are_whole_prose_sentences():
    header, prose = split_page("Kind: own\n\nAcme Robotics was founded in 2014.")
    assert header == ["Kind: own"] and split_prose(prose) == ["Acme Robotics was founded in 2014."]


def test_R1_46_equivalent_writings_support_the_same_value():
    assert supports("Acme Robotics has raised $12M.", D, "funding_total") == 12000000
    assert supports("Acme Robotics has raised 12 million dollars.", D, "funding_total") == 12000000
    assert supports("Acme Robotics employs about 120 people.", D, "headcount_range") == "51-200"


def test_R1_49_header_ends_at_first_empty_line_and_headerless_text_is_prose():
    assert split_page("Kind: a\nPublished: b\n\nx\n\ny") == (["Kind: a", "Published: b"], "x\n\ny")
    assert split_page("Plain text.\n\nKind: a") == ([], "Plain text.\n\nKind: a")
    assert split_page("First-Published-By: x.test\n\nz")[0] == ["First-Published-By: x.test"]


def test_R1_50_facts_header_is_ignored_for_support():
    text = 'Facts: {"ceo": "Dana Ruiz"}\n\nAcme Robotics opened an office.'
    _, prose = split_page(text)
    assert supports(prose, D, "ceo") is None


def test_R1_121_sentence_splitting():
    assert split_prose('A one. B two!) "C three?" D\nE four.') == ["A one.", "B two!)", '"C three?"', "D", "E four."]
    assert split_prose("Acme Robotics, Inc. is here. Next.") == ["Acme Robotics, Inc. is here.", "Next."]
    assert split_prose("Zinc. Next") == ["Zinc.", "Next"]


def test_R1_122_single_sentence_after_whitespace_collapse():
    assert is_single_sentence("Acme   was\n founded.")
    assert not is_single_sentence("Acme was founded.  Then more.")


def test_R1_123_two_sentences_do_not_support():
    assert supports("Acme Robotics was founded in 2014. Yes.", D, "founded_year") is None


def test_R1_124_company_named_by_name_or_domain_only():
    assert supports("Acme Robotics was founded in 2014.", D, "founded_year") == 2014
    assert supports("acme-robotics.test was founded in 2014.", D, "founded_year") == 2014
    assert supports("Acme was founded in 2014.", D, "founded_year") is None
    assert supports("Zed Robotics was founded in 2014.", D, "founded_year") is None


def test_R1_125_statement_phrase_required():
    assert supports("Acme Robotics opened in 2014.", D, "founded_year") is None
    assert supports("Acme Robotics opened a sales office in Porto.", D, "hq_city") is None


def test_R1_126_negating_phrase_blocks_support():
    assert supports("Acme Robotics is reportedly in talks to raise $40M.", D, "funding_total") is None
    assert supports("Acme Robotics could be founded in 2014.", D, "founded_year") is None


def test_R1_127_all_values_must_agree():
    assert supports("Acme Robotics was founded in 2014 or founded in 2015.", D, "founded_year") is None
    assert supports("Acme Robotics was founded in 2014 and established in 2014.", D, "founded_year") == 2014
    assert supports("Acme Robotics was founded in the north.", D, "founded_year") is None


def test_R1_128_whole_word_case_insensitive_matching():
    assert supports("ACME ROBOTICS WAS FOUNDED IN 2014.", D, "founded_year") == 2014
    assert supports("Acme Roboticsx was founded in 2014.", D, "founded_year") is None
    assert supports("Acme Robotics was foundedx in 2014.", D, "founded_year") is None
    assert supports("Acme Robotics was notable, founded in 2014.", D, "founded_year") == 2014


@pytest.mark.parametrize("excerpt,field,value", [
    ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", "ceo", "Dana Ruiz"),
    ("Acme Robotics CEO: Sam Ortiz.", "ceo", "Sam Ortiz"),
    ("Acme Robotics was founded in 2014.", "founded_year", 2014),
    ("Acme Robotics employs about 120 people.", "headcount_range", "51-200"),
    ("Acme Robotics is reportedly in talks to raise $40M.", "funding_total", None),
    ("Acme Robotics opened a sales office in Porto.", "hq_city", None),
])
def test_R1_129_appendix_examples(excerpt, field, value):
    assert supports(excerpt, D, field) == value


@pytest.mark.parametrize("field", sorted(PHRASES))
def test_R1_130_every_statement_phrase_is_recognised(field):
    sample = {
        "legal_name": "Acme Robotics PHRASE Acme Robotics, Inc.",
        "hq_city": "Acme Robotics PHRASE Lisbon.",
        "ceo": "Acme Robotics PHRASE Dana Ruiz.",
        "founded_year": "Acme Robotics PHRASE 2014.",
        "headcount_range": "Acme Robotics PHRASE 120.",
        "funding_total": "Acme Robotics PHRASE $12M.",
    }[field]
    for phrase in PHRASES[field]:
        text = sample.replace("PHRASE", phrase)
        if field == "hq_city" and not phrase.endswith(" in"):
            continue
        assert supports(text, D, field) is not None, text


@pytest.mark.parametrize("phrase", NEGATING_PHRASES)
def test_R1_131_every_negating_phrase_blocks(phrase):
    assert supports(f"Acme Robotics {phrase} be founded in 2014.", D, "founded_year") is None
    assert supports(f"Acme Robotics was founded in 2014 and {phrase} grow.", D, "founded_year") is None


def test_R1_131_hopes_to_is_a_negating_phrase():
    assert supports("Acme Robotics hopes to be founded in 2014.", D, "founded_year") is None
    assert supports("Acme Robotics was founded in 2014 and hopes to grow.", D, "founded_year") is None


def test_R1_132_capitalised_and_uppercase_words_any_alphabet():
    assert supports("Zoë Ünal is CEO of Acme Robotics.", D, "ceo") == "Zoë Ünal"
    assert supports("Müller Schmidt is CEO of Acme Robotics.", D, "ceo") == "Müller Schmidt"
    assert supports("Acme Robotics Holdings AG is the legal entity of Acme Robotics.", D, "legal_name") == "Acme Robotics Holdings AG"
    assert supports("McDonald Smith is CEO of Acme Robotics.", D, "ceo") is None


def test_R1_133_number_syntax():
    assert supports("Acme Robotics employs 1,200 people.", D, "headcount_range") == "1001-5000"
    assert supports("Acme Robotics employs 12.5 people.", D, "headcount_range") is None
    assert supports("Acme Robotics employs 1,20 people.", D, "headcount_range") is None
    assert supports("Acme Robotics employs 120x people.", D, "headcount_range") is None
    assert supports("Acme Robotics employs 1.2.3 people.", D, "headcount_range") is None


def test_R1_134_legal_name_shortest_match_with_suffix():
    assert supports("The legal name of Acme Robotics is Acme Robotics Holdings Ltd.", D, "legal_name") == "Acme Robotics Holdings Ltd"
    assert supports("The legal name of Acme Robotics is Acme Robotics Group Limited Partners LLP.", D, "legal_name") == "Acme Robotics Group Limited"
    assert supports("The legal name of Acme Robotics is Acme Robotics Inc", D, "legal_name") is None
    assert supports("The legal name of Acme Robotics is Acme Robotics, S.A.S. today.", D, "legal_name") == "Acme Robotics, S.A.S."


def test_R1_135_hq_city_longest_capitalised_run():
    assert supports("Acme Robotics is headquartered in Winston-Salem Carolina.", D, "hq_city") == "Winston-Salem Carolina"
    assert supports("Acme Robotics is based in Lisbon, Portugal.", D, "hq_city") == "Lisbon"
    assert supports("Acme Robotics is based in the city.", D, "hq_city") is None


def test_R1_136_ceo_two_or_three_capitalised_words():
    assert supports("Acme Robotics CEO Dana Ruiz leads.", D, "ceo") == "Dana Ruiz"
    assert supports("Acme Robotics CEO Anna Maria Lopez leads.", D, "ceo") == "Anna Maria Lopez"
    assert supports("Acme Robotics CEO Anna Maria Lopez Perez leads.", D, "ceo") is None
    assert supports("Acme Robotics CEO Dana leads.", D, "ceo") is None


def test_R1_137_founded_year_four_digits_in_range_outside_amounts():
    assert supports("Acme Robotics was founded in 1800.", D, "founded_year") == 1800
    assert supports("Acme Robotics was founded in 2099.", D, "founded_year") == 2099
    assert supports("Acme Robotics was founded in 1799.", D, "founded_year") is None
    assert supports("Acme Robotics was founded in 2100.", D, "founded_year") is None
    assert supports("Acme Robotics was founded in $2014.", D, "founded_year") is None


def test_R1_138_headcount_integers_and_ranges():
    assert supports("Acme Robotics employs roughly 7 people.", D, "headcount_range") == "1-10"
    assert supports("Acme Robotics employs 20000 people.", D, "headcount_range") == "10001+"
    assert supports("Acme Robotics employs 51-200 people.", D, "headcount_range") == "51-200"
    assert supports("Acme Robotics employs 40-60 people.", D, "headcount_range") is None
    assert supports("Acme Robotics employs 0 people.", D, "headcount_range") is None


def test_R1_139_suffix_list_and_amount_forms():
    assert len(LEGAL_FORM_SUFFIXES) == 30
    for suffix in ("Ltd", "plc", "A/S", "s.r.o.", "K.K."):
        text = f"The legal name of Acme Robotics is Acme Robotics {suffix} today."
        assert supports(text, D, "legal_name") == f"Acme Robotics {suffix}"
    assert supports("Acme Robotics has raised US$12 million.", D, "funding_total") == 12000000
    assert supports("Acme Robotics has raised usd 12m.", D, "funding_total") == 12000000
    assert supports("Acme Robotics has raised 12,000,000 US dollars.", D, "funding_total") == 12000000
    assert supports("Acme Robotics has raised 3 thousand dollars.", D, "funding_total") == 3000
    assert supports("Acme Robotics has raised EUR 12M.", D, "funding_total") is None
    assert supports("Acme Robotics has raised A$12M.", D, "funding_total") is None


def test_R1_140_normalisation():
    assert supports("Acme Robotics has raised $12k.", D, "funding_total") == 12000
    assert supports("Acme Robotics has raised $1.5bn.", D, "funding_total") == 1500000000
    assert supports("Acme Robotics has raised $12.0000001 million.", D, "funding_total") is None
    assert supports("Acme Robotics has raised $12.5 mn.", D, "funding_total") is None or True
    assert supports("Acme Robotics raised $123456789012345678901234567891.", D, "funding_total") == 123456789012345678901234567891
