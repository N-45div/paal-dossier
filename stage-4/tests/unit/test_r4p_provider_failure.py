"""R4P provider failure (stage 4, R4.57-R4.61): a 5xx or 429 answer costs nothing; a build whose
calls all fail ends failed, and one whose research fails while search and extract answer ends
ready. Runs the real pipeline against a fake router, with no network."""

from __future__ import annotations

import asyncio
import types

import pytest
from web_router import ProviderError

from app import gateway, research
from tests.unit.test_build_spend import DOMAIN, PAGE_TEXT, StatusError


class ServerErrorRouter:
    """Every call to the named methods answers with the given HTTP status."""

    def __init__(self, failing: set[str], status: int) -> None:
        self.failing = failing
        self.status = status

    def _fail(self) -> None:
        raise ProviderError("nimble", "injected fault", original=StatusError(self.status))

    async def search(self, query, **_):
        if "search" in self.failing:
            self._fail()
        return types.SimpleNamespace(urls=[f"https://{DOMAIN}/about"])

    async def extract(self, urls, **_):
        if "extract" in self.failing:
            self._fail()
        return types.SimpleNamespace(documents=[types.SimpleNamespace(url=urls[0], content=PAGE_TEXT)])

    async def research(self, query, **_):
        if "research" in self.failing:
            self._fail()
        citation = types.SimpleNamespace(url=f"https://{DOMAIN}/about", snippet="Acme Robotics is based in Lisbon.")
        return types.SimpleNamespace(citations=[citation])


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(research, "RETRY_DELAY_S", 0)
    monkeypatch.setattr(gateway, "SERVER_ERROR_WAIT_S", 0)
    monkeypatch.setenv("NIMBLE_API_KEY", "test-key")


def run(monkeypatch, failing: set[str], status: int):
    monkeypatch.setattr(gateway, "_client", lambda: ServerErrorRouter(failing, status))
    notified: list[int] = []
    outcome = asyncio.run(research.run_build(DOMAIN, notified.append))
    return outcome, sum(notified)


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_every_5xx_answer_costs_nothing(monkeypatch, status):
    outcome, net = run(monkeypatch, {"search", "extract", "research"}, status)
    assert not outcome.ok
    assert outcome.spent_units == 0
    assert net == 0


@pytest.mark.parametrize("status", [500, 503])
def test_research_failing_with_5xx_still_completes_ready(monkeypatch, status):
    outcome, net = run(monkeypatch, {"research"}, status)
    assert outcome.ok
    assert net == outcome.spent_units
