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


def test_patience_is_uniform_and_at_least_thirty_seconds():
    t = Timeouts()
    assert min(t.search_s, t.extract_s, t.research_s, t.min_call_s) >= 30
    assert t.build_s <= 280


# live-shape parsing and timing (R1.84)
from types import SimpleNamespace

from app.research.providers import ProviderCalls, claims_of
from tests.research.fake_router import FakeRouter


def research_response(structured, *citations):
    return SimpleNamespace(structured=structured, citations=list(citations))


def citation(field, snippet="", url="https://x.test/p", extra=None):
    return SimpleNamespace(field=field, snippet=snippet, url=url, extra=extra or {})


def test_claims_read_every_excerpt_and_field_path_form():
    response = research_response(
        {"ceo": "Dana Ruiz", "founded_year": "2014"},
        citation("$.ceo", "first.", extra={"excerpts": ["first.", "second."]}),
        citation("founded_year", "Acme was founded in 2014."),
        citation("$.hq_city", "Based in Lisbon."),  # no value claimed for this field
        citation(None, "unfielded source"),
    )
    claims = claims_of(response)
    assert [(c.field, c.value, c.excerpt) for c in claims] == [
        ("ceo", "Dana Ruiz", "first."),
        ("ceo", "Dana Ruiz", "second."),
        ("founded_year", 2014, "Acme was founded in 2014."),
    ]


def test_claims_ignore_a_list_answer():
    assert claims_of(research_response([{"ceo": "A B"}], citation("$.ceo", "x"))) == []


def test_no_call_is_started_with_less_than_the_minimum_wait_left():
    timeouts = Timeouts(build_s=20)
    router = FakeRouter("halvorsen-robotics.test")
    calls = ProviderCalls(lambda units: None, timeouts, env={"NIMBLE_API_KEY": "k"}, router=router)
    results, outcome = asyncio.run(calls.search("halvorsen-robotics.test"))
    assert results is None and not outcome.ok and router.calls == []
