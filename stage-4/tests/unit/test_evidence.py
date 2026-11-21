"""Unit tests for app/budget.py and app/evidence.py: the ledger, candidates and the transitional decision."""

from app.budget import BUILD_BUDGET_UNITS, Ledger
from app.evidence import collect_candidates, decide_fields
from app.gateway import ServedPage
from app.support import FIELDS

DOMAIN = "acme-robotics.test"


def page(url, prose, headers=None):
    return ServedPage(url=url, prose=prose, headers=dict(headers or {}))


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
    assert not ledger.reserve(1)


def test_release_gives_units_back_and_never_goes_negative():
    ledger = Ledger(limit=10)
    ledger.reserve(4)
    ledger.release(4)
    assert ledger.spent == 0
    ledger.release(3)
    assert ledger.spent == 0


# --- collect_candidates ----------------------------------------------------------


def test_candidates_come_back_per_field_with_page_kind_and_time():
    pages = [page("https://acme-robotics.test/about", "Acme Robotics was founded in 2014.",
                  {"Published": "2026-01-10T00:00:00Z"})]
    result = collect_candidates(DOMAIN, pages)
    assert tuple(result) == FIELDS
    [candidate] = result["founded_year"]
    assert candidate.value == 2014
    assert candidate.url == "https://acme-robotics.test/about"
    assert candidate.excerpt == "Acme Robotics was founded in 2014."
    assert candidate.provider == "nimble"
    assert candidate.kind == "own"
    assert candidate.published_at == "2026-01-10T00:00:00+00:00"


def test_kind_follows_the_declared_kind_or_the_host():
    pages = [
        page("https://bizdata.test/acme", "Acme Robotics was founded in 2014.", {"Kind": "news"}),
        page("https://bizdata.test/acme2", "Acme Robotics was founded in 2015."),
    ]
    result = collect_candidates(DOMAIN, pages)["founded_year"]
    assert [c.kind for c in result] == ["news", "aggregator"]
    assert [c.published_at for c in result] == [None, None]


def test_one_candidate_per_value_per_page_keeps_the_first_excerpt():
    pages = [page("https://a.test/1", "Acme Robotics was founded in 2015.\n\n"
                                      "Acme Robotics was founded in 2015.")]
    result = collect_candidates(DOMAIN, pages)["founded_year"]
    assert len(result) == 1


def test_every_supported_value_of_a_page_is_its_own_candidate():
    pages = [page("https://a.test/1", "Acme Robotics was founded in 2014.\n"
                                      "Acme Robotics was founded in 2015 by Dana Ruiz.")]
    values = sorted(c.value for c in collect_candidates(DOMAIN, pages)["founded_year"])
    assert values == [2014, 2015]


def test_distinct_pages_give_distinct_candidates_for_the_same_value():
    pages = [page("https://a.test/1", "Acme Robotics was founded in 2014."),
             page("https://b.test/1", "Acme Robotics was founded in 2014.")]
    assert len(collect_candidates(DOMAIN, pages)["founded_year"]) == 2


def test_header_text_is_never_evidence():
    pages = [page("https://a.test/1", "Body without facts.", {"Facts": "Acme Robotics was founded in 2014"})]
    assert collect_candidates(DOMAIN, pages)["founded_year"] == []


# --- decide_fields (transitional) ---------------------------------------------------


def test_every_field_is_present_and_unknown_without_evidence():
    decided = decide_fields(collect_candidates(DOMAIN, []))
    assert tuple(decided) == FIELDS
    assert all(result.value is None and result.citations == [] for result in decided.values())


def test_value_supported_by_most_distinct_pages_wins():
    pages = [
        page("https://a.test/1", "Acme Robotics was founded in 2014."),
        page("https://b.test/1", "Acme Robotics was founded in 2015."),
        page("https://c.test/1", "Acme Robotics was founded in 2015."),
    ]
    assert decide_fields(collect_candidates(DOMAIN, pages))["founded_year"].value == 2015


def test_ties_go_to_the_value_whose_first_excerpt_is_earliest():
    pages = [
        page("https://a.test/1", "Acme Robotics was founded in 2015."),
        page("https://b.test/1", "Acme Robotics was founded in 2014."),
    ]
    assert decide_fields(collect_candidates(DOMAIN, pages))["founded_year"].value == 2015


def test_citations_are_at_most_three_and_each_supports_the_value():
    pages = [page(f"https://p{i}.test/x", "Acme Robotics was founded in 2014.") for i in range(5)]
    result = decide_fields(collect_candidates(DOMAIN, pages))["founded_year"]
    assert result.value == 2014
    assert len({c["url"] for c in result.citations}) == 3
    assert all(c["excerpt"] == "Acme Robotics was founded in 2014." for c in result.citations)
