"""Field decision (L1.12), cost classification of failures (§9) and timeouts (L1.18)."""

import asyncio

from web_router.exceptions import DeadlineExceededError, ProviderError

from app.research.evidence import Candidate, decide_field
from app.research.providers import Timeouts, is_charged_failure

from tests.research.fake_router import connection_error, http_error


def candidate(value, url, excerpt="x", provider="nimble"):
    return Candidate("ceo", value, url, excerpt, provider)


def test_no_candidates_is_unknown():
    assert decide_field([]) == {"value": None, "status": "unknown", "citations": []}


def test_most_urls_wins_and_only_its_excerpts_are_cited():
    field = decide_field([candidate("A B", "u1"), candidate("C D", "u2"), candidate("C D", "u3")])
    assert field["value"] == "C D"
    assert {c["url"] for c in field["citations"]} == {"u2", "u3"}


def test_tie_goes_to_first_gathered():
    assert decide_field([candidate("A B", "u1"), candidate("C D", "u2")])["value"] == "A B"


def test_citations_capped_at_five_distinct_urls_first():
    many = [candidate("A B", f"u{i}", f"e{i}") for i in range(8)] + [candidate("A B", "u0", "again")]
    citations = decide_field(many)["citations"]
    assert len(citations) == 5 and len({c["url"] for c in citations}) == 5


def test_http_refusals_are_free():
    assert not is_charged_failure(http_error(500))
    assert not is_charged_failure(http_error(429))
    assert not is_charged_failure(ProviderError("tavily", "rate", kind="rate_limit"))


def test_timeouts_connection_failures_and_missing_pages_are_charged():
    assert is_charged_failure(DeadlineExceededError("nimble", 1.0))
    assert is_charged_failure(asyncio.TimeoutError())
    assert is_charged_failure(connection_error())
    assert is_charged_failure(ProviderError("nimble", "x", kind="timeout"))
    assert is_charged_failure(ProviderError("tavily", "no URL could be extracted: no page at this URL"))


def test_timeouts_live_versus_mock():
    live = Timeouts.for_environment({})
    assert live.search_s >= 30 and live.research_s >= 100 and live.build_s <= 280
    assert Timeouts.for_environment({"NIMBLE_BASE_URL": "https://sdk.nimbleway.com"}) == live
    mock = Timeouts.for_environment({"NIMBLE_BASE_URL": "http://web:8080/nimble"})
    assert mock.build_s < 10 and mock.search_s < 5
