"""Unit tests for run_build's on_spend notifications (Rul-11), with a fake WebRouter client.

The fake answers the three Nimble calls the build makes. Its failures are provider
errors with an HTTP status, which must release their reservation.
"""

import asyncio
import types

import pytest
from web_router import ProviderError

from app import gateway, research
from app.budget import Ledger

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


# --- 429 handling (Rul-S2-5) ----------------------------------------------------------


def rate_limited() -> ProviderError:
    return ProviderError("nimble", "rate limited", original=StatusError(429))


class ThrottledRouter(FakeRouter):
    """Answers 429 to the first ``throttles`` calls of each method, then behaves normally."""

    def __init__(self, throttles: int) -> None:
        super().__init__(set())
        self.throttles = throttles
        self.calls: dict[str, int] = {}

    def _gate(self, method: str) -> None:
        self.calls[method] = self.calls.get(method, 0) + 1
        if self.calls[method] <= self.throttles:
            raise rate_limited()

    async def search(self, query, **kwargs):
        self._gate("search")
        return await super().search(query, **kwargs)

    async def extract(self, urls, **kwargs):
        self._gate("extract")
        return await super().extract(urls, **kwargs)

    async def research(self, query, **kwargs):
        self._gate("research")
        return await super().research(query, **kwargs)


def test_three_429s_are_retried_and_the_build_succeeds(monkeypatch):
    monkeypatch.setattr(gateway, "RATE_LIMIT_WAIT_S", 0)
    router = ThrottledRouter(throttles=3)
    monkeypatch.setattr(gateway, "_client", lambda: router)
    notified: list[int] = []
    outcome = asyncio.run(research.run_build(DOMAIN, notified.append))
    assert outcome.ok
    assert sum(notified) == outcome.spent_units


def test_four_429s_give_up_on_that_call_without_spend(monkeypatch):
    monkeypatch.setattr(gateway, "RATE_LIMIT_WAIT_S", 0)
    router = ThrottledRouter(throttles=10**6)
    monkeypatch.setattr(gateway, "_client", lambda: router)
    notified: list[int] = []
    outcome = asyncio.run(research.run_build(DOMAIN, notified.append))
    assert not outcome.ok
    assert outcome.spent_units == 0
    assert sum(notified) == 0


def test_rate_limit_waits_at_least_one_point_oh_five_seconds(monkeypatch):
    waits: list[float] = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(gateway.asyncio, "sleep", fake_sleep)
    router = ThrottledRouter(throttles=2)
    monkeypatch.setattr(gateway, "_client", lambda: router)
    gw = gateway.NimbleGateway(Ledger())
    value, refused = asyncio.run(gw.search(DOMAIN))
    assert value is not None and not refused
    assert waits == [gateway.RATE_LIMIT_WAIT_S, gateway.RATE_LIMIT_WAIT_S]
    assert gateway.RATE_LIMIT_WAIT_S >= 1.05
