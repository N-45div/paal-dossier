"""Every provider call of a build, made through WebRouter and accounted in units (§9)."""

from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from web_router import AsyncWebRouter
from web_router.exceptions import DeadlineExceededError, ProviderError, ResearchTimeoutError

from app.research.pages import ServedText

SEARCH_COSTS = {"nimble": {"lite": 1, "fast": 5, "deep": 15}, "tavily": {"lite": 8, "fast": 16, "deep": 16}}
EXTRACT_COSTS = {"nimble": 1, "tavily": 2}
RESEARCH_COST = 25
UNITS_PER_BUILD = 80
RETRY_PAUSE_S = 1.1  # the mock refuses a repeat of a throttled call for one second

LIVE_NIMBLE_HOST = "sdk.nimbleway.com"
RESEARCH_FIELD_QUERY = "Research the company at {domain}: its registered legal name, headquarters city, CEO, founding year, headcount and total equity funding."
RESEARCH_PROPERTIES = {
    "legal_name": {"type": "string"},
    "hq_city": {"type": "string"},
    "ceo": {"type": "string"},
    "founded_year": {"type": "integer"},
    "headcount_range": {"type": "string"},
    "funding_total": {"type": "integer"},
}


@dataclass(frozen=True)
class Timeouts:
    search_s: float
    extract_s: float
    research_s: float
    build_s: float
    min_call_s: float  # a call is only started when at least this long is left for it to wait

    @staticmethod
    def for_environment(env: dict[str, str] | None = None) -> Timeouts:
        env = os.environ if env is None else env
        base = env.get("NIMBLE_BASE_URL")
        live = not base or urlparse(base).hostname == LIVE_NIMBLE_HOST
        if live:
            return Timeouts(search_s=45, extract_s=45, research_s=120, build_s=280, min_call_s=30)
        return Timeouts(search_s=4, extract_s=4, research_s=5, build_s=9, min_call_s=0.5)


@dataclass
class Claim:
    field: str
    value: Any
    url: str
    excerpt: str


@dataclass
class CallOutcome:
    ok: bool
    cost: int = 0  # units charged for the call


@dataclass
class Gathered:
    """What a build has obtained from providers so far."""

    texts: list[ServedText] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    search_urls: list[str] = field(default_factory=list)
    extract_tried: set[str] = field(default_factory=set)
    successes: int = 0
    domain_searched: bool = False

    def has_full_text(self, url: str) -> bool:
        return any(t.url == url and t.complete for t in self.texts)


def is_charged_failure(error: BaseException) -> bool:
    """True when a failed call still costs its units: it timed out, lost its connection, or was answered with no page."""
    if isinstance(error, (DeadlineExceededError, ResearchTimeoutError, asyncio.TimeoutError)):
        return True
    if not isinstance(error, ProviderError):
        return False
    if "no URL could be extracted" in str(error):
        return True
    if getattr(error, "kind", None) == "timeout":
        return True
    return getattr(error, "status_code", None) is None and getattr(error, "kind", None) in (None, "upstream")


class ProviderCalls:
    """Calls Nimble (and Tavily when configured) through ``web_router``, spending units against one build budget."""

    def __init__(
        self,
        spend: Callable[[int], None],
        timeouts: Timeouts,
        env: dict[str, str] | None = None,
        router: Any = None,
    ) -> None:
        env = dict(os.environ if env is None else env)
        self._spend = spend
        self._timeouts = timeouts
        self._committed = 0
        self._started = time.monotonic()
        self.tavily_enabled = bool(env.get("TAVILY_API_KEY") and env.get("TAVILY_BASE_URL"))
        config: dict[str, dict[str, Any]] = {
            "nimble": {"max_retries": 0, "timeout": timeouts.search_s, "api_key": env.get("NIMBLE_API_KEY")},
        }
        if self.tavily_enabled:
            config["tavily"] = {"api_base_url": env["TAVILY_BASE_URL"], "api_key": env["TAVILY_API_KEY"], "timeout": timeouts.search_s}
        if env.get("NIMBLE_BASE_URL"):
            config["nimble"]["base_url"] = env["NIMBLE_BASE_URL"]
        self._router = router if router is not None else AsyncWebRouter("nimble", provider_config=config)

    @property
    def committed(self) -> int:
        return self._committed

    def seconds_left(self) -> float:
        return self._timeouts.build_s - (time.monotonic() - self._started)

    def can_afford(self, cost: int) -> bool:
        return self._committed + cost <= UNITS_PER_BUILD

    async def close(self) -> None:
        await self._router.aclose()

    async def _call(self, cost: int, make_call: Callable[[], Any], limit_s: float, attempts: int) -> tuple[Any, CallOutcome]:
        """Run one provider call with up to ``attempts`` tries; a refused try costs nothing, so is retried."""
        outcome = CallOutcome(False)
        for attempt in range(attempts):
            budget_s = min(limit_s, self.seconds_left())
            if budget_s < self._timeouts.min_call_s or not self.can_afford(cost):
                break
            self._committed += cost
            try:
                result = await asyncio.wait_for(make_call(), budget_s)
            except Exception as error:  # a provider failure never fails the build
                if is_charged_failure(error):
                    self._spend(cost)
                    outcome = CallOutcome(False, cost)
                    return None, outcome
                self._committed -= cost
                if attempt + 1 < attempts and self.seconds_left() > RETRY_PAUSE_S + self._timeouts.min_call_s:
                    await asyncio.sleep(RETRY_PAUSE_S)
                continue
            self._spend(cost)
            return result, CallOutcome(True, cost)
        return None, outcome

    async def search(self, query: str, provider: str = "nimble", depth: str = "lite", attempts: int = 2) -> tuple[list[Any] | None, CallOutcome]:
        cost = SEARCH_COSTS[provider][depth]

        def make() -> Any:
            return self._router.search(query, provider=provider, search_depth=depth, max_results=10, data_apis=False)

        response, outcome = await self._call(cost, make, self._timeouts.search_s, attempts)
        return (None if response is None else response.results), outcome

    async def extract(self, url: str, provider: str = "nimble", attempts: int = 2) -> tuple[str | None, CallOutcome]:
        def make() -> Any:
            return self._router.extract([url], provider=provider)

        response, outcome = await self._call(EXTRACT_COSTS[provider], make, self._timeouts.extract_s, attempts)
        documents = [] if response is None else response.documents
        return (documents[0].content if documents else None), outcome

    async def research(self, domain: str) -> tuple[list[Claim], CallOutcome]:
        schema = {"type": "object", "properties": RESEARCH_PROPERTIES}

        def make() -> Any:
            return self._router.research(
                RESEARCH_FIELD_QUERY.format(domain=domain),
                provider="nimble",
                output_schema=schema,
                timeout=self._timeouts.research_s,
            )

        response, outcome = await self._call(RESEARCH_COST, make, self._timeouts.research_s + 2, 2)
        return ([] if response is None else claims_of(response)), outcome


_FIELD_PATH = re.compile(r"""^\$?\.?\[?['"]?([A-Za-z_]+)""")
_INTEGER_FIELDS = ("founded_year", "funding_total")


def _claim_field(path: str | None) -> str | None:
    match = _FIELD_PATH.match(path or "")
    return match.group(1) if match and match.group(1) in RESEARCH_PROPERTIES else None


def _claim_value(name: str, value: Any) -> Any:
    """The claimed value; an integer field given as digits is read as an integer."""
    if name in _INTEGER_FIELDS and isinstance(value, str) and value.strip().replace(",", "").isdigit():
        return int(value.strip().replace(",", ""))
    return value


def claims_of(response: Any) -> list[Claim]:
    """The (field, value, url, excerpt) claims of a research answer: one per cited excerpt of a field with a value."""
    structured = response.structured if isinstance(response.structured, dict) else {}
    claims = []
    for citation in response.citations:
        name = _claim_field(citation.field)
        if name is None or structured.get(name) is None:
            continue
        extra = citation.extra or {}
        excerpts = [citation.snippet, *(extra.get("excerpts") or [])]
        for excerpt in dict.fromkeys(e for e in excerpts if isinstance(e, str) and e.strip()):
            claims.append(Claim(name, _claim_value(name, structured[name]), citation.url, excerpt))
    return claims
