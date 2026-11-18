"""R1.84 without a live key: live-mode patience, proven on a virtual clock."""
import asyncio

import pytest

from app.research import build as build_module
from app.research.config import Config

from fakes import FakeRouter, FakeRuntime
from virtual_time import run_virtual

DOMAIN = "acme-robotics.test"
PAGES = {
    "https://acme-robotics.test/about": (
        "Acme Robotics was founded in 2014. Acme Robotics is headquartered in Lisbon."
    ),
}
CLAIM = [("ceo", "Dana Ruiz", "https://x.test/1",
          "Dana Ruiz has led Acme Robotics as chief executive since 2021.")]


class Slow(FakeRouter):
    def __init__(self, *args, search=0, extract=0, research=0, **kw):
        super().__init__(*args, **kw)
        self.delays = {"search": search, "extract": extract, "research": research}

    async def search(self, *a, **k):
        await asyncio.sleep(self.delays["search"])
        return await super().search(*a, **k)

    async def extract(self, *a, **k):
        await asyncio.sleep(self.delays["extract"])
        return await super().extract(*a, **k)

    async def research(self, *a, **k):
        await asyncio.sleep(self.delays["research"])
        return await super().research(*a, **k)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.delenv("NIMBLE_BASE_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_BASE_URL", raising=False)

    def go(router):
        config = Config.from_env()
        assert config.live
        monkeypatch.setattr(build_module.Config, "from_env", classmethod(lambda cls: config))
        monkeypatch.setattr(build_module, "open_runtime", lambda _c: FakeRuntime(router))
        spent = []
        result, elapsed = run_virtual(lambda: build_module.run_build(DOMAIN, spent.append))
        return result, elapsed, spent
    return go


def test_R1_84_a_25_second_search_is_waited_for(live):
    result, elapsed, _ = live(Slow(PAGES, search=25))
    assert result["fields"]["founded_year"]["value"] == 2014
    assert 25 <= elapsed < 300


def test_R1_84_a_70_second_research_run_is_waited_for(live):
    result, elapsed, spent = live(Slow(PAGES, claims=CLAIM, research=70))
    assert result["fields"]["ceo"]["value"] == "Dana Ruiz"
    assert elapsed >= 70 and 25 in spent


def test_R1_84_gathering_continues_past_100_seconds(live):
    result, elapsed, _ = live(Slow(PAGES, claims=CLAIM, search=40, extract=40, research=120))
    assert result["fields"]["hq_city"]["value"] == "Lisbon"   # extracted at 80 s
    assert result["fields"]["ceo"]["value"] == "Dana Ruiz"    # research answered at 120 s
    assert 120 <= elapsed < 300


def test_R1_84_build_ends_within_300_seconds_whatever_happens(live):
    result, elapsed, spent = live(Slow(PAGES, search=10**6, extract=10**6, research=10**6))
    assert elapsed < 300
    assert result["ok"] is False
    assert sum(spent) <= 80


@pytest.mark.parametrize("base_url,expected", [
    (None, True),
    ("https://sdk.nimbleway.com", True),
    ("https://sdk.nimbleway.com/", True),
    ("http://web:8080/nimble", False),
    ("", False),
])
def test_R1_84_live_detector(monkeypatch, base_url, expected):
    if base_url is None:
        monkeypatch.delenv("NIMBLE_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("NIMBLE_BASE_URL", base_url)
    assert Config.from_env().live is expected
