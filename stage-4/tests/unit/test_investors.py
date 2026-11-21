"""The `investors` field (stage 4, R4B): investor names from excerpts, members and the decision."""

from datetime import date

from app.candidates import Candidate
from app.investors import decide_investors, investor_names, is_member

DOMAIN = "acme-robotics.test"
URL = "https://acme-robotics.test/news"


def _candidate(name, url=URL, kind="news", true_from=None):
    return Candidate(value=name, url=url, excerpt=f"Backed by {name}.", provider="nimble",
                     kind=kind, published_at=None, true_from=true_from)


def test_led_by_with_an_amount_takes_any_run_after_the_phrase():
    text = "Acme Robotics raised $40M in a round led by General Atlantic."
    assert investor_names(DOMAIN, text) == {"General Atlantic"}


def test_suffix_run_is_an_investor_name():
    assert investor_names(DOMAIN, "Acme Robotics was backed by Bluebird Capital.") == {"Bluebird Capital"}


def test_two_suffix_runs_are_two_names():
    text = "Acme Robotics was backed by Northwind Ventures and Harbor Partners."
    assert investor_names(DOMAIN, text) == {"Northwind Ventures", "Harbor Partners"}


def test_led_by_a_person_without_amount_names_no_investor():
    assert investor_names(DOMAIN, "Acme Robotics is led by Dana Ruiz.") == set()


def test_excerpt_without_a_statement_phrase_names_no_investor():
    assert investor_names(DOMAIN, "Bluebird Capital owns a stake in Acme Robotics.") == set()


def test_negated_excerpt_names_no_investor():
    assert investor_names(DOMAIN, "Acme Robotics is not backed by Bluebird Capital.") == set()


def test_name_with_one_word_and_suffix_is_not_a_name_without_amount():
    assert investor_names(DOMAIN, "Acme Robotics had an investor named Fund.") == set()


def test_is_member_when_a_candidate_is_own_or_filing():
    assert is_member([_candidate("Bluebird Capital", kind="own")], {"a.test"})
    assert is_member([_candidate("Bluebird Capital", kind="filing")], {"a.test"})


def test_is_member_when_two_distinct_origins_support_it():
    assert is_member([_candidate("Bluebird Capital"), _candidate("Bluebird Capital")],
                     {"dealwire.test", "registry.test"})


def test_not_a_member_from_one_news_origin():
    assert not is_member([_candidate("Bluebird Capital")], {"dealwire.test"})


def test_decision_members_sorted_and_citations_follow_members():
    own = _candidate("Northwind Ventures", kind="own", true_from=date(2024, 5, 2))
    news = _candidate("Bluebird Capital", url="https://dealwire.test/a", kind="news")
    origin = lambda c: c.url.split("/")[2]
    decision = decide_investors([news, own], origin)
    assert decision.status == "known"
    assert decision.value == ["Northwind Ventures"]
    assert decision.citations == [{"url": URL, "excerpt": own.excerpt, "provider": "nimble"}]


def test_decision_unknown_without_members():
    decision = decide_investors([_candidate("Bluebird Capital")], lambda c: c.url.split("/")[2])
    assert decision.status == "unknown"
    assert decision.value is None
    assert decision.true_from is None
    assert decision.citations == []
    assert decision.selected == ()


def test_member_true_from_is_earliest_non_null_and_field_is_latest_of_members():
    early = _candidate("Northwind Ventures", kind="own", true_from=date(2023, 1, 1))
    late = _candidate("Northwind Ventures", url="https://dealwire.test/x", kind="news",
                      true_from=date(2024, 6, 1))
    other = _candidate("Bluebird Capital", kind="own", true_from=date(2022, 3, 3))
    decision = decide_investors([early, late, other], lambda c: c.url.split("/")[2])
    assert decision.member_true_from("Northwind Ventures") == date(2023, 1, 1)
    assert decision.true_from == date(2023, 1, 1)


def test_field_true_from_is_null_when_a_member_has_none():
    with_date = _candidate("Northwind Ventures", kind="own", true_from=date(2023, 1, 1))
    no_date = _candidate("Bluebird Capital", kind="own", true_from=None)
    decision = decide_investors([with_date, no_date], lambda c: c.url.split("/")[2])
    assert decision.true_from is None
