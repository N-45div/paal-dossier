"""Unit tests for run_build's on_spend notifications (Rul-11), with a fake WebRouter client.

The fake answers the three Nimble calls the build makes. Its failures are provider
errors with an HTTP status, which must release their reservation.
"""

import asyncio
import types

import pytest
from web_router import ProviderError

from app import gateway, research

DOMAIN = "acme-robotics.test"
PAGE_TEXT = "Facts: {}\n\nAcme Robotics was founded in 2014. Acme Robotics is based in Lisbon."


class StatusError(Exception):
    """Stands in for an SDK error carrying an HTTP status code."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def refused(provider: str = "nimble") -> ProviderError:
    return ProviderError(provider, "injected fault", original=StatusError(500))


class FakeRouter:
    """Answers search, extract and research; any method listed in ``failing`` is refused."""

    def __init__(self, failing: set[str]) -> None:
        self.failing = failing

    async def search(self, query, **_):
        if "search" in self.failing:
            raise refused()
        return types.SimpleNamespace(urls=[f"https://{DOMAIN}/about"])

    async def extract(self, urls, **_):
        if "extract" in self.failing:
            raise refused()
        return types.SimpleNamespace(
            documents=[types.SimpleNamespace(url=urls[0], content=PAGE_TEXT)]
        )

    async def research(self, query, **_):
        if "research" in self.failing:
            raise refused()
        citation = types.SimpleNamespace(url=f"https://{DOMAIN}/about", snippet="Acme Robotics is based in Lisbon.")
        return types.SimpleNamespace(citations=[citation])


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(research, "RETRY_DELAY_S", 0)
    monkeypatch.setenv("NIMBLE_API_KEY", "test-key")


def run_with(monkeypatch, failing: set[str]):
    monkeypatch.setattr(gateway, "_client", lambda: FakeRouter(failing))
    notified: list[int] = []
    outcome = asyncio.run(research.run_build(DOMAIN, notified.append))
    return outcome, sum(notified)


def test_notifications_net_to_spent_units_when_everything_answers(monkeypatch):
    outcome, net = run_with(monkeypatch, failing=set())
    assert outcome.ok
    assert outcome.spent_units > 0
    assert net == outcome.spent_units


def test_refused_calls_release_their_reservations(monkeypatch):
    outcome, net = run_with(monkeypatch, failing={"search", "extract", "research"})
    assert not outcome.ok
    assert outcome.spent_units == 0
    assert net == 0


def test_partial_refusal_nets_to_spent_units(monkeypatch):
    outcome, net = run_with(monkeypatch, failing={"research"})
    assert outcome.ok
    assert net == outcome.spent_units


def test_run_build_tolerates_no_callback(monkeypatch):
    monkeypatch.setattr(gateway, "_client", lambda: FakeRouter(set()))
    outcome = asyncio.run(research.run_build(DOMAIN))
    assert outcome.ok
