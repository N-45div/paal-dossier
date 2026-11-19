"""Fragment search and per-text work stay bounded (R1.105, R1.76)."""

import time

from dossier.engine.evidence import Evidence
from dossier.engine.providers import Page
from dossier.engine.support import FRAGMENT_SENTENCE_MAX_CHARS, FragmentBudget, supporting_excerpts

D = "long-proof.test"
FILLER = ("plain words here and there " * 2000)


def cpu(function):
    start = time.process_time()
    result = function()
    return result, time.process_time() - start


def test_forty_kilobyte_sentence_with_company_phrase_and_value_at_the_start_is_under_a_second():
    sentence = "Long Proof was founded in 2014 " + FILLER[:40000] + " Long Proof"
    assert 40000 < len(sentence) <= FRAGMENT_SENTENCE_MAX_CHARS
    found, seconds = cpu(lambda: supporting_excerpts(sentence, D, FragmentBudget()))
    assert seconds < 1.0
    assert found == [("founded_year", 2014, "Long Proof was founded in 2014")]


def test_sentence_over_the_fragment_limit_is_not_searched_but_stays_fast():
    sentence = "Long Proof was founded in 2014 " + FILLER[: FRAGMENT_SENTENCE_MAX_CHARS + 1]
    found, seconds = cpu(lambda: supporting_excerpts(sentence, D, FragmentBudget()))
    assert seconds < 2.0
    assert found == []


def test_exhausted_build_budget_only_drops_fragments_and_does_not_fail():
    sentence = "Long Proof was founded in 2014 " + FILLER[:30000]
    found = supporting_excerpts(sentence, D, FragmentBudget(checks=0, sentences=0))
    assert found == []


def test_build_sized_pages_load_in_well_under_five_seconds():
    body = ("Long Proof was founded in 2014 and " + ("zeta " * 90).strip() + ". ") * 300
    assert len(body) > 140_000
    pages = [Page(f"https://long-proof.test/p{k}", "t", body, "nimble") for k in range(10)]

    def load():
        evidence = Evidence(D)
        for page in pages:
            evidence.add_page(page)
        return evidence.decide()

    fields, seconds = cpu(load)
    assert seconds < 5.0
    assert fields["founded_year"].value == 2014
