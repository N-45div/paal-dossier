"""R4P retries (stage 4, R4.57-R4.61): a 5xx answer is retried in the gateway; an error answer costs
nothing; the build keeps the evidence of the calls that answer. Real pipeline, fake router, no network."""

from __future__ import annotations

import asyncio
import types

import pytest
from web_router import ProviderError

from app import gateway, research
from tests.unit.test_build_spend import DOMAIN, PAGE_TEXT, StatusError

ABOUT = f"https://{DOMAIN}/about"
NEWS = f"https://news.test/{DOMAIN}"


class FaultRouter:
    """Answers search, extract and research. ``first_fail[method]`` calls of that method fail once
    with 500 each; ``always_fail_url`` maps an extract URL to a status that it always answers."""

    def __init__(self, first_fail: dict[str, int] | None = None,
                 always_fail_url: dict[str, int] | None = None) -> None:
        self.first_fail = dict(first_fail or {})
        self.always_fail_url = dict(always_fail_url or {})
        self.billed = 0

    def _maybe_fail(self, method: str) -> None:
        if self.first_fail.get(method, 0) > 0:
            self.first_fail[method] -= 1
            raise ProviderError("nimble", "injected 500", original=StatusError(500))

    async def search(self, query, **_):
        self._maybe_fail("search")
        self.billed += 1
        return types.SimpleNamespace(urls=[ABOUT, NEWS])

    async def extract(self, urls, **_):
        url = urls[0]
        if url in self.always_fail_url:
            raise ProviderError("nimble", "injected", original=StatusError(self.always_fail_url[url]))
        self._maybe_fail("extract")
        self.billed += 1
        return types.SimpleNamespace(documents=[types.SimpleNamespace(url=url, content=PAGE_TEXT)])

    async def research(self, query, **_):
        self._maybe_fail("research")
        self.billed += 1
        citation = types.SimpleNamespace(url=ABOUT, snippet="Acme Robotics is based in Lisbon.")
        return types.SimpleNamespace(citations=[citation])


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(research, "RETRY_DELAY_S", 0)
    monkeypatch.setattr(gateway, "SERVER_ERROR_WAIT_S", 0)
    monkeypatch.setenv("NIMBLE_API_KEY", "test-key")


def run(monkeypatch, router: FaultRouter):
    monkeypatch.setattr(gateway, "_client", lambda: router)
    notified: list[int] = []
    outcome = asyncio.run(research.run_build(DOMAIN, notified.append))
    return outcome, sum(notified)


def fields_of(outcome) -> dict:
    return {name: (result.value, sorted(c["url"] for c in result.citations))
            for name, result in outcome.fields.items()}


def test_first_call_of_each_kind_failing_once_gives_the_same_fields(monkeypatch):
    baseline, _ = run(monkeypatch, FaultRouter())
    flaky, net = run(monkeypatch, FaultRouter(first_fail={"search": 1, "extract": 1, "research": 1}))
    assert flaky.ok and baseline.ok
    assert fields_of(flaky) == fields_of(baseline)
    assert flaky.spent_units == baseline.spent_units  # the errors billed nothing
    assert net == flaky.spent_units


def test_one_url_always_failing_with_503_leaves_the_other_pages_counting(monkeypatch):
    outcome, net = run(monkeypatch, FaultRouter(always_fail_url={NEWS: 503}))
    assert outcome.ok
    assert ABOUT in outcome.pages  # the page that answered still counts
    assert NEWS not in outcome.pages
    assert net == outcome.spent_units


def test_exact_domain_search_failing_once_then_answering(monkeypatch):
    baseline, _ = run(monkeypatch, FaultRouter())
    outcome, _ = run(monkeypatch, FaultRouter(first_fail={"search": 1}))
    assert outcome.ok and fields_of(outcome) == fields_of(baseline)


def test_every_call_failing_ends_failed_with_no_spend(monkeypatch):
    every = {"search": 10**6, "extract": 10**6, "research": 10**6}
    outcome, net = run(monkeypatch, FaultRouter(first_fail=every))
    assert not outcome.ok
    assert outcome.spent_units == 0 and net == 0
