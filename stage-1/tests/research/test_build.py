"""run_build against a fake router: accuracy on the sample corpus (M1.5), budget (M1.1), L1.21, failures (L1.23)."""

import asyncio
import json

import pytest
from web_router.exceptions import DeadlineExceededError

from app.research import run_build
from app.research.pages import ServedText, is_citation_of
from app.research.providers import UNITS_PER_BUILD
from app.research.support import FIELDS, supports

from tests.research.fake_router import FIXTURES, FakeRouter, connection_error, http_error, served_text

KEY = json.loads((FIXTURES / "key.json").read_text())
LABELLED = [d for d, v in KEY.items() if "expected" in v]


@pytest.fixture(autouse=True)
def mock_environment(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "k")
    monkeypatch.setenv("NIMBLE_BASE_URL", "http://mock.invalid/nimble")
    monkeypatch.setattr("app.research.providers.RETRY_PAUSE_S", 0)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_BASE_URL", raising=False)


def build(domain, router):
    spent: list[int] = []
    result = asyncio.run(run_build(domain, spent.append, router=router))
    return result, spent


@pytest.mark.parametrize("domain", LABELLED)
def test_fields_match_the_key(domain):
    result, spent = build(domain, FakeRouter(domain))
    expected = KEY[domain]["expected"]["1"]["0"]
    assert result["ok"]
    for field in FIELDS:
        want = expected[field]
        got = result["fields"][field]
        if want is None:
            assert got["status"] == "unknown"
        else:
            assert got["status"] == "known"
            assert got["value"] in want if isinstance(want, list) else got["value"] == want


@pytest.mark.parametrize("domain", LABELLED)
def test_every_citation_is_served_text_supporting_its_value(domain):
    router = FakeRouter(domain)
    result, _ = build(domain, router)
    pages = {p["url"]: ServedText(p["url"], "nimble", served_text(p)) for p in router._pages()}
    for field, entry in result["fields"].items():
        if entry["status"] == "unknown":
            assert entry["citations"] == []
            continue
        assert 1 <= len(entry["citations"]) <= 5
        for citation in entry["citations"]:
            assert citation["provider"] == "nimble"
            assert supports(citation["excerpt"], domain, field, entry["value"])
            assert is_citation_of(citation["excerpt"], pages[citation["url"]])


@pytest.mark.parametrize("domain", LABELLED)
def test_budget_and_single_domain_search(domain):
    router = FakeRouter(domain)
    result, spent = build(domain, router)
    assert sum(spent) <= UNITS_PER_BUILD
    searches = [c for c in router.calls if c[0] == "search"]
    assert [c[3] for c in searches].count(domain) == 1
    assert all(c[2] == "lite" for c in searches)


def test_unknown_company_has_unknown_fields_and_is_ready():
    router = FakeRouter("quillmate.test")
    result, _ = build("nobody.test", router)
    assert result["ok"] and all(f["status"] == "unknown" and f["citations"] == [] for f in result["fields"].values())


def test_failed_when_every_call_errors_and_nothing_is_charged():
    error = http_error(500)
    router = FakeRouter("halvorsen-robotics.test", fail={"search": error, "extract": error, "research": error})
    result, spent = build("halvorsen-robotics.test", router)
    assert result["ok"] is False
    assert spent == []
    assert all(f["status"] == "unknown" for f in result["fields"].values())


def test_domain_search_is_retried_only_after_an_error():
    domain = "halvorsen-robotics.test"
    router = FakeRouter(domain, fail={"search": http_error(429)})
    build(domain, router)
    attempts = [c for c in router.calls if c[0] == "search" and c[3] == domain]
    assert 1 < len(attempts) <= 4


def test_timeouts_and_lost_connections_are_charged():
    domain = "halvorsen-robotics.test"
    router = FakeRouter(domain, fail={"search": connection_error(), "extract": DeadlineExceededError("nimble", 1.0)})
    result, spent = build(domain, router)
    assert sum(spent) >= 25  # the research run, plus the charged extracts and searches
    assert sum(spent) <= UNITS_PER_BUILD


def test_research_error_alone_keeps_ready_and_most_fields():
    domain = "halvorsen-robotics.test"
    router = FakeRouter(domain, fail={"research": http_error(500)})
    result, spent = build(domain, router)
    assert result["ok"] and sum(spent) < 25 + 30
    assert result["fields"]["ceo"]["status"] == "known"


def test_research_claim_not_supported_by_its_own_citation_is_not_asserted():
    domain = "halvorsen-robotics.test"
    router = FakeRouter(domain, fail={"search": http_error(500), "extract": http_error(500)})
    router.company["research"]["nimble"]["0"] = [
        {"field": "ceo", "value": "Priya Dalton", "url": "https://x.test/", "excerpt": "Priya Dalton is a person."}
    ]
    result, _ = build(domain, router)
    assert result["fields"]["ceo"]["status"] == "unknown"


def issued_cost(router):
    costs = {"search": 1, "extract": 1, "research": 25}
    return sum(costs[call[0]] for call in router.calls)


@pytest.mark.parametrize("domain", LABELLED)
def test_spend_accounts_for_every_issued_call(domain):
    router = FakeRouter(domain)
    _, spent = build(domain, router)
    assert sum(spent) == issued_cost(router)


def test_a_failing_branch_leaves_no_call_unaccounted():
    domain = "halvorsen-robotics.test"
    router = FakeRouter(domain, fail={"extract": connection_error()})
    _, spent = build(domain, router)
    assert sum(spent) == issued_cost(router)
