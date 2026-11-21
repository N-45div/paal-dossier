"""R4.31: a candidate of `investors` is one investor name, one per (name, page); a research claim
is never one of them. Builder-b, R4B."""

from app.evidence import collect_investors
from app.gateway import ServedPage

DOMAIN = "acme-robotics.test"
PAGE = "https://dealwire.test/acme-round"


def page(url: str, prose: str) -> ServedPage:
    return ServedPage(url=url, prose=prose, headers={"Kind": "news"})


def test_r4_31_each_name_in_a_sentence_is_its_own_candidate():
    """R4.31: one candidate per investor name, carrying the same excerpt and page."""
    text = ("Acme Robotics raised $40M in a round led by General Atlantic, "
            "backed by Bluebird Capital.")
    found = collect_investors(DOMAIN, [page(PAGE, text)])
    names = sorted(c.value for c in found)
    assert names == ["Bluebird Capital", "General Atlantic"]
    assert {c.url for c in found} == {PAGE}
    assert len({c.excerpt for c in found}) == 1


def test_r4_31_one_candidate_per_name_and_page_not_per_mention():
    """R4.31: the same name twice on one page is one candidate for that page."""
    text = "Acme Robotics raised $40M in a round led by General Atlantic."
    again = "Later, General Atlantic also invested in Acme Robotics."
    found = collect_investors(DOMAIN, [page(PAGE, text + " " + again)])
    assert [c.value for c in found].count("General Atlantic") == 1


def test_r4_31_the_same_name_on_two_pages_is_two_candidates():
    """R4.31: candidates are per (name, page), so each page supports the name separately."""
    text = "Acme Robotics raised $40M in a round led by General Atlantic."
    found = collect_investors(DOMAIN, [page(PAGE, text),
                                       page("https://registry.test/acme", text)])
    assert sorted(c.url for c in found) == sorted([PAGE, "https://registry.test/acme"])


def test_r4_31_no_candidate_without_a_statement_phrase_in_served_prose():
    """R4.31: a candidate's excerpt is a served sentence that names the investor (no claim text)."""
    found = collect_investors(DOMAIN, [page(PAGE, "Acme Robotics builds warehouse robots.")])
    assert found == []
