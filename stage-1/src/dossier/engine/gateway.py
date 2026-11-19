"""The only code that calls a provider. Every call goes through WebRouter (spec 2, R1.10).

Budget (R1.127-R1.131): a call reserves its table cost before it is sent. When the provider
answers with an error status, the reserve is given back. A call that gets no answer (timeout,
connection failure, unreadable answer) keeps its reserve. An extract URL that is answered with
no page (404) costs its unit: only other error statuses refuse a URL.

Calls are synchronous. Reserving, refunding and the counters are under one lock, so several
threads may call the gateway at once. Every call has a timeout of at least 30 s and never sets
`render`. The search cap is 10 results.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from web_router import ResearchTimeoutError, WebRouter

FIELD_NAMES = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "legal_name": {"type": "string"},
        "hq_city": {"type": "string"},
        "ceo": {"type": "string"},
        "founded_year": {"type": "integer"},
        "headcount_range": {"type": "string"},
        "funding_total": {"type": "integer"},
    },
}

# Cost table, spec section 9 (units).
SEARCH_COST = {
    ("nimble", "lite"): 1,
    ("nimble", "fast"): 5,
    ("nimble", "deep"): 15,
    ("tavily", "lite"): 8,
    ("tavily", "fast"): 16,
    ("tavily", "deep"): 16,
}
EXTRACT_COST = {"nimble": 1, "tavily": 2}  # per URL requested
RESEARCH_COST = 25  # nimble, when the run is started

MAX_RESULTS = 10
CALL_TIMEOUT_S = 30.0  # per call, the least the live providers are allowed
SEARCH_ADMIT_S = 30.0  # time left needed before a search or extract may start
RESEARCH_ADMIT_S = 60.0  # time left needed before a research run may start
DEFAULT_DEADLINE_S = 280.0  # hard cap per build (RL1.12)

OK = "ok"  # the provider answered without an error status
ERROR = "error"  # the provider refused with an error status; the reserve was returned
UNANSWERED = "unanswered"  # no answer (timeout, connection): the cost stands
REFUSED = "refused"  # not sent: budget, deadline, cancel, or no such provider or depth


@dataclass(frozen=True)
class Page:
    """A page as one provider call served it. `text` is exactly the text the call returned."""

    url: str
    title: str
    text: str
    provider: str


@dataclass(frozen=True)
class Claim:
    """A value a research run claimed for `field`, with the excerpt it cited."""

    field: str
    value: Any
    url: str
    excerpt: str
    provider: str


@dataclass(frozen=True)
class Reply:
    """The outcome of one call. `items`: list[Page] for search, dict[url, Page | None] for
    extract, list[Claim] for research. Empty when the call did not answer."""

    status: str
    items: Any


class Gateway:
    """Budgeted access to the providers for one build. Use as a context manager, or close()."""

    def __init__(
        self,
        budget: int = 80,
        deadline_s: float = DEFAULT_DEADLINE_S,
        cancel: threading.Event | None = None,
        router: Any = None,
    ) -> None:
        self.budget = budget
        self.deadline_s = deadline_s
        self.cancel = cancel
        self.spent = 0
        self.any_success = False
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._router = router if router is not None else _new_router()

    def __enter__(self) -> Gateway:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        close = getattr(self._router, "close", None)
        if close is not None:
            close()

    def search(self, query: str, depth: str = "lite", provider: str = "nimble", max_results: int = MAX_RESULTS) -> Reply:
        cost = SEARCH_COST.get((provider, depth))
        if cost is None or not self._admit(cost, SEARCH_ADMIT_S):
            return Reply(REFUSED, [])
        try:
            response = self._router.search(
                query,
                provider=provider,
                search_depth=depth,
                max_results=min(max_results, MAX_RESULTS),
            )
        except Exception as error:
            return self._failed(error, cost, [])
        pages = [
            Page(result.url, result.title, result.content or result.description, provider)
            for result in response.results[:MAX_RESULTS]
        ]
        return self._answered(pages)

    def extract(self, urls: list[str], provider: str = "nimble") -> Reply:
        unit = EXTRACT_COST.get(provider)
        urls = list(dict.fromkeys(urls))
        if unit is None or not urls or not self._admit(unit * len(urls), CALL_TIMEOUT_S):
            return Reply(REFUSED, {})
        missing: dict[str, Page | None] = {url: None for url in urls}
        try:
            response = self._router.extract(urls, provider=provider)
        except Exception as error:
            failures = getattr(error, "url_failures", None)
            if failures is None:
                return self._failed(error, unit * len(urls), missing)
            refused = {f.url for f in failures if _is_refusal(f.status_code, extract=True)}
            return self._extract_answered(missing, refused, unit, provider, urls)
        documents = {document.url: document for document in response.documents}
        items: dict[str, Page | None] = {}
        for url in urls:
            document = documents.get(url)
            items[url] = Page(url, document.title, document.content, provider) if document else None
        refused = {f.url for f in response.failures if _is_refusal(f.status_code, extract=True)}
        return self._extract_answered(items, refused - set(documents), unit, provider, urls)

    def research(self, domain: str) -> Reply:
        if not self._admit(RESEARCH_COST, RESEARCH_ADMIT_S):
            return Reply(REFUSED, [])
        timeout = self.deadline_s - self._elapsed()
        try:
            response = self._router.research(
                _research_query(domain),
                provider="nimble",
                output_schema=FIELD_SCHEMA,
                timeout=timeout,
            )
        except ResearchTimeoutError:
            return Reply(UNANSWERED, [])  # the run keeps going and its cost stands
        except Exception as error:
            return self._failed(error, RESEARCH_COST, [])
        return self._answered(_claims(response))

    def _admit(self, cost: int, needed_s: float) -> bool:
        with self._lock:
            if self.cancel is not None and self.cancel.is_set():
                return False
            if self._elapsed() + needed_s > self.deadline_s:
                return False
            if self.spent + cost > self.budget:
                return False
            self.spent += cost
            return True

    def _refund(self, cost: int) -> None:
        with self._lock:
            self.spent -= cost

    def _elapsed(self) -> float:
        return time.monotonic() - self._started

    def _answered(self, items: Any) -> Reply:
        with self._lock:
            self.any_success = True
        return Reply(OK, items)

    def _failed(self, error: BaseException, cost: int, empty: Any) -> Reply:
        if _is_refusal(_status_of(error), extract=False):
            self._refund(cost)
            return Reply(ERROR, empty)
        return Reply(UNANSWERED, empty)

    def _extract_answered(
        self,
        items: dict[str, Page | None],
        refused: set[str],
        unit: int,
        provider: str,
        urls: list[str],
    ) -> Reply:
        refunded = [url for url in urls if url in refused and items.get(url) is None]
        if refunded:
            self._refund(unit * len(refunded))
        if len(refunded) == len(urls):
            return Reply(ERROR, items)
        return self._answered(items)


def _is_refusal(status: int | None, extract: bool) -> bool:
    """An error status refuses the call. For extract, 404 is a missing page and costs its unit."""
    if status is None or status < 400:
        return False
    return not (extract and status == 404)


def _status_of(error: BaseException) -> int | None:
    """The HTTP status of an error or of the error it wraps, when one is recorded."""
    current: BaseException | None = error
    for _ in range(10):
        if current is None:
            return None
        status = getattr(current, "status_code", None)
        if isinstance(status, int):
            return status
        current = current.__cause__ or current.__context__
    return None


def _research_query(domain: str) -> str:
    return (
        f"Research the company whose web domain is {domain}: its registered legal name, "
        "headquarters city, chief executive, year founded, headcount range and total equity "
        "funding raised, with the source of each."
    )


def _claims(response: Any) -> list[Claim]:
    structured = response.structured if isinstance(response.structured, dict) else {}
    claims = []
    for citation in response.citations:
        name = _field_name(citation.field)
        value = structured.get(name) if name else None
        if value is None or not citation.snippet:
            continue
        claims.append(Claim(name, value, citation.url, citation.snippet, "nimble"))
    return claims


def _field_name(path: str | None) -> str | None:
    if not path or not path.startswith("$."):
        return None
    name = path[2:]
    return name if name in FIELD_NAMES else None


def _new_router() -> WebRouter:
    # An empty base URL counts as set and breaks every call (mock README): drop it instead.
    for variable in ("NIMBLE_BASE_URL", "TAVILY_BASE_URL"):
        if os.environ.get(variable) == "":
            del os.environ[variable]
    config: dict[str, dict[str, Any]] = {"nimble": {"timeout": CALL_TIMEOUT_S, "max_retries": 0}}
    if os.environ.get("TAVILY_API_KEY"):
        tavily: dict[str, Any] = {"timeout": CALL_TIMEOUT_S}
        if os.environ.get("TAVILY_BASE_URL"):
            tavily["api_base_url"] = os.environ["TAVILY_BASE_URL"]
        config["tavily"] = tavily
    return WebRouter(provider="nimble", provider_config=config, router=None)
