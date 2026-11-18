"""Cost in units of each provider call (spec section 9)."""
from __future__ import annotations

NIMBLE = "nimble"
TAVILY = "tavily"

_SEARCH = {
    NIMBLE: {"lite": 1, "fast": 5, "deep": 15},
    TAVILY: {"lite": 8, "fast": 16, "deep": 16},
}
_EXTRACT_PER_URL = {NIMBLE: 1, TAVILY: 2}
NIMBLE_RESEARCH = 25


def search_cost(provider: str, depth: str) -> int:
    return _SEARCH[provider][depth]


def extract_cost(provider: str, urls: int = 1) -> int:
    return _EXTRACT_PER_URL[provider] * urls
