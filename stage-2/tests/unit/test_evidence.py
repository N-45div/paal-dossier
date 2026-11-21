"""Unit tests for app/budget.py and app/evidence.py: the ledger and the per-field decision."""

from app.budget import BUILD_BUDGET_UNITS, Ledger
from app.evidence import collect_candidates, decide_fields
from app.gateway import CitedClaim, ServedPage
from app.support import FIELDS

DOMAIN = "acme-robotics.test"


def page(url, prose):
    return ServedPage(url=url, prose=prose)


# --- budget ----------------------------------------------------------------------


def test_ledger_limit_is_80_units():
    assert BUILD_BUDGET_UNITS == 80
    assert Ledger().limit == 80


def test_reserve_refuses_what_does_not_fit():
    ledger = Ledger(limit=10)
    assert ledger.reserve(9)
    assert not ledger.reserve(2)
    assert ledger.spent == 9


def test_reserve_exactly_to_the_limit():
    ledger = Ledger(limit=10)
    assert ledger.reserve(10)
    assert ledger.spent == 10
    assert not ledger.reserve(1)


def test_release_gives_units_back_and_never_goes_negative():
    ledger = Ledger(limit=10)
    ledger.reserve(4)
    ledger.release(4)
    assert ledger.spent == 0
    ledger.release(3)
    assert ledger.spent == 0


# --- collect_candidates ----------------------------------------------------------


def test_page_sentences_become_candidates_with_their_url():
    pages = [page("https://acme-robotics.test/about", "Acme Robotics was founded in 2014.")]
    candidates = collect_candidates(DOMAIN, pages, [])
    assert [(c.field, c.value, c.url, c.provider) for c in candidates] == [
        ("founded_year", 2014, "https://acme-robotics.test/about", "nimble")
    ]


def test_research_citation_counts_only_when_it_is_verbatim_prose_of_a_gathered_page():
    pages = [page("https://acme-robotics.test/about", "Acme Robotics is based in Lisbon.")]
    claims = [
        CitedClaim("https://acme-robotics.test/about", "Acme Robotics is based in Lisbon."),
        CitedClaim("https://acme-robotics.test/about", "Acme Robotics is based in Porto."),
        CitedClaim("https://elsewhere.test/page", "Acme Robotics is based in Lisbon."),
    ]
    candidates = collect_candidates(DOMAIN, pages, claims)
    values = [(c.field, c.value, c.url) for c in candidates]
    assert values.count(("hq_city", "Lisbon", "https://acme-robotics.test/about")) == 2
    assert ("hq_city", "Porto", "https://acme-robotics.test/about") not in values


def test_research_citation_must_be_verbatim_not_reworded():
    pages = [page("https://acme-robotics.test/about", "Acme Robotics was founded in 2014.")]
    claims = [CitedClaim("https://acme-robotics.test/about", "Acme Robotics was founded in 2015.")]
    candidates = collect_candidates(DOMAIN, pages, claims)
    assert [(c.value, c.excerpt) for c in candidates] == [(2014, "Acme Robotics was founded in 2014.")]


def test_research_citation_header_text_is_not_evidence():
    pages = [page("https://acme-robotics.test/about", "Acme Robotics was founded in 2014.")]
    claims = [CitedClaim("https://acme-robotics.test/about", "Facts: Acme Robotics was founded in 2014")]
    candidates = collect_candidates(DOMAIN, pages, claims)
    assert [c.excerpt for c in candidates] == ["Acme Robotics was founded in 2014."]


# --- decide_fields ---------------------------------------------------------------


def test_every_field_is_present_and_unknown_without_evidence():
    decided = decide_fields([])
    assert tuple(decided) == FIELDS
    assert all(result.value is None and result.citations == [] for result in decided.values())


def test_value_supported_by_most_distinct_pages_wins():
    pages = [
        page("https://a.test/1", "Acme Robotics was founded in 2014."),
        page("https://b.test/1", "Acme Robotics was founded in 2015."),
        page("https://c.test/1", "Acme Robotics was founded in 2015."),
    ]
    decided = decide_fields(collect_candidates(DOMAIN, pages, []))
    assert decided["founded_year"].value == 2015


def test_ties_go_to_the_value_whose_first_excerpt_is_earliest():
    pages = [
        page("https://a.test/1", "Acme Robotics was founded in 2014."),
        page("https://b.test/1", "Acme Robotics was founded in 2015."),
    ]
    decided = decide_fields(collect_candidates(DOMAIN, pages, []))
    assert decided["founded_year"].value == 2014


def test_same_page_repeating_a_value_counts_once():
    pages = [
        page("https://a.test/1", "Acme Robotics was founded in 2015.\n\nAcme Robotics was founded in 2015."),
        page("https://b.test/1", "Acme Robotics was founded in 2014."),
        page("https://c.test/1", "Acme Robotics was founded in 2014."),
    ]
    decided = decide_fields(collect_candidates(DOMAIN, pages, []))
    assert decided["founded_year"].value == 2014


def test_citations_are_at_most_three_and_each_supports_the_value():
    pages = [
        page(f"https://p{i}.test/x", "Acme Robotics was founded in 2014.") for i in range(5)
    ]
    result = decide_fields(collect_candidates(DOMAIN, pages, []))["founded_year"]
    assert result.value == 2014
    assert len(result.citations) == 3
    assert len({c["url"] for c in result.citations}) == 3
    for citation in result.citations:
        assert citation["excerpt"] == "Acme Robotics was founded in 2014."
        assert citation["provider"] == "nimble"


def test_citation_dicts_have_url_excerpt_and_provider():
    pages = [page("https://a.test/1", "Acme Robotics raised $12M.")]
    result = decide_fields(collect_candidates(DOMAIN, pages, []))["funding_total"]
    assert result.value == 12_000_000
    assert result.citations == [
        {"url": "https://a.test/1", "excerpt": "Acme Robotics raised $12M.", "provider": "nimble"}
    ]
