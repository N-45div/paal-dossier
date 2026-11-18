"""P4 ledger ids that need their own checks (see stage-1/LEDGER.md)."""
import pytest

from app.research import costs
from app.research.config import Config
from app.research.runtime import _provider_config


def clear(monkeypatch):
    for name in ("NIMBLE_BASE_URL", "TAVILY_BASE_URL", "TAVILY_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_R1_141_costs_table():
    assert [costs.search_cost("nimble", d) for d in ("lite", "fast", "deep")] == [1, 5, 15]
    assert [costs.search_cost("tavily", d) for d in ("lite", "fast", "deep")] == [8, 16, 16]
    assert (costs.extract_cost("nimble"), costs.extract_cost("tavily", 3)) == (1, 6)
    assert costs.NIMBLE_RESEARCH == 25


def test_R1_84_live_mode_waits_at_least_thirty_seconds_per_call(monkeypatch):
    clear(monkeypatch)
    for base in (None, "https://sdk.nimbleway.com", "https://sdk.nimbleway.com/v2"):
        if base:
            monkeypatch.setenv("NIMBLE_BASE_URL", base)
        config = Config.from_env()
        assert config.live and config.call_timeout >= 30 and config.research_timeout >= 60
        assert config.build_deadline >= 120 and config.build_deadline < 300


def test_R1_83_mock_mode_outwaits_slow_providers_and_ends_before_event_wait(monkeypatch):
    clear(monkeypatch)
    monkeypatch.setenv("NIMBLE_BASE_URL", "http://web:8080/nimble")
    config = Config.from_env()
    assert not config.live
    assert config.call_timeout >= 11 and config.build_deadline <= 30


def test_R1_09_R1_10_tavily_base_url_goes_to_provider_config(monkeypatch):
    clear(monkeypatch)
    monkeypatch.setenv("TAVILY_BASE_URL", "http://web:8080/tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    config = Config.from_env()
    assert config.tavily_enabled
    assert _provider_config(config)["tavily"] == {"api_base_url": "http://web:8080/tavily"}


def test_R1_06_tavily_is_optional(monkeypatch):
    clear(monkeypatch)
    assert not Config.from_env().tavily_enabled
    assert "tavily" not in _provider_config(Config.from_env())


def test_R1_07_only_web_router_reaches_providers():
    import pathlib
    import re
    root = pathlib.Path(costs.__file__).parent
    source = "\n".join(p.read_text() for p in root.glob("*.py"))
    assert not re.search(r"^\s*(import|from)\s+(httpx|requests|aiohttp|urllib3|nimble_python|tavily)\b", source, re.M)


def test_R1_02a_only_six_fields_are_researched():
    from app.research import FIELD_NAMES
    from app.research.gateway import FIELD_SCHEMA_TYPES
    assert set(FIELD_SCHEMA_TYPES) == set(FIELD_NAMES) and len(FIELD_NAMES) == 6
